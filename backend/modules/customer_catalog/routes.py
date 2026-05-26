"""Customer-curated catalog selection routes (Phase 6 API surface).

Endpoints (all under /api/customers/{customer_id}/selections):
  GET    ""              — list with derived 'failed' overlay + supplier_id filter
  POST   "/{product_id}" — add (idempotent — returns 201 even when already selected)
  DELETE "/{product_id}" — hard-delete (matches the existing model — no removed_at column)
  POST   "/bulk"         — bulk add

Stale detection is owned by `import_jobs.service._finalize_job` — sync jobs
flip selection.status from 'pushed' → 'stale' when the source product was
updated in the same sync. We don't recompute status here.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.auth.dependencies import get_current_user
from modules.auth.models import User
from modules.catalog.models import CustomerProductSelection, Product
from modules.customers.models import Customer
from modules.decorations.models import CustomerProductDecoration
from modules.push_log.models import ProductPushLog
from modules.suppliers.models import Supplier

from .schemas import (
    SelectionBulkCreate,
    SelectionBulkResponse,
    SelectionRead,
    SelectionStatus,
)

router = APIRouter(prefix="/api/customers", tags=["customer_catalog"])


def _to_read(
    sel: CustomerProductSelection,
    product: Product,
    status_str: SelectionStatus,
    *,
    supplier_has_decoration_overlay: bool = False,
    decoration_ready: bool = False,
    supplier_slug: str | None = None,
) -> SelectionRead:
    return SelectionRead(
        id=sel.id,
        customer_id=sel.customer_id,
        product_id=sel.product_id,
        status=status_str,
        added_at=sel.added_at,
        pushed_at=sel.pushed_at,
        supplier_id=product.supplier_id,
        supplier_sku=product.supplier_sku,
        supplier_slug=supplier_slug,
        product_name=product.product_name,
        product_type=product.product_type,
        image_url=product.image_url,
        ops_product_id=product.ops_product_id,
        last_synced=product.last_synced,
        supplier_has_decoration_overlay=supplier_has_decoration_overlay,
        decoration_ready=decoration_ready,
    )


async def _latest_failed_pids(
    db: AsyncSession, customer_id: UUID, product_ids: list[UUID]
) -> set[UUID]:
    """Return product_ids whose latest push attempt for this customer failed."""
    if not product_ids:
        return set()
    logs = (
        await db.execute(
            select(ProductPushLog)
            .where(
                ProductPushLog.customer_id == customer_id,
                ProductPushLog.product_id.in_(product_ids),
            )
            .order_by(ProductPushLog.pushed_at.desc())
        )
    ).scalars().all()

    failed: set[UUID] = set()
    seen: set[UUID] = set()
    for log in logs:
        if log.product_id in seen:
            continue
        seen.add(log.product_id)
        if log.status == "failed":
            failed.add(log.product_id)
    return failed


@router.get(
    "/{customer_id}/selections", response_model=list[SelectionRead]
)
async def list_selections(
    customer_id: UUID,
    supplier_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """List active selections for a customer.

    Status precedence:
      1. 'failed' — overlaid when the latest push_log entry failed
      2. otherwise the stored selection.status (selected / pushed / stale)
    """
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")

    q = (
        select(CustomerProductSelection, Product)
        .join(Product, Product.id == CustomerProductSelection.product_id)
        .where(
            CustomerProductSelection.customer_id == customer_id,
            Product.archived_at.is_(None),
        )
        .order_by(CustomerProductSelection.added_at.desc())
    )
    if supplier_id is not None:
        q = q.where(Product.supplier_id == supplier_id)

    rows = (await db.execute(q)).all()
    if not rows:
        return []

    product_ids = [r[0].product_id for r in rows]
    supplier_ids = {r[1].supplier_id for r in rows}

    failed_set = await _latest_failed_pids(db, customer_id, product_ids)

    # Decoration visibility (parallel to push_candidates.service)
    decorated_ids: set[UUID] = set(
        (await db.execute(
            select(CustomerProductDecoration.product_id).where(
                CustomerProductDecoration.customer_id == customer_id,
                CustomerProductDecoration.product_id.in_(product_ids),
            )
        )).scalars().all()
    )
    overlay_by_supplier: dict[UUID, bool] = {}
    slug_by_supplier: dict[UUID, str] = {}
    for row in (await db.execute(
        select(Supplier.id, Supplier.has_decoration_overlay, Supplier.slug).where(
            Supplier.id.in_(supplier_ids)
        )
    )):
        overlay_by_supplier[row.id] = bool(row.has_decoration_overlay)
        slug_by_supplier[row.id] = row.slug

    out: list[SelectionRead] = []
    for sel, product in rows:
        if sel.product_id in failed_set:
            status_str: SelectionStatus = "failed"
        else:
            stored = sel.status if sel.status in {"selected", "pushed", "stale"} else "selected"
            status_str = stored  # type: ignore[assignment]
        out.append(_to_read(
            sel, product, status_str,
            supplier_has_decoration_overlay=overlay_by_supplier.get(product.supplier_id, False),
            decoration_ready=product.id in decorated_ids,
            supplier_slug=slug_by_supplier.get(product.supplier_id),
        ))
    return out


@router.post(
    "/{customer_id}/selections/bulk",
    response_model=SelectionBulkResponse,
    status_code=201,
)
async def bulk_add_selections(
    customer_id: UUID,
    body: SelectionBulkCreate,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk-add selections. Skips already-selected. Idempotent."""
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")

    if not body.product_ids:
        return SelectionBulkResponse(added=0, already_selected=0, not_found=0)

    valid_products = {
        p.id: p
        for p in (
            await db.execute(
                select(Product).where(
                    Product.id.in_(body.product_ids),
                    Product.archived_at.is_(None),
                )
            )
        ).scalars().all()
    }
    not_found = len(set(body.product_ids)) - len(valid_products)

    existing_ids = set(
        (
            await db.execute(
                select(CustomerProductSelection.product_id).where(
                    CustomerProductSelection.customer_id == customer_id,
                    CustomerProductSelection.product_id.in_(valid_products.keys()),
                )
            )
        ).scalars().all()
    )

    added = 0
    already = 0
    now = datetime.now(timezone.utc)
    for pid in valid_products.keys():
        if pid in existing_ids:
            already += 1
            continue
        db.add(
            CustomerProductSelection(
                customer_id=customer_id,
                product_id=pid,
                status="selected",
                added_at=now,
            )
        )
        added += 1

    await db.commit()
    return SelectionBulkResponse(
        added=added, already_selected=already, not_found=not_found
    )


