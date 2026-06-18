"""Integration Gateway — M1: `build_push_payload()` + `OPSPushPayload`.

Replaces the prior VPCE-shaped `OpsPushPayloadBuilder.to_mutation_plan()`
with the Integration Gateway contract from
`docs/superpowers/specs/2026-05-11-integration-gateway-design.md`.

What this module owns
---------------------
1. Loading the per-(customer, product) context for one push.
2. Applying the markup engine (absorbs Bug 3 fix per M1 §"Bug 3 absorbed
   by M1's build_push_payload()").
3. Composing the OPS GraphQL mutation plan in the order locked by
   Rev 1 §"OPS auth flow and outbound mutation contract":
       setProduct
     → setProductSize × N            (sorted by sort_order ASC, then (color,size,sku))
     → setProductPrice  × N          (qty=1, qty_to=999999, depends on matching size step)
     → option attach     × M         (two strategy modes, mixing forbidden)
     → updateProductStock × N        (action=Reset, last step)
4. Emitting an `OPSPushPayload` Pydantic model that the worker can
   serialize into `step_results JSONB` as each mutation completes.

What this module deliberately does NOT do
-----------------------------------------
- No HTTP / OPS calls (worker calls OpsClient with this payload).
- No DB writes — pure read + compose.
- No `payload_hash` computation over the inbound gateway request body —
  that lives in `modules/integrations/routes.py` (M2). What we DO provide
  is the `canonicalize_json()` + `compute_payload_hash()` helpers used by
  the gateway, since the canonicalization rules are the same.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.catalog.models import (
    Product,
    ProductImage,
    ProductOption,
    ProductOptionAttribute,
    ProductVariant,
)
from modules.customers.models import Customer
from modules.decorations.models import CustomerProductDecoration
from modules.markup.engine import apply_markup, resolve_rule
from modules.ops_config.models import ProductStorefrontConfig
from modules.pricing.overrides import apply_pricing_overrides
from modules.pricing.resolvers import to_cents
from modules.markup.models import MarkupRule
from modules.push_mappings.models import PushMapping, PushMappingOption
from modules.suppliers.models import Supplier


# ---------------------------------------------------------------------------
# Option strategy — spec §"PC61 outbound mutation sequence" / Preflight gates
# ---------------------------------------------------------------------------


class OptionStrategy(str, Enum):
    """How the OPS push attaches per-product options.

    Spec rule: chosen ONCE per customer; mixing modes inside one push
    request is forbidden.
    """

    MASTER_OPTION_ATTACH = "master_option_attach"
    PRODUCT_LOCAL_OPTION_CREATE = "product_local_option_create"


# ---------------------------------------------------------------------------
# Pydantic output models — what `build_push_payload()` returns
# ---------------------------------------------------------------------------


class OPSMutationStep(BaseModel):
    """One mutation in the plan. Worker walks these in order; on each
    successful response it appends an entry to `step_results JSONB` and
    persists OPS-returned IDs to `cleanup_targets` before issuing the
    next mutation (Rev 1 §"Step-level recovery")."""

    model_config = ConfigDict(extra="forbid")

    step: int = Field(..., ge=1, description="1-based ordinal in the plan")
    mutation: str = Field(..., description="GraphQL mutation name, e.g. setProduct")
    source_key: str = Field(
        ...,
        description=(
            "Stable key used by `step_results.source_key` so a resumed "
            "worker can re-find this step after a crash: e.g. "
            "'supplier_sku:PC61', 'variant_sku:PC61-NAV-S', "
            "'option_key:lamMaterial', 'attribute_key:lamMaterial/gloss'"
        ),
    )
    variables: dict[str, Any] = Field(..., description="GraphQL input variables")
    requires_response_from: list[int] = Field(
        default_factory=list,
        description=(
            "Step numbers whose responses this step's `$stepN.field` "
            "placeholders refer to. Worker substitutes at execute time."
        ),
    )


class OPSComputedPrice(BaseModel):
    """One row of the post-markup price table."""

    model_config = ConfigDict(extra="forbid")

    variant_sku: str
    color: Optional[str] = None
    size: Optional[str] = None
    sort_order: int = 0
    base_price: float = Field(..., description="Wholesale cost — becomes vendor_price in OPS")
    final_price: float = Field(..., description="Customer sell price — becomes price in OPS")
    markup_pct: Optional[float] = None
    markup_amount: Optional[float] = None
    rounding: str = "none"
    storefront_override_applied: bool = Field(
        default=False,
        description="True when product_storefront_configs.pricing_overrides altered final_price",
    )


class OPSPushPayload(BaseModel):
    """Result of `build_push_payload()`. Persisted into push_log indirectly
    via `step_results JSONB` (as the worker walks through it) and returned
    from `POST /api/integrations/v1/push-requests` when `dry_run=true`."""

    model_config = ConfigDict(extra="forbid")

    # ---- Identity ----
    customer_id: UUID
    product_id: UUID
    supplier_slug: str
    supplier_sku: str

    # ---- Mode flags ----
    push_mode: str = Field(..., description="'create' or 'update' — gated by existing push_mappings")
    option_strategy: OptionStrategy
    existing_ops_product_id: Optional[int] = Field(
        None,
        description="When push_mode='update', the products_id from push_mappings",
    )

    # ---- Computed pricing (markup engine output) ----
    computed_prices: list[OPSComputedPrice]
    markup_rule_id: Optional[UUID] = None

    # ---- Mutation plan ----
    plan: list[OPSMutationStep]

    # ---- Image policy (beta = single primary front image only) ----
    primary_image_url: Optional[str] = None
    image_warnings: list[str] = Field(default_factory=list)

    # ---- Metadata ----
    estimated_mutations: int
    built_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ---- OPS target snapshot for UI display (no secrets) ----
    ops_target: dict[str, Any] = Field(default_factory=dict)


class OPSStepResult(BaseModel):
    """Append-only entry written to `product_push_log.step_results JSONB`
    after each successful upstream OPS mutation. Spec §"Step-level recovery
    and partial-write contract"."""

    model_config = ConfigDict(extra="forbid")

    step: int
    source_key: str
    mutation: str
    request_fingerprint: str
    ops_ids: dict[str, Any] = Field(default_factory=dict)
    attempted_at: datetime


