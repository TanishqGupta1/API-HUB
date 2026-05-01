"""Pricing API request/response models.

`QuoteRequest` is shared by both apparel and print paths; resolvers ignore
fields they do not consume. The endpoint validates only what Pydantic can
check from the body in isolation (qty > 0, dimensions are non-negative).
Cross-field validation (variant exists, dimensions in bounds, etc.) lives
in the resolver against the database.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    variant_id: Optional[UUID] = None
    width: Optional[Decimal] = Field(default=None, ge=0)
    height: Optional[Decimal] = Field(default=None, ge=0)
    qty: int = Field(gt=0)
    selected_attribute_ids: list[UUID] = Field(default_factory=list)


class TierMatch(BaseModel):
    group: str
    qty_band: str
    tier_price: Decimal


class OptionMultiplierTrace(BaseModel):
    option_key: str
    attribute_key: Optional[str] = None
    multiplier: Decimal


class ApparelBreakdown(BaseModel):
    base: Decimal
    tier_match: Optional[TierMatch] = None
    qty: int
    fallback: bool = False


class PrintBreakdown(BaseModel):
    base: Decimal
    area: Decimal
    area_factor: Decimal
    option_multipliers: list[OptionMultiplierTrace] = Field(default_factory=list)
    setup_cost: Decimal = Decimal("0")
    qty: int


class QuoteResult(BaseModel):
    unit_price: Decimal
    total: Decimal
    currency: str = "USD"
    breakdown: ApparelBreakdown | PrintBreakdown


class CustomerQuoteResult(QuoteResult):
    """Quote with markup + storefront overrides applied on top of the base."""
    base_unit_price: Decimal
    markup_pct: Optional[Decimal] = None
    rounding: Optional[str] = None
    storefront_override_applied: bool = False
