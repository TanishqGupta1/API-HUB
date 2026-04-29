from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from modules.suppliers.models import Supplier

from modules.push_log.models import ProductPushLog
from .models import Category, Product, ProductOption, ProductVariant
from .schemas import ProductListRead, ProductRead, OPSCategoryInput

router = APIRouter(prefix="/api/products", tags=["catalog"])
categories_router = APIRouter(prefix="/api/categories", tags=["catalog"])


async def _category_descendants(db: AsyncSession, root_id: UUID) -> list[UUID]:
    """Return root_id + all descendant category ids via PostgreSQL recursive CTE."""
    cte_sql = text("""
        WITH RECURSIVE descendants AS (
            SELECT id FROM categories WHERE id = :root_id
            UNION ALL
            SELECT c.id FROM categories c
            JOIN descendants d ON c.parent_id = d.id
        )
        SELECT id FROM descendants
    """)
    rows = (await db.execute(cte_sql, {"root_id": root_id})).fetchall()
    return [row[0] for row in rows]


@router.get("", response_model=list[ProductListRead])
async def list_products(
    supplier_id: Optional[UUID] = None,
    category_id: Optional[UUID] = None,
    customer_id: Optional[UUID] = None,
    brand: Optional[str] = None,
    search: Optional[str] = None,
    archived: bool = False,
    skip: int = 0,
    limit: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_db),
):
    variant_agg = (
        select(
            ProductVariant.product_id.label("product_id"),
            func.count(ProductVariant.id).label("variant_count"),
            func.min(ProductVariant.base_price).label("price_min"),
            func.max(ProductVariant.base_price).label("price_max"),
            func.coalesce(func.sum(ProductVariant.inventory), 0).label("total_inventory"),
        )
        .group_by(ProductVariant.product_id)
        .subquery()
    )

    query = (
        select(
            Product,
            variant_agg.c.variant_count,
            variant_agg.c.price_min,
            variant_agg.c.price_max,
            variant_agg.c.total_inventory,
        )
        .outerjoin(variant_agg, variant_agg.c.product_id == Product.id)
    )
    if archived:
        query = query.where(Product.archived_at.is_not(None))
    else:
        query = query.where(Product.archived_at.is_(None))
    if supplier_id:
        query = query.where(Product.supplier_id == supplier_id)
    if category_id:
        descendants = await _category_descendants(db, category_id)
        query = query.where(Product.category_id.in_(descendants))
    if customer_id:
        pushed_ids = (
            await db.execute(
                select(ProductPushLog.product_id)
                .where(ProductPushLog.customer_id == customer_id)
                .distinct()
            )
        ).scalars().all()
        query = query.where(Product.id.in_(pushed_ids))
    if brand:
        query = query.where(Product.brand == brand)
    if search:
        from sqlalchemy import or_
        query = query.where(
            or_(
                Product.product_name.ilike(f"%{search}%"),
                Product.supplier_sku.ilike(f"%{search}%"),
                Product.brand.ilike(f"%{search}%"),
            )
        )
    query = query.offset(skip).limit(limit).order_by(Product.product_name)

    rows = (await db.execute(query)).all()
    products = [row[0] for row in rows]

    supplier_ids = {p.supplier_id for p in products}
    supplier_map: dict[UUID, str] = {}
    if supplier_ids:
        sup_rows = await db.execute(
            select(Supplier.id, Supplier.name).where(Supplier.id.in_(supplier_ids))
        )
        supplier_map = {row.id: row.name for row in sup_rows}

    out: list[ProductListRead] = []
    for prod, vcount, pmin, pmax, total_inv in rows:
        data = ProductListRead.model_validate(prod)
        data.variant_count = int(vcount or 0)
        data.price_min = pmin
        data.price_max = pmax
        data.total_inventory = int(total_inv or 0)
        data.supplier_name = supplier_map.get(prod.supplier_id)
        out.append(data)
    return out


@router.post("/{product_id}/archive")
async def archive_product(product_id: UUID, db: AsyncSession = Depends(get_db)):
    prod = await db.get(Product, product_id)
    if not prod:
        raise HTTPException(404, "Product not found")
    if prod.archived_at is None:
        prod.archived_at = datetime.now(timezone.utc)
        await db.commit()
    return {"archived": True, "archived_at": prod.archived_at}


@router.post("/{product_id}/restore")
async def restore_product(product_id: UUID, db: AsyncSession = Depends(get_db)):
    prod = await db.get(Product, product_id)
    if not prod:
        raise HTTPException(404, "Product not found")
    prod.archived_at = None
    await db.commit()
    return {"archived": False}


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.variants),
            selectinload(Product.images),
            selectinload(Product.options).selectinload(ProductOption.attributes),
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(404, "Product not found")

    supplier = await db.get(Supplier, product.supplier_id)
    data = ProductRead.model_validate(product)
    data.supplier_name = supplier.name if supplier else None
    data.images = sorted(data.images, key=lambda i: i.sort_order)
    data.options = sorted(data.options, key=lambda o: o.sort_order)
    for opt in data.options:
        opt.attributes = sorted(opt.attributes, key=lambda a: a.sort_order)
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


@categories_router.get("/{category_id}/ops-input", response_model=OPSCategoryInput)
async def get_category_ops_input(category_id: UUID, db: AsyncSession = Depends(get_db)):
    cat = await db.get(Category, category_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    return OPSCategoryInput(
        category_name=cat.name,
        parent_id=-1,
        status=1,
        category_internal_name=cat.external_id or cat.name.lower().replace(" ", "_"),
    )
