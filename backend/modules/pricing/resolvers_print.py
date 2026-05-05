"""Print pricing — base_price_per_sq_unit * width * height.

Formula may also be stored in print_details.raw_payload as:
  {"base": "1.50", "area_factor": "0.04", "base_setup": "0.00"}

When raw_payload.formula is present it takes precedence over base_price_per_sq_unit.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import PrintDetails, Product

from .errors import BoundsError, MissingPricingDataError
from .resolvers import to_cents
from .schemas import OptionMultiplierTrace, PrintBreakdown, QuoteRequest, QuoteResult


class FormulaResolver:
    async def resolve(
        self, req: QuoteRequest, product: Product, db: AsyncSession
    ) -> QuoteResult:
        details = await db.get(PrintDetails, product.id)
        if details is None:
            raise MissingPricingDataError(
                f"Print product {product.id} has no print_details"
            )

        if req.width is None:
            raise BoundsError("width is required for print products")
        if req.height is None:
            raise BoundsError("height is required for print products")

        self._check_bounds(req.width, req.height, details)

        # Formula: prefer raw_payload formula dict, fall back to base_price_per_sq_unit
        formula = (details.raw_payload or {}).get("formula") if details.raw_payload else None

        if formula:
            base = Decimal(str(formula.get("base", "0")))
            area_factor = Decimal(str(formula.get("area_factor", "1")))
            base_setup = Decimal(str(formula.get("base_setup", "0")))
        elif details.base_price_per_sq_unit is not None:
            base = Decimal(details.base_price_per_sq_unit)
            area_factor = Decimal("1")
            base_setup = Decimal("0")
        else:
            raise MissingPricingDataError(
                f"Print product {product.id} has no formula or base_price_per_sq_unit"
            )

        area = req.width * req.height
        unit = base * area * area_factor
        unit_price = to_cents(unit)

        total = to_cents(unit_price * Decimal(req.qty) + base_setup)

        return QuoteResult(
            unit_price=unit_price,
            total=total,
            currency="USD",
            breakdown=PrintBreakdown(
                base=to_cents(base),
                area=area,
                area_factor=area_factor,
                option_multipliers=[],
                setup_cost=to_cents(base_setup),
                qty=req.qty,
            ),
        )

    def _check_bounds(
        self, width: Decimal, height: Decimal, details: PrintDetails
    ) -> None:
        if details.min_width is not None and width < Decimal(details.min_width):
            raise BoundsError(f"width {width} below minimum {details.min_width}")
        if details.max_width is not None and width > Decimal(details.max_width):
            raise BoundsError(f"width {width} above maximum {details.max_width}")
        if details.min_height is not None and height < Decimal(details.min_height):
            raise BoundsError(f"height {height} below minimum {details.min_height}")
        if details.max_height is not None and height > Decimal(details.max_height):
            raise BoundsError(f"height {height} above maximum {details.max_height}")
