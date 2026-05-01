"""Pricing resolvers — strategy per product.pricing_method.

`resolve_quote` is the single entry point. It loads the product, picks a
resolver, and returns a typed `QuoteResult`. Each resolver is responsible
for its own validation against the database (variant existence, bounds,
formula presence, etc.).

Internal helpers
----------------
to_cents     — shared rounding (ROUND_HALF_UP) used by all resolvers.
load_product — single DB fetch; callers that already have the product should
               use resolve_quote_for_product to avoid a second round-trip.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import Product

from .errors import MissingPricingDataError
from .schemas import QuoteRequest, QuoteResult

CENT = Decimal("0.01")


def to_cents(value: Decimal) -> Decimal:
    """Round to 2 decimal places using ROUND_HALF_UP (banker-rounding-free)."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


class BaseResolver(Protocol):
    async def resolve(
        self, req: QuoteRequest, product: Product, db: AsyncSession
    ) -> QuoteResult: ...


async def load_product(product_id: UUID, db: AsyncSession) -> Product:
    """Load a product by ID; raises MissingPricingDataError if not found."""
    product = await db.get(Product, product_id)
    if product is None:
        raise MissingPricingDataError(f"Product {product_id} not found")
    return product


async def resolve_quote_for_product(
    req: QuoteRequest, product: Product, db: AsyncSession
) -> QuoteResult:
    """Run the resolver for an already-loaded product (avoids re-fetching)."""
    resolver = _resolver_for(product)
    return await resolver.resolve(req, product, db)


async def resolve_quote(
    req: QuoteRequest, db: AsyncSession
) -> QuoteResult:
    product = await load_product(req.product_id, db)
    return await resolve_quote_for_product(req, product, db)


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