@router.post(
    "/{customer_id}/selections/{product_id}",
    response_model=SelectionRead,
    status_code=201,
)
async def add_selection(
    customer_id: UUID,
    product_id: UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a product to a customer's catalog. Idempotent."""
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    if product.archived_at is not None:
        raise HTTPException(409, "Product is archived")

    existing = (
        await db.execute(
            select(CustomerProductSelection).where(
                CustomerProductSelection.customer_id == customer_id,
                CustomerProductSelection.product_id == product_id,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        return _to_read(existing, product, existing.status)  # type: ignore[arg-type]

    sel = CustomerProductSelection(
        customer_id=customer_id,
        product_id=product_id,
        status="selected",
    )
    db.add(sel)
    await db.commit()
    await db.refresh(sel)
    return _to_read(sel, product, "selected")


@router.delete(
    "/{customer_id}/selections/{product_id}", status_code=204
)
async def remove_selection(
    customer_id: UUID,
    product_id: UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hard-delete a selection (matches the existing model — no soft-delete column)."""
    sel = (
        await db.execute(
            select(CustomerProductSelection).where(
                CustomerProductSelection.customer_id == customer_id,
                CustomerProductSelection.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    if sel is None:
        raise HTTPException(404, "Selection not found")
    await db.delete(sel)
    await db.commit()
