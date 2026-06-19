from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from modules.auth.dependencies import CurrentUser, VGAdmin
from modules.suppliers.models import Supplier
from .option_collapse import derive_options, derive_options_bulk

from modules.push_log.models import ProductPushLog
from .models import Category, Product, ProductOption, ProductOptionAttribute, ProductVariant
from .exporter import build_supplier_product, push_products_to_graphx
from .option_collapse import derive_options, derive_options_bulk
from .schemas import (
    ProductListRead,
    ProductRead,
    ProductPreview,
    VariantPreview,
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
    current_user: CurrentUser,
    supplier_id: Optional[UUID] = None,
    category_id: Optional[UUID] = None,
    customer_id: Optional[UUID] = None,
    brand: Optional[str] = None,
    search: Optional[str] = None,
    product_type: Optional[str] = None,
    archived: bool = False,
    skip: int = 0,
    limit: int = Query(default=50, le=1000),
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
    if customer_id is not None and current_user.role == "customer_admin":
        if customer_id != current_user.customer_id:
            raise HTTPException(403, "Not authorized for this customer")
    if customer_id:
        pushed_ids = (
            await db.execute(
                select(ProductPushLog.product_id)
                .where(ProductPushLog.customer_id == customer_id)
                .distinct()
            )
        ).scalars().all()
        query = query.where(Product.id.in_(pushed_ids))
    if product_type:
        query = query.where(Product.product_type == product_type)
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
    query = query.offset(skip).limit(limit).order_by(Product.last_synced.desc(), Product.product_name)

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


@router.post("/derive-options")
async def derive_all_product_options(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    supplier_id: Optional[UUID] = Query(default=None),
):
    """Backfill: (re)derive Color/Size options for all products (or one supplier)."""
    return await derive_options_bulk(db, supplier_id)


@router.post("/{product_id}/derive-options")
async def derive_product_options(
    product_id: UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """(Re)derive Color/Size options for one product from its variant matrix."""
    res = await derive_options(db, product_id)
    return {
        "product_id": str(product_id),
        "colors": res.colors,
        "sizes": res.sizes,
        "color_attrs": res.color_attrs,
        "size_attrs": res.size_attrs,
    }


@router.post("/{product_id}/push-to-graphx")
async def push_one_product_to_graphx(
    product_id: UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    tenant_slug: str = Query(default="vg"),
):
    """Push a single product to graphx as IMPORTED_FROM_SUPPLIER."""
    import os
    import httpx
    payload = await build_supplier_product(db, product_id)
    if not payload["options"]:
        raise HTTPException(400, "Product has no options — run derive-options first")
    product = await db.get(Product, product_id)
    supplier = await db.get(Supplier, product.supplier_id) if product else None

    url = os.environ["GRAPHX_INGEST_URL"]
    secret = os.environ["GRAPHX_INGEST_SECRET"]
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            url,
            headers={"x-ingest-secret": secret},
            json={
                "supplier_key": supplier.slug if supplier else "",
                "tenant_slug": tenant_slug,
                "products": [payload],
            },
        )
        body = None
        if r.headers.get("content-type", "").startswith("application/json"):
            try:
                body = r.json()
            except Exception:
                body = None
    return {"status": r.status_code, "body": body}


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
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.variants).selectinload(ProductVariant.prices),
            selectinload(Product.images),
            selectinload(Product.options).selectinload(ProductOption.attributes),
            selectinload(Product.apparel_details),
            selectinload(Product.print_details),
            selectinload(Product.sizes),
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(404, "Product not found")

    supplier = await db.get(Supplier, product.supplier_id)
    data = ProductRead.model_validate(product)
    data.supplier_name = supplier.name if supplier else None
    data.supplier_slug = supplier.slug if supplier else None
    data.supplier_has_decoration_overlay = bool(supplier.has_decoration_overlay) if supplier else False
    data.images = sorted(data.images, key=lambda i: i.sort_order)

    data.options = sorted(data.options, key=lambda o: o.sort_order)
    for opt in data.options:
        opt.attributes = sorted(opt.attributes, key=lambda a: a.sort_order)
    return data


