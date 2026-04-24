from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.customers.models import Customer

from .models import ProductPushLog
from .schemas import ProductPushStatus, PushLogCreate, PushLogRead

router = APIRouter(tags=["push_log"])


@router.get("/api/push-log", response_model=list[PushLogRead])
async def list_push_logs(
    product_id: UUID | None = None,
    customer_id: UUID | None = None,
    limit: int = Query(default=20, le=200),
    db: AsyncSession = Depends(get_db),
):
    from modules.catalog.models import Product
    from modules.suppliers.models import Supplier

    q = (
        select(
            ProductPushLog,
            Product.product_name,
            Customer.name.label("customer_name"),
            Supplier.name.label("supplier_name"),
        )
        .join(Product, ProductPushLog.product_id == Product.id)
        .join(Customer, ProductPushLog.customer_id == Customer.id)
        .join(Supplier, Product.supplier_id == Supplier.id)
        .order_by(ProductPushLog.pushed_at.desc())
    )
    if product_id:
        q = q.where(ProductPushLog.product_id == product_id)
    if customer_id:
        q = q.where(ProductPushLog.customer_id == customer_id)
    q = q.limit(limit)

    rows = (await db.execute(q)).all()
    out = []
    for log, prod_name, cust_name, supp_name in rows:
        data = PushLogRead.model_validate(log)
        data.product_name = prod_name
        data.customer_name = cust_name
        data.supplier_name = supp_name
        out.append(data)
    return out




@router.post("/api/push-log", response_model=PushLogRead, status_code=201)
async def create_push_log(body: PushLogCreate, db: AsyncSession = Depends(get_db)):
    from modules.catalog.models import Product
    from modules.suppliers.models import Supplier

    log = ProductPushLog(**body.model_dump())
    db.add(log)
    await db.commit()
    await db.refresh(log)

    # Join to get display names — same contract as list_push_logs
    row = await db.execute(
        select(
            ProductPushLog,
            Product.product_name,
            Customer.name.label("customer_name"),
            Supplier.name.label("supplier_name"),
        )
        .join(Product, ProductPushLog.product_id == Product.id)
        .join(Customer, ProductPushLog.customer_id == Customer.id)
        .join(Supplier, Product.supplier_id == Supplier.id)
        .where(ProductPushLog.id == log.id)
    )
    result = row.one_or_none()
    if result:
        log_obj, prod_name, cust_name, supp_name = result
        data = PushLogRead.model_validate(log_obj)
        data.product_name = prod_name
        data.customer_name = cust_name
        data.supplier_name = supp_name
        return data
    return PushLogRead.model_validate(log)


@router.get("/api/products/{product_id}/push-status", response_model=list[ProductPushStatus])
async def get_push_status(product_id: UUID, db: AsyncSession = Depends(get_db)):
    # Single query: latest log per customer for this product using subquery
    subq = (
        select(
            ProductPushLog.customer_id,
            func.max(ProductPushLog.pushed_at).label("latest_at"),
        )
        .where(ProductPushLog.product_id == product_id)
        .group_by(ProductPushLog.customer_id)
        .subquery()
    )
    logs_result = await db.execute(
        select(ProductPushLog).join(
            subq,
            (ProductPushLog.customer_id == subq.c.customer_id)
            & (ProductPushLog.pushed_at == subq.c.latest_at),
        )
    )
    latest_logs = {log.customer_id: log for log in logs_result.scalars().all()}

    # Get all customers in one query
    customers_result = await db.execute(select(Customer))
    out = []
    for c in customers_result.scalars().all():
        log = latest_logs.get(c.id)
        out.append(
            ProductPushStatus(
                customer_id=c.id,
                customer_name=c.name,
                ops_product_id=log.ops_product_id if log else None,
                status=log.status if log else "not_pushed",
                pushed_at=log.pushed_at if log else None,
            )
        )
    return out
