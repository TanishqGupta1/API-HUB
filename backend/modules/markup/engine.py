"""Markup rule resolution + price calculation.

Scope/precedence (most-specific wins; within a tier, higher priority wins):
  1. scope = "product:{supplier_sku}"  — product-level override
  2. scope = "category:{category}"     — category-level override
  3. scope = "all"                     — customer-wide default
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.catalog.models import Product
from modules.customers.models import Customer

from .models import MarkupRule

HUNDRED = Decimal("100")
CENT = Decimal("0.01")


def resolve_rule(
    rules: Iterable[Any],
    supplier_sku: str,
    category: Optional[str],
) -> Optional[Any]:
    """Return the best-matching rule for this product, or None if no rule applies."""
    rules = list(rules)
    product_scope = f"product:{supplier_sku}"
    category_scope = f"category:{category}" if category else None

    def best(scope: str) -> Optional[Any]:
        candidates = [r for r in rules if r.scope == scope]
        return max(candidates, key=lambda r: r.priority) if candidates else None

    return (
        best(product_scope)
        or (best(category_scope) if category_scope else None)
        or best("all")
    )


def apply_markup(base_price: Optional[Decimal], rule: Optional[Any]) -> Optional[Decimal]:
    """Apply a markup rule to a base price. Returns base_price unchanged if no rule."""
    if base_price is None:
        return None
    if rule is None:
        return Decimal(base_price).quantize(CENT, rounding=ROUND_HALF_UP)

    # str() coercion keeps float→Decimal round-trips exact (avoids Decimal(0.1))
    base = Decimal(str(base_price))
    markup_pct = Decimal(str(rule.markup_pct))
    price = base * (Decimal("1") + markup_pct / HUNDRED)

    if rule.min_margin is not None:
        min_margin = Decimal(str(rule.min_margin))
        floor_price = base * (Decimal("1") + min_margin / HUNDRED)
        if price < floor_price:
            price = floor_price

    if rule.rounding == "nearest_99":
        price = Decimal(math.floor(price)) + Decimal("0.99")
    elif rule.rounding == "nearest_dollar":
        price = Decimal(round(price))

    return price.quantize(CENT, rounding=ROUND_HALF_UP)


async def calculate_price(
    db: AsyncSession, customer_id: UUID, product_id: UUID
) -> dict:
    """Load product + customer rules, apply markup, return OPS-ready payload."""
    product = (
        await db.execute(
            select(Product)
            .where(Product.id == product_id)
            .options(
                selectinload(Product.variants),
                selectinload(Product.images),
            )
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(404, "Product not found")

    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    if not customer.is_active:
        raise HTTPException(409, f"Customer '{customer.name}' is not active")

    rules = (
        await db.execute(
            select(MarkupRule).where(MarkupRule.customer_id == customer_id)
        )
    ).scalars().all()
    rule = resolve_rule(rules, product.supplier_sku, product.category)

    def variant_payload(v) -> dict:
        final = apply_markup(v.base_price, rule)
        return {
            "sku": v.sku,
            "color": v.color,
            "size": v.size,
            "base_price": float(v.base_price) if v.base_price is not None else None,
            "final_price": float(final) if final is not None else None,
            "inventory": v.inventory,
        }

    return {
        "product": {
            "supplier_sku": product.supplier_sku,
            "name": product.product_name,
            "brand": product.brand,
            "category": product.category,
        },
        "variants": [variant_payload(v) for v in product.variants],
        "images": [
            {"url": i.url, "image_type": i.image_type}
            for i in sorted(product.images, key=lambda i: i.sort_order)
        ],
        "markup_rule": (
            {
                "id": str(rule.id),
                "scope": rule.scope,
                "markup_pct": float(rule.markup_pct),
                "priority": rule.priority,
            }
            if rule
            else None
        ),
    }
