from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from modules.suppliers.models import Supplier

from .models import Category, Product, ProductOption, ProductOptionAttribute, ProductVariant
from .schemas import (
    ProductListRead,
    ProductRead,
    OPSCategoryInput,
    OptionUpdate,
    AttributeUpdate,
    OptionIngest,
)

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
    if brand:
        query = query.where(Product.brand == brand)
    if search:
        query = query.where(Product.product_name.ilike(f"%{search}%"))
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


# ---------------------------------------------------------------------------
# Product Options & Attributes Management
# ---------------------------------------------------------------------------

@router.patch("/{product_id}/options/{option_id}")
async def update_option(
    product_id: UUID, option_id: UUID, body: OptionUpdate, db: AsyncSession = Depends(get_db)
):
    opt = await db.get(ProductOption, option_id)
    if not opt or opt.product_id != product_id:
        raise HTTPException(404, "Option not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(opt, field, value)

    await db.commit()
    return {"success": True}


@router.delete("/{product_id}/options/{option_id}")
async def delete_option(product_id: UUID, option_id: UUID, db: AsyncSession = Depends(get_db)):
    opt = await db.get(ProductOption, option_id)
    if not opt or opt.product_id != product_id:
        raise HTTPException(404, "Option not found")

    await db.delete(opt)
    await db.commit()
    return {"success": True}


@router.patch("/{product_id}/options/{option_id}/attributes/{attr_id}")
async def update_attribute(
    product_id: UUID,
    option_id: UUID,
    attr_id: UUID,
    body: AttributeUpdate,
    db: AsyncSession = Depends(get_db),
):
    attr = await db.get(ProductOptionAttribute, attr_id)
    if not attr or attr.product_option_id != option_id:
        raise HTTPException(404, "Attribute not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(attr, field, value)

    await db.commit()
    return {"success": True}


@router.post("/{product_id}/options/bulk-save")
async def bulk_save_options(
    product_id: UUID, body: list[OptionIngest], db: AsyncSession = Depends(get_db)
):
    # Get existing options for this product
    existing_opts_res = await db.execute(
        select(ProductOption).where(ProductOption.product_id == product_id)
    )
    existing_opts = {opt.option_key: opt for opt in existing_opts_res.scalars().all()}

    for opt_data in body:
        if opt_data.option_key in existing_opts:
            # Update existing option
            opt = existing_opts[opt_data.option_key]
            opt.title = opt_data.title
            opt.sort_order = opt_data.sort_order
            opt.enabled = True
        else:
            # Create new option
            opt = ProductOption(
                product_id=product_id,
                option_key=opt_data.option_key,
                title=opt_data.title,
                options_type=opt_data.options_type,
                sort_order=opt_data.sort_order,
                required=opt_data.required,
                enabled=True,
            )
            db.add(opt)
        
        await db.flush()

        # Update attributes for this option
        if isinstance(opt_data.attributes, list):
            existing_attrs_res = await db.execute(
                select(ProductOptionAttribute).where(ProductOptionAttribute.product_option_id == opt.id)
            )
            existing_attrs = {attr.title: attr for attr in existing_attrs_res.scalars().all()}

            for attr_data in opt_data.attributes:
                if attr_data.title in existing_attrs:
                    # Update existing attribute
                    attr = existing_attrs[attr_data.title]
                    attr.price = attr_data.price
                    attr.sort_order = attr_data.sort_order
                    attr.enabled = True
                else:
                    # Create new attribute
                    attr = ProductOptionAttribute(
                        product_option_id=opt.id,
                        title=attr_data.title,
                        price=attr_data.price,
                        sort_order=attr_data.sort_order,
                        enabled=True,
                    )
                    db.add(attr)

    await db.commit()
    return {"success": True}
