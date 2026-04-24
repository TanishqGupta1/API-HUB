from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import Product
from modules.push_log.models import ProductPushLog


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

    log_result = await db.execute(
        select(ProductPushLog)
        .where(
            ProductPushLog.customer_id == customer_id,
            ProductPushLog.product_id.in_([p.id for p in rows]),
        )
        .order_by(ProductPushLog.pushed_at.desc())
    )
    logs_by_product: dict[UUID, str] = {}
    for log in log_result.scalars().all():
        if log.product_id not in logs_by_product:
            logs_by_product[log.product_id] = log.ops_product_id

    return [
        {
            "product_id": str(p.id),
            "supplier_sku": p.supplier_sku,
            "product_name": p.product_name,
            "ops_product_id": logs_by_product.get(p.id),
        }
        for p in rows
    ]
