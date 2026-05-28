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
    ProductRef,
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

        # INVENTORY_ONLY: skip full discover/hydrate — read known SKUs from DB
        # and only update variant.inventory. Much faster than full hydrate.
        if mode == DiscoveryMode.INVENTORY_ONLY:
            await _run_inventory_only(db, job, adapter, supplier)
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

        # Semaphore limits concurrent SOAP calls — 10 at a time is safe for
        # SanMar without hitting rate limits, giving ~10x speedup over serial.
        _sem = asyncio.Semaphore(10)

        async def _hydrate_one(ref) -> tuple[bool, dict | None]:
            """Fetch and persist one product. Returns (success, error_dict|None)."""
            async with _sem:
                retries = 2
                while retries >= 0:
                    try:
                        ingest = await adapter.hydrate_product(ref)
                        async with async_session() as own_db:
                            await persist_product(own_db, supplier.id, ingest)
                            await own_db.commit()
                        return True, None
                    except AuthError as e:
                        return False, {"phase": "hydrate", "ref": ref.supplier_sku, "code": e.code, "msg": str(e), "fatal": True}
                    except TransientError as e:
                        if retries > 0:
                            backoff = 2 ** (2 - retries)
                            log.info("Transient error for %s, retrying in %ds... (%d left)", ref.supplier_sku, backoff, retries)
                            retries -= 1
                            await asyncio.sleep(backoff)
                            continue
                        return False, {"phase": "hydrate", "ref": ref.supplier_sku, "code": getattr(e, "code", None), "msg": str(e)}
                    except (SupplierError, PersistError, AdapterError) as e:
                        return False, {"phase": "hydrate", "ref": ref.supplier_sku, "code": getattr(e, "code", None), "msg": str(e)}
                    except Exception as e:  # noqa: BLE001
                        log.exception("unexpected per-product error for %s: %s", ref.supplier_sku, e)
                        return False, {"phase": "hydrate", "ref": ref.supplier_sku, "msg": str(e)}
                return False, {"phase": "hydrate", "ref": ref.supplier_sku, "msg": "exhausted retries"}

        results = await asyncio.gather(*[_hydrate_one(ref) for ref in refs])

        success_count = 0
        fail_count = 0
        auth_fatal = None
        for success, err in results:
            if success:
                success_count += 1
            else:
                if err and err.get("fatal"):
                    auth_fatal = err
                errors.append(err)
                fail_count += 1

        if auth_fatal:
            await _finalize_job(db, job, status="failed", errors=errors, success_count=success_count, failed_count=fail_count, supplier=supplier, mode=mode)
            return

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


async def _run_inventory_only(
    db: AsyncSession,
    job: SyncJob,
    adapter,
    supplier: Supplier,
) -> None:
    """Fast inventory-only sync: updates variant.inventory without re-fetching
    product/pricing/images. Reads known SKUs from DB, calls inventory SOAP
    for each, writes back inventory counts. Parallelised with Semaphore(10)."""
    from sqlalchemy import select, update
    from modules.catalog.models import Product, ProductVariant

    skus = (await db.execute(
        select(Product.supplier_sku)
        .where(Product.supplier_id == supplier.id, Product.archived_at.is_(None))
    )).scalars().all()

    job.total_products = len(skus)
    await db.commit()

    sem = asyncio.Semaphore(10)
    success_count = 0
    fail_count = 0
    errors: list[dict] = []

    async def _fetch_inv(sku: str):
        async with sem:
            try:
                ref = ProductRef(supplier_sku=sku)
                inv_map = await adapter.hydrate_inventory_only(ref)
                if inv_map:
                    async with async_session() as own_db:
                        for part_id, qty in inv_map.items():
                            await own_db.execute(
                                update(ProductVariant)
                                .where(
                                    ProductVariant.part_id == part_id,
                                )
                                .values(inventory=qty)
                            )
                        await own_db.commit()
                return True, None
            except NotImplementedError:
                return False, {"phase": "inventory_only", "ref": sku, "msg": "adapter does not support inventory_only"}
            except Exception as exc:
                log.warning("Inventory-only error for %s: %s", sku, exc)
                return False, {"phase": "inventory_only", "ref": sku, "msg": str(exc)}

    results = await asyncio.gather(*[_fetch_inv(sku) for sku in skus])
    for ok, err in results:
        if ok:
            success_count += 1
        else:
            fail_count += 1
            if err:
                errors.append(err)

    status = "success" if not errors else "partial_success" if success_count > 0 else "failed"
    await _finalize_job(
        db, job,
        status=status,
        errors=errors or None,
        success_count=success_count,
        failed_count=fail_count,
        supplier=supplier,
        mode=DiscoveryMode.INVENTORY_ONLY,
    )


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
