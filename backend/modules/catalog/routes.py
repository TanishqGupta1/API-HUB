from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from modules.suppliers.models import Supplier

from .models import Product, ProductVariant
from .schemas import ProductListRead, ProductRead

router = APIRouter(prefix="/api/products", tags=["catalog"])


@router.get("", response_model=list[ProductListRead])
async def list_products(
    supplier_id: Optional[UUID] = None,
    brand: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(Product)
    if supplier_id:
        query = query.where(Product.supplier_id == supplier_id)
    if brand:
        query = query.where(Product.brand == brand)
    if search:
        query = query.where(Product.product_name.ilike(f"%{search}%"))
    query = query.offset(skip).limit(limit).order_by(Product.product_name)

    result = await db.execute(query)
    products = result.scalars().all()

    # Batch-fetch supplier names to avoid N+1
    supplier_ids = {p.supplier_id for p in products}
    supplier_map: dict[UUID, str] = {}
    if supplier_ids:
        rows = await db.execute(
            select(Supplier.id, Supplier.name).where(Supplier.id.in_(supplier_ids))
        )
        supplier_map = {row.id: row.name for row in rows}

    out = []
    for p in products:
        count = (
            await db.execute(
                select(func.count())
                .select_from(ProductVariant)
                .where(ProductVariant.product_id == p.id)
            )
        ).scalar() or 0
        data = ProductListRead.model_validate(p)
        data.variant_count = count
        data.supplier_name = supplier_map.get(p.supplier_id)
        out.append(data)
    return out


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.variants),
            selectinload(Product.images),
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(404, "Product not found")

    supplier = await db.get(Supplier, product.supplier_id)
    data = ProductRead.model_validate(product)
    data.supplier_name = supplier.name if supplier else None
    data.images = sorted(data.images, key=lambda i: i.sort_order)
    return data