# ---------------------------------------------------------------------------
# RFC 8785 JSON Canonicalization Scheme
# ---------------------------------------------------------------------------
#
# Spec Rev 1 §"Idempotency semantics (locked)" requires:
#   1. Parse raw body as JSON.
#   2. Recursively remove object members whose value is `null`.
#   3. Preserve array order exactly, including `null` elements.
#   4. Serialize per RFC 8785 (UTF-8, lex-sorted keys, RFC 8785 number
#      formatting, no insignificant whitespace).
#   5. SHA-256 the UTF-8 bytes, lowercase hex.


def _strip_nulls_from_objects(value: Any) -> Any:
    """Recursively drop object members whose value is `None`. Array order
    and array `None`s are preserved exactly."""
    if isinstance(value, dict):
        return {
            k: _strip_nulls_from_objects(v)
            for k, v in value.items()
            if v is not None
        }
    if isinstance(value, list):
        return [_strip_nulls_from_objects(v) for v in value]
    return value


def _canonical_number(n: Union[int, float]) -> str:
    """RFC 8785 number serialization (ECMA-262 §7.1.12.1 "Number::toString").

    Key rules for our beta:
      - Integers serialize without exponent or decimal point: 0, -1, 12345
      - Booleans are NOT numbers (handled by `_canonical_value`)
      - +0 and -0 both serialize as "0"
      - NaN / Infinity / -Infinity are not representable in JSON → raise

    We rely on Python's `repr()` for floats which already follows the
    shortest-round-trip rule that ECMA-262 + RFC 8785 mandate.

    KNOWN LIMITATION: Python's repr and ECMA-262 §7.1.12.1 can diverge
    on subnormal floats (|x| < ~2.2e-308) and on a handful of edge
    cases near the float64 boundary. Our payloads (prices in dollars,
    inventory counts, qty breaks) are all in the normal-double range,
    so this divergence is unreachable in practice. If a future caller
    needs strict ECMA-262 compliance, swap to `numpy.format_float_positional`
    or `json.encoder.float_repr` with a custom formatter.
    """
    if isinstance(n, bool):  # bool is subclass of int in Python
        raise TypeError("bool should be handled by _canonical_value, not _canonical_number")
    if isinstance(n, int):
        return str(n)
    # float
    if math.isnan(n) or math.isinf(n):
        raise ValueError(f"Cannot canonicalize non-finite number: {n}")
    if n == 0:
        return "0"
    # Python's repr() gives shortest round-trip representation.
    s = repr(n)
    # repr can produce e.g. '1e+20' which is RFC-8785-legal; normalize
    # '1.0' → '1' since RFC 8785 says integers drop the decimal point.
    if s.endswith(".0"):
        s = s[:-2]
    # Normalize exponent: Python uses 'e+20', RFC 8785 also uses 'e+20'.
    # No change needed.
    return s


def _canonical_string(s: str) -> str:
    """JSON-encode a string per RFC 8785 §3.2.3 (control chars + required
    escapes, lowercase \\uXXXX for the few required escapes)."""
    return json.dumps(s, ensure_ascii=False)


