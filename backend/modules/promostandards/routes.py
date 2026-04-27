"""Sync trigger endpoints for PromoStandards suppliers.

n8n calls these endpoints to kick off SOAP syncs. Each POST returns
immediately (HTTP 202) with a SyncJob id; the actual SOAP work runs
as a FastAPI BackgroundTask. n8n polls GET /api/sync-jobs/{job_id}
until status flips to "completed" or "failed".

Upstream deps (Tanishq T3b + T4) are imported lazily inside the
background task so this module stays importable while those land.
"""

import os
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session, get_db
from modules.suppliers.models import Supplier
from modules.suppliers.service import get_cached_endpoints
from modules.sync_jobs.models import SyncJob

from .resolver import resolve_wsdl_url
from modules.catalog.ingest import require_ingest_secret

router = APIRouter(prefix="/api/sync", tags=["sync"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_active_supplier(db: AsyncSession, supplier_id: UUID) -> Supplier:
    supplier = (
        await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    ).scalar_one_or_none()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    if not supplier.is_active:
        raise HTTPException(409, f"Supplier '{supplier.name}' is not active")
    return supplier


def _get_auth_config(supplier: Supplier) -> dict:
    """Return auth_config from the database."""
    return dict(supplier.auth_config or {})


async def _ensure_no_active_job(
    db: AsyncSession, supplier_id: UUID, job_type: str
) -> None:
    """409 if a queued/running job already exists for this supplier+job_type.

    Prevents racing workers from stepping on each other (duplicate SOAP calls,
    upsert contention, wasted WSDL fetches).
    """
    existing = (
        await db.execute(
            select(SyncJob.id).where(
                SyncJob.supplier_id == supplier_id,
                SyncJob.job_type == job_type,
                SyncJob.status.in_(("queued", "running")),
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            409,
            f"A {job_type} sync for this supplier is already in progress "
            f"(job {existing}).",
        )


async def _create_job(
    db: AsyncSession, supplier: Supplier, job_type: str
) -> SyncJob:
    # Starts as "queued" — the background worker flips to "running" when it
    # actually begins work. Prevents GET /status from lying during the window
    # between 202 response and worker dispatch.
    job = SyncJob(
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        job_type=job_type,
        status="queued",
        started_at=datetime.now(timezone.utc),
        records_processed=0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def _mark_job_running(session: AsyncSession, job_id: UUID) -> None:
    job = await session.get(SyncJob, job_id)
    if job and job.status == "queued":
        job.status = "running"
        await session.commit()


async def _finish_job(
    session: AsyncSession,
    job_id: UUID,
    *,
    status: str,
    records_processed: int = 0,
    error: str | None = None,
) -> None:
    job = await session.get(SyncJob, job_id)
    if not job:
        return
    job.status = status
    job.records_processed = records_processed
    job.error_log = error
    job.finished_at = datetime.now(timezone.utc)
    await session.commit()


# ---------------------------------------------------------------------------
# Background workers — each opens its own DB session
# ---------------------------------------------------------------------------

async def _run_full_product_sync(
    job_id: UUID,
    supplier_id: UUID,
    auth_config: dict,
    wsdl_product: str,
    wsdl_inventory: str | None,
    wsdl_ppc: str | None,
    wsdl_media: str | None,
    limit: int | None = None,
) -> None:
    async with async_session() as session:
        await _mark_job_running(session, job_id)
        try:
            # Lazy imports — Tanishq T3b/T4 land these. Explicit ImportError
            # handling so a missing adapter module marks the job failed with a
            # clear message instead of sitting in "running" until n8n times out.
            from .client import PromoStandardsClient  # type: ignore
            from .normalizer import upsert_products  # type: ignore
        except ImportError as exc:
            await _finish_job(
                session,
                job_id,
                status="failed",
                error=f"PromoStandards adapter not yet deployed: {exc}",
            )
            return

        try:
            product_client = PromoStandardsClient(wsdl_product, auth_config)
            product_ids = await product_client.get_sellable_product_ids()
            
            if limit:
                product_ids = product_ids[:limit]
                
            products = await product_client.get_products_batch(product_ids)

            inventory = []
            if wsdl_inventory:
                inv_client = PromoStandardsClient(wsdl_inventory, auth_config)
                inventory = await inv_client.get_inventory(product_ids)

            pricing: list = []
            if wsdl_ppc:
                ppc_client = PromoStandardsClient(wsdl_ppc, auth_config)
                pricing = await ppc_client.get_pricing(product_ids)  # type: ignore[attr-defined]

            media: list = []
            if wsdl_media:
                media_client = PromoStandardsClient(wsdl_media, auth_config)
                media = await media_client.get_media(product_ids)  # type: ignore[attr-defined]

            await upsert_products(
                session, supplier_id, products, inventory, pricing, media
            )
            await _finish_job(
                session, job_id, status="completed", records_processed=len(products)
            )
        except Exception as exc:
            await _finish_job(session, job_id, status="failed", error=str(exc))


async def _run_rest_sync(
    job_id: UUID,
    supplier_id: UUID,
    protocol: str,
    base_url: str,
    auth_config: dict,
    field_mappings: dict | None,
) -> None:
    """Background worker for REST/HMAC suppliers (S&S, 4Over)."""
    async with async_session() as session:
        await _mark_job_running(session, job_id)

        try:
            from modules.rest_connector.client import RESTConnectorClient
            from modules.rest_connector.ss_normalizer import ss_to_ps_format
            from modules.rest_connector.fourover_client import FourOverClient
            from modules.rest_connector.fourover_normalizer import normalize_4over
            from .normalizer import upsert_products
        except ImportError as exc:
            await _finish_job(
                session,
                job_id,
                status="failed",
                error=f"REST adapter not yet deployed: {exc}",
            )
            return

        try:
            if protocol == "rest":
                client = RESTConnectorClient(base_url=base_url, auth_config=auth_config)
                raw = await client.get_products()
                products, inventory, pricing, media = ss_to_ps_format(raw)
            else:  # "rest_hmac"
                client = FourOverClient(base_url=base_url, auth_config=auth_config)
                raw = await client.get_products()
                mapping = (field_mappings or {}).get("mapping") or {}
                products = normalize_4over(raw, mapping)
                inventory, pricing, media = [], [], []

            await upsert_products(
                session, supplier_id, products, inventory, pricing, media
            )
            await _finish_job(
                session,
                job_id,
                status="completed",
                records_processed=len(products),
            )
        except Exception as exc:
            await _finish_job(session, job_id, status="failed", error=str(exc))


async def _run_inventory_sync(
    job_id: UUID,
    supplier_id: UUID,
    auth_config: dict,
    wsdl_product: str,
    wsdl_inventory: str,
) -> None:
    async with async_session() as session:
        await _mark_job_running(session, job_id)
        try:
            from .client import PromoStandardsClient  # type: ignore
            from .normalizer import update_inventory_only  # type: ignore
        except ImportError as exc:
            await _finish_job(
                session,
                job_id,
                status="failed",
                error=f"PromoStandards adapter not yet deployed: {exc}",
            )
            return

        try:
            product_client = PromoStandardsClient(wsdl_product, auth_config)
            product_ids = await product_client.get_sellable_product_ids()

            inv_client = PromoStandardsClient(wsdl_inventory, auth_config)
            inventory = await inv_client.get_inventory(product_ids)

            await update_inventory_only(session, supplier_id, inventory)
            await _finish_job(
                session, job_id, status="completed", records_processed=len(inventory)
            )
        except Exception as exc:
            await _finish_job(session, job_id, status="failed", error=str(exc))


async def _run_pricing_sync(
    job_id: UUID,
    supplier_id: UUID,
    auth_config: dict,
    wsdl_product: str,
    wsdl_ppc: str,
) -> None:
    async with async_session() as session:
        await _mark_job_running(session, job_id)
        try:
            from .client import PromoStandardsClient  # type: ignore
            from .normalizer import update_pricing_only  # type: ignore
        except ImportError as exc:
            await _finish_job(
                session,
                job_id,
                status="failed",
                error=f"PromoStandards adapter not yet deployed: {exc}",
            )
            return

        try:
            product_client = PromoStandardsClient(wsdl_product, auth_config)
            product_ids = await product_client.get_sellable_product_ids()

            ppc_client = PromoStandardsClient(wsdl_ppc, auth_config)
            pricing = await ppc_client.get_pricing(product_ids)  # type: ignore[attr-defined]

            await update_pricing_only(session, supplier_id, pricing)
            await _finish_job(
                session, job_id, status="completed", records_processed=len(pricing)
            )
        except Exception as exc:
            await _finish_job(session, job_id, status="failed", error=str(exc))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/{supplier_id}/products", status_code=202, dependencies=[Depends(require_ingest_secret)])
async def trigger_product_sync(
    supplier_id: UUID,
    background_tasks: BackgroundTasks,
    limit: int | None = Query(None, description="Limit the number of products to sync for testing"),
    db: AsyncSession = Depends(get_db),
):
    supplier = await _load_active_supplier(db, supplier_id)
    await _ensure_no_active_job(db, supplier_id, "full_sync")

    if supplier.protocol in ("soap", "promostandards"):
        endpoints = await get_cached_endpoints(db, supplier_id)
        wsdl_product = resolve_wsdl_url(endpoints, "product_data")
        if not wsdl_product:
            raise HTTPException(502, "Product Data WSDL not found in supplier endpoint cache")
        
        job = await _create_job(db, supplier, job_type="full_sync")
        background_tasks.add_task(
            _run_full_product_sync,
            job.id,
            supplier.id,
            _get_auth_config(supplier),
            wsdl_product,
            resolve_wsdl_url(endpoints, "inventory"),
            resolve_wsdl_url(endpoints, "ppc"),
            resolve_wsdl_url(endpoints, "media"),
            limit,
        )
    elif supplier.protocol in ("rest", "rest_hmac", "ops_graphql"):
        # Placeholder for REST/GraphQL background task — wiring B2/G2 requirement
        job = await _create_job(db, supplier, job_type="full_sync")
        # background_tasks.add_task(_run_rest_sync, job.id, supplier)
    else:
        raise HTTPException(400, f"Sync not implemented for protocol '{supplier.protocol}'")

    return {"job_id": str(job.id), "status": job.status, "job_type": job.job_type}


@router.post("/{supplier_id}/inventory", status_code=202, dependencies=[Depends(require_ingest_secret)])
async def trigger_inventory_sync(
    supplier_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    supplier = await _load_active_supplier(db, supplier_id)
    endpoints = await get_cached_endpoints(db, supplier_id)

    await _ensure_no_active_job(db, supplier_id, "inventory")

    wsdl_product = resolve_wsdl_url(endpoints, "product_data")
    wsdl_inventory = resolve_wsdl_url(endpoints, "inventory")
    if not wsdl_product or not wsdl_inventory:
        raise HTTPException(
            502, "Product Data or Inventory WSDL missing from endpoint cache"
        )

    job = await _create_job(db, supplier, job_type="inventory")
    background_tasks.add_task(
        _run_inventory_sync,
        job.id,
        supplier.id,
        _get_auth_config(supplier),
        wsdl_product,
        wsdl_inventory,
    )
    return {"job_id": str(job.id), "status": job.status, "job_type": job.job_type}


@router.post("/{supplier_id}/pricing", status_code=202, dependencies=[Depends(require_ingest_secret)])
async def trigger_pricing_sync(
    supplier_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    supplier = await _load_active_supplier(db, supplier_id)
    endpoints = await get_cached_endpoints(db, supplier_id)

    await _ensure_no_active_job(db, supplier_id, "pricing")

    wsdl_product = resolve_wsdl_url(endpoints, "product_data")
    wsdl_ppc = resolve_wsdl_url(endpoints, "ppc")
    if not wsdl_product or not wsdl_ppc:
        raise HTTPException(
            502, "Product Data or PPC WSDL missing from endpoint cache"
        )

    job = await _create_job(db, supplier, job_type="pricing")
    background_tasks.add_task(
        _run_pricing_sync,
        job.id,
        supplier.id,
        _get_auth_config(supplier),
        wsdl_product,
        wsdl_ppc,
    )
    return {"job_id": str(job.id), "status": job.status, "job_type": job.job_type}


@router.post("/{supplier_id}/products/rest", status_code=202)
async def trigger_rest_sync(
    supplier_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Kick off a full-catalog sync for REST/HMAC suppliers (S&S, 4Over).

    Separate endpoint from /products because _load_active_ps_supplier
    rejects non-SOAP protocols by design.
    """
    supplier = (
        await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    ).scalar_one_or_none()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    if not supplier.is_active:
        raise HTTPException(409, f"Supplier '{supplier.name}' is not active")
    if supplier.protocol not in ("rest", "rest_hmac"):
        raise HTTPException(
            400,
            f"Supplier '{supplier.name}' uses protocol '{supplier.protocol}'; "
            f"use POST /api/sync/{supplier_id}/products for SOAP suppliers",
        )
    if not supplier.base_url:
        raise HTTPException(
            400, f"Supplier '{supplier.name}' has no base_url configured"
        )

    await _ensure_no_active_job(db, supplier_id, "full_sync")
    job = await _create_job(db, supplier, job_type="full_sync")

    background_tasks.add_task(
        _run_rest_sync,
        job.id,
        supplier.id,
        supplier.protocol,
        supplier.base_url,
        _get_auth_config(supplier),
        dict(supplier.field_mappings or {}) if supplier.field_mappings else None,
    )
    return {"job_id": str(job.id), "status": job.status, "job_type": job.job_type}


@router.get("/{supplier_id}/status")
async def latest_sync_status(
    supplier_id: UUID, db: AsyncSession = Depends(get_db)
):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, "Supplier not found")

    job = (
        await db.execute(
            select(SyncJob)
            .where(SyncJob.supplier_id == supplier_id)
            .order_by(SyncJob.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if not job:
        return {"supplier_id": str(supplier_id), "status": "never_synced"}

    return {
        "supplier_id": str(supplier_id),
        "job_id": str(job.id),
        "job_type": job.job_type,
        "status": job.status,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "records_processed": job.records_processed,
        "error_log": job.error_log,
    }
