"""Apparel pricing — variant_prices tier lookup with base_price fallback."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import Product, ProductVariant, VariantPrice

from .errors import MissingPricingDataError
from .resolvers import to_cents
from .schemas import (
    ApparelBreakdown,
    QuoteRequest,
    QuoteResult,
    TierMatch,
)


class TieredVariantResolver:
    async def resolve(
        self, req: QuoteRequest, product: Product, db: AsyncSession
    ) -> QuoteResult:
        if req.variant_id is None:
            raise MissingPricingDataError(
                "apparel quote requires variant_id"
            )

        variant = await db.get(ProductVariant, req.variant_id)
        if variant is None or variant.product_id != product.id:
            raise MissingPricingDataError(
                f"Variant {req.variant_id} not found on product {product.id}"
            )

        tier = await self._best_tier(variant.id, req.qty, db)
        base = Decimal(variant.base_price) if variant.base_price is not None else None

        if tier is not None:
            unit_price = to_cents(tier.price)
            qty_max_str = str(tier.quantity_max) if tier.quantity_max is not None else "∞"
            tier_match = TierMatch(
                group=tier.price_type,
                qty_band=f"{tier.quantity_min}-{qty_max_str}",
                tier_price=unit_price,
            )
            fallback = False
        elif base is not None:
            unit_price = to_cents(base)
            tier_match = None
            fallback = True
        else:
            raise MissingPricingDataError(
                f"Variant {variant.id} has no variant_prices and no base_price"
            )

        total = to_cents(unit_price * Decimal(req.qty))
        return QuoteResult(
            unit_price=unit_price,
            total=total,
            currency="USD",
            breakdown=ApparelBreakdown(
                base=to_cents(base) if base is not None else unit_price,
                tier_match=tier_match,
                qty=req.qty,
                fallback=fallback,
            ),
        )

    async def _best_tier(
        self, variant_id, qty: int, db: AsyncSession
    ) -> VariantPrice | None:
        """Return the tier whose [quantity_min, quantity_max] band contains qty.

        When multiple tiers match (e.g. MSRP + Net), prefer Net > Sale > MSRP > Case.
        """
        rows = (await db.execute(
            select(VariantPrice).where(
                VariantPrice.variant_id == variant_id,
                VariantPrice.quantity_min <= qty,
            ).where(
                (VariantPrice.quantity_max == None) |  # noqa: E711
                (VariantPrice.quantity_max >= qty)
            )
        )).scalars().all()
        if not rows:
            return None

        priority = {"Net": 0, "Sale": 1, "MSRP": 2, "Case": 3}
        rows = sorted(rows, key=lambda r: (priority.get(r.price_type, 99), r.price_type))
        return rows[0]
