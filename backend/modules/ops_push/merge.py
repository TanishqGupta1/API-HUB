"""Admin-UI preview shape — legacy merge of product + pricing + decorations.

NOT the canonical OPS push payload. The push pipeline uses
``modules.ops_push.payload_builder.build_push_payload`` (Pydantic
``OPSPushPayload`` with mutation plan + computed prices + ops_target).
This module exists for one remaining caller:

  - ``service.push_product`` returns this merged dict to the admin UI as the
    preview-pane body for POST /api/push/{cid}/{pid}.

Once the admin preview pane is repointed at ``build_push_payload``'s output,
this module can be deleted (M1 plan T25). No new callers should be added.

What it composes:

1. Variant rows with both ``vendor_price`` (supplier wholesale) and ``price``
   (customer-facing — markup + decoration uplift applied).
2. Decoration overlays folded into per-variant ``decorations`` and ``price``.
3. ``images[]`` gallery (sorted by sort_order) alongside the ``image_url`` hero
   (decoration preview if present, otherwise the product primary image).

If ``priced_variants`` is supplied (from ``markup.engine.calculate_price``),
its ``base_price`` / ``final_price`` are used; otherwise we fall back to the
raw DB ``variant.base_price`` with no markup — only kept for the rare caller
that has no customer/markup context.
"""
import os
from typing import Any, Optional


def merge_product_with_decorations(
    product: Any,
    customer_id: Any,
    decorations: list[dict] | None,
    priced_variants: Optional[list[dict]] = None,
) -> dict:
    """Build the OPS-bound payload for one product + customer + decorations.

    Args:
        product: SQLAlchemy ``Product`` instance. Must have ``variants`` loaded;
            ``images`` is used if loaded, otherwise the ``images[]`` field will
            be empty.
        customer_id: UUID of the target customer (used to build the decoration
            preview URL when decorations are present).
        decorations: List of decoration option dicts saved for this customer.
            Each item may have ``placement``, ``method``, ``price_addition``.
        priced_variants: Optional. Output of
            ``markup.engine.calculate_price()['variants']`` — when supplied,
            its ``base_price`` and ``final_price`` are used per variant.
            Without it, no markup is applied (Phase 8 Bug 2 fix is to always
            pass this).
    """
    # Decoration extract
    dec_cost = 0.0
    dec_areas: list[dict] = []
    if decorations:
        for dec in decorations:
            dec_cost += float(dec.get("price_addition", 0.0) or 0.0)
            dec_areas.append({
                "placement": dec.get("placement"),
                "method": dec.get("method"),
                "price": float(dec.get("price_addition", 0.0) or 0.0),
            })

    # Index markup-applied prices by SKU for O(1) lookup per variant.
    priced_by_sku: dict[str, dict] = {}
    if priced_variants:
        for pv in priced_variants:
            sku = pv.get("sku")
            if sku:
                priced_by_sku[sku] = pv

    variants: list[dict] = []
    if hasattr(product, "variants") and product.variants:
        for v in product.variants:
            priced = priced_by_sku.get(v.sku) if v.sku else None

            # vendor_price = wholesale (pre-markup, pre-decoration)
            if priced and priced.get("base_price") is not None:
                vendor_price = float(priced["base_price"])
            elif v.base_price is not None:
                vendor_price = float(v.base_price)
            else:
                vendor_price = 0.0

            # price = markup-applied + decoration uplift
            if priced and priced.get("final_price") is not None:
                base_for_calc = float(priced["final_price"])
            else:
                # No markup context — pass vendor_price through, log a warning.
                base_for_calc = vendor_price
            final_price = base_for_calc + dec_cost

            variants.append({
                "sku": v.sku,
                "color": v.color,
                "size": v.size,
                "inventory": v.inventory,
                "vendor_price": vendor_price,
                "price": final_price,
                "decorations": dec_areas,
            })

    # Hero image — decoration preview takes precedence
    api_url = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
    if decorations:
        image_url = f"{api_url}/api/customers/{customer_id}/products/{product.id}/decorations/preview.png"
    else:
        image_url = product.image_url

    # Full gallery — sorted by sort_order so OPS storefront renders in
    # deterministic order. (Phase 8 Bug 3 fix.) If ``product.images`` is
    # not loaded (lazy relationship), fall back to empty list — caller is
    # responsible for loading it via selectinload(Product.images).
    images: list[dict] = []
    raw_images = getattr(product, "images", None)
    if raw_images:
        try:
            for img in sorted(raw_images, key=lambda i: i.sort_order or 0):
                images.append({
                    "url": img.url,
                    "image_type": img.image_type,
                    "color": img.color,
                    "sort_order": img.sort_order or 0,
                })
        except Exception:
            # Defensive: lazy-load attempt in async context will raise.
            # Better to ship the payload with image_url only than to crash.
            images = []

    payload = {
        "external_id": product.supplier_sku,
        "name": product.product_name,
        "description": product.description,
        "brand": product.brand,
        "categories": [product.category] if product.category else [],
        "type": product.product_type,
        "image_url": image_url,
        "images": images,
        "variants": variants,
    }

    return payload
