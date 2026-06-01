"""Customer-facing quote: resolve base price then apply markup + storefront overrides."""
from __future__ import annotations

import math
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.customers.models import Customer
from modules.markup.engine import apply_markup, resolve_rule
from modules.markup.models import MarkupRule

from .errors import MissingPricingDataError
from .resolvers import load_product, resolve_quote_for_product, to_cents
from .schemas import CustomerQuoteResult, QuoteRequest, QuoteResult


async def resolve_customer_quote(
    req: QuoteRequest,
    customer_id: UUID,
    db: AsyncSession,
) -> CustomerQuoteResult:
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise MissingPricingDataError(f"Customer {customer_id} not found")

    # Load product once — reused for both pricing and markup rule lookup (M3).
    product = await load_product(req.product_id, db)
    base_result: QuoteResult = await resolve_quote_for_product(req, product, db)

    rules = (
        await db.execute(
            select(MarkupRule).where(MarkupRule.customer_id == customer_id)
        )
    ).scalars().all()

    # Derive supplier slug so `supplier:{slug}`-scoped rules resolve here too.
    # Without this, supplier-scoped rules match in the push payload
    # (markup/engine.calculate_price passes supplier_slug) but were silently
    # ignored in the customer quote — making the two pricing paths disagree.
    from modules.suppliers.models import Supplier
    supplier = await db.get(Supplier, product.supplier_id)
    supplier_slug = supplier.slug if supplier else None

    rule = resolve_rule(rules, product.supplier_sku, product.category, supplier_slug)

    marked_up_unit = apply_markup(base_result.unit_price, rule)

    final_unit, override_applied = await _apply_storefront_override(
        req.product_id, customer_id, marked_up_unit, db
    )

    unit_price = to_cents(final_unit)
    total = to_cents(unit_price * Decimal(req.qty))

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

    All rounding uses to_cents (ROUND_HALF_UP) for consistency with the
    rest of the pricing pipeline (M2).
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
        return to_cents(Decimal(str(overrides["fixed_unit_price"]))), True

    if "extra_markup_pct" in overrides:
        pct = Decimal(str(overrides["extra_markup_pct"]))
        new_unit = new_unit * (Decimal("1") + pct / Decimal("100"))

    rounding = overrides.get("rounding")
    if rounding == "nearest_99":
        new_unit = Decimal(math.floor(new_unit)) + Decimal("0.99")
    elif rounding == "nearest_dollar":
        # Use to_cents-compatible rounding, not Python's banker rounding (M2).
        new_unit = Decimal(math.floor(new_unit + Decimal("0.5")))

    return new_unit, True
