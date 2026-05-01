"""Drives a supplier import:
   resolve adapter -> discover -> hydrate -> persist -> record sync_jobs.

Auth errors abort and mark the job 'failed'.
Per-product errors continue the loop and are logged to sync_jobs.errors[].
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from modules.catalog.persistence import (
    PersistError,
    persist_product,
)
from modules.suppliers.models import Supplier
from modules.sync_jobs.models import SyncJob

from .base import (
    AdapterError,
    AuthError,
    DiscoveryMode,
    SupplierError,
    TransientError,
)
from .registry import (
    AdapterNotConfiguredError,
    AdapterNotRegisteredError,
    get_adapter,
)


log = logging.getLogger("import_jobs")


async def create_pending_import_job(
    *,
    supplier_id: uuid.UUID,
    mode: DiscoveryMode,
) -> uuid.UUID:
    """Create a queued sync_job synchronously so the caller can poll it."""
    async with async_session() as db:
        supplier = await db.get(Supplier, supplier_id)
        if supplier is None:
            raise ValueError(f"supplier {supplier_id} not found")
        job = SyncJob(
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            job_type=f"import:{mode.value}",
            status="pending",
            started_at=datetime.now(timezone.utc),
            total_products=0,
            success_count=0,
            failed_count=0,
            records_processed=0,
            errors=None,
            discovery_mode=mode.value,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job.id


async def run_existing_import_job(
    *,
    job_id: uuid.UUID,
    supplier_id: uuid.UUID,
    mode: DiscoveryMode,
    limit: Optional[int] = None,
    explicit_list: Optional[list[str]] = None,
) -> None:
    """Execute the work of an already-created sync_job."""
    async with async_session() as db:
        supplier = await db.get(Supplier, supplier_id)
        job = await db.get(SyncJob, job_id)
        if supplier is None or job is None:
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await db.commit()

        errors: list[dict] = []

        try:
            adapter = get_adapter(supplier, db)
        except (AdapterNotConfiguredError, AdapterNotRegisteredError) as e:
            errors.append({"phase": "registry", "msg": str(e)})
            await _finalize_job(db, job, status="failed", errors=errors, supplier=supplier, mode=mode)
            return

        try:
            refs = await adapter.discover(
                mode, limit=limit, explicit_list=explicit_list,
            )
        except AuthError as e:
            errors.append({"phase": "discover", "code": e.code, "msg": str(e)})
            await _finalize_job(db, job, status="failed", errors=errors, supplier=supplier, mode=mode)
            return
        except (SupplierError, TransientError, AdapterError) as e:
            errors.append({"phase": "discover", "code": getattr(e, "code", None), "msg": str(e)})
            await _finalize_job(db, job, status="failed", errors=errors, supplier=supplier, mode=mode)
            return

        job.total_products = len(refs)
        await db.commit()

        success_count = 0
        fail_count = 0
        for ref in refs:
            retries = 2
            while retries >= 0:
                try:
                    ingest = await adapter.hydrate_product(ref)
                    await persist_product(db, supplier.id, ingest)
                    await db.commit()
                    success_count += 1
                    break
                except AuthError as e:
                    # Mid-loop auth = still fatal.
                    errors.append({"phase": "hydrate", "ref": ref.supplier_sku, "code": e.code, "msg": str(e)})
                    await db.rollback()
                    await _finalize_job(db, job, status="failed", errors=errors, success_count=success_count, failed_count=fail_count, supplier=supplier, mode=mode)
                    return
                except TransientError as e:
                    if retries > 0:
                        backoff = 2 ** (2 - retries)
                        log.info("Transient error for %s, retrying in %ds... (%d left)", ref.supplier_sku, backoff, retries)
                        retries -= 1
                        await db.rollback()
                        await asyncio.sleep(backoff)
                        continue
                    errors.append({
                        "phase": "hydrate",
                        "ref": ref.supplier_sku,
                        "code": getattr(e, "code", None),
                        "msg": str(e),
                    })
                    await db.rollback()
                    fail_count += 1
                    break
                except (SupplierError, PersistError, AdapterError) as e:
                    errors.append({
                        "phase": "hydrate",
                        "ref": ref.supplier_sku,
                        "code": getattr(e, "code", None),
                        "msg": str(e),
                    })
                    await db.rollback()
                    fail_count += 1
                    break
                except Exception as e:                              # noqa: BLE001
                    # Unexpected — log + continue but track in errors[].
                    log.exception("unexpected per-product error: %s", e)
                    errors.append({"phase": "hydrate", "ref": ref.supplier_sku, "msg": str(e)})
                    await db.rollback()
                    fail_count += 1
                    break

        status = (
            "success" if not errors
            else "failed" if success_count == 0
            else "partial_success"
        )
        await _finalize_job(
            db, job, 
            status=status, 
            errors=errors or None, 
            success_count=success_count,
            failed_count=fail_count,
            supplier=supplier, 
            mode=mode
        )



async def run_import(
    *,
    supplier_id: uuid.UUID,
    mode: DiscoveryMode,
    limit: Optional[int] = None,
    explicit_list: Optional[list[str]] = None,
) -> uuid.UUID:
    job_id = await create_pending_import_job(supplier_id=supplier_id, mode=mode)
    await run_existing_import_job(
        job_id=job_id,
        supplier_id=supplier_id,
        mode=mode,
        limit=limit,
        explicit_list=explicit_list,
    )
    return job_id


async def _finalize_job(
    db: AsyncSession,
    job: SyncJob,
    *,
    status: str,
    errors: Optional[list[dict]] = None,
    success_count: int = 0,
    failed_count: int = 0,
    supplier: Optional[Supplier] = None,
    mode: Optional[DiscoveryMode] = None,
) -> None:
    job.status = status
    job.errors = errors
    job.success_count = success_count
    job.failed_count = failed_count
    job.records_processed = success_count

    if status in ("success", "partial_success") and supplier is not None and mode is not None:
        now = datetime.now(timezone.utc)
        if mode == DiscoveryMode.FULL:
            supplier.last_full_sync = now
        elif mode == DiscoveryMode.DELTA:
            supplier.last_delta_sync = now
            
        # Task 3: Stale Detection Logic
        from sqlalchemy import update, select
        from modules.catalog.models import CustomerProductSelection, Product
        
        # Mark as 'stale' if product.last_synced (now) > selection.pushed_at
        # This only affects products that were actually updated in this sync.
        # We look for all selections for this supplier's products.
        subq = (
            select(Product.id)
            .where(Product.supplier_id == supplier.id)
            .where(Product.last_synced >= job.started_at)
        )
        stmt = (
            update(CustomerProductSelection)
            .where(CustomerProductSelection.product_id.in_(subq))
            .where(CustomerProductSelection.status == "pushed")
            .where(CustomerProductSelection.pushed_at < now)
            .values(status="stale")
        )
        await db.execute(stmt)

    job.completed_at = datetime.now(timezone.utc)
    await db.commit()
