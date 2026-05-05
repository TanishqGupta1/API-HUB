"""Pricing API — print formula resolver + bounds."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import delete


@pytest.mark.asyncio
async def test_print_resolver_evaluates_formula(db, seed_supplier):
    """24x36 print: base=1.50, area_factor=0.04 => unit=1.50*864*0.04=51.84."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, PrintDetailsIngest
    from modules.catalog.models import Product
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import PrintBreakdown, QuoteRequest
    from database import async_session

    payload = ProductIngest(
        supplier_sku="PRINT-FORMULA",
        product_name="Decal - Formula Test",
        product_type="print",
        print_details=PrintDetailsIngest(
            min_width=Decimal("1"),
            max_width=Decimal("96"),
            min_height=Decimal("1"),
            max_height=Decimal("96"),
            raw_payload={"formula": {"base": "1.50", "area_factor": "0.04", "base_setup": "0"}},
        ),
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        await s.commit()

    async with async_session() as s:
        result = await resolve_quote(
            QuoteRequest(product_id=pid, width=Decimal("24"), height=Decimal("36"), qty=10),
            s,
        )

    # area=864, unit=1.50*864*0.04=51.84, total=51.84*10=518.40
    assert result.unit_price == Decimal("51.84")
    assert result.total == Decimal("518.40")
    assert isinstance(result.breakdown, PrintBreakdown)
    assert result.breakdown.area == Decimal("864")
    assert result.breakdown.area_factor == Decimal("0.04")

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_print_resolver_uses_base_price_per_sq_unit(db, seed_supplier):
    """Falls back to base_price_per_sq_unit when no formula in raw_payload."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, PrintDetailsIngest
    from modules.catalog.models import Product
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session

    payload = ProductIngest(
        supplier_sku="PRINT-SQUNIT",
        product_name="Banner - Sq Unit",
        product_type="print",
        print_details=PrintDetailsIngest(
            min_width=Decimal("1"),
            max_width=Decimal("96"),
            min_height=Decimal("1"),
            max_height=Decimal("96"),
            base_price_per_sq_unit=Decimal("0.50"),
        ),
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        await s.commit()

    async with async_session() as s:
        result = await resolve_quote(
            QuoteRequest(product_id=pid, width=Decimal("10"), height=Decimal("10"), qty=2),
            s,
        )
    # area=100, unit=0.50*100*1=50.00, total=50.00*2=100.00
    assert result.unit_price == Decimal("50.00")
    assert result.total == Decimal("100.00")

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_print_resolver_rejects_dimension_below_bounds(db, seed_supplier):
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, PrintDetailsIngest
    from modules.catalog.models import Product
    from modules.pricing.errors import BoundsError
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session

    payload = ProductIngest(
        supplier_sku="BOUNDS-1",
        product_name="bounded decal",
        product_type="print",
        print_details=PrintDetailsIngest(
            min_width=Decimal("1"),
            max_width=Decimal("96"),
            min_height=Decimal("1"),
            max_height=Decimal("96"),
            base_price_per_sq_unit=Decimal("0.10"),
        ),
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        await s.commit()

    async with async_session() as s:
        with pytest.raises(BoundsError, match="width"):
            await resolve_quote(QuoteRequest(product_id=pid, width=Decimal("0.5"), height=Decimal("10"), qty=1), s)
        with pytest.raises(BoundsError, match="height"):
            await resolve_quote(QuoteRequest(product_id=pid, width=Decimal("10"), height=Decimal("999"), qty=1), s)
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_print_resolver_requires_dimensions(db, seed_supplier):
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, PrintDetailsIngest
    from modules.catalog.models import Product
    from modules.pricing.errors import BoundsError
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session

    payload = ProductIngest(
        supplier_sku="NEED-DIMS",
        product_name="needs dims",
        product_type="print",
        print_details=PrintDetailsIngest(base_price_per_sq_unit=Decimal("0.10")),
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        await s.commit()

    async with async_session() as s:
        with pytest.raises(BoundsError, match="width"):
            await resolve_quote(QuoteRequest(product_id=pid, qty=1), s)
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_print_resolver_missing_pricing_data_errors(db, seed_supplier):
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, PrintDetailsIngest
    from modules.catalog.models import Product
    from modules.pricing.errors import MissingPricingDataError
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session

    payload = ProductIngest(
        supplier_sku="NO-PRICE",
        product_name="no price",
        product_type="print",
        print_details=PrintDetailsIngest(),  # no formula, no base_price_per_sq_unit
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        await s.commit()

    async with async_session() as s:
        with pytest.raises(MissingPricingDataError):
            await resolve_quote(QuoteRequest(product_id=pid, width=Decimal("1"), height=Decimal("1"), qty=1), s)
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()
