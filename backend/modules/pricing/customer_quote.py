"""Customer-facing quote: resolve base price then apply markup + storefront overrides."""
from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.markup.engine import apply_markup, resolve_rule
from modules.markup.models import MarkupRule
from modules.catalog.models import Product

from .errors import MissingPricingDataError
from .resolvers import _to_cents, resolve_quote
from .schemas import CustomerQuoteResult, QuoteRequest, QuoteResult

CENT = Decimal("0.01")


async def resolve_customer_quote(
    req: QuoteRequest,
    customer_id: UUID,
    db: AsyncSession,
) -> CustomerQuoteResult:
    base_result: QuoteResult = await resolve_quote(req, db)

    product = await db.get(Product, req.product_id)
    if product is None:
        raise MissingPricingDataError(f"Product {req.product_id} not found")

    rules = (
        await db.execute(
            select(MarkupRule).where(MarkupRule.customer_id == customer_id)
        )
    ).scalars().all()
    rule = resolve_rule(rules, product.supplier_sku, product.category)

    marked_up_unit = apply_markup(base_result.unit_price, rule)

    final_unit, override_applied = await _apply_storefront_override(
        req.product_id, customer_id, marked_up_unit, db
    )

    unit_price = _to_cents(final_unit)
    total = _to_cents(unit_price * Decimal(req.qty))

    return CustomerQuoteResult(
        unit_price=unit_price,
        total=total,
        currency=base_result.currency,
        breakdown=base_result.breakdown,
        base_unit_price=base_result.unit_price,
        markup_pct=Decimal(str(rule.markup_pct)) if rule else None,
        rounding=rule.rounding if rule else None,
        storefront_override_applied=override_applied,
    )


async def _apply_storefront_override(
    product_id: UUID,
    customer_id: UUID,
    current_unit: Decimal,
    db: AsyncSession,
) -> tuple[Decimal, bool]:
    """Apply pricing_overrides from product_storefront_configs.

    Supported keys:
      - "fixed_unit_price": str  — replaces price entirely
      - "extra_markup_pct": str  — additional % on top of marked-up price
      - "rounding": "nearest_99" | "nearest_dollar" | "none"
    """
    from modules.ops_config.models import ProductStorefrontConfig

    cfg = (await db.execute(
        select(ProductStorefrontConfig).where(
            ProductStorefrontConfig.product_id == product_id,
            ProductStorefrontConfig.customer_id == customer_id,
        )
    )).scalar_one_or_none()

    if cfg is None or not cfg.pricing_overrides:
        return current_unit, False

    overrides = cfg.pricing_overrides
    new_unit = current_unit

    if "fixed_unit_price" in overrides:
        return Decimal(str(overrides["fixed_unit_price"])), True

    if "extra_markup_pct" in overrides:
        pct = Decimal(str(overrides["extra_markup_pct"]))
        new_unit = new_unit * (Decimal("1") + pct / Decimal("100"))

    rounding = overrides.get("rounding")
    if rounding == "nearest_99":
        new_unit = Decimal(math.floor(new_unit)) + Decimal("0.99")
    elif rounding == "nearest_dollar":
        new_unit = Decimal(round(new_unit))

    return new_unit, True
