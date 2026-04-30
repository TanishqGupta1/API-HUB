"""Centralized persistence service for the catalog.

Handles idempotent upserts of products and their complex polymorphic relationships.
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Product,
    ProductVariant,
    ProductImage,
    ProductOption,
    ProductOptionAttribute,
    ApprelDetails,
    PrintDetails,
    VariantPrice,
    ProductSize,
)
from .schemas import ProductIngest


async def persist_product(
    db: AsyncSession, supplier_id: UUID, item: ProductIngest, category_id: UUID | None = None
) -> UUID:
    """Idempotently upsert a product and all its related details.

    This is the single source of truth for writing supplier data to the DB.
    """
    now = datetime.now(timezone.utc)

    # 1. Upsert Product spine
    product_stmt = pg_insert(Product).values(
        supplier_id=supplier_id,
        supplier_sku=item.supplier_sku,
        product_name=item.product_name,
        brand=item.brand,
        category=item.category_name,
        category_id=category_id,
        description=item.description,
        product_type=item.product_type,
        image_url=item.image_url,
        ops_product_id=item.ops_product_id,
        external_catalogue=item.external_catalogue,
        last_synced=now,
    ).on_conflict_do_update(
        index_elements=["supplier_id", "supplier_sku"],
        set_={
            "product_name": item.product_name,
            "brand": item.brand,
            "category": item.category_name,
            "category_id": category_id,
            "description": item.description,
            "product_type": item.product_type,
            "image_url": item.image_url,
            "ops_product_id": item.ops_product_id,
            "external_catalogue": item.external_catalogue,
            "last_synced": now,
        },
    ).returning(Product.id)

    result = await db.execute(product_stmt)
    product_id = result.scalar_one()

    # 2. Upsert Polymorphic Details
    if item.apparel_details:
        app_stmt = pg_insert(ApprelDetails).values(
            product_id=product_id,
            pricing_method=item.apparel_details.pricing_method,
            raw_payload=item.apparel_details.raw_payload,
        ).on_conflict_do_update(
            index_elements=["product_id"],
            set_={
                "pricing_method": item.apparel_details.pricing_method,
                "raw_payload": item.apparel_details.raw_payload,
            },
        )
        await db.execute(app_stmt)

    if item.print_details:
        pr_stmt = pg_insert(PrintDetails).values(
            product_id=product_id,
            pricing_method=item.print_details.pricing_method,
            min_width=item.print_details.min_width,
            max_width=item.print_details.max_width,
            min_height=item.print_details.min_height,
            max_height=item.print_details.max_height,
            size_unit=item.print_details.size_unit,
            base_price_per_sq_unit=item.print_details.base_price_per_sq_unit,
            raw_payload=item.print_details.raw_payload,
        ).on_conflict_do_update(
            index_elements=["product_id"],
            set_={
                "pricing_method": item.print_details.pricing_method,
                "min_width": item.print_details.min_width,
                "max_width": item.print_details.max_width,
                "min_height": item.print_details.min_height,
                "max_height": item.print_details.max_height,
                "size_unit": item.print_details.size_unit,
                "base_price_per_sq_unit": item.print_details.base_price_per_sq_unit,
                "raw_payload": item.print_details.raw_payload,
            },
        )
        await db.execute(pr_stmt)

    # 3. Upsert Product Sizes (Delete-and-reinsert for simplicity as they are few)
    if item.sizes:
        await db.execute(delete(ProductSize).where(ProductSize.product_id == product_id))
        for s in item.sizes:
            db.add(ProductSize(
                product_id=product_id,
                width=s.width,
                height=s.height,
                unit=s.unit,
                label=s.label
            ))

    # 4. Upsert Variants and Tiered Prices
    for v in item.variants:
        variant_stmt = pg_insert(ProductVariant).values(
            product_id=product_id,
            color=v.color,
            size=v.size,
            sku=v.sku,
            base_price=v.base_price,
            inventory=v.inventory,
            warehouse=v.warehouse,
        ).on_conflict_do_update(
            index_elements=["product_id", "color", "size"],
            set_={
                "sku": v.sku,
                "base_price": v.base_price,
                "inventory": v.inventory,
                "warehouse": v.warehouse,
            },
        ).returning(ProductVariant.id)
        v_res = await db.execute(variant_stmt)
        variant_id = v_res.scalar_one()

        if v.prices:
            # Delete old prices and reinsert new ones
            await db.execute(delete(VariantPrice).where(VariantPrice.variant_id == variant_id))
            for p in v.prices:
                db.add(VariantPrice(
                    variant_id=variant_id,
                    price_type=p.price_type,
                    quantity_min=p.quantity_min,
                    quantity_max=p.quantity_max,
                    price=p.price
                ))

    # 5. Upsert Images
    for idx, img in enumerate(item.images):
        image_stmt = pg_insert(ProductImage).values(
            product_id=product_id,
            url=img.url,
            image_type=img.image_type,
            color=img.color,
            sort_order=img.sort_order or idx,
        ).on_conflict_do_update(
            index_elements=["product_id", "url"],
            set_={
                "image_type": img.image_type,
                "color": img.color,
                "sort_order": img.sort_order or idx,
            },
        )
        await db.execute(image_stmt)

    # 6. Upsert Options (Reuse the logic from ingest.py or similar)
    if item.options:
        from .ingest import _upsert_options
        await _upsert_options(db, product_id, item.options)

    return product_id
