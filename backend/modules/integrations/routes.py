"""Integration Gateway — 4 endpoints under /api/integrations/v1/"""
import hashlib
import logging
import secrets
import uuid as uuid_mod
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.auth.dependencies import VGAdmin
from modules.catalog.persistence import persist_product
from modules.catalog.schemas import IngestResult, ProductIngest
from modules.ops_push.gateway import execute_push, prepare_push_intent
from modules.suppliers.models import Supplier
from modules.sync_jobs.models import SyncJob
from .auth import OrchestratorKey, check_key_scope
from .models import IntegrationKey
from .schemas import (
    IntegrationKeyCreate,
    IntegrationKeyCreated,
    IntegrationKeyOut,
    PushRequest,
    PushRequestAccepted,
    PushRequestLinks,
    PushStatusOut,
    StepResultOut,
)
from modules.push_log.models import ProductPushLog
from modules.push_log.schemas import StepResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/v1", tags=["integrations"])
admin_router = APIRouter(prefix="/api/integrations", tags=["integrations_admin"])


# ── POST /push-requests ──────────────────────────────────────────────

@router.post(
    "/push-requests",
    status_code=202,
    response_model=PushRequestAccepted,
    summary="Push a product to a customer's OPS storefront",
)
async def create_push_request(
    req: PushRequest,
    background_tasks: BackgroundTasks,
    key: OrchestratorKey,
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    check_key_scope(key, str(req.target.customer_id), req.source.supplier_slug)

    accepted = await prepare_push_intent(req, key, db, idempotency_key=idempotency_key)

    # Idempotent replay — already terminal, no execute needed
    if accepted.status not in ("accepted", "queued"):
        return accepted

    # Dry-run is fast (FakeOpsClient is in-memory) — execute inline so the
    # 202 response already carries terminal status=dry_run_pushed. Live
    # pushes still run as a BackgroundTask so the request returns immediately
    # and the orchestrator polls GET /push-requests/{id} for the outcome.
    if req.dry_run:
        await execute_push(accepted.push_log_id)
        terminal = await db.get(ProductPushLog, accepted.push_log_id)
        if terminal is not None:
            await db.refresh(terminal)
            accepted = PushRequestAccepted(
                push_log_id=terminal.id,
                status=terminal.status,
                customer_id=terminal.customer_id,
                supplier_slug=terminal.supplier_slug or req.source.supplier_slug,
                supplier_sku=terminal.supplier_sku,
                ops_product_id=terminal.ops_product_id,
                dry_run=terminal.dry_run,
                callback_status=terminal.callback_status,
                created_at=terminal.pushed_at,
                links=PushRequestLinks(
                    self=f"/api/integrations/v1/push-requests/{terminal.id}"
                ),
            )
        return accepted

    background_tasks.add_task(execute_push, accepted.push_log_id)
    return accepted


# ── GET /push-requests/{push_log_id} ────────────────────────────────

@router.get(
    "/push-requests/{push_log_id}",
    response_model=PushStatusOut,
    summary="Poll push status",
)
async def get_push_status(
    push_log_id: uuid_mod.UUID,
    key: OrchestratorKey,
    db: AsyncSession = Depends(get_db),
):
    push_log = await db.get(ProductPushLog, push_log_id)
    if not push_log:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "UNKNOWN_REF", "message": "Push request not found"
        })

    terminal = push_log.status in ("pushed", "failed", "partial_failure", "rejected", "dry_run_pushed", "canceled")

    return PushStatusOut(
        push_log_id=push_log.id,
        status=push_log.status,
        customer_id=push_log.customer_id,
        supplier_slug=push_log.supplier_slug,
        supplier_sku=push_log.supplier_sku,
        ops_product_id=push_log.ops_product_id,
        error=push_log.error,
        step_results=[StepResultOut(**s) for s in (push_log.step_results or [])],
        cleanup_targets=push_log.cleanup_targets,
        callback_status=push_log.callback_status,
        callback_attempts=push_log.callback_attempts,
        finished_at=push_log.pushed_at if terminal else None,
        links=PushRequestLinks(self=f"/api/integrations/v1/push-requests/{push_log_id}"),
    )


# ── POST /suppliers/{supplier_slug}/products ─────────────────────────

