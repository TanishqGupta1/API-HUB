"""Customer self-service portal API — /api/portal/*

All routes require customer_admin role. Each endpoint is automatically
scoped to the requesting user's customer_id from the JWT — no customer_id
in the URL, no risk of horizontal data access.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.auth.dependencies import CustomerAdmin
from modules.auth.models import User
from modules.catalog.models import Product
from modules.customer_catalog.models import CustomerProductSelection
from modules.customers.models import Customer
from modules.customers.routes import _with_counts
from modules.customers.schemas import CustomerRead
from modules.markup.models import MarkupRule
from modules.push_log.models import ProductPushLog
from modules.sync_jobs.models import SyncJob
from modules.suppliers.models import Supplier

router = APIRouter(prefix="/api/portal", tags=["portal"])


# ── GET /api/portal/me ────────────────────────────────────────────────

@router.get("/me", response_model=CustomerRead)
async def portal_me(current_user: CustomerAdmin, db: AsyncSession = Depends(get_db)):
    """Return the customer record associated with the logged-in storefront user."""
    customer = await db.get(Customer, current_user.customer_id)
    if not customer:
        raise HTTPException(404, "Storefront not found")
    return await _with_counts(db, customer)


# ── GET /api/portal/dashboard ─────────────────────────────────────────

@router.get("/dashboard")
async def portal_dashboard(current_user: CustomerAdmin, db: AsyncSession = Depends(get_db)):
    """Summary stats for the customer's storefront dashboard."""
    cid = current_user.customer_id
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    products_selected = (await db.execute(
        select(func.count()).select_from(CustomerProductSelection)
        .where(CustomerProductSelection.customer_id == cid)
    )).scalar() or 0

    products_pushed = (await db.execute(
        select(func.count()).select_from(ProductPushLog)
        .where(ProductPushLog.customer_id == cid, ProductPushLog.status == "pushed")
    )).scalar() or 0

    pushes_this_week = (await db.execute(
        select(func.count()).select_from(ProductPushLog)
        .where(
            ProductPushLog.customer_id == cid,
            ProductPushLog.pushed_at >= week_ago,
        )
    )).scalar() or 0

    push_failures_this_week = (await db.execute(
        select(func.count()).select_from(ProductPushLog)
        .where(
            ProductPushLog.customer_id == cid,
            ProductPushLog.status == "failed",
            ProductPushLog.pushed_at >= week_ago,
        )
    )).scalar() or 0

    # Recent pushes (last 5)
    recent_pushes_rows = (await db.execute(
        select(ProductPushLog)
        .where(ProductPushLog.customer_id == cid)
        .order_by(ProductPushLog.pushed_at.desc())
        .limit(5)
    )).scalars().all()

    recent_pushes = [
        {
            "push_log_id": str(p.id),
            "status": p.status,
            "ops_product_id": p.ops_product_id,
            "supplier_sku": p.supplier_sku,
            "supplier_slug": p.supplier_slug,
            "pushed_at": p.pushed_at.isoformat() if p.pushed_at else None,
            "error": p.error,
        }
        for p in recent_pushes_rows
    ]

    # Active suppliers (those with products selected by this customer)
    active_suppliers = (await db.execute(
        select(func.count(Supplier.id.distinct()))
        .join(Product, Product.supplier_id == Supplier.id)
        .join(CustomerProductSelection, CustomerProductSelection.product_id == Product.id)
        .where(CustomerProductSelection.customer_id == cid)
    )).scalar() or 0

    return {
        "products_selected": products_selected,
        "products_pushed": products_pushed,
        "pushes_this_week": pushes_this_week,
        "push_failures_this_week": push_failures_this_week,
        "active_suppliers": active_suppliers,
        "recent_pushes": recent_pushes,
    }


# ── GET /api/portal/push-history ──────────────────────────────────────

