"""Map raw 4Over JSON → canonical PSProductData using supplier-specific field mapping.

The Field Mapping UI (`/mappings/{supplierId}`) lets the user visually pair
each 4Over field name with a canonical field (product_name, supplier_sku,
color, size, etc.). That mapping is saved to `supplier.field_mappings["mapping"]`
as a `{source_field: canonical_field}` dict.

This normalizer consumes the raw 4Over JSON (from FourOverClient) together
with that mapping dict, and returns the canonical `PSProductData` shape used
by every other supplier (SanMar, Alphabroder, S&S). That means Tanishq's
`upsert_products()` in the Task 4 DB layer can process 4Over data unchanged.

4Over variants have more axes than apparel (paperType, coating, fold,
paper_weight, finish, ...). When the user has explicitly mapped a variant
field to color/size, that's where it goes. Anything else on the variant gets
packed into `PSProductPart.attributes` so no information is lost.

This module is pure Python — no DB session, no HTTP calls, no pytest plugins.
Unit-testable offline.
"""

from __future__ import annotations

from typing import Any

from modules.promostandards.schemas import PSProductData, PSProductPart


# Canonical field names recognised at the product level.
# Must match the CANONICAL_FIELDS array in
# frontend/src/app/mappings/[supplierId]/page.tsx.
_PRODUCT_LEVEL_CANONICAL = {
    "product_name",
    "supplier_sku",
    "brand",
    "description",
    "product_type",
    "image_url",
}

# Canonical fields applied at the variant (PSProductPart) level.
# Anything not in this set that appears on a variant gets packed into
# PSProductPart.attributes.
_VARIANT_LEVEL_CANONICAL = {"color", "size"}


def _apply_mapping(raw: dict, mapping: dict[str, str]) -> dict[str, Any]:
    """Build a canonical-keyed dict from a raw dict using a source→target mapping.

    Only keys that appear in both ``raw`` and ``mapping`` are included. Values
    are passed through unchanged.

    Example:
        raw     = {"productName": "Tri-Fold", "basePrice": 45.99, "uuid": "x"}
        mapping = {"productName": "product_name", "uuid": "supplier_sku"}
        returns {"product_name": "Tri-Fold", "supplier_sku": "x"}
    """
    return {
        canonical: raw[source]
        for source, canonical in mapping.items()
        if source in raw
    }


def _normalize_one_variant(
    raw_variant: dict,
    mapping: dict[str, str],
    *,
    part_id_key: str | None = None,
) -> PSProductPart:
    """Turn one raw 4Over variant dict into a PSProductPart.

    Args:
        raw_variant: The variant dict from 4Over (e.g. one entry of
            raw_product["variants"]).
        mapping: Same source→canonical mapping used at the product level.
        part_id_key: Source key whose value becomes PSProductPart.part_id.
            Usually the variant's own identifier field — looked up from the
            mapping if ``supplier_sku`` is mapped to a variant field. Falls
            back to deriving from the raw variant's "partId"/"id"/"uuid".

    Attributes handling:
        Any variant key NOT referenced by the mapping (and not the part_id
        source key) gets stringified and stored in PSProductPart.attributes.
        This preserves coating, fold, paper_weight, finish, etc. even when
        the user didn't explicitly map them — nothing is silently dropped.
    """
    canonical = _apply_mapping(raw_variant, mapping)

    # Choose the part_id: explicit mapping wins, then common fallbacks.
    part_id = (
        canonical.pop("supplier_sku", None)
        or raw_variant.get(part_id_key or "")
        or raw_variant.get("partId")
        or raw_variant.get("id")
        or raw_variant.get("uuid")
        or ""
    )

    # Collect unmapped variant fields into attributes so nothing is lost.
    mapped_source_keys = set(mapping.keys())
    attributes: dict[str, str] = {}
    for key, value in raw_variant.items():
        # Skip keys that had an explicit canonical mapping (handled above),
        # and skip the id fallbacks we've already consumed.
        if key in mapped_source_keys:
            continue
        if key in {"partId", "id", "uuid", part_id_key}:
            continue
        # Stringify primitives; skip nested dicts/lists (they have no
        # natural place in a flat attributes dict).
        if isinstance(value, (str, int, float, bool)):
            attributes[key] = str(value)

    return PSProductPart(
        part_id=str(part_id),
        color_name=canonical.get("color"),
        size_name=canonical.get("size"),
        description=canonical.get("description"),
        attributes=attributes,
    )


def normalize_4over(
    raw_products: list[dict],
    field_mapping: dict[str, str],
    *,
    variants_key: str = "variants",
) -> list[PSProductData]:
    """Apply a source→canonical field mapping to raw 4Over product JSON.

    Args:
        raw_products: List of dicts from ``FourOverClient.get_products()``.
        field_mapping: ``{source_field: canonical_field}`` as stored under
            ``supplier.field_mappings["mapping"]`` by the Field Mapping UI.
        variants_key: Name of the list-of-variants key on each raw product.
            Defaults to "variants"; override once we confirm the exact
            4Over response shape with sandbox credentials.

    Returns:
        List of PSProductData, one per valid input product. Products for
        which the mapping does not produce a ``supplier_sku`` are skipped
        silently so a single bad record doesn't abort the whole sync.

    Raises:
        TypeError: if raw_products is not a list or field_mapping not a dict.
    """
    if not isinstance(raw_products, list):
        raise TypeError("raw_products must be a list of dicts")
    if not isinstance(field_mapping, dict):
        raise TypeError("field_mapping must be a dict")

    out: list[PSProductData] = []

    for raw in raw_products:
        if not isinstance(raw, dict):
            continue

        canonical = _apply_mapping(raw, field_mapping)

        supplier_sku = canonical.get("supplier_sku")
        if not supplier_sku:
            # Skip malformed products rather than abort the whole batch.
            continue

        # Build the variant list (may be empty if 4Over returned a
        # single-variant product without a variants array).
        raw_variants = raw.get(variants_key) or []
        parts = [_normalize_one_variant(v, field_mapping) for v in raw_variants]

        # product_type is treated as a single string in PSProductData.
        # If the user mapped a category field, it lives in canonical["product_type"].
        # Default to "print" for 4Over so downstream code can distinguish
        # apparel from print products.
        product_type = canonical.get("product_type") or "print"

        # Categories is a list on PSProductData. The UI only maps a single
        # product_type string today, so we wrap it for consistency.
        categories = [canonical["product_type"]] if canonical.get("product_type") else []

        out.append(
            PSProductData(
                product_id=str(supplier_sku),
                product_name=canonical.get("product_name"),
                description=canonical.get("description"),
                brand=canonical.get("brand"),
                categories=categories,
                product_type=product_type,
                primary_image_url=canonical.get("image_url"),
                parts=parts,
            )
        )

    return out
