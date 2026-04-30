"""Pricing API — apparel resolver + endpoint."""
from __future__ import annotations

from decimal import Decimal

import pytest


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
