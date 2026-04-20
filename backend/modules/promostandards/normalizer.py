"""Normalization layer — maps PromoStandards data to the canonical database schema.

Uses PostgreSQL 'ON CONFLICT DO UPDATE' to support idempotent syncs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import select

from modules.catalog.models import Product, ProductVariant, ProductImage
from .schemas import PSInventoryLevel, PSMediaItem, PSPricePoint, PSProductData

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)


async def upsert_products(
    db: AsyncSession,
    supplier_id: UUID,
    products: list[PSProductData],
    inventory: list[PSInventoryLevel] | None = None,
    pricing: list[PSPricePoint] | None = None,
    media: list[PSMediaItem] | None = None,
) -> int:
    """Perform a full sync: products + variants + images.

    Returns the number of products processed.
    """
    processed_count = 0
    now = datetime.now(timezone.utc)

    # Pre-index inventory, pricing, and media by part_id or product_id for fast lookup
    inv_map = {lvl.part_id: lvl for lvl in (inventory or [])}
    price_map = {pp.part_id: pp for pp in (pricing or [])}
    
    # Media is usually per product or per product+color
    media_by_prod = {}
    for item in (media or []):
        if item.product_id not in media_by_prod:
            media_by_prod[item.product_id] = []
        media_by_prod[item.product_id].append(item)

    for p_data in products:
        # 1. Upsert Product
        stmt = pg_insert(Product).values(
            supplier_id=supplier_id,
            supplier_sku=p_data.product_id,
            product_name=p_data.product_name or "Unknown Product",
            brand=p_data.brand,
            category=p_data.categories[0] if p_data.categories else None,
            description=p_data.description,
            product_type=p_data.product_type,
            image_url=p_data.primary_image_url,
            last_synced=now,
        ).on_conflict_do_update(
            constraint="uq_product_supplier_sku",
            set_={
                "product_name": p_data.product_name or "Unknown Product",
                "brand": p_data.brand,
                "category": p_data.categories[0] if p_data.categories else None,
                "description": p_data.description,
                "image_url": p_data.primary_image_url,
                "last_synced": now,
            }
        ).returning(Product.id)
        
        res = await db.execute(stmt)
        product_id = res.scalar_one()

        # 2. Upsert Variants
        for part in p_data.parts:
            part_inv = inv_map.get(part.part_id)
            part_price = price_map.get(part.part_id)

            v_stmt = pg_insert(ProductVariant).values(
                product_id=product_id,
                color=part.color_name,
                size=part.size_name,
                sku=part.part_id,
                base_price=part_price.price if part_price else None,
                inventory=part_inv.quantity_available if part_inv else None,
                warehouse=part_inv.warehouse_code if part_inv else None,
            ).on_conflict_do_update(
                constraint="uq_variant_product_color_size",
                set_={
                    "sku": part.part_id,
                    "base_price": part_price.price if part_price else None,
                    "inventory": part_inv.quantity_available if part_inv else None,
                    "warehouse": part_inv.warehouse_code if part_inv else None,
                }
            )
            await db.execute(v_stmt)

        # 3. Upsert Images
        prod_media = media_by_prod.get(p_data.product_id, [])
        # Also always include the primary image if present
        if p_data.primary_image_url:
            img_stmt = pg_insert(ProductImage).values(
                product_id=product_id,
                url=p_data.primary_image_url,
                image_type="front",
            ).on_conflict_do_nothing() # Don't update primary image every time
            await db.execute(img_stmt)

        for m in prod_media:
            m_stmt = pg_insert(ProductImage).values(
                product_id=product_id,
                url=m.url,
                image_type=m.media_type,
                color=m.color_name,
            ).on_conflict_do_update(
                constraint="uq_product_image_url",
                set_={"image_type": m.media_type, "color": m.color_name}
            )
            await db.execute(m_stmt)

        processed_count += 1
        # Commit every 50 products to keep transactions manageable
        if processed_count % 50 == 0:
            await db.commit()

    await db.commit()
    return processed_count


async def update_inventory_only(
    db: AsyncSession, supplier_id: UUID, inventory: list[PSInventoryLevel]
) -> int:
    """Lightweight sync: updates only inventory levels on existing variants.

    Returns the number of variants updated.
    """
    updated_count = 0
    for item in inventory:
        # Find the variant by SKU (part_id) for this supplier's products
        # This is a bit slow if done one by one; in V2 we can optimize with a bulk update.
        stmt = (
            select(ProductVariant)
            .join(Product)
            .where(Product.supplier_id == supplier_id)
            .where(ProductVariant.sku == item.part_id)
        )
        res = await db.execute(stmt)
        variant = res.scalar_one_or_none()
        
        if variant:
            variant.inventory = item.quantity_available
            variant.warehouse = item.warehouse_code
            updated_count += 1
            
        if updated_count % 100 == 0:
            await db.commit()
            
    await db.commit()
    return updated_count


async def update_pricing_only(
    db: AsyncSession, supplier_id: UUID, pricing: list[PSPricePoint]
) -> int:
    """Updates only the base_price on existing variants."""
    updated_count = 0
    for item in pricing:
        stmt = (
            select(ProductVariant)
            .join(Product)
            .where(Product.supplier_id == supplier_id)
            .where(ProductVariant.sku == item.part_id)
        )
        res = await db.execute(stmt)
        variant = res.scalar_one_or_none()
        
        if variant:
            variant.base_price = item.price
            updated_count += 1
            
        if updated_count % 100 == 0:
            await db.commit()
            
    await db.commit()
    return updated_count
