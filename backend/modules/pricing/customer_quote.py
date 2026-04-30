"""Customer-facing quote: resolve base price then apply markup rules."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.markup.engine import apply_markup, resolve_rule
from modules.markup.models import MarkupRule
from modules.catalog.models import Product

from .errors import MissingPricingDataError
from .resolvers import resolve_quote
from .schemas import CustomerQuoteResult, QuoteRequest, QuoteResult


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
    marked_up_total = (marked_up_unit * Decimal(req.qty)).quantize(
        Decimal("0.01")
    )

    return CustomerQuoteResult(
        unit_price=marked_up_unit,
        total=marked_up_total,
        currency=base_result.currency,
        breakdown=base_result.breakdown,
        base_unit_price=base_result.unit_price,
        markup_pct=Decimal(str(rule.markup_pct)) if rule else None,
        rounding=rule.rounding if rule else None,
        storefront_override_applied=False,
    )