@router.get("/push-history")
async def portal_push_history(
    current_user: CustomerAdmin,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Paginated push log for this storefront."""
    cid = current_user.customer_id
    rows = (await db.execute(
        select(ProductPushLog)
        .where(ProductPushLog.customer_id == cid)
        .order_by(ProductPushLog.pushed_at.desc())
        .offset(skip).limit(limit)
    )).scalars().all()

    total = (await db.execute(
        select(func.count()).select_from(ProductPushLog)
        .where(ProductPushLog.customer_id == cid)
    )).scalar() or 0

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [
            {
                "push_log_id": str(r.id),
                "product_id": str(r.product_id),
                "status": r.status,
                "ops_product_id": r.ops_product_id,
                "supplier_sku": r.supplier_sku,
                "supplier_slug": r.supplier_slug,
                "dry_run": r.dry_run,
                "error": r.error,
                "pushed_at": r.pushed_at.isoformat() if r.pushed_at else None,
            }
            for r in rows
        ],
    }


# ── GET /api/portal/catalog ───────────────────────────────────────────

@router.get("/catalog")
async def portal_catalog(
    current_user: CustomerAdmin,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Products selected for this storefront, with push status."""
    cid = current_user.customer_id

    selections = (await db.execute(
        select(CustomerProductSelection, Product)
        .join(Product, Product.id == CustomerProductSelection.product_id)
        .where(CustomerProductSelection.customer_id == cid)
        .order_by(CustomerProductSelection.added_at.desc())
        .offset(skip).limit(limit)
    )).all()

    total = (await db.execute(
        select(func.count()).select_from(CustomerProductSelection)
        .where(CustomerProductSelection.customer_id == cid)
    )).scalar() or 0

    # Latest push status per product
    push_status_rows = (await db.execute(
        select(ProductPushLog.product_id, ProductPushLog.status, ProductPushLog.ops_product_id)
        .where(
            ProductPushLog.customer_id == cid,
            ProductPushLog.product_id.in_([s.product_id for _, s in selections] if selections else [])  # type: ignore[union-attr]
        )
        .distinct(ProductPushLog.product_id)
        .order_by(ProductPushLog.product_id, ProductPushLog.pushed_at.desc())
    )).all()
    push_map = {str(r.product_id): {"status": r.status, "ops_product_id": r.ops_product_id} for r in push_status_rows}

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [
            {
                "selection_id": str(sel.id),
                "product_id": str(prod.id),
                "supplier_sku": prod.supplier_sku,
                "product_name": prod.product_name,
                "brand": prod.brand,
                "image_url": prod.image_url,
                "added_at": sel.added_at.isoformat() if sel.added_at else None,
                "push_status": push_map.get(str(prod.id)),
            }
            for sel, prod in selections
        ],
    }


# ── GET /api/portal/markup-rules ──────────────────────────────────────

@router.get("/markup-rules")
async def portal_markup_rules(current_user: CustomerAdmin, db: AsyncSession = Depends(get_db)):
    """Pricing rules for this storefront (read-only)."""
    rows = (await db.execute(
        select(MarkupRule)
        .where(MarkupRule.customer_id == current_user.customer_id)
        .order_by(MarkupRule.priority.desc())
    )).scalars().all()

    return [
        {
            "id": str(r.id),
            "scope": r.scope,
            "markup_pct": float(r.markup_pct) if r.markup_pct is not None else None,
            "markup_amount": float(r.markup_amount) if r.markup_amount is not None else None,
            "min_margin": float(r.min_margin) if r.min_margin else None,
            "rounding": r.rounding,
            "priority": r.priority,
            "is_active": r.is_active,
        }
        for r in rows
    ]


# ── PATCH /api/portal/account ─────────────────────────────────────────

@router.patch("/account")
async def portal_update_account(
    body: dict,
    current_user: CustomerAdmin,
    db: AsyncSession = Depends(get_db),
):
    """Customer_admin self-service: update OPS client secret only."""
    customer = await db.get(Customer, current_user.customer_id)
    if not customer:
        raise HTTPException(404, "Storefront not found")

    forbidden = set(body.keys()) - {"ops_client_secret"}
    if forbidden:
        raise HTTPException(403, f"Cannot modify: {sorted(forbidden)}")

    if body.get("ops_client_secret"):
        existing = customer.ops_auth_config or {}
        customer.ops_auth_config = {**existing, "client_secret": body["ops_client_secret"]}
        await db.commit()

    return {"updated": True}
