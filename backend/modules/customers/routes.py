from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.markup.models import MarkupRule
from modules.push_log.models import ProductPushLog

from .models import Customer
from .schemas import CustomerCreate, CustomerRead

router = APIRouter(prefix="/api/customers", tags=["customers"])


async def _with_counts(db: AsyncSession, customer: Customer) -> CustomerRead:
    products_pushed = (
        await db.execute(
            select(func.count()).select_from(ProductPushLog).where(
                ProductPushLog.customer_id == customer.id,
                ProductPushLog.status == "pushed",
            )
        )
    ).scalar() or 0

    markup_rules_count = (
        await db.execute(
            select(func.count()).select_from(MarkupRule).where(
                MarkupRule.customer_id == customer.id
            )
        )
    ).scalar() or 0

    data = CustomerRead.model_validate(customer)
    data.products_pushed = products_pushed
    data.markup_rules_count = markup_rules_count
    return data


@router.get("", response_model=list[CustomerRead])
async def list_customers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).order_by(Customer.created_at.desc()))
    customers = result.scalars().all()
    return [await _with_counts(db, c) for c in customers]


@router.post("", response_model=CustomerRead, status_code=201)
async def create_customer(body: CustomerCreate, db: AsyncSession = Depends(get_db)):
    customer = Customer(
        name=body.name,
        ops_base_url=body.ops_base_url,
        ops_token_url=body.ops_token_url,
        ops_client_id=body.ops_client_id,
        ops_auth_config={"client_secret": body.ops_client_secret},
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return await _with_counts(db, customer)


@router.get("/{customer_id}", response_model=CustomerRead)
async def get_customer(customer_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(404, "Customer not found")
    return await _with_counts(db, customer)


@router.patch("/{customer_id}", response_model=CustomerRead)
async def update_customer(
    customer_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(404, "Customer not found")
    for field in ("name", "ops_base_url", "ops_token_url", "ops_client_id", "is_active"):
        if field in body:
            setattr(customer, field, body[field])
    if "ops_client_secret" in body and body["ops_client_secret"]:
        customer.ops_auth_config = {"client_secret": body["ops_client_secret"]}
    await db.commit()
    await db.refresh(customer)
    return await _with_counts(db, customer)


@router.delete("/{customer_id}")
async def delete_customer(customer_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(404, "Customer not found")
    await db.delete(customer)
    await db.commit()
    return {"deleted": True}


@router.post("/{customer_id}/test")
async def test_customer(customer_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(404, "Customer not found")
    # TODO: attempt OAuth2 token fetch against ops_token_url
    return {"ok": True, "customer_id": str(customer_id)}
