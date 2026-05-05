from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.auth.dependencies import CurrentUser
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
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(404, "Customer not found")

    # customer_admin can only rotate their own ops_client_secret. URLs and
    # other fields are vg_admin-only — a compromised customer_admin must not
    # be able to redirect OPS calls to an attacker host.
    if current_user.role == "customer_admin":
        if str(current_user.customer_id) != str(customer_id):
            raise HTTPException(403, "Cannot edit a different customer")
        if "ops_client_secret" in body and body["ops_client_secret"]:
            existing = customer.ops_auth_config or {}
            customer.ops_auth_config = {**existing, "client_secret": body["ops_client_secret"]}
        await db.commit()
        await db.refresh(customer)
        return await _with_counts(db, customer)

    # vg_admin
    for field in ("name", "ops_base_url", "ops_token_url", "ops_client_id", "is_active"):
        if field in body:
            setattr(customer, field, body[field])
    if "ops_client_secret" in body and body["ops_client_secret"]:
        existing = customer.ops_auth_config or {}
        customer.ops_auth_config = {**existing, "client_secret": body["ops_client_secret"]}
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

    client_secret = (customer.ops_auth_config or {}).get("client_secret", "")
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.post(
                customer.ops_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": customer.ops_client_id,
                    "client_secret": client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code == 200:
            return {
                "ok": True,
                "customer_id": str(customer_id),
                "token_endpoint": customer.ops_token_url,
            }
        return {
            "ok": False,
            "customer_id": str(customer_id),
            "token_endpoint": customer.ops_token_url,
            "http_status": resp.status_code,
            "error": resp.text[:200],
        }
    except Exception as exc:
        return {
            "ok": False,
            "customer_id": str(customer_id),
            "token_endpoint": customer.ops_token_url,
            "error": str(exc)[:200],
        }
