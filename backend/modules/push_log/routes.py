from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.customers.models import Customer

from .models import ProductPushLog
from .schemas import ProductPushStatus, PushLogCreate, PushLogRead

router = APIRouter(tags=["push_log"])


@router.post("/api/push-log", response_model=PushLogRead, status_code=201)
async def create_push_log(body: PushLogCreate, db: AsyncSession = Depends(get_db)):
    log = ProductPushLog(**body.model_dump())
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


@router.get("/api/products/{product_id}/push-status", response_model=list[ProductPushStatus])
async def get_push_status(product_id: UUID, db: AsyncSession = Depends(get_db)):
    # Get all customers
    customers_result = await db.execute(select(Customer))
    customers = {c.id: c.name for c in customers_result.scalars().all()}

    # Get latest push log per customer for this product
    out = []
    for customer_id, customer_name in customers.items():
        result = await db.execute(
            select(ProductPushLog)
            .where(
                ProductPushLog.product_id == product_id,
                ProductPushLog.customer_id == customer_id,
            )
            .order_by(ProductPushLog.pushed_at.desc())
            .limit(1)
        )
        log = result.scalar_one_or_none()
        out.append(
            ProductPushStatus(
                customer_id=customer_id,
                customer_name=customer_name,
                ops_product_id=log.ops_product_id if log else None,
                status=log.status if log else "not_pushed",
                pushed_at=log.pushed_at if log else None,
            )
        )
    return out