@router.post(
    "/suppliers/{supplier_slug}/products",
    status_code=202,
    summary="Upsert catalog products from an orchestrator",
)
async def ingest_supplier_products(
    supplier_slug: str,
    batch: list[ProductIngest],
    key: OrchestratorKey,
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Batched catalog upsert from an orchestrator (n8n, curl, anything).

    Body is a list of `ProductIngest` — same canonical shape every supplier
    protocol normalizes to. Persistence reuses `catalog.persistence.persist_product`,
    which performs an ON CONFLICT DO UPDATE upsert, so the endpoint is
    idempotent-by-construction: two POSTs with the same batch leave the DB in
    an identical state. The `Idempotency-Key` header is logged on the
    SyncJob row for orchestrator-side retry tracing but is not used to short-
    circuit duplicate processing (the upsert semantics make that unnecessary).
    """
    # Scope check — key must be allowed for this supplier ("*" customer placeholder
    # since ingest does not target a single customer).
    check_key_scope(key, "*", supplier_slug)

    supplier = (
        await db.execute(select(Supplier).where(Supplier.slug == supplier_slug))
    ).scalar_one_or_none()
    if not supplier:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "UNKNOWN_REF",
            "message": f"Supplier '{supplier_slug}' not found",
        })
    if not supplier.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={
            "code": "SUPPLIER_INACTIVE",
            "message": f"Supplier '{supplier_slug}' is inactive",
        })

    job = SyncJob(
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        job_type="products",
        status="running",
        started_at=datetime.now(timezone.utc),
        records_processed=0,
        total_products=len(batch),
    )
    db.add(job)
    await db.flush()

    processed = 0
    errors: list[dict] = []
    for item in batch:
        try:
            await persist_product(db, supplier.id, item, category_id=None)
            processed += 1
        except Exception as exc:  # noqa: BLE001 — per-item isolation
            logger.warning(
                "ingest_supplier_products: persist_product failed sku=%s err=%s",
                item.supplier_sku,
                exc,
            )
            errors.append({"supplier_sku": item.supplier_sku, "error": str(exc)[:300]})

    job.records_processed = processed
    job.success_count = processed
    job.failed_count = len(errors)
    job.completed_at = datetime.now(timezone.utc)
    job.status = "completed" if not errors else "partial_failure"
    if errors:
        job.errors = errors
    await db.commit()

    if idempotency_key:
        logger.info(
            "ingest_supplier_products idempotency_key=%s sync_job=%s processed=%d",
            idempotency_key,
            job.id,
            processed,
        )

    return {
        "status": job.status,
        "supplier_slug": supplier_slug,
        "sync_job_id": str(job.id),
        "records_processed": processed,
        "failed_count": len(errors),
        "errors": errors,
    }


# ── GET /suppliers/{supplier_slug}/schema ────────────────────────────

@router.get(
    "/suppliers/{supplier_slug}/schema",
    summary="Discover required and optional fields for a supplier",
)
async def get_supplier_schema(
    supplier_slug: str,
    key: OrchestratorKey,
):
    return {
        "supplier_slug": supplier_slug,
        "required": ["supplier_sku", "product_name", "variants"],
        "optional": ["brand", "description", "images", "options", "decorations"],
        "variant_required": ["part_id", "sku", "base_price"],
        "variant_optional": ["color", "size", "sort_order", "inventory", "prices"],
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Admin routes — integration key management (JWT, vg_admin only)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@admin_router.get("/keys", response_model=list[IntegrationKeyOut])
async def list_keys(
    _: VGAdmin,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(IntegrationKey).order_by(IntegrationKey.created_at.desc()))
    return result.scalars().all()


@admin_router.post("/keys", response_model=IntegrationKeyCreated, status_code=201)
async def create_key(
    body: IntegrationKeyCreate,
    _: VGAdmin,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.get(IntegrationKey, body.id)
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Key ID already exists")

    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    key = IntegrationKey(
        id=body.id,
        key_hash=key_hash,
        name=body.name,
        allowed_customer_ids=body.allowed_customer_ids,
        allowed_supplier_slugs=body.allowed_supplier_slugs,
        rate_limit_per_minute=body.rate_limit_per_minute,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)

    return IntegrationKeyCreated(
        id=key.id,
        name=key.name,
        allowed_customer_ids=key.allowed_customer_ids,
        allowed_supplier_slugs=key.allowed_supplier_slugs,
        rate_limit_per_minute=key.rate_limit_per_minute,
        is_active=key.is_active,
        last_used_at=key.last_used_at,
        created_at=key.created_at,
        revoked_at=key.revoked_at,
        raw_key=raw_key,
    )


@admin_router.post("/keys/{key_id}/revoke", status_code=200)
async def revoke_key(
    key_id: str,
    _: VGAdmin,
    db: AsyncSession = Depends(get_db),
):
    key = await db.get(IntegrationKey, key_id)
    if not key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Key not found")
    key.revoked_at = datetime.now(timezone.utc)
    key.is_active = False
    await db.commit()
    return {"status": "revoked", "key_id": key_id}
