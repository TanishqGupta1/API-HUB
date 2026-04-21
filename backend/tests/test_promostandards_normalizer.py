"""Integration tests for the PromoStandards normalizer.

Hits the configured Postgres (docker compose up postgres). Each test creates
its own supplier via the ``seed_supplier`` fixture and cleanup runs between
tests, so repeat runs don't accumulate rows.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from database import async_session
from modules.catalog.models import Product, ProductImage, ProductVariant
from modules.promostandards.normalizer import (
    update_inventory_only,
    update_pricing_only,
    upsert_products,
)
from modules.promostandards.schemas import (
    PSInventoryLevel,
    PSMediaItem,
    PSPricePoint,
    PSProductData,
    PSProductPart,
)

pytestmark = pytest.mark.asyncio


def _sample_product(product_id: str = "PC61") -> PSProductData:
    return PSProductData(
        product_id=product_id,
        product_name="Essential Tee",
        brand="Port & Company",
        categories=["T-Shirts"],
        description="100% cotton",
        primary_image_url="https://img.example.com/pc61.jpg",
        parts=[
            PSProductPart(part_id=f"{product_id}-NVY-M", color_name="Navy", size_name="M"),
            PSProductPart(part_id=f"{product_id}-NVY-L", color_name="Navy", size_name="L"),
        ],
    )


async def _count(cls, filter_by):
    async with async_session() as s:
        rows = (await s.execute(select(cls).filter_by(**filter_by))).scalars().all()
        return len(rows)


async def test_upsert_creates_products_variants_images(seed_supplier):
    async with async_session() as s:
        n = await upsert_products(
            s,
            seed_supplier.id,
            [_sample_product("PC61")],
            inventory=[
                PSInventoryLevel(
                    product_id="PC61", part_id="PC61-NVY-M",
                    quantity_available=120, warehouse_code="Seattle",
                ),
            ],
            pricing=[
                PSPricePoint(
                    product_id="PC61", part_id="PC61-NVY-M",
                    price=3.99, quantity_min=1, price_type="piece",
                ),
            ],
            media=[
                PSMediaItem(product_id="PC61", url="https://img.example.com/pc61-front.jpg"),
            ],
        )
    assert n == 1

    async with async_session() as s:
        product = (
            await s.execute(
                select(Product).where(
                    Product.supplier_id == seed_supplier.id,
                    Product.supplier_sku == "PC61",
                )
            )
        ).scalar_one()
        assert product.product_name == "Essential Tee"
        assert product.brand == "Port & Company"
        assert product.category == "T-Shirts"
        assert product.last_synced is not None

        variants = (
            await s.execute(
                select(ProductVariant).where(ProductVariant.product_id == product.id)
            )
        ).scalars().all()
        by_size = {v.size: v for v in variants}
        assert set(by_size) == {"M", "L"}
        assert by_size["M"].inventory == 120
        assert by_size["M"].warehouse == "Seattle"
        assert by_size["M"].base_price == Decimal("3.99")
        # L has no inventory/pricing rows → fields stay None.
        assert by_size["L"].inventory is None
        assert by_size["L"].base_price is None

        images = (
            await s.execute(
                select(ProductImage).where(ProductImage.product_id == product.id)
            )
        ).scalars().all()
        assert len(images) == 1
        assert images[0].url == "https://img.example.com/pc61-front.jpg"


async def test_upsert_is_idempotent(seed_supplier):
    payload = [_sample_product("PC90H")]
    async with async_session() as s:
        await upsert_products(s, seed_supplier.id, payload)
    async with async_session() as s:
        await upsert_products(s, seed_supplier.id, payload)

    assert await _count(Product, {"supplier_id": seed_supplier.id}) == 1

    async with async_session() as s:
        product_id = (
            await s.execute(
                select(Product.id).where(
                    Product.supplier_id == seed_supplier.id,
                    Product.supplier_sku == "PC90H",
                )
            )
        ).scalar_one()
    assert await _count(ProductVariant, {"product_id": product_id}) == 2


async def test_upsert_updates_existing_row(seed_supplier):
    async with async_session() as s:
        await upsert_products(s, seed_supplier.id, [_sample_product("PC61")])

    updated = _sample_product("PC61")
    updated.product_name = "Essential Tee (renamed)"
    updated.brand = "PortCo"
    async with async_session() as s:
        await upsert_products(s, seed_supplier.id, [updated])

    async with async_session() as s:
        product = (
            await s.execute(
                select(Product).where(
                    Product.supplier_id == seed_supplier.id,
                    Product.supplier_sku == "PC61",
                )
            )
        ).scalar_one()
        assert product.product_name == "Essential Tee (renamed)"
        assert product.brand == "PortCo"


async def test_update_inventory_only_touches_only_inventory(seed_supplier):
    async with async_session() as s:
        await upsert_products(
            s,
            seed_supplier.id,
            [_sample_product("PC61")],
            pricing=[
                PSPricePoint(
                    product_id="PC61", part_id="PC61-NVY-M",
                    price=3.99, quantity_min=1, price_type="piece",
                )
            ],
        )

    async with async_session() as s:
        updated = await update_inventory_only(
            s,
            seed_supplier.id,
            [
                PSInventoryLevel(
                    product_id="PC61", part_id="PC61-NVY-M",
                    quantity_available=42, warehouse_code="Reno",
                )
            ],
        )
    assert updated == 1

    async with async_session() as s:
        variant = (
            await s.execute(
                select(ProductVariant).where(ProductVariant.sku == "PC61-NVY-M")
            )
        ).scalar_one()
        assert variant.inventory == 42
        assert variant.warehouse == "Reno"
        # Pricing from the full sync must survive the inventory-only update.
        assert variant.base_price == Decimal("3.99")


async def test_update_pricing_only_picks_piece_tier(seed_supplier):
    async with async_session() as s:
        await upsert_products(s, seed_supplier.id, [_sample_product("PC61")])

    async with async_session() as s:
        updated = await update_pricing_only(
            s,
            seed_supplier.id,
            [
                # Not the piece tier — higher qty, but only qty tier present.
                PSPricePoint(
                    product_id="PC61", part_id="PC61-NVY-M",
                    price=2.50, quantity_min=48, price_type="piece",
                ),
                PSPricePoint(
                    product_id="PC61", part_id="PC61-NVY-M",
                    price=3.99, quantity_min=1, price_type="piece",
                ),
            ],
        )
    assert updated == 1

    async with async_session() as s:
        variant = (
            await s.execute(
                select(ProductVariant).where(ProductVariant.sku == "PC61-NVY-M")
            )
        ).scalar_one()
        # piece @ quantity_min=1 wins over the 48-pack tier.
        assert variant.base_price == Decimal("3.99")


async def test_update_inventory_skips_unknown_parts(seed_supplier):
    # No products seeded for this supplier — inventory should be skipped cleanly.
    async with async_session() as s:
        updated = await update_inventory_only(
            s,
            seed_supplier.id,
            [
                PSInventoryLevel(
                    product_id="UNKNOWN", part_id="UNKNOWN-M",
                    quantity_available=1,
                )
            ],
        )
    assert updated == 0
