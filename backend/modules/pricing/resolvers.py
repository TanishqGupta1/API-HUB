"""Pricing resolvers — strategy per product.pricing_method.

`resolve_quote` is the single entry point. It loads the product, picks a
resolver, and returns a typed `QuoteResult`. Each resolver is responsible
for its own validation against the database (variant existence, bounds,
formula presence, etc.).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import Product

from .errors import MissingPricingDataError
from .schemas import QuoteRequest, QuoteResult

CENT = Decimal("0.01")


def _to_cents(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


class BaseResolver(Protocol):
    async def resolve(
        self, req: QuoteRequest, product: Product, db: AsyncSession
    ) -> QuoteResult: ...


async def resolve_quote(
    req: QuoteRequest, db: AsyncSession
) -> QuoteResult:
    product = await db.get(Product, req.product_id)
    if product is None:
        raise MissingPricingDataError(f"Product {req.product_id} not found")
    resolver = _resolver_for(product)
    return await resolver.resolve(req, product, db)


def _resolver_for(product: Product) -> BaseResolver:
    # pricing_method lives on the detail tables; dispatch by product_type
    product_type = product.product_type
    if product_type == "apparel":
        from .resolvers_apparel import TieredVariantResolver
        return TieredVariantResolver()
    if product_type == "print":
        from .resolvers_print import FormulaResolver
        return FormulaResolver()
    raise MissingPricingDataError(
        f"product.pricing_method={product_type!r} has no resolver"
    )