@router.get("/{product_id}/export")
async def export_product(product_id: UUID, db: AsyncSession = Depends(get_db)):
    """Return a self-contained JSON snapshot of a product for local download.

    Auth: protected by router-level ``dependencies=[Depends(get_current_user)]``
    applied in main.py — no explicit param needed here.
    """
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.variants).selectinload(ProductVariant.prices),
            selectinload(Product.images),
            selectinload(Product.sizes),
            selectinload(Product.options).selectinload(ProductOption.attributes),
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(404, "Product not found")

    supplier = await db.get(Supplier, product.supplier_id)

    variants = [
        {
            "sku": v.sku,
            "color": v.color,
            "size": v.size,
            "base_price": float(v.base_price) if v.base_price is not None else None,
            "inventory": v.inventory,
            "prices": [
                {
                    "price_type": p.price_type,
                    "quantity_min": p.quantity_min,
                    "quantity_max": p.quantity_max,
                    "price": float(p.price),
                }
                for p in (v.prices or [])
            ],
        }
        for v in (product.variants or [])
    ]

    sizes = [
        {
            "width": float(s.width),
            "height": float(s.height),
            "unit": s.unit,
            "label": s.label,
        }
        for s in (product.sizes or [])
    ]

    prices = [float(v["base_price"]) for v in variants if v["base_price"] is not None]

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "product": {
            "id": str(product.id),
            "supplier_sku": product.supplier_sku,
            "product_name": product.product_name,
            "brand": product.brand,
            "description": product.description,
            "product_type": product.product_type,
            "image_url": product.image_url,
            "supplier": {
                "id": str(supplier.id) if supplier else None,
                "name": supplier.name if supplier else None,
                "slug": supplier.slug if supplier else None,
                "protocol": supplier.protocol if supplier else None,
            },
        },
        "variants": variants,
        "sizes": sizes,
        "pricing_summary": {
            "variant_count": len(variants),
            "price_min": min(prices) if prices else None,
            "price_max": max(prices) if prices else None,
        },
        "images": [{"id": str(img.id), "url": img.url, "image_type": img.image_type, "color": img.color, "sort_order": img.sort_order} for img in (product.images or [])],
        "options": [
            {
                "option_key": o.option_key,
                "title": o.title,
                "options_type": o.options_type,
                "attributes": [
                    {"title": a.title, "attribute_key": a.attribute_key, "sort_order": a.sort_order}
                    for a in sorted(o.attributes or [], key=lambda a: a.sort_order)
                ],
            }
            for o in sorted(product.options or [], key=lambda o: o.sort_order)
        ],
    }


@router.get("/{product_id}/preview", response_model=ProductPreview)
async def get_product_preview(product_id: UUID, db: AsyncSession = Depends(get_db)):
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

    missing: list[str] = []
    if not product.product_name:
        missing.append("title")
    if not product.description:
        missing.append("description")
    if not product.brand:
        missing.append("brand")
    if not product.category:
        missing.append("category")
    if not product.images:
        missing.append("images")

    variants: list[VariantPreview] = []
    for v in product.variants:
        if not v.sku:
            missing.append(f"sku (variant {v.color or ''} {v.size or ''})".strip())
        if v.base_price is None:
            missing.append(f"price (variant {v.sku or v.color or v.size or ''})".strip())
        if v.inventory is None:
            missing.append(f"inventory (variant {v.sku or v.color or v.size or ''})".strip())
        variants.append(VariantPreview(
            sku=v.sku,
            size=v.size,
            color=v.color,
            price=float(v.base_price) if v.base_price is not None else None,
            inventory=v.inventory,
        ))

    return ProductPreview(
        id=product.id,
        title=product.product_name,
        description=product.description,
        brand=product.brand,
        category=product.category,
        images=product.images,
        variants=variants,
        missing_fields=missing,
    )


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
    product_id: UUID,
    body: list[OptionIngest],
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    existing_opts_res = await db.execute(
        select(ProductOption).where(ProductOption.product_id == product_id)
    )
    existing_opts = {opt.option_key: opt for opt in existing_opts_res.scalars().all()}

    saved = 0
    errors: list[dict] = []

    for opt_data in body:
        sp = await db.begin_nested()
        try:
            if opt_data.option_key in existing_opts:
                opt = existing_opts[opt_data.option_key]
                opt.title = opt_data.title
                opt.sort_order = opt_data.sort_order
                opt.enabled = True
            else:
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

            if isinstance(opt_data.attributes, list):
                existing_attrs_res = await db.execute(
                    select(ProductOptionAttribute).where(
                        ProductOptionAttribute.product_option_id == opt.id
                    )
                )
                existing_attrs = {attr.title: attr for attr in existing_attrs_res.scalars().all()}

                for attr_data in opt_data.attributes:
                    if attr_data.title in existing_attrs:
                        attr = existing_attrs[attr_data.title]
                        attr.price = attr_data.price
                        attr.sort_order = attr_data.sort_order
                        attr.enabled = True
                    else:
                        db.add(ProductOptionAttribute(
                            product_option_id=opt.id,
                            title=attr_data.title,
                            price=attr_data.price,
                            sort_order=attr_data.sort_order,
                            enabled=True,
                        ))

            await sp.commit()
            saved += 1
        except Exception as exc:
            await sp.rollback()
            errors.append({"option_key": opt_data.option_key, "error": str(exc)})

    await db.commit()
    if errors:
        return {"success": False, "saved": saved, "errors": errors}
    return {"success": True, "saved": saved}


# ─── Variant → Option collapse routes ────────────────────────────────────────

@router.post("/derive-options")
async def derive_all_product_options(
    _admin: VGAdmin,
    db: AsyncSession = Depends(get_db),
    supplier_id: Optional[UUID] = Query(default=None),
):
    """Backfill: (re)derive Color/Size options for all products (or one supplier)."""
    return await derive_options_bulk(db, supplier_id)


@router.post("/{product_id}/derive-options")
async def derive_product_options(
    product_id: UUID,
    _admin: VGAdmin,
    db: AsyncSession = Depends(get_db),
):
    """(Re)derive Color/Size options for one product from its variant matrix."""
    res = await derive_options(db, product_id)
    return {
        "product_id": str(product_id),
        "colors": res.colors,
        "sizes": res.sizes,
        "color_attrs": res.color_attrs,
        "size_attrs": res.size_attrs,
    }
