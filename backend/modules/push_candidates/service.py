from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import Product
from modules.decorations.models import CustomerProductDecoration
from modules.push_log.models import ProductPushLog
from modules.suppliers.models import Supplier


async def list_candidates(
    db: AsyncSession,
    customer_id: UUID,
    supplier_id: Optional[UUID] = None,
    only_never_pushed: bool = False,
    limit: int = 100,
) -> list[dict]:
    """Return products eligible to push for a given customer.

    Filters:
    - last_synced must not be null (product has been fetched from supplier)
    - if only_never_pushed=True, exclude products already pushed to this customer
    """
    query = select(Product).where(Product.last_synced.is_not(None))
    if supplier_id:
        query = query.where(Product.supplier_id == supplier_id)

    if only_never_pushed:
        pushed_subq = (
            select(ProductPushLog.product_id)
            .where(
                ProductPushLog.customer_id == customer_id,
                ProductPushLog.status == "pushed",
            )
            .scalar_subquery()
        )
        query = query.where(Product.id.not_in(pushed_subq))

    query = query.limit(limit).order_by(Product.product_name)
    rows = (await db.execute(query)).scalars().all()

    if not rows:
        return []

    product_ids = [p.id for p in rows]

    # Push log: last ops_product_id per product
    log_result = await db.execute(
        select(ProductPushLog)
        .where(
            ProductPushLog.customer_id == customer_id,
            ProductPushLog.product_id.in_(product_ids),
        )
        .order_by(ProductPushLog.pushed_at.desc())
    )
    logs_by_product: dict[UUID, str] = {}
    for log in log_result.scalars().all():
        if log.product_id not in logs_by_product:
            logs_by_product[log.product_id] = log.ops_product_id

    # Decoration status: which products have a saved decoration for this customer
    dec_result = await db.execute(
        select(CustomerProductDecoration.product_id).where(
            CustomerProductDecoration.customer_id == customer_id,
            CustomerProductDecoration.product_id.in_(product_ids),
        )
    )
    decorated_ids: set[UUID] = set(dec_result.scalars().all())

    # Supplier decoration overlay flags
    supplier_ids = {p.supplier_id for p in rows}
    sup_result = await db.execute(
        select(Supplier.id, Supplier.has_decoration_overlay).where(
            Supplier.id.in_(supplier_ids)
        )
    )
    overlay_by_supplier: dict[UUID, bool] = {
        row.id: bool(row.has_decoration_overlay) for row in sup_result
    }

    return [
        {
            "product_id": str(p.id),
            "supplier_sku": p.supplier_sku,
            "product_name": p.product_name,
            "product_type": p.product_type,
            "supplier_id": str(p.supplier_id),
            "image_url": p.image_url,
            "ops_product_id": logs_by_product.get(p.id),
            "supplier_has_decoration_overlay": overlay_by_supplier.get(p.supplier_id, False),
            "decoration_ready": p.id in decorated_ids,
        }
        for p in rows
    ]