def _canonical_value(v: Any) -> str:
    """Recursive canonicalizer. Null-stripping is done BEFORE calling
    this — see `canonicalize_json()`."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return _canonical_number(v)
    if isinstance(v, str):
        return _canonical_string(v)
    if isinstance(v, list):
        return "[" + ",".join(_canonical_value(x) for x in v) + "]"
    if isinstance(v, dict):
        # RFC 8785 §3.2.3 — sort by UTF-16 code unit. Python's default
        # str sort uses Unicode code points, which diverges from UTF-16
        # for supplementary-plane chars (U+10000+) because those need a
        # surrogate pair in UTF-16. Encoding to utf-16-be makes the sort
        # operate on the actual code units the spec mandates.
        items = sorted(v.items(), key=lambda kv: kv[0].encode("utf-16-be"))
        return (
            "{"
            + ",".join(
                f"{_canonical_string(k)}:{_canonical_value(val)}"
                for k, val in items
            )
            + "}"
        )
    # Coerce Decimal / UUID / datetime to string — caller should normalize
    # before this point. Defensive: stringify.
    return _canonical_string(str(v))


def canonicalize_json(value: Any) -> str:
    """RFC 8785 JCS serialization with the spec's null-stripping rule
    applied first. Returns a deterministic UTF-8 string."""
    stripped = _strip_nulls_from_objects(value)
    return _canonical_value(stripped)


def compute_payload_hash(value: Any) -> str:
    """Lowercase hex SHA-256 over the canonicalized JSON bytes. This is
    `payload_hash` per Rev 1 §"Idempotency semantics (locked)"."""
    canon = canonicalize_json(value)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Internal context loader
# ---------------------------------------------------------------------------


@dataclass
class _PushContext:
    """In-memory snapshot needed to build the payload. Loaded once."""

    customer: Customer
    product: Product
    supplier: Supplier
    variants: list[ProductVariant]
    images: list[ProductImage]
    options: list[ProductOption]
    markup_rules: list[MarkupRule]
    push_mapping: Optional[PushMapping]
    push_mapping_options: list[PushMappingOption]
    decoration_options: list[dict]
    storefront_config: Optional[ProductStorefrontConfig]


async def _load_context(
    db: AsyncSession,
    customer_id: UUID,
    product_id: UUID,
) -> _PushContext:
    """Single-round-trip load of everything build_push_payload needs."""

    product = (
        await db.execute(
            select(Product)
            .where(Product.id == product_id)
            .options(
                selectinload(Product.variants),
                selectinload(Product.images),
                selectinload(Product.options).selectinload(
                    ProductOption.attributes
                ),
            )
        )
    ).scalar_one_or_none()
    if product is None:
        raise ValueError(f"Product {product_id} not found")

    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise ValueError(f"Customer {customer_id} not found")

    supplier = await db.get(Supplier, product.supplier_id)
    if supplier is None:
        raise ValueError(f"Supplier {product.supplier_id} not found")

    markup_rules = (
        await db.execute(
            select(MarkupRule).where(MarkupRule.customer_id == customer_id)
        )
    ).scalars().all()

    push_mapping = (
        await db.execute(
            select(PushMapping)
            .where(
                PushMapping.customer_id == customer_id,
                PushMapping.source_product_id == product_id,
            )
            .options(selectinload(PushMapping.options))
        )
    ).scalar_one_or_none()
    push_mapping_options = list(push_mapping.options) if push_mapping else []

    decoration_row = (
        await db.execute(
            select(CustomerProductDecoration).where(
                CustomerProductDecoration.customer_id == customer_id,
                CustomerProductDecoration.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    decoration_options = (
        list(decoration_row.decoration_options) if decoration_row else []
    )

    storefront_config = (
        await db.execute(
            select(ProductStorefrontConfig).where(
                ProductStorefrontConfig.customer_id == customer_id,
                ProductStorefrontConfig.product_id == product_id,
            )
        )
    ).scalar_one_or_none()

    return _PushContext(
        customer=customer,
        product=product,
        supplier=supplier,
        variants=list(product.variants),
        images=sorted(product.images, key=lambda i: i.sort_order or 0),
        options=list(product.options),
        markup_rules=list(markup_rules),
        push_mapping=push_mapping,
        push_mapping_options=push_mapping_options,
        decoration_options=decoration_options,
        storefront_config=storefront_config,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _placeholder(step: int, field_name: str) -> str:
    """`$stepN.field` reference marker resolved at execute time."""
    return f"$step{step}.{field_name}"


def _to_float(d: Optional[Decimal]) -> Optional[float]:
    return float(d) if d is not None else None


def _request_fingerprint(variables: dict[str, Any]) -> str:
    """Stable 16-char hex digest over `variables`. Used by the worker to
    detect drift if it retries a step after a partial failure."""
    canon = canonicalize_json(variables)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


def _variant_sort_key(v: ProductVariant) -> tuple[int, str, str, str]:
    """Sort variants by `sort_order` ASC, then lex `(color, size, sku)`.

    `sort_order` is the new M0 column; we use `getattr(..., 0)` so this
    code keeps working before the M0 migration lands.
    """
    return (
        getattr(v, "sort_order", 0) or 0,
        (v.color or "").lower(),
        (v.size or "").lower(),
        (v.sku or "").lower(),
    )


def _customer_prefix(customer: Customer, supplier: Supplier) -> str:
    """Customer-prefixed title rule: prefer supplier.push_name_prefix
    (already configured per supplier in current DB), fall back to
    UPPERCASE first two letters of supplier slug + dash."""
    return supplier.push_name_prefix or f"{supplier.slug[:2].upper()}-"


# ---------------------------------------------------------------------------
# Mutation step builders
# ---------------------------------------------------------------------------


def _build_setProduct_step(
    ctx: _PushContext, push_mode: str, existing_ops_id: Optional[int], primary_image_url: Optional[str]
) -> OPSMutationStep:
    """setProduct is always step 1 (no more separate setProductCategory).

    create mode: products_id omitted (or 0).
    update mode: products_id = existing OPS product id from push_mappings.
    """
    title = f"{_customer_prefix(ctx.customer, ctx.supplier)}{ctx.product.product_name}"
    # Field names verified against OPS's live ProductInput schema:
    #   - product_description  (NOT products_description)
    #   - imagename            (NOT products_image)
    #   - category_id (Int)    (NOT category_name) — sourced from the storefront
    #     mapping; omitted when unmapped (category is optional) so the push
    #     isn't blocked while category mapping is still being set up.
    #   - `brand` dropped — ProductInput has no brand field.
    # Description fan-out: OPS has multiple description fields. `product_description`
    # ends up in OPS's `short_description` (visible only in admin), while the
    # storefront PDP renders `long_description`. Reference product 361 leaves
    # short_description empty and uses long_description for the customer-visible
    # copy — we mirror that. Sending the same supplier blurb to both fields is
    # safe: if a future storefront theme switches to short_description, we're
    # still covered.
    _desc = ctx.product.description or ""
    inp: dict[str, Any] = {
        "products_id": existing_ops_id if push_mode == "update" else 0,
        "products_title": title,
        "products_internal_title": ctx.product.supplier_sku,
        # main_sku is OPS's product-level SKU, written via setProduct at the
        # product level (size_id=0) — a real, writable ProductInput field
        # (see docs/ops/SOURCE.md). We set it to supplier_sku so the product
        # carries a stable, supplier-traceable identity in OPS.
        #
        # NOTE: this does NOT by itself prevent duplicate pushes. The gateway's
        # pre-push dedup currently calls getProductBySku, which is NOT a real
        # OPS query (see docs/ops/SOURCE.md) and always returns nothing. Real
        # dedup must look the product up by main_sku via getProductSkuMatrix or
        # the `products`/`productsDetails` queries — tracked separately.
        "main_sku": ctx.product.supplier_sku,
        "visible": 1,
        "product_description": _desc,
        "long_description": _desc,
        # ── Required OPS ProductInput fields for all products ──────────
        # Phase 1 audit findings (June 2026):
        #   * predefined_product_type — silent reject when null
        #   * price_defining_method — silent reject of "qty" string;
        #     OPS expects a numeric string. "1" = qty-based pricing
        #     (verified against working products on staging.visualgraphx)
        #   * measurement_unit_id — silent reject when 0/null
        #   * enable_stock_management — required for updateProductStock
        #     to find variants; without it, all stock writes fail
        #   * product_type — working OPS products always have this set;
        #     null may hide the product from some admin UI filters
        "predefined_product_type": "1",
        "price_defining_method": "1",
        "measurement_unit_id": 1,
        "enable_stock_management": "1",
        "product_type": "1",
    }
    # Category resolution: per-product storefront override wins; if absent,
    # fall back to the per-customer default_ops_category_id (Phase 2 of the
    # OPS push audit). Without a category, OPS hides the product from the
    # admin's default browse view, so we want a sensible fallback.
    _cat = (ctx.storefront_config.ops_category_id if ctx.storefront_config else None) \
        or getattr(ctx.customer, "default_ops_category_id", None)
    if _cat:
        try:
            inp["category_id"] = int(_cat)
        except (TypeError, ValueError):
            pass
    if primary_image_url:
        # OPS stores `imagename` as a relative filename and prepends its own
        # CDN base path (e.g. ".../images/product/{filename}") at serve time.
        # Sending a full URL like "https://cdnm.sanmar.com/.../PC61.jpg" causes
        # OPS to double-prefix it into garbage. Strip to the filename only.
        #
        # NOTE: this only fixes the URL format. The image file must still
        # exist on OPS's CDN — currently it doesn't, because we have no
        # upload pipeline to push the bytes (Phase 3 partial fix). Customers
        # see a clean broken-image link instead of a malformed URL. Full fix
        # requires either: (a) Christian opens OPS's CDN to fetch from
        # SanMar's IP, or (b) we add a media upload step via OPS's REST
        # upload endpoint (no GraphQL mutation exists for binary upload).
        inp["imagename"] = primary_image_url.rsplit("/", 1)[-1]
    variables: dict[str, Any] = {"inputs": [inp]}

    return OPSMutationStep(
        step=1,
        mutation="setProduct",
        source_key=f"supplier_sku:{ctx.product.supplier_sku}",
        variables=variables,
        requires_response_from=[],
    )


def _build_setProductSize_placeholder_step(step_num: int) -> OPSMutationStep:
    """Single placeholder setProductSize for apparel (Phase 8 rewrite).

    Reference product 361 in visualgraphx OPS staging has exactly one
    productSize entry ("Default" placeholder) plus 12 productAdditionalOptions
    for the real Size/Color/Material picker. OPS requires at least one size
    row even when the customer-facing variant selection comes from the
    Additional Options panel — without it OPS hides the product from
    the storefront's "Add to cart" flow.
    """
    return OPSMutationStep(
        step=step_num,
        mutation="setProductSize",
        source_key="placeholder_size",
        variables={
            "inputs": [{
                "products_id": _placeholder(1, "products_id"),
                "size_title": "Default",
                "visible": "1",  # OPS ProductSizeInput.visible is String
            }]
        },
        requires_response_from=[1],
    )


def _extract_attribute_values(
    variants: list[ProductVariant],
) -> tuple[list[str], list[str]]:
    """Pull unique apparel attribute values out of the flat variant list.

    Apparel products from SanMar come as flat "Color/Size" combinations
    (e.g. Black/S, Black/M, White/S). OPS's reference apparel model
    (product 361 in visualgraphx staging) shows that EACH attribute value
    is its own top-level `setAdditionalOption` row — not attributes under
    a grouping option. So XS, S, M, L, XL... become 5 separate options.

    Returns (colors, sizes) preserving sort_order. Colors first so the
    UI renders Color choices above Size choices in the OPS storefront.
    """
    sorted_variants = sorted(variants, key=_variant_sort_key)

    sizes: list[str] = []
    seen_sizes: set[str] = set()
    colors: list[str] = []
    seen_colors: set[str] = set()
    for v in sorted_variants:
        size = (v.size or "").strip()
        if size and size not in seen_sizes:
            seen_sizes.add(size)
            sizes.append(size)
        color = (v.color or "").strip()
        if color and color not in seen_colors:
            seen_colors.add(color)
            colors.append(color)

    return colors, sizes


def _build_apparel_option_group_step(
    step_num: int, kind: str, title: str, sort_order: int
) -> OPSMutationStep:
    """Create one parent setAdditionalOption group for a Color or Size dimension.

    Each apparel dimension (Color, Size) becomes a single top-level option group.
    Actual values (Red, S, 2XL …) are added as setAdditionalOptionAttributes
    children so that setProductsAttributePrice can attach per-attribute pricing.

    Fields verified against the live OPS 81-op collection (2026-06-17):
      - `multiplier` / `multiplier_type` do NOT exist on AdditionalOptionInput.
        Per-size pricing is handled exclusively via setProductsAttributePrice.
      - `apply_multiplication="1"` enables the OPS multiplication path for this
        option group; the actual per-attribute price is set downstream.
    """
    key = re.sub(r"[^a-z0-9]+", "_", kind.lower()).strip("_") or "opt"
    return OPSMutationStep(
        step=step_num,
        mutation="setAdditionalOption",
        source_key=f"apparel_group:{kind}",
        variables={
            "inputs": [{
                "prod_add_opt_id": 0,           # 0 = create; OPS upserts on option_key
                "products_id": _placeholder(1, "products_id"),
                "option_key": key,
                "title": title,
                "description": "",
                "options_type": "textmp",
                "price_calculate_type": "0",
                "apply_multiplication": "1",
                "applicable_for": "0",
                "status": "1",
                "required": "1",
                "hire_designer_option": "0",
                "size_id": 0,
                "master_option_id": 0,
                "sort_order": sort_order,
                "delete": 0,
            }]
        },
        requires_response_from=[1],
    )


def _build_apparel_option_attribute_step(
    step_num: int,
    parent_option_step: int,
    kind: str,
    value: str,
    sort_order: int,
) -> OPSMutationStep:
    """Create one attribute value under a parent apparel option group.

    Input fields verified against live OPS collection (setAdditionalOptionAttributes,
    AdditionalOptionAttributesInput). Returns attribute_id which is required by
    _build_apparel_attribute_price_step for per-size pricing.

    `kind` ("color" / "size") is local — used only for source_key uniqueness.
    """
    safe_key = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "val"
    return OPSMutationStep(
        step=step_num,
        mutation="setAdditionalOptionAttributes",
        source_key=f"apparel_attr:{kind}/{safe_key}",
        variables={
            "inputs": [{
                "attribute_id": 0,              # 0 = create
                "prod_add_opt_id": _placeholder(parent_option_step, "prod_add_opt_id"),
                "label": value,
                "attribute_key": safe_key,
                "status": "1",
                "sort_order": sort_order,
                "setup_cost": 0,
                "default_attribute": "0",
                "delete": 0,
            }]
        },
        requires_response_from=[parent_option_step],
    )


def _build_apparel_attribute_price_step(
    step_num: int,
    attribute_step: int,
    variant_sku: str,
    base_price: float,
    final_price: float,
) -> OPSMutationStep:
    """Set the per-size sell price for one apparel size attribute.

    Uses setProductsAttributePrice (verified live in OPS 81-op collection).
    `attribute_id` comes from the matching setAdditionalOptionAttributes response.
    `size_from=0, size_to=99999999` covers the entire print-size range — since
    apparel uses a single placeholder OPS size (Default), this unconditionally
    applies the per-size price for any print-size selection.

    This replaces the invalid `multiplier`/`multiplier_type` approach: those
    fields do not exist on AdditionalOptionInput per the live OPS schema.
    """
    return OPSMutationStep(
        step=step_num,
        mutation="setProductsAttributePrice",
        source_key=f"attr_price:size/{variant_sku}",
        variables={
            "inputs": [{
                "attribute_id": _placeholder(attribute_step, "attribute_id"),
                "size_from": 0,
                "size_to": 99999999,
                "attributes_price": final_price,
                "vendor_price": base_price,
                "delete": 0,
            }]
        },
        requires_response_from=[attribute_step],
    )


# Standard apparel volume-discount curve, applied to every push since SanMar
# does NOT return quantity tiers via getConfigurationAndPricing — they only
# give a single flat per-variant wholesale price. Mirrors reference product
# 361's 6-row Price table shape (1-11, 12-50, 51-500, 501-1000, 1001-5000,
# 5001-9999) with a typical apparel discount progression. Adjust per-customer
# via markup rules in a later phase if needed.
APPAREL_VOLUME_TIERS: tuple[tuple[int, int, float], ...] = (
    (1, 11, 1.00),
    (12, 50, 0.98),
    (51, 500, 0.96),
    (501, 1000, 0.94),
    (1001, 5000, 0.92),
    (5001, 9999, 0.90),
)


def _build_setProductPrice_step(
    step_num: int,
    size_step: int,
    variant_sku: str,
    base_price: float,
    final_price: float,
    qty_from: int = 1,
    qty_to: int = 999999,
    source_key_suffix: str = "",
) -> OPSMutationStep:
    """One setProductPrice row. For apparel, the synthesizer calls this once
    per APPAREL_VOLUME_TIERS row, producing the 6-tier table shape that
    matches reference product 361's "Range Based With Multiplication"
    pricing method.
    """
    key = f"variant_sku:{variant_sku}"
    if source_key_suffix:
        key = f"{key}/{source_key_suffix}"
    return OPSMutationStep(
        step=step_num,
        mutation="setProductPrice",
        source_key=key,
        variables={
            "inputs": [{
                "products_id": _placeholder(1, "products_id"),
                # OPS returns `id` from setProductSize, normalized to `size_id` in gateway.
                "size_id": _placeholder(size_step, "size_id"),
                "qty": qty_from,
                "qty_to": qty_to,
                "price": final_price,
                "vendor_price": base_price,
                "visible": "1",  # OPS ProductPriceInput.visible is String
                # user_type_id is required by OPS. Without it OPS returns
                # result:true with id:null and silently drops the price.
                # "1" = default/all-users user type (matches existing OPS
                # products). Verified live against staging.visualgraphx
                # (a direct setProductPrice without this field returns
                # id:null; adding "1" returns a real id).
                "user_type_id": "1",
                # price_defining_method MUST be set on each price too — not
                # just on the parent product. OPS validation message:
                # "Price Defining method is required."
                "price_defining_method": "1",
            }]
        },
        requires_response_from=[1, size_step],
    )


def _build_setAssignOptions_step(
    step_num: int, mapping: PushMappingOption
) -> OPSMutationStep:
    """master_option_attach mode — one setAssignOptions per mapping row."""
    return OPSMutationStep(
        step=step_num,
        mutation="setAssignOptions",
        source_key=(
            f"option_key:{mapping.source_option_key}"
            + (f"/{mapping.source_attribute_key}" if mapping.source_attribute_key else "")
        ),
        variables={
            "inputs": [{
                "products_id": _placeholder(1, "products_id"),
                "master_option_id": mapping.target_ops_option_id,
                "sort_order": getattr(mapping, "sort_order", 0) or 0,
            }]
        },
        requires_response_from=[1],
    )


def _build_setAdditionalOption_step(
    step_num: int, opt: ProductOption
) -> OPSMutationStep:
    """product_local_option_create mode — create a local option on the
    OPS product (no master option mapping required)."""
    return OPSMutationStep(
        step=step_num,
        mutation="setAdditionalOption",
        source_key=f"option_key:{opt.option_key}",
        variables={
            "inputs": [{
                "products_id": _placeholder(1, "products_id"),
                "option_key": opt.option_key,
                "title": opt.title or opt.option_key,
                "options_type": getattr(opt, "options_type", "combo"),
                "sort_order": opt.sort_order or 0,
            }]
        },
        requires_response_from=[1],
    )


def _build_setAdditionalOptionAttributes_step(
    step_num: int,
    option_step: int,
    opt_key: str,
    attr: ProductOptionAttribute,
) -> OPSMutationStep:
    """product_local_option_create mode — attach attribute to local option."""
    return OPSMutationStep(
        step=step_num,
        mutation="setAdditionalOptionAttributes",
        source_key=f"attribute_key:{opt_key}/{attr.attribute_key}",
        variables={
            "inputs": [{
                # OPS setAdditionalOption returns `id`, normalized to `prod_add_opt_id` in gateway.
                "prod_add_opt_id": _placeholder(option_step, "prod_add_opt_id"),
                "attribute_key": attr.attribute_key,
                "label": attr.title or attr.attribute_key,
                "setup_cost": _to_float(getattr(attr, "setup_cost", None)) or 0.0,
                "multiplier": _to_float(getattr(attr, "multiplier", None)) or 1.0,
            }]
        },
        requires_response_from=[option_step],
    )


def _build_updateProductStock_step(
    step_num: int, size_step: int, variant_sku: str, inventory: int
) -> OPSMutationStep:
    """Inventory LAST step per Rev 1 §"PC61 outbound mutation sequence".

    Phase 6 — stock_id resolution via read-back:
      OPS's updateProductStock identifies the variant by stock_id (or by
      product_sku). There is NO per-size SKU field in OPS's schema, so
      product_sku never matches anything for products we created via API.
      Instead the gateway runs a productStocks(product_id) read-back
      after setProductSize completes and resolves the right stock_id
      from a `(product_id, size_id) -> stock_id` map.

      This step carries:
        * `_size_id_ref` — placeholder resolved to the OPS size_id of the
          matching setProductSize step, used by the gateway as the lookup
          key into the stock-read-back map.
        * `stock_id` — pre-populated to None; the gateway overwrites it
          at execute time with the looked-up stock_id, or skips the step
          with a clear warning when no stock entry exists for that size
          (admin must initialize stock in OPS UI first; the API has no
          way to create initial stock entries).

      action=Add increments existing stock; for fresh products with zero
      starting stock the admin-initialized entry will be 0 and Add brings
      it to the desired quantity.
    """
    return OPSMutationStep(
        step=step_num,
        mutation="updateProductStock",
        source_key=f"variant_sku:{variant_sku}",
        variables={
            "action": "Add",
            # _size_id_ref is a gateway-only sentinel (prefixed with _ to
            # mark it as not-part-of-the-OPS-mutation). The gateway strips
            # it before sending and uses it to find the stock_id.
            "_size_id_ref": _placeholder(size_step, "size_id"),
            "input": {
                "stock_quantity": inventory,
            },
        },
        requires_response_from=[size_step],
    )


def _build_setProductsImageGallery_step(
    step_num: int, ctx: _PushContext, products_id_step: int = 1
) -> Optional[OPSMutationStep]:
    """One setProductsImageGallery for the whole product.

    OPS has no file-upload mutation; images are referenced by URL in each
    item's `products_large_image_name`, and OPS fetches + optimizes them
    server-side when optimizeimg=1 (verified live against staging — see
    `scripts/ops_image_spike.py`). Depends on step 1 for products_id; OPS
    returns that id as a string but this mutation needs a top-level Int!, so
    the gateway coerces it at execute time.

    Returns None when the product has no usable image URLs (nothing to push).
    """
    if not ctx.images:
        return None
    title = ctx.product.product_name or ctx.product.supplier_sku
    image_arr = [
        {
            "products_image_gallery_id": 0,  # 0 = create
            "delete": 0,
            "title": title,
            "products_large_image_name": img.url,
            "sort_order": (img.sort_order or idx),
            "status": "1",
        }
        for idx, img in enumerate(ctx.images)
        if img.url
    ]
    if not image_arr:
        return None
    return OPSMutationStep(
        step=step_num,
        mutation="setProductsImageGallery",
        source_key=f"images:{ctx.product.supplier_sku}",
        variables={
            "products_id": _placeholder(products_id_step, "products_id"),
            "optimizeimg": 1,
            "input": {"image_arr": image_arr},
        },
        requires_response_from=[products_id_step],
    )


# ---------------------------------------------------------------------------
# Public entrypoint: build_push_payload()
# ---------------------------------------------------------------------------


async def build_push_payload(
    db: AsyncSession,
    customer_id: UUID,
    product_id: UUID,
    *,
    option_strategy: OptionStrategy = OptionStrategy.MASTER_OPTION_ATTACH,
) -> OPSPushPayload:
    """Async DB wrapper. Loads context, then calls `_synthesize_payload`.

    Splitting the DB load from the pure synthesis lets unit tests build
    the payload without a live session by constructing a `_PushContext`
    directly (see test_payload_builder.py).
    """
    ctx = await _load_context(db, customer_id, product_id)
    return _synthesize_payload(ctx, option_strategy)


def _synthesize_payload(
    ctx: _PushContext,
    option_strategy: OptionStrategy = OptionStrategy.MASTER_OPTION_ATTACH,
) -> OPSPushPayload:
    """Pure synthesis from a loaded `_PushContext`.

    M1 owns Bug 3 fix internally: markup is applied here, not in a
    downstream caller. The returned `OPSPushPayload.computed_prices`
    still carries the per-variant prices for audit / quoting; the mutation
    plan itself embeds a single base price (cheapest variant) on the
    placeholder size row.

    Mutation order (Phase 8 apparel rewrite — verified against live OPS
    81-op collection 2026-06-17):
       step 1   : setProduct
       step 2   : setProductSize × 1  (placeholder "Default")
       steps 3-8: setProductPrice × 6 (APPAREL_VOLUME_TIERS qty-based curve)
       step 9   : setAdditionalOption  (Color group)
       steps 10+: setAdditionalOptionAttributes × C  (each unique color)
       next     : setAdditionalOption  (Size group)
       next+    : setAdditionalOptionAttributes × S  (each unique size)
       next+    : setProductsAttributePrice × S      (per-size sell price)
       [opt]    : setProductsImageGallery   (OPS_PUSH_INCLUDE_IMAGES=1)
       [opt]    : updateProductStock × 1    (OPS_PUSH_INCLUDE_STOCK=1, total qty)

    Note: `multiplier`/`multiplier_type` are NOT fields on AdditionalOptionInput
    (verified against live schema — they do not exist). Per-size pricing is
    handled entirely by setProductsAttributePrice keyed on attribute_id.

    The `option_strategy` parameter is retained for API back-compat but no
    longer branches behavior — the apparel flow is the single canonical path.
    """
    customer_id = ctx.customer.id
    product_id = ctx.product.id

    # ---- Resolve markup rule + compute per-variant prices ----
    rule = resolve_rule(
        ctx.markup_rules,
        supplier_sku=ctx.product.supplier_sku,
        category=ctx.product.category,
        supplier_slug=ctx.supplier.slug,
    )

    # ---- Order variants deterministically (Rev 1 + Rev 3 P2.5) ----
    ordered_variants = sorted(ctx.variants, key=_variant_sort_key)

    # Storefront overrides — must match the customer-quote path byte-for-byte
    # or a customer can be quoted one price and have a different price pushed
    # to OPS. Shared pure helper lives in pricing.overrides.
    overrides_dict = (
        ctx.storefront_config.pricing_overrides if ctx.storefront_config else None
    )

    computed_prices: list[OPSComputedPrice] = []
    for v in ordered_variants:
        final = apply_markup(v.base_price, rule)
        override_applied = False
        if final is not None and overrides_dict:
            final, override_applied = apply_pricing_overrides(final, overrides_dict)
            final = to_cents(final)
        variant_sku = v.sku or f"{ctx.product.supplier_sku}-{str(v.id)[:8]}"
        computed_prices.append(
            OPSComputedPrice(
                variant_sku=variant_sku,
                color=v.color,
                size=v.size,
                sort_order=getattr(v, "sort_order", 0) or 0,
                base_price=_to_float(v.base_price) or 0.0,
                final_price=_to_float(final) or 0.0,
                markup_pct=(_to_float(rule.markup_pct) if rule else None),
                markup_amount=(_to_float(rule.markup_amount) if rule else None),
                rounding=(rule.rounding if rule else "none"),
                storefront_override_applied=override_applied,
            )
        )

    # ---- Resolve create vs update mode ----
    existing_ops_id: Optional[int] = None
    push_mode = "create"
    if ctx.push_mapping and ctx.push_mapping.target_ops_product_id:
        existing_ops_id = int(ctx.push_mapping.target_ops_product_id)
        push_mode = "update"

    # ---- Image policy (beta = single primary front image) ----
    primary_image_url: Optional[str] = None
    image_warnings: list[str] = []
    front_images = [img for img in ctx.images if (img.image_type or "front") == "front"]
    if front_images:
        primary_image_url = front_images[0].url
        if len(ctx.images) > 1:
            image_warnings.append(
                f"Beta sends only the primary front image. "
                f"{len(ctx.images) - 1} additional image(s) ignored."
            )
    elif ctx.images:
        primary_image_url = ctx.images[0].url
        image_warnings.append(
            "No front-type image found; using first available image."
        )

    # ---- Compose the mutation plan ----
    #
    # Phase 8 rewrite — apparel-first model matching reference product 361
    # (visualgraphx OPS staging). Replaces per-variant setProductSize + per-
    # variant setProductPrice with: ONE placeholder setProductSize + ONE
    # base setProductPrice + setAdditionalOption groups for Size/Color whose
    # attributes drive the customer-facing variant pickers. See
    # docs/backlog-ops-additional-options.md for the full rationale.
    plan: list[OPSMutationStep] = []

    # Step 1: setProduct
    plan.append(_build_setProduct_step(ctx, push_mode, existing_ops_id, primary_image_url))

    # Step 2: setProductSize placeholder (OPS requires at least one size row
    # even when variant selection comes from Additional Options).
    placeholder_size_step = 2
    plan.append(_build_setProductSize_placeholder_step(placeholder_size_step))
    next_step = 3

    # Step 3+: 6 setProductPrice rows for the standard apparel volume curve
    # (APPAREL_VOLUME_TIERS). Mirrors reference product 361's 6-tier shape.
    # Per-size variation lives on each setAdditionalOption's `multiplier`,
    # applied on top of whichever tier the customer's qty lands in.
    if computed_prices:
        base_final = min(p.final_price for p in computed_prices)
        base_vendor = min(p.base_price for p in computed_prices)
        for qty_from, qty_to, factor in APPAREL_VOLUME_TIERS:
            plan.append(
                _build_setProductPrice_step(
                    next_step,
                    placeholder_size_step,
                    "placeholder",
                    round(base_vendor * factor, 2),
                    round(base_final * factor, 2),
                    qty_from=qty_from,
                    qty_to=qty_to,
                    source_key_suffix=f"qty{qty_from}-{qty_to}",
                )
            )
            next_step += 1

    # ── Apparel option groups: Color + Size ───────────────────────────────────
    #
    # Architecture (live OPS 81-op collection, 2026-06-17):
    #   1. One setAdditionalOption parent group per dimension (Color, Size).
    #   2. Each value (Red, S, 2XL …) added as setAdditionalOptionAttributes
    #      child → returns attribute_id.
    #   3. Per-size pricing attached via setProductsAttributePrice using
    #      attribute_id — this replaces the invalid multiplier/multiplier_type
    #      approach (those fields do not exist on AdditionalOptionInput).
    #   Colors have no price variation; only Size gets attribute price steps.

    colors, sizes = _extract_attribute_values(ordered_variants)

    # Per-size price lookup: size label → (base_price, final_price).
    # Same size in multiple colors → take the min (SanMar standard practice).
    base_final = min((p.final_price for p in computed_prices), default=0.0)
    size_to_prices: dict[str, tuple[float, float]] = {}
    for p in computed_prices:
        sz = (p.size or "").strip()
        if not sz:
            continue
        existing = size_to_prices.get(sz)
        if existing is None or p.final_price < existing[1]:
            size_to_prices[sz] = (p.base_price, p.final_price)

    # Color group + color attributes (no price steps needed).
    color_group_step = next_step
    plan.append(_build_apparel_option_group_step(color_group_step, "color", "Color", sort_order=0))
    next_step += 1
    for i, color in enumerate(colors):
        plan.append(_build_apparel_option_attribute_step(
            next_step, color_group_step, "color", color, sort_order=i
        ))
        next_step += 1

    # Size group + size attributes + per-size price steps.
    size_group_step = next_step
    plan.append(_build_apparel_option_group_step(
        size_group_step, "size", "Size", sort_order=len(colors)
    ))
    next_step += 1
    size_attr_steps: list[tuple[str, int]] = []  # (size_value, attr_step_num)
    for i, size_val in enumerate(sizes):
        plan.append(_build_apparel_option_attribute_step(
            next_step, size_group_step, "size", size_val, sort_order=i
        ))
        size_attr_steps.append((size_val, next_step))
        next_step += 1

    # setProductsAttributePrice per size — depends on each size attribute step.
    for size_val, attr_step in size_attr_steps:
        base_p, final_p = size_to_prices.get(size_val, (base_final, base_final))
        plan.append(_build_apparel_attribute_price_step(
            next_step, attr_step, size_val, base_p, final_p
        ))
        next_step += 1

    # Image gallery — pushes product images via setProductsImageGallery.
    # DEFERRED by default (opt in with OPS_PUSH_INCLUDE_IMAGES=1): OPS does NOT
    # fetch external URLs — it treats `products_large_image_name` as a filename
    # inside its own media library and prepends its CDN path, so passing a
    # supplier/CDN URL produces a broken path (verified via
    # scripts/ops_image_readback.py on #547) and pollutes the gallery with dead
    # rows. The step is wired and ready; enable it once images are uploaded into
    # OPS media and we pass bare OPS filenames. Placed before stock so inventory
    # stays the final step (Rev 1 contract). Best-effort/warn-only in the gateway.
    import os as _os

    if _os.getenv("OPS_PUSH_INCLUDE_IMAGES", "0") == "1":
        gallery_step = _build_setProductsImageGallery_step(next_step, ctx, products_id_step=1)
        if gallery_step is not None:
            plan.append(gallery_step)
            next_step += 1

    # Stock — apparel rewrite collapses per-variant stock into ONE write
    # against the placeholder size, since variant selection now flows through
    # Additional Options (no per-variant size_id exists). Total inventory =
    # sum of all variant inventories. Per-attribute stock tracking will
    # require a separate model once OPS exposes a per-attribute stock mutation.
    # Deferred by default: opt in with OPS_PUSH_INCLUDE_STOCK=1.
    if _os.getenv("OPS_PUSH_INCLUDE_STOCK", "0") == "1":
        total_inventory = sum((v.inventory or 0) for v in ordered_variants)
        plan.append(
            _build_updateProductStock_step(
                next_step,
                placeholder_size_step,
                "placeholder",
                total_inventory,
            )
        )
        next_step += 1

    client_id = ctx.customer.ops_client_id or ""
    return OPSPushPayload(
        customer_id=customer_id,
        product_id=product_id,
        supplier_slug=ctx.supplier.slug,
        supplier_sku=ctx.product.supplier_sku,
        push_mode=push_mode,
        option_strategy=option_strategy,
        existing_ops_product_id=existing_ops_id,
        computed_prices=computed_prices,
        markup_rule_id=(rule.id if rule else None),
        plan=plan,
        primary_image_url=primary_image_url,
        image_warnings=image_warnings,
        estimated_mutations=len(plan),
        ops_target={
            "base_url": ctx.customer.ops_base_url,
            "client_id_last4": client_id[-4:] if client_id else "",
        },
    )


__all__ = [
    "OptionStrategy",
    "OPSMutationStep",
    "OPSComputedPrice",
    "OPSPushPayload",
    "OPSStepResult",
    "canonicalize_json",
    "compute_payload_hash",
    "build_push_payload",
]
