from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete as sa_delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.auth.dependencies import require_customer_access
from modules.catalog.models import Product
from modules.customers.models import Customer

from .models import CustomerProductDecoration
from .schemas import DecorationCreate, DecorationRead

router = APIRouter(prefix="/api/customers", tags=["decorations"])


@router.put(
    "/{customer_id}/products/{product_id}/decorations",
    response_model=DecorationRead,
    dependencies=[Depends(require_customer_access)],
)
async def upsert_decoration(
    customer_id: uuid.UUID,
    product_id: uuid.UUID,
    body: DecorationCreate,
    db: AsyncSession = Depends(get_db),
) -> DecorationRead:
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(404, f"Customer {customer_id} not found")

    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, f"Product {product_id} not found")

    now = datetime.now(timezone.utc)
    options_json = body.decoration_options

    stmt = (
        pg_insert(CustomerProductDecoration)
        .values(
            customer_id=customer_id,
            product_id=product_id,
            decoration_options=options_json,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["customer_id", "product_id"],
            set_={"decoration_options": options_json, "updated_at": now},
        )
        .returning(CustomerProductDecoration)
    )
    row = (await db.execute(stmt)).scalar_one()
    await db.commit()
    return DecorationRead.model_validate(row)


@router.get(
    "/{customer_id}/products/{product_id}/decorations",
    response_model=DecorationRead,
    dependencies=[Depends(require_customer_access)],
)
async def get_decoration(
    customer_id: uuid.UUID,
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DecorationRead:
    row = await db.get(CustomerProductDecoration, (customer_id, product_id))
    if row is None:
        raise HTTPException(404, "No decoration found")
    return DecorationRead.model_validate(row)


@router.delete(
    "/{customer_id}/products/{product_id}/decorations",
    status_code=204,
    response_model=None,
    dependencies=[Depends(require_customer_access)],
)
async def delete_decoration(
    customer_id: uuid.UUID,
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    row = await db.get(CustomerProductDecoration, (customer_id, product_id))
    if row is None:
        raise HTTPException(404, "No decoration to delete")
    await db.delete(row)
    await db.commit()
from fastapi.responses import Response
from .engine import generate_decorated_image

@router.get(
    "/{customer_id}/products/{product_id}/decorations/preview.png",
    response_class=Response,
    dependencies=[Depends(require_customer_access)],
)
async def get_decoration_preview(
    customer_id: uuid.UUID,
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Dynamically generate a PNG preview of the decorated product."""
    row = await db.get(CustomerProductDecoration, (customer_id, product_id))
    if row is None:
        raise HTTPException(404, "No decoration found")

    product = await db.get(Product, product_id)
    if not product or not product.image_url:
        raise HTTPException(404, "Product image not found")

    from .schemas import DecorationOption
    options = [DecorationOption.model_validate(opt) for opt in row.decoration_options]

    img_bytes = await generate_decorated_image(product.image_url, options)
    return Response(content=img_bytes, media_type="image/png")
