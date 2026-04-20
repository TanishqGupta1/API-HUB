from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from modules.suppliers.models import Supplier

from .models import Category, Product, ProductVariant
from .schemas import ProductListRead, ProductRead

router = APIRouter(prefix="/api/products", tags=["catalog"])
categories_router = APIRouter(prefix="/api/categories", tags=["catalog"])


async def _category_descendants(db: AsyncSession, root_id: UUID) -> list[UUID]:
    """Return root_id + all descendant category ids (BFS)."""
    all_cats = (
        await db.execute(select(Category.id, Category.parent_id))
    ).all()
    children_by_parent: dict[UUID, list[UUID]] = {}
    for cid, pid in all_cats:
        if pid is not None:
            children_by_parent.setdefault(pid, []).append(cid)

    out = [root_id]
    stack = [root_id]
    while stack:
        cur = stack.pop()
        for child in children_by_parent.get(cur, []):
            if child not in out:
                out.append(child)
                stack.append(child)
    return out


@router.get("", response_model=list[ProductListRead])
async def list_products(
    supplier_id: Optional[UUID] = None,
    category_id: Optional[UUID] = None,
    brand: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(Product)
    if supplier_id:
        query = query.where(Product.supplier_id == supplier_id)
    if category_id:
        # Include products in this category AND any descendant categories.
        descendants = await _category_descendants(db, category_id)
        query = query.where(Product.category_id.in_(descendants))
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


# ---------------------------------------------------------------------------
# Categories (read-only)
# ---------------------------------------------------------------------------

@categories_router.get("")
async def list_categories(
    supplier_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """List categories, optionally scoped to one supplier.

    Returns shallow list with parent_id so the frontend can build a tree.
    """
    query = select(Category)
    if supplier_id:
        query = query.where(Category.supplier_id == supplier_id)
    query = query.order_by(Category.sort_order, Category.name)

    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": str(c.id),
            "supplier_id": str(c.supplier_id),
            "external_id": c.external_id,
            "name": c.name,
            "parent_id": str(c.parent_id) if c.parent_id else None,
            "sort_order": c.sort_order,
        }
        for c in rows
    ]


@categories_router.get("/{category_id}")
async def get_category(category_id: UUID, db: AsyncSession = Depends(get_db)):
    cat = await db.get(Category, category_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    return {
        "id": str(cat.id),
        "supplier_id": str(cat.supplier_id),
        "external_id": cat.external_id,
        "name": cat.name,
        "parent_id": str(cat.parent_id) if cat.parent_id else None,
        "sort_order": cat.sort_order,
    }
