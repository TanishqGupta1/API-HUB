"""Integration Gateway — 4 endpoints under /api/integrations/v1/"""
import hashlib
import secrets
import uuid as uuid_mod
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.auth.dependencies import VGAdmin
from modules.ops_push.gateway import execute_push, prepare_push_intent
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

    # If idempotent replay — already terminal, no execute needed
    if accepted.status not in ("accepted", "queued"):
        return accepted

    # Async execute (BackgroundTask keeps the request fast)
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
    body: dict,
    key: OrchestratorKey,
    db: AsyncSession = Depends(get_db),
):
    # Scope check — key must be allowed for this supplier
    check_key_scope(key, "*", supplier_slug)
    # Full catalog upsert implementation lives in Task 6 (payload_builder)
    # For now: accept and acknowledge
    return {"status": "accepted", "supplier_slug": supplier_slug, "items": len(body.get("items", []))}


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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Admin proxy — JWT-authenticated push (for the in-app admin UI to call
# the gateway without the operator copy-pasting an orchestrator key).
#
# The proxy uses a synthetic, never-expiring integration key row called
# "_admin_ui_proxy" so prepare_push_intent's `key_id` foreign-key still
# resolves cleanly and push_log rows stay distinguishable in audit views
# (key_id="_admin_ui_proxy" → "this push was triggered from the admin UI").
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ADMIN_PROXY_KEY_ID = "_admin_ui_proxy"


async def _get_or_create_admin_proxy_key(db: AsyncSession) -> IntegrationKey:
    """Idempotent singleton — ensures the synthetic admin-proxy key exists."""
    key = await db.get(IntegrationKey, ADMIN_PROXY_KEY_ID)
    if key:
        return key
    # The raw key is never exposed — admin proxy uses JWT, not header.
    # The hash is a sentinel value that cannot match any real X-Orchestrator-Key
    # because token_urlsafe() never produces this exact string.
    sentinel_hash = hashlib.sha256(b"__admin_ui_proxy_never_exposed__").hexdigest()
    key = IntegrationKey(
        id=ADMIN_PROXY_KEY_ID,
        key_hash=sentinel_hash,
        name="Admin UI proxy (JWT-authenticated)",
        allowed_customer_ids=None,   # null = all customers
        allowed_supplier_slugs=None,  # null = all suppliers
        rate_limit_per_minute=600,    # admin gets a higher ceiling than orchestrators
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key


@admin_router.get(
    "/admin/push-requests/{push_log_id}",
    response_model=PushStatusOut,
    summary="Admin-only status poll (JWT auth) — mirrors /v1/push-requests/{id}",
)
async def admin_push_status(
    push_log_id: uuid_mod.UUID,
    _: VGAdmin,
    db: AsyncSession = Depends(get_db),
):
    """Identical response shape to the orchestrator GET, just admin JWT-auth.
    Lets the admin UI poll push status without an X-Orchestrator-Key."""
    push_log = await db.get(ProductPushLog, push_log_id)
    if not push_log:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "UNKNOWN_REF", "message": "Push request not found"
        })
    terminal = push_log.status in (
        "pushed", "failed", "partial_failure", "rejected", "dry_run_pushed", "canceled"
    )
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
        links=PushRequestLinks(self=f"/api/integrations/admin/push-requests/{push_log_id}"),
    )


@admin_router.post(
    "/admin/push-requests",
    status_code=202,
    response_model=PushRequestAccepted,
    summary="Admin-only push proxy (JWT auth, no X-Orchestrator-Key required)",
)
async def admin_push_request(
    req: PushRequest,
    background_tasks: BackgroundTasks,
    _: VGAdmin,
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Same pipeline as the orchestrator gateway, just authed with admin JWT.

    Internally calls `prepare_push_intent + execute_push` so the live behavior
    (preflight, RFC 8785 idempotency, halt-no-rollback) is identical.
    The operator does NOT need to create or paste an integration key —
    the admin UI's existing session cookie is sufficient.
    """
    proxy_key = await _get_or_create_admin_proxy_key(db)
    # No scope check — admin JWT already gates this route.
    accepted = await prepare_push_intent(req, proxy_key, db, idempotency_key=idempotency_key)
    # Skip background execution if idempotent replay returned a terminal row
    if accepted.status not in ("accepted", "queued"):
        return accepted
    background_tasks.add_task(execute_push, accepted.push_log_id)
    return accepted
