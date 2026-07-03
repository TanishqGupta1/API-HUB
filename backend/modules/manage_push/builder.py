"""Serialize a Connect Product into a ConnectProductPush payload for GraphX-Manage.

CRITICAL (plan decision 4 / AC10): this builds **wholesale cost only** and NEVER calls
`markup.engine.apply_markup`. Manage owns sell pricing (markup on top of the cost we send);
applying Connect markup here would double-mark-up. The module deliberately does not import the
markup engine.

Field mapping (Connect catalog → ConnectProductPush, consumed by Manage's connect-ingest):
  - color / size  → options[] derived from DISTINCT ProductVariant.color / .size (K420's
    collapsed ProductOptions are decoration options — Print Sides/Production Time/Ink Finish/Ink
    Type — not color/size; those are carried through as additional options).
  - cost          → Net VariantPrice tiers (price_type="Net"); base_cost = the qty=1 Net floor.
    (Per-size cost variation is flattened to the product floor for now — Manage models size as an
    option, not a priced ProductSize; per-size cost is a future refinement.)
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

# Standard apparel size order so "Size" reads XS→6XL, not alphabetical.
_SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL", "2XL", "XXXL", "3XL", "4XL", "5XL", "6XL"]
_SIZE_RANK = {s: i for i, s in enumerate(_SIZE_ORDER)}


def _slug(s: str) -> str:
    """Lowercase hyphen-slug for an attribute_key (stable natural key on the Manage side)."""
    return re.sub(r"[^a-z0-9]+", "-", (s or "").strip().lower()).strip("-") or "na"


def _size_sort_key(s: str) -> tuple[int, str]:
    return (_SIZE_RANK.get((s or "").upper(), 999), s or "")


def build_connect_product_push(product: Any, supplier_slug: str) -> dict[str, Any]:
    """Build the cost-only ConnectProductPush dict for one Connect Product.

    `product` must have variants (+ each variant's prices) and options (+ attributes) loaded.
    """
    variants = list(getattr(product, "variants", []) or [])

    # ── options: color + size derived from variants ──
    options: list[dict[str, Any]] = []

    colors = sorted({v.color for v in variants if v.color})
    if colors:
        options.append({
            "option_key": "color",
            "title": "Color",
            "options_type": "swatch",
            "attributes": [
                {"title": c, "attribute_key": _slug(c), "sort_order": i} for i, c in enumerate(colors)
            ],
        })

    sizes = sorted({v.size for v in variants if v.size}, key=_size_sort_key)
    if sizes:
        options.append({
            "option_key": "size",
            "title": "Size",
            "options_type": "dropdown",
            "attributes": [
                {"title": s, "attribute_key": _slug(s), "sort_order": i} for i, s in enumerate(sizes)
            ],
        })

    # ── decoration/print options already collapsed on the Connect product ──
    for o in (getattr(product, "options", []) or []):
        attrs = sorted(getattr(o, "attributes", []) or [], key=lambda a: a.sort_order or 0)
        if not attrs:
            continue
        options.append({
            "option_key": o.option_key,
            "title": o.title,
            "options_type": o.options_type or "radio",
            "attributes": [
                {
                    "title": a.title,
                    "attribute_key": a.attribute_key or _slug(a.title),
                    "sort_order": a.sort_order or i,
                }
                for i, a in enumerate(attrs)
            ],
        })

    # ── cost: Net wholesale only (NO markup) ──
    net_rows = [
        pr
        for v in variants
        for pr in (getattr(v, "prices", []) or [])
        if pr.price_type == "Net" and pr.price is not None
    ]
    cost: dict[str, Any] = {"currency": "USD"}
    if net_rows:
        # Group by (qty_from, qty_to); vendor_price = the floor (min) cost in that break.
        groups: dict[tuple[int, int | None], Decimal] = {}
        for pr in net_rows:
            key = (pr.quantity_min or 1, pr.quantity_max)
            if key not in groups or pr.price < groups[key]:
                groups[key] = pr.price
        tiers = [
            {"qty_from": qmin, "qty_to": qmax, "vendor_price": str(price)}
            for (qmin, qmax), price in sorted(groups.items(), key=lambda kv: kv[0][0])
        ]
        cost["tiers"] = tiers
        qty1 = [p for (qmin, _qmax), p in groups.items() if qmin == 1]
        cost["base_cost"] = str(min(qty1)) if qty1 else str(min(groups.values()))

    return {
        "supplier_slug": supplier_slug,
        "supplier_sku": product.supplier_sku,
        "product_name": product.product_name,
        "brand": getattr(product, "brand", None),
        "product_class": "PRINT_PRODUCT",
        "options": options,
        "cost": cost,
        "availability": {"discontinued": getattr(product, "archived_at", None) is not None},
        "provenance": {"source": "CONNECT", "connect_ref": f"{supplier_slug}:{product.supplier_sku}"},
    }
