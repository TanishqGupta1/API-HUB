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
