"""Shared pure-math helper for storefront pricing_overrides.

Both the customer-quote path (`pricing/customer_quote.py`) and the push
payload-build path (`ops_push/payload_builder.py`) must apply the same
overrides — otherwise a customer can be quoted one price and have a
different price pushed to OPS.

This module contains *only* the math on an already-loaded ``overrides``
dict. The DB lookup of ``ProductStorefrontConfig`` stays in each caller
so the push path can reuse its already-loaded context without a second
query.

Supported keys (mirrors the quote-side contract in
``_apply_storefront_override``):
  - ``fixed_unit_price``  : str — replaces price entirely (short-circuits)
  - ``extra_markup_pct``  : str — additional % on top of marked-up price
  - ``rounding``          : ``nearest_99`` | ``nearest_dollar`` | ``none``
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Mapping, Optional


def apply_pricing_overrides(
    current_unit: Decimal,
    overrides: Optional[Mapping[str, object]],
) -> tuple[Decimal, bool]:
    """Apply storefront pricing_overrides to a unit price.

    Returns the (possibly-adjusted) unit price and a flag indicating
    whether any override applied. Callers are responsible for the final
    ``to_cents`` rounding step so this stays pure and unit-test friendly.
    """
    if not overrides:
        return current_unit, False

    if "fixed_unit_price" in overrides:
        return Decimal(str(overrides["fixed_unit_price"])), True

    new_unit = current_unit
    applied = False

    if "extra_markup_pct" in overrides:
        pct = Decimal(str(overrides["extra_markup_pct"]))
        new_unit = new_unit * (Decimal("1") + pct / Decimal("100"))
        applied = True

    rounding = overrides.get("rounding")
    if rounding == "nearest_99":
        new_unit = Decimal(math.floor(new_unit)) + Decimal("0.99")
        applied = True
    elif rounding == "nearest_dollar":
        # Match the quote path: floor(x + 0.5), not Python's banker rounding.
        new_unit = Decimal(math.floor(new_unit + Decimal("0.5")))
        applied = True

    return new_unit, applied
