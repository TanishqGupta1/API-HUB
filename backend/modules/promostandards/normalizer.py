"""Normalize parsed PromoStandards data into the canonical DB schema.

Three entry points:

- ``upsert_products`` — full catalog sync. Takes products (with parts), and
  optionally inventory/pricing/media. Upserts ``products``,
  ``product_variants``, and ``product_images``.
- ``update_inventory_only`` — cheap delta. Only touches
  ``product_variants.inventory`` / ``warehouse``.
- ``update_pricing_only`` — cheap delta. Only touches
  ``product_variants.base_price``.

All writes go through ``INSERT ... ON CONFLICT DO UPDATE`` so repeat syncs
are idempotent and don't leave stale rows behind.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import Product, ProductImage, ProductVariant

from .schemas import PSInventoryLevel, PSMediaItem, PSPricePoint, PSProductData

_BATCH_SIZE = 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunks(items: Sequence, size: int) -> Iterable[Sequence]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _pick_base_price(prices: list[PSPricePoint]) -> Decimal | None:
    """Pick the "piece" tier at quantity_min=1 if present, else the lowest."""
    if not prices:
        return None
    piece_tier = [p for p in prices if p.price_type == "piece" and p.quantity_min <= 1]
    chosen = piece_tier[0] if piece_tier else min(prices, key=lambda p: p.price)
    return Decimal(str(chosen.price))


# ---------------------------------------------------------------------------
# upsert_products — full sync
# ---------------------------------------------------------------------------

async def upsert_products(
    db: AsyncSession,
    supplier_id: UUID,
    products: list[PSProductData],
    inventory: list[PSInventoryLevel] | None = None,
    pricing: list[PSPricePoint] | None = None,
    media: list[PSMediaItem] | None = None,
) -> int:
    """Full upsert: products + variants + images.

    Returns the count of products processed. Inventory and pricing are folded
    into variants as they're written; media becomes ``product_images`` rows.
    """
    if not products:
        return 0

    inventory = inventory or []
    pricing = pricing or []
    media = media or []

    # Pre-index inventory/pricing by (product_id, part_id) for O(1) lookup
    # during variant construction.
    inv_index: dict[tuple[str, str], PSInventoryLevel] = {
        (i.product_id, i.part_id): i for i in inventory
    }
    price_index: dict[tuple[str, str], list[PSPricePoint]] = {}
    for p in pricing:
        price_index.setdefault((p.product_id, p.part_id), []).append(p)

    now = datetime.now(timezone.utc)
    sku_to_id: dict[str, UUID] = {}
    total = 0

    for batch in _chunks(products, _BATCH_SIZE):
        # --- products ----------------------------------------------------
        product_rows = [
            {
                "supplier_id": supplier_id,
                "supplier_sku": p.product_id,
                "product_name": p.product_name or p.product_id,
                "brand": p.brand,
                "category": p.categories[0] if p.categories else None,
                "description": p.description,
                "product_type": p.product_type or "apparel",
                "image_url": p.primary_image_url,
                "last_synced": now,
            }
            for p in batch
        ]
        stmt = (
            pg_insert(Product)
            .values(product_rows)
            .on_conflict_do_update(
                constraint="uq_product_supplier_sku",
                set_={
                    "product_name": pg_insert(Product).excluded.product_name,
                    "brand": pg_insert(Product).excluded.brand,
                    "category": pg_insert(Product).excluded.category,
                    "description": pg_insert(Product).excluded.description,
                    "product_type": pg_insert(Product).excluded.product_type,
                    "image_url": pg_insert(Product).excluded.image_url,
                    "last_synced": pg_insert(Product).excluded.last_synced,
                },
            )
            .returning(Product.id, Product.supplier_sku)
        )
        result = await db.execute(stmt)
        for row_id, row_sku in result.all():
            sku_to_id[row_sku] = row_id

        # --- variants ----------------------------------------------------
        variant_rows: list[dict] = []
        for p in batch:
            pid_db = sku_to_id.get(p.product_id)
            if not pid_db:
                continue
            for part in p.parts:
                inv = inv_index.get((p.product_id, part.part_id))
                prices = price_index.get((p.product_id, part.part_id), [])
                variant_rows.append(
                    {
                        "product_id": pid_db,
                        "color": part.color_name,
                        "size": part.size_name,
                        "sku": part.part_id,
                        "base_price": _pick_base_price(prices),
                        "inventory": inv.quantity_available if inv else None,
                        "warehouse": inv.warehouse_code if inv else None,
                    }
                )

        if variant_rows:
            for variant_batch in _chunks(variant_rows, _BATCH_SIZE):
                v_stmt = pg_insert(ProductVariant).values(list(variant_batch))
                v_stmt = v_stmt.on_conflict_do_update(
                    constraint="uq_variant_product_color_size",
                    set_={
                        "sku": v_stmt.excluded.sku,
                        "base_price": v_stmt.excluded.base_price,
                        "inventory": v_stmt.excluded.inventory,
                        "warehouse": v_stmt.excluded.warehouse,
                    },
                )
                await db.execute(v_stmt)

        # --- images ------------------------------------------------------
        image_rows: list[dict] = []
        for m in media:
            pid_db = sku_to_id.get(m.product_id)
            if not pid_db:
                continue
            image_rows.append(
                {
                    "product_id": pid_db,
                    "url": m.url,
                    "image_type": m.media_type or "front",
                    "color": m.color_name,
                    "sort_order": 0,
                }
            )
        if image_rows:
            for image_batch in _chunks(image_rows, _BATCH_SIZE):
                img_stmt = pg_insert(ProductImage).values(list(image_batch))
                img_stmt = img_stmt.on_conflict_do_update(
                    constraint="uq_product_image_url",
                    set_={
                        "image_type": img_stmt.excluded.image_type,
                        "color": img_stmt.excluded.color,
                    },
                )
                await db.execute(img_stmt)

        await db.commit()
        total += len(batch)

    return total


# ---------------------------------------------------------------------------
# update_inventory_only — cheap delta
# ---------------------------------------------------------------------------

async def update_inventory_only(
    db: AsyncSession,
    supplier_id: UUID,
    inventory: list[PSInventoryLevel],
) -> int:
    """Update ``inventory`` and ``warehouse`` on existing variants.

    No product rows created. Variants not already present are silently
    skipped — run a full sync first.
    """
    if not inventory:
        return 0

    # Build a supplier_sku → product_id map in one query.
    skus = list({i.product_id for i in inventory})
    sku_rows = await db.execute(
        select(Product.id, Product.supplier_sku).where(
            Product.supplier_id == supplier_id,
            Product.supplier_sku.in_(skus),
        )
    )
    sku_to_id = {sku: pid for pid, sku in sku_rows.all()}
    if not sku_to_id:
        return 0

    total = 0
    for chunk in _chunks(inventory, _BATCH_SIZE):
        for level in chunk:
            pid_db = sku_to_id.get(level.product_id)
            if not pid_db:
                continue
            variant = (
                await db.execute(
                    select(ProductVariant).where(
                        ProductVariant.product_id == pid_db,
                        ProductVariant.sku == level.part_id,
                    )
                )
            ).scalar_one_or_none()
            if not variant:
                continue
            variant.inventory = level.quantity_available
            variant.warehouse = level.warehouse_code
            total += 1
        await db.commit()
    return total


# ---------------------------------------------------------------------------
# update_pricing_only — cheap delta
# ---------------------------------------------------------------------------

async def update_pricing_only(
    db: AsyncSession,
    supplier_id: UUID,
    pricing: list[PSPricePoint],
) -> int:
    """Update ``base_price`` on existing variants."""
    if not pricing:
        return 0

    # Group price points per (product_id, part_id) so we pick one base price
    # per variant instead of overwriting N times.
    grouped: dict[tuple[str, str], list[PSPricePoint]] = {}
    for p in pricing:
        grouped.setdefault((p.product_id, p.part_id), []).append(p)

    skus = list({pid for pid, _ in grouped})
    sku_rows = await db.execute(
        select(Product.id, Product.supplier_sku).where(
            Product.supplier_id == supplier_id,
            Product.supplier_sku.in_(skus),
        )
    )
    sku_to_id = {sku: pid for pid, sku in sku_rows.all()}
    if not sku_to_id:
        return 0

    total = 0
    items = list(grouped.items())
    for chunk in _chunks(items, _BATCH_SIZE):
        for (product_id, part_id), prices in chunk:
            pid_db = sku_to_id.get(product_id)
            if not pid_db:
                continue
            variant = (
                await db.execute(
                    select(ProductVariant).where(
                        ProductVariant.product_id == pid_db,
                        ProductVariant.sku == part_id,
                    )
                )
            ).scalar_one_or_none()
            if not variant:
                continue
            variant.base_price = _pick_base_price(prices)
            total += 1
        await db.commit()
    return total
