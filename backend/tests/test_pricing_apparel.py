"""Pricing API — apparel resolver + endpoint."""
from __future__ import annotations

from decimal import Decimal

import pytest


@pytest.mark.asyncio
async def test_apparel_quote_quantizes_to_two_decimals(db, seed_supplier):
    """Tier price 3.337 -> rounds to 3.34; total 3.34 * 3 = 10.02."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, VariantIngest, VariantPriceIngest, ApparelDetailsIngest
    from modules.catalog.models import Product, ProductVariant
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session
    from sqlalchemy import select, delete

    payload = ProductIngest(
        supplier_sku="QUANT-1",
        product_name="quant",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="QV1",
                color="B",
                size="M",
                base_price=Decimal("3.337"),
                prices=[
                    VariantPriceIngest(price_type="Net", quantity_min=1, quantity_max=2147483647, price=Decimal("3.337")),
                ],
            ),
        ],
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        await s.commit()
        vid = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()

    async with async_session() as s:
        result = await resolve_quote(
            QuoteRequest(product_id=pid, variant_id=vid, qty=3), s
        )
        assert result.unit_price == Decimal("3.34")
        assert result.total == Decimal("10.02")

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_apparel_resolver_currency_passthrough(db, seed_supplier):
    """Response always includes currency=USD."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, VariantIngest, VariantPriceIngest, ApparelDetailsIngest
    from modules.catalog.models import Product, ProductVariant
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session
    from sqlalchemy import select, delete

    payload = ProductIngest(
        supplier_sku="CUR-1",
        product_name="cur",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="CURV1",
                color="W",
                size="S",
                base_price=Decimal("9.99"),
                prices=[
                    VariantPriceIngest(price_type="Net", quantity_min=1, quantity_max=2147483647, price=Decimal("9.99")),
                ],
            ),
        ],
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        await s.commit()
        vid = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()

    async with async_session() as s:
        result = await resolve_quote(
            QuoteRequest(product_id=pid, variant_id=vid, qty=1), s
        )
        assert result.currency == "USD"

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


def test_quote_request_accepts_apparel_payload():
    from modules.pricing.schemas import QuoteRequest

    req = QuoteRequest(
        product_id="00000000-0000-0000-0000-000000000001",
        variant_id="00000000-0000-0000-0000-000000000002",
        qty=50,
    )
    assert req.qty == 50
    assert req.variant_id is not None


def test_quote_request_accepts_print_payload():
    from modules.pricing.schemas import QuoteRequest

    req = QuoteRequest(
        product_id="00000000-0000-0000-0000-000000000001",
        width=Decimal("24"),
        height=Decimal("36"),
        qty=10,
        selected_attribute_ids=["00000000-0000-0000-0000-000000000003"],
    )
    assert req.width == Decimal("24")
    assert req.height == Decimal("36")
    from uuid import UUID
    assert req.selected_attribute_ids == [UUID("00000000-0000-0000-0000-000000000003")]


def test_quote_request_rejects_zero_qty():
    from pydantic import ValidationError
    from modules.pricing.schemas import QuoteRequest
    with pytest.raises(ValidationError):
        QuoteRequest(product_id="00000000-0000-0000-0000-000000000001", qty=0)


def test_pricing_errors_are_distinct():
    from modules.pricing.errors import (
        BoundsError,
        MissingPricingDataError,
        PricingError,
    )
    assert issubclass(BoundsError, PricingError)
    assert issubclass(MissingPricingDataError, PricingError)
    assert BoundsError is not MissingPricingDataError


@pytest.mark.asyncio
async def test_resolve_quote_dispatches_by_pricing_method(db, seed_supplier):
    """Unknown pricing_method raises MissingPricingDataError."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ApparelDetailsIngest, ProductIngest
    from modules.pricing.errors import MissingPricingDataError
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session
    import sqlalchemy

    payload = ProductIngest(
        supplier_sku="DISPATCH-1",
        product_name="dispatch test",
        product_type="embroidery",   # unknown type — no resolver
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        await s.commit()

    async with async_session() as s:
        with pytest.raises(MissingPricingDataError, match="pricing_method"):
            await resolve_quote(QuoteRequest(product_id=pid, qty=1), s)
        from modules.catalog.models import Product
        await s.execute(sqlalchemy.delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_apparel_resolver_picks_tier_for_qty(db, seed_supplier):
    """qty=1 hits the qty_min=1 tier; qty=144 hits the higher-qty tier."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, VariantIngest, VariantPriceIngest, ApparelDetailsIngest
    from modules.catalog.models import Product, ProductVariant
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import ApparelBreakdown, QuoteRequest
    from database import async_session
    from sqlalchemy import select, delete

    payload = ProductIngest(
        supplier_sku="TIER-1",
        product_name="tiered apparel",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="V-TIER-1",
                color="Black",
                size="L",
                base_price=Decimal("8.00"),
                prices=[
                    VariantPriceIngest(price_type="Net", quantity_min=1, quantity_max=11, price=Decimal("12.50")),
                    VariantPriceIngest(price_type="Net", quantity_min=12, quantity_max=143, price=Decimal("11.00")),
                    VariantPriceIngest(price_type="Net", quantity_min=144, quantity_max=2147483647, price=Decimal("9.50")),
                ],
            ),
        ],
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        await s.commit()
        variant_id = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()

    async with async_session() as s:
        result1 = await resolve_quote(QuoteRequest(product_id=pid, variant_id=variant_id, qty=1), s)
        assert result1.unit_price == Decimal("12.50")
        assert result1.total == Decimal("12.50")
        assert isinstance(result1.breakdown, ApparelBreakdown)
        assert result1.breakdown.tier_match.group == "Net"
        assert result1.breakdown.tier_match.qty_band == "1-11"
        assert result1.breakdown.fallback is False

        result144 = await resolve_quote(QuoteRequest(product_id=pid, variant_id=variant_id, qty=144), s)
        assert result144.unit_price == Decimal("9.50")
        assert result144.total == Decimal("1368.00")
        assert result144.breakdown.tier_match.qty_band == "144-2147483647"

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_apparel_resolver_falls_back_to_base_price(db, seed_supplier):
    """No variant_prices rows -> falls back to variant.base_price."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, VariantIngest, ApparelDetailsIngest
    from modules.catalog.models import Product, ProductVariant
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session
    from sqlalchemy import select, delete

    payload = ProductIngest(
        supplier_sku="FALLBACK-1",
        product_name="fallback apparel",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(part_id="V-FB", color="White", size="M", base_price=Decimal("7.25"), prices=[]),
        ],
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        await s.commit()
        variant_id = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()

    async with async_session() as s:
        result = await resolve_quote(QuoteRequest(product_id=pid, variant_id=variant_id, qty=10), s)
        assert result.unit_price == Decimal("7.25")
        assert result.total == Decimal("72.50")
        assert result.breakdown.fallback is True
        assert result.breakdown.tier_match is None

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_apparel_resolver_requires_variant_id(db, seed_supplier):
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, ApparelDetailsIngest
    from modules.catalog.models import Product
    from modules.pricing.errors import MissingPricingDataError
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session
    from sqlalchemy import delete

    payload = ProductIngest(
        supplier_sku="NEED-VID",
        product_name="need variant",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest(),
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        await s.commit()

    async with async_session() as s:
        with pytest.raises(MissingPricingDataError, match="variant_id"):
            await resolve_quote(QuoteRequest(product_id=pid, qty=1), s)
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()
