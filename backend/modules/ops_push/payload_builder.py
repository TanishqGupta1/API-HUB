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


def _ops_product_type(product: Product) -> str:
    """Map our Product.product_type to the OPS setProduct `product_type`
    (sale-type) String.

    All products go to Print Products: "1,2,3" = Custom Design, Upload Centre,
    Browse Design — matching the verified structure of product 600 on staging.
    """
    return "1,2,3"


def _ops_product_type_for_context(product: Product, customer: Customer) -> str:
    """OPS sale-type driven by the storefront's predefined_product_type.

    Print Products (predefined_product_type=0) → "1,2,3" (Custom Design etc).
    Ready To Buy  (predefined_product_type=1) → "15" (Add to cart).
    Verified against TST655 (product 634) on staging.
    """
    predefined = int(getattr(customer, "ops_predefined_product_type", None) or 0)
    if predefined == 1:
        return "15"
    return _ops_product_type(product)


def _build_description_fields(description: Optional[str]) -> dict[str, str]:
    """Split supplier description into OPS short + long description fields.

    OPS has two description slots:
      product_description  — short description shown in product listings
      long_description     — full PDP body

    Supplier feeds give a single blob. First paragraph becomes the short
    description; the full text goes into long_description.
    """
    full = (description or "").strip()
    if "\n" in full:
        short = full.split("\n")[0].strip()
    else:
        short = full
    return {"product_description": short, "long_description": full}


def _customer_prefix(customer: Customer, supplier: Supplier) -> str:
    """Customer-prefixed title rule: prefer supplier.push_name_prefix
    (already configured per supplier in current DB), fall back to
    UPPERCASE first two letters of supplier slug + dash."""
    return supplier.push_name_prefix or f"{supplier.slug[:2].upper()}-"


# ---------------------------------------------------------------------------
# Mutation step builders
# ---------------------------------------------------------------------------


def _desc_to_html(text: str) -> str:
    """Convert newline-separated plain text description to an HTML list for OPS WYSIWYG editor."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return ""
    return "<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"


def _build_setProduct_step(
    ctx: _PushContext,
    push_mode: str,
    existing_ops_id: Optional[int],
    primary_image_url: Optional[str],
    enable_stock_management: str = "1",
    category_id_override: Optional[int] = None,
    large_image_url: Optional[str] = None,
) -> OPSMutationStep:
    """setProduct is always step 1 (no more separate setProductCategory).

    create mode: products_id omitted (or 0).
    update mode: products_id = existing OPS product id from push_mappings.

    `enable_stock_management` (Int enum, sent as a String) MUST align with the
    sku_type used by every setProductSku step (AI-3): `1` (Only Size) ↔
    `size_wise`, `2` (Size with Product Option) ↔ `size_option_wise`. The
    caller derives it once per product and threads it here.
    """
    title = f"{_customer_prefix(ctx.customer, ctx.supplier)}{ctx.product.product_name}"
    # Field names verified against OPS's live ProductInput schema:
    #   - product_description  (NOT products_description)
    #   - imagename            (NOT products_image)
    #   - category_id (Int)    (NOT category_name) — sourced from the storefront
    #     mapping; omitted when unmapped (category is optional) so the push
    #     isn't blocked while category mapping is still being set up.
    #   - `brand` dropped — ProductInput has no brand field.
    inp: dict[str, Any] = {
        "products_id": existing_ops_id if push_mode == "update" else 0,
        "products_title": title,
        "products_internal_title": ctx.product.supplier_sku,
        # main_sku is OPS's product-level SKU (set via setProduct per OPS docs:
        # "To set the main product SKU, use the setProduct mutation with the
        # main_sku field"). It MUST equal the supplier_sku because the gateway's
        # pre-push dedup (_dedup_lookup_in_ops → find_product_id_by_main_sku)
        # matches OPS products on main_sku — otherwise it can never find a
        # product we created, and a re-push without a local push_mapping creates
        # a duplicate in OPS instead of replacing the existing product.
        "main_sku": ctx.product.supplier_sku,
        "visible": 1,
        # OPS has three description slots (verified against OPS Postman docs):
        #   product_description    → "Short Description" (listings / cards)
        #   long_description       → "Long Description"  (PDP body)
        #   long_description_two   → "Long Description 2" (PDP secondary tab)
        # Supplier feeds (e.g. SanMar PromoStandards) give us a single blob of
        # marketing copy, so we mirror it into both Short and Long. Without
        # long_description, the OPS storefront PDP shows an empty description tab
        # even though Short is populated.
        **_build_description_fields(ctx.product.description),
        # ── Required OPS ProductInput fields for all products ──────────
        # Phase 1 audit findings (June 2026):
        #   * predefined_product_type — silent reject when null
        #   * price_defining_method — silent reject of "qty" string;
        #     OPS expects a numeric string. "1" = qty-based pricing
        #     (verified against working products on staging.visualgraphx)
        #   * measurement_unit_id — silent reject when 0/null
        #   * enable_stock_management — required for updateProductStock
        #     to find variants; without it, all stock writes fail. Int enum
        #     (0 None / 1 Only Size / 2 Size with Product Option); MUST match
        #     setProductSku.sku_type (AI-3) or SKUs stay unregistered for
        #     stock → "Invalid Product SKU".
        #   * product_type — OPS sale-type, comma-separated String (1 Custom
        #     Design · 2 Upload Center · 3 Browse Design · 7 Quote · 8 Hire
        #     Designer · 15 Add to cart). Apparel sold from stock → "15";
        #     anything else keeps "1" (Custom Design). NOTE: distinct from our
        #     Product.product_type ("apparel"/"print"). See _ops_product_type.
        #   * price_defining_method — "1" (qty-based) verified working on
        #     staging.visualgraphx. AI-8 TODO: confirm the right value for a
        #     stock apparel product by mirroring a known-good LIVE product via
        #     productsDetails before flipping it (the collection template shows
        #     "3", but that's not a verified apparel-from-stock product).
        "predefined_product_type": str(
            getattr(ctx.customer, "ops_predefined_product_type", None) or 0
        ),
        "price_defining_method": "1",
        "measurement_unit_id": 1,
        "enable_stock_management": enable_stock_management,
        "product_type": _ops_product_type_for_context(ctx.product, ctx.customer),
        # product_service_type is a REQUIRED ProductInput field per the OPS
        # setProduct docs ("Must be 1 always"). OPS currently tolerates its
        # absence, but the contract marks it required — send "1" explicitly
        # so a future OPS validation tightening doesn't silently fail pushes.
        # (String in the schema, despite the docs showing an Int example.)
        "product_service_type": "1",
    }
    # Category resolution order:
    #   1. category_id_override — the gateway's auto-category resolver created/
    #      looked up the OPS category matching this product's category name.
    #   2. per-product storefront override.
    #   3. per-customer default_ops_category_id (Phase 2 of the OPS push audit).
    # Without a category, OPS hides the product from the admin's default browse
    # view, so we want a sensible fallback.
    _cat = category_id_override \
        or (ctx.storefront_config.ops_category_id if ctx.storefront_config else None) \
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
        # `imagename` → Description page "Small Image" slot
        # `product_desc_image` → "Large Image" slot
        # OPS requires two distinct filenames; if we send the same file for
        # both, it stores only the small image. Use large_image_url (a second
        # product image) when available, otherwise fall back to primary.
        inp["imagename"] = primary_image_url.rsplit("/", 1)[-1]
        large_url = large_image_url if large_image_url else primary_image_url
        inp["product_desc_image"] = large_url.rsplit("/", 1)[-1]
    variables: dict[str, Any] = {"inputs": [inp]}

    return OPSMutationStep(
        step=1,
        mutation="setProduct",
        source_key=f"supplier_sku:{ctx.product.supplier_sku}",
        variables=variables,
        requires_response_from=[],
    )


def _build_setProductSize_step(
    step_num: int, variant: ProductVariant, variant_sku: str
) -> OPSMutationStep:
    """One setProductSize per variant. Depends on step 1 for products_id."""
    color = (variant.color or "").strip()
    size = (variant.size or "").strip()
    if color and size:
        size_title = f"{color} / {size}"
    else:
        size_title = color or size or variant_sku
    return OPSMutationStep(
        step=step_num,
        mutation="setProductSize",
        source_key=f"variant_sku:{variant_sku}",
        variables={
            "inputs": [{
                "products_id": _placeholder(1, "products_id"),
                "size_title": size_title,
                "visible": "1",  # OPS ProductSizeInput.visible is String
            }]
        },
        requires_response_from=[1],
    )


def _build_setProductSize_titled(step_num: int, size_title: str) -> OPSMutationStep:
    """One setProductSize for a physical size title (apparel color+size mode).
    Creates a designer canvas entry keyed by size name (e.g. "S", "M", "XL"),
    not by the full color+size combo.
    """
    return OPSMutationStep(
        step=step_num,
        mutation="setProductSize",
        source_key=f"size:{size_title}",
        variables={
            "inputs": [{
                "products_id": _placeholder(1, "products_id"),
                "size_title": size_title,
                "visible": "1",
            }]
        },
        requires_response_from=[1],
    )


def _build_setAdditionalOption_from_values(
    step_num: int,
    *,
    option_key: str,
    title: str,
    sort_order: int = 0,
) -> OPSMutationStep:
    """Build a setAdditionalOption step from raw values (no ORM object).

    price_calculate_type="1" (Fixed) is required by OPS — omitting it causes
    OPS_REJECTED: Price Calculation Type is required. "1" = fixed price adder,
    which is correct for colour/size selectors that carry no extra cost.
    """
    return OPSMutationStep(
        step=step_num,
        mutation="setAdditionalOption",
        source_key=f"option_key:{option_key}",
        variables={
            "inputs": [{
                "products_id": _placeholder(1, "products_id"),
                "option_key": option_key,
                "title": title,
                "options_type": "combo",
                "sort_order": sort_order,
                "price_calculate_type": "1",
                "hire_designer_option": "0",
                "status": "1",
            }]
        },
        requires_response_from=[1],
    )


def _build_setAdditionalOptionAttribute_from_values(
    step_num: int,
    option_step: int,
    *,
    attribute_key: str,
    label: str,
    sort_order: int = 0,
) -> OPSMutationStep:
    """Build a setAdditionalOptionAttributes step from raw values (no ORM object)."""
    return OPSMutationStep(
        step=step_num,
        mutation="setAdditionalOptionAttributes",
        source_key=f"attribute_key:color/{attribute_key}",
        variables={
            "inputs": [{
                "prod_add_opt_id": _placeholder(option_step, "prod_add_opt_id"),
                "attribute_key": attribute_key,
                "label": label,
                "setup_cost": 0.0,
                "multiplier": 1.0,
            }]
        },
        requires_response_from=[option_step],
    )


def _build_setProductsAttributePrice_step(
    step_num: int,
    attr_step: int,
    product_step: int,
    size_step: int,
    *,
    attributes_price: float,
    vendor_price: float,
) -> OPSMutationStep:
    """Set a per-attribute price upcharge via setProductsAttributePrice.

    This is the correct OPS mutation for "Additional Options Price" —
    the page visible at /admin/product_additionalinfo_price.php.
    OPS requires ALL of (product_id, attribute_id, size_id, size_from, size_to):
      - product_id   ← setProduct response (product_step)
      - attribute_id ← setAdditionalOptionAttributes response (attr_step)
      - size_id      ← setProductSize response (size_step, the "Default" canvas)
      - size_from / size_to ← the qty/size range; 1..999999 = any quantity.
    Verified live on staging: omitting size_id → INVALID_OPERATION; omitting
    size_from → "Size From is required"; omitting product_id → "Cannot read
    properties of undefined (reading 'products_id')". All five are mandatory.
    attributes_price = final (customer) upcharge; vendor_price = wholesale upcharge.
    """
    return OPSMutationStep(
        step=step_num,
        mutation="setProductsAttributePrice",
        source_key=f"attr_price:step{attr_step}",
        variables={
            "inputs": [{
                "product_id": _placeholder(product_step, "products_id"),
                "attribute_id": _placeholder(attr_step, "attribute_id"),
                "size_id": _placeholder(size_step, "size_id"),
                "size_from": 1,
                "size_to": 999999,
                "attributes_price": attributes_price,
                "vendor_price": vendor_price,
                "delete": 0,
            }]
        },
        requires_response_from=[attr_step, product_step, size_step],
    )


def _build_setProductPrice_step(
    step_num: int,
    size_step: int,
    variant_sku: str,
    base_price: float,
    final_price: float,
) -> OPSMutationStep:
    """One setProductPrice per variant — sends the supplier's actual price
    as-is (qty=1, qty_to=999999). No synthetic volume tiers."""
    return OPSMutationStep(
        step=step_num,
        mutation="setProductPrice",
        source_key=f"variant_sku:{variant_sku}",
        variables={
            "inputs": [{
                "products_id": _placeholder(1, "products_id"),
                "size_id": _placeholder(size_step, "size_id"),
                "qty": 1,
                "qty_to": 999999,
                "price": final_price,
                "vendor_price": base_price,
                "visible": "1",
                "user_type_id": "1",
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
                "price_calculate_type": "1",
                "hire_designer_option": "0",
                "status": "1",
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


def _build_setProductSku_step(
    step_num: int,
    size_step: int,
    variant_sku: str,
    *,
    sku_type: str,
    option_attr_pairs: Optional[list[tuple[int, int]]] = None,
) -> OPSMutationStep:
    """Assign a per-variant SKU to the OPS product (setProductSku).

    ``sku_type`` is a PRODUCT-LEVEL decision (AI-3): OPS allows only one SKU
    method per product and it MUST match setProduct.enable_stock_management
    (`size_wise`↔1, `size_option_wise`↔2). The caller passes the same value
    for every variant of a product, so the modes can never mix.

    ``size_wise`` — the variant is keyed on size_id alone (every current SanMar
    product: colors aren't modeled as OPS options yet, each variant is a size).
    ``size_option_wise`` — the variant keys on one or more (option, attribute)
    pairs (e.g. Color + Size). ``option_attr_pairs`` is a list of
    (option_step, attribute_step) tuples; placeholders are resolved to OPS ids
    and comma-joined by the gateway into prod_add_opt_ids / attribute_ids
    strings (setProductSku declares both as String!).
    """
    inp: dict[str, Any] = {
        "products_id": _placeholder(1, "products_id"),
        "size_id": _placeholder(size_step, "size_id"),
        "sku": variant_sku,
        "delete": 0,
        "sku_type": sku_type,
    }
    requires = [1, size_step]
    if sku_type == "size_option_wise" and option_attr_pairs:
        inp["prod_add_opt_ids"] = [
            _placeholder(opt_step, "prod_add_opt_id") for opt_step, _ in option_attr_pairs
        ]
        inp["attribute_ids"] = [
            _placeholder(attr_step, "attribute_id") for _, attr_step in option_attr_pairs
        ]
        for opt_step, attr_step in option_attr_pairs:
            requires += [opt_step, attr_step]
    return OPSMutationStep(
        step=step_num,
        mutation="setProductSku",
        source_key=f"sku:{variant_sku}",
        variables={"inputs": [inp]},
        requires_response_from=requires,
    )


def _build_updateProductStock_step(
    step_num: int, variant_sku: str, inventory: int
) -> OPSMutationStep:
    """Set available stock for one variant via updateProductStock.

    Inventory is the LAST stage per Rev 1 §"PC61 outbound mutation sequence",
    and it MUST run after the setProductSku stage: it identifies the variant by
    `product_sku` — the same SKU setProductSku assigns in OPS. Because that SKU
    now exists, we no longer need the old stock_id read-back (a
    productStocks(product_id) lookup that skipped variants with no
    admin-initialized stock entry). OPS resolves the variant straight from
    product_sku.

    action="Reset" sets the absolute available quantity to `inventory`. This
    keeps re-pushes idempotent: now that dedup routes a re-push through update
    mode, "Add"/"Remove" would drift the count on every push, whereas "Reset"
    always lands on the supplier's current inventory.
    """
    return OPSMutationStep(
        step=step_num,
        mutation="updateProductStock",
        source_key=f"stock:{variant_sku}",
        variables={
            "product_sku": variant_sku,
            "action": "Reset",
            "input": {
                "stock_quantity": inventory,
                "comment": "Synced from API-HUB",
            },
        },
        requires_response_from=[],
    )


def _build_setProductsImageGallery_step(
    step_num: int,
    ctx: _PushContext,
    products_id_step: int = 1,
    color_attr_steps: Optional[dict[str, tuple[int, int]]] = None,
) -> Optional[OPSMutationStep]:
    """One setProductsImageGallery for the whole product.

    OPS has no file-upload mutation; images are referenced by URL in each
    item's `products_large_image_name`, and OPS fetches + optimizes them
    server-side when optimizeimg=1 (verified live against staging — see
    `scripts/ops_image_spike.py`). Depends on step 1 for products_id; OPS
    returns that id as a string but this mutation needs a top-level Int!, so
    the gateway coerces it at execute time.

    ``color_attr_steps`` (apparel mode only): mapping of lowercased color name
    → (color_option_step, color_attribute_step). When an image carries a color
    matching one of these keys, the row is tagged with ``option_id`` /
    ``attribute_id`` (placeholders the gateway resolves to OPS ids), so the
    OPS storefront swaps the main image when the customer picks that color.

    Returns None when the product has no usable image URLs (nothing to push).
    """
    if not ctx.images:
        return None
    title = ctx.product.product_name or ctx.product.supplier_sku
    color_attr_steps = color_attr_steps or {}
    image_arr: list[dict[str, Any]] = []
    extra_requires: set[int] = set()
    for idx, img in enumerate(ctx.images):
        if not img.url:
            continue
        row: dict[str, Any] = {
            "products_image_gallery_id": 0,  # 0 = create
            "delete": 0,
            "title": title,
            "products_large_image_name": img.url,
            "sort_order": (img.sort_order or idx),
            "status": "1",
        }
        color_key = (img.color or "").strip().lower()
        pair = color_attr_steps.get(color_key) if color_key else None
        if pair:
            opt_step, attr_step = pair
            row["option_id"] = _placeholder(opt_step, "prod_add_opt_id")
            row["attribute_id"] = _placeholder(attr_step, "attribute_id")
            extra_requires.update((opt_step, attr_step))
        image_arr.append(row)
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
        requires_response_from=sorted({products_id_step, *extra_requires}),
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
    category_id_override: Optional[int] = None,
) -> OPSPushPayload:
    """Async DB wrapper. Loads context, then calls `_synthesize_payload`.

    Splitting the DB load from the pure synthesis lets unit tests build
    the payload without a live session by constructing a `_PushContext`
    directly (see test_payload_builder.py).

    category_id_override: when set, this OPS category_id wins over the
    storefront-config / customer-default resolution. The gateway's auto-category
    resolver passes the id it created/looked up for the product's category name.
    """
    ctx = await _load_context(db, customer_id, product_id)
    return _synthesize_payload(ctx, option_strategy, category_id_override=category_id_override)


def _synthesize_payload(
    ctx: _PushContext,
    option_strategy: OptionStrategy = OptionStrategy.MASTER_OPTION_ATTACH,
    *,
    category_id_override: Optional[int] = None,
) -> OPSPushPayload:
    """Pure synthesis from a loaded `_PushContext`.

    M1 owns Bug 3 fix internally: markup is applied here, not in a
    downstream caller. The returned `OPSPushPayload.computed_prices`
    is the customer-facing sell price; the mutation plan embeds those
    values directly into each `setProductPrice.price` variable.

    Mutation order (locked, Rev 1):
       step 1            : setProduct
       steps 2 .. 1+N    : setProductSize × N (sorted)
       steps 2+N .. 1+2N : setProductPrice × N (depends on matching size step)
       option steps      : setAssignOptions × M   (master_option_attach mode)
                       OR : setAdditionalOption + setAdditionalOptionAttributes
                            (product_local_option_create mode)
       final N steps     : updateProductStock × N (action=Reset)
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
    # Selection order: `primary` (the authoritative catalog hero shot) →
    # `front` (any front-facing image, but includes swatches & model shots)
    # → first available. Without the `primary` preference, F236 et al. land
    # the color-swatch (e.g. F236sw.jpg) as the small_image because it sorts
    # first among the `front`-typed rows.
    primary_image_url: Optional[str] = None
    image_warnings: list[str] = []
    primary_images = [img for img in ctx.images if (img.image_type or "") == "primary"]
    front_images = [img for img in ctx.images if (img.image_type or "front") == "front"]
    if primary_images:
        primary_image_url = primary_images[0].url
    elif front_images:
        primary_image_url = front_images[0].url
    elif ctx.images:
        primary_image_url = ctx.images[0].url
        image_warnings.append(
            "No front-type image found; using first available image."
        )
    # Large image: pick the first image that differs from primary_image_url so
    # OPS stores distinct filenames in the Small and Large image slots.
    large_image_url: Optional[str] = None
    for _img in ctx.images:
        if _img.url and _img.url != primary_image_url:
            large_image_url = _img.url
            break
    if not large_image_url and ctx.product.image_url and ctx.product.image_url != primary_image_url:
        large_image_url = ctx.product.image_url

    if primary_image_url and len(ctx.images) > 1:
        image_warnings.append(
            f"Beta sends only the primary front image. "
            f"{len(ctx.images) - 1} additional image(s) ignored."
        )

    # ---- Detect apparel (color+size) vs size-only/print mode ----
    # When variants carry colors (apparel), OPS Additional Options must represent
    # Color and Size separately. Previously the code created one setProductSize per
    # color+size COMBO (e.g. "Blueberry / 6XL") which caused every combo to appear
    # as a designer canvas template instead of appearing in Additional Options.
    has_colors = any((v.color or "").strip() for v in ordered_variants)

    # ---- Compose the mutation plan ----
    plan: list[OPSMutationStep] = []
    next_step = 2
    size_step_by_sku: dict[str, int] = {}
    attr_step_by_value: dict[str, tuple[int, int]] = {}

    if has_colors:
        # Apparel mode: a SINGLE "Default" Designer canvas, both Color and Size
        # exposed as Additional Option dropdowns. OPS requires at least one
        # setProductSize entry for the storefront UI to render at all, so we
        # send one "Default" canvas; the physical sizes (S/M/L/XL/...) live as
        # Size attribute values instead, matching the apparel pattern where the
        # customer picks both dropdowns at checkout.
        # enable_stock_management=0 (None): decorated print apparel is made-to-order,
        # no stock tracking — avoids "Invalid Product SKU or initial stock not added!"
        # errors from updateProductStock for SKUs OPS hasn't initialized stock for.
        enable_stock_management = "0"
        sku_type = "size_option_wise"

        plan.append(_build_setProduct_step(
            ctx, push_mode, existing_ops_id, primary_image_url,
            enable_stock_management=enable_stock_management,
            category_id_override=category_id_override,
            large_image_url=large_image_url,
        ))

        # Extract unique physical sizes in first-appearance order
        seen_s: dict[str, None] = {}
        for v in ordered_variants:
            s = (v.size or "").strip()
            if s:
                seen_s[s] = None
        unique_sizes = list(seen_s.keys()) or ["Default"]

        # Extract unique colors in first-appearance order
        seen_c: dict[str, None] = {}
        for v in ordered_variants:
            c = (v.color or "").strip()
            if c:
                seen_c[c] = None
        unique_colors = list(seen_c.keys())

        # Detect "no real size choice": single size or only OSFA-style labels.
        # Bags, many caps, and other accessories have one universal size —
        # showing a Size dropdown with one value is confusing and serves no
        # purpose for the customer. Skip the Size option in those cases.
        _SINGLE_SIZE_LABELS = {"osfa", "one size", "one size fits all", "os", "n/a", "default"}
        # Filter junk labels BEFORE counting so a product with two junk labels
        # (e.g. OSFA + OS, or OSFA + N/A from dirty supplier data) is still
        # treated as "no real size choice" and skips the pointless dropdown.
        _real_size_vals = [
            s for s in unique_sizes if s.strip().lower() not in _SINGLE_SIZE_LABELS
        ]
        _has_real_sizes = len(_real_size_vals) >= 1

        # ONE setProductSize "Default" — OPS requires at least one canvas to
        # render the storefront purchase panel. The user picks size via the
        # Size Additional Option below, not via the canvas selector.
        default_size_step = next_step
        plan.append(_build_setProductSize_titled(next_step, "Default"))
        next_step += 1

        # All variant SKUs key on the single "Default" canvas
        for v, price in zip(ordered_variants, computed_prices):
            size_step_by_sku[price.variant_sku] = default_size_step

        # Dynamic per-attribute price upcharge calculation.
        # For EACH option axis (size AND color) find the cheapest variant
        # carrying each attribute value. The canvas is the single globally
        # cheapest variant; every attribute value that costs more than the
        # canvas carries the difference as an OPS "Additional Options Price"
        # upcharge. Whichever axis (or both) drives the price, the upcharge
        # follows the data — no axis is hard-coded.
        #
        # NOTE (OPS limitation, not a bug): OPS adds option upcharges
        # ADDITIVELY (size upcharge + color upcharge). That is exact when the
        # price is driven by a single axis. When BOTH axes independently raise
        # the price of the same variant, the additive sum can over-state that
        # specific combo — OPS's per-attribute pricing model cannot express a
        # per-(color×size) price through setProductsAttributePrice.
        _size_final_price: dict[str, float] = {}   # size_lower  → cheapest final price
        _size_base_price: dict[str, float] = {}    # size_lower  → matching vendor price
        _color_final_price: dict[str, float] = {}  # color_lower → cheapest final price
        _color_base_price: dict[str, float] = {}   # color_lower → matching vendor price
        for cp in computed_prices:
            sk = (cp.size or "").strip().lower()
            if sk and (sk not in _size_final_price or cp.final_price < _size_final_price[sk]):
                _size_final_price[sk] = cp.final_price
                _size_base_price[sk] = cp.base_price
            ck = (cp.color or "").strip().lower()
            if ck and (ck not in _color_final_price or cp.final_price < _color_final_price[ck]):
                _color_final_price[ck] = cp.final_price
                _color_base_price[ck] = cp.base_price

        # Canvas = the single cheapest variant by final price. Taking cost AND
        # price from the SAME variant keeps the published (vendor_price, price)
        # pair consistent — two independent min()s could otherwise pull cost
        # from one variant and price from another, understating the margin.
        _canvas_cp = (
            min(computed_prices, key=lambda cp: cp.final_price)
            if computed_prices else None
        )
        _canvas_final = _canvas_cp.final_price if _canvas_cp else 0.0
        _canvas_base = _canvas_cp.base_price if _canvas_cp else 0.0

        # ONE setProductPrice for the Default canvas — the cheapest size price.
        # Size upcharges are handled via setup_cost on the Size attributes below.
        if _canvas_cp is not None:
            plan.append(_build_setProductPrice_step(
                next_step, default_size_step,
                _canvas_cp.variant_sku,
                _canvas_base, _canvas_final,
            ))
            next_step += 1

        # Color Additional Option + one attribute per unique color
        color_option_step = next_step
        plan.append(_build_setAdditionalOption_from_values(
            next_step, option_key="color", title="Color", sort_order=0,
        ))
        next_step += 1
        for i, color_val in enumerate(unique_colors):
            attr_step = next_step
            plan.append(_build_setAdditionalOptionAttribute_from_values(
                next_step, color_option_step,
                attribute_key=color_val.lower().replace(" ", "_"),
                label=color_val, sort_order=i,
            ))
            attr_step_by_value[color_val.lower()] = (color_option_step, attr_step)
            next_step += 1

            # If this color costs more than the canvas (e.g. a premium colour),
            # push the difference as an Additional Options Price upcharge so the
            # pricier colour isn't silently sold at the cheapest colour's price.
            ck = color_val.strip().lower()
            _c_final_upcharge = round(
                max(0.0, _color_final_price.get(ck, _canvas_final) - _canvas_final), 2
            )
            _c_vendor_upcharge = round(
                max(0.0, _color_base_price.get(ck, _canvas_base) - _canvas_base), 2
            )
            if _c_final_upcharge > 0:
                plan.append(_build_setProductsAttributePrice_step(
                    next_step, attr_step, 1, default_size_step,
                    attributes_price=_c_final_upcharge,
                    vendor_price=_c_vendor_upcharge,
                ))
                next_step += 1

        # Size Additional Option + one attribute per unique physical size.
        # Skipped when there is no real size choice (OSFA / single-size products
        # like bags and many cap styles). This avoids a pointless "Size: OSFA"
        # dropdown that confuses customers and adds no value.
        # Each size carries setup_cost = (size_price - base_price) so OPS adds
        # the correct upcharge automatically when the customer picks that size.
        size_attr_step_by_value: dict[str, tuple[int, int]] = {}
        if _has_real_sizes:
            size_option_step = next_step
            plan.append(_build_setAdditionalOption_from_values(
                next_step, option_key="size", title="Size", sort_order=1,
            ))
            next_step += 1
            for i, size_val in enumerate(unique_sizes):
                attr_step = next_step
                sk = size_val.strip().lower()
                plan.append(_build_setAdditionalOptionAttribute_from_values(
                    next_step, size_option_step,
                    attribute_key=size_val.lower().replace(" ", "_"),
                    label=size_val, sort_order=i,
                ))
                size_attr_step_by_value[size_val.lower()] = (size_option_step, attr_step)
                next_step += 1

                # If this size costs more than the base, push a price upcharge
                # via setProductsAttributePrice — the correct OPS mutation for
                # "Additional Options Price". Only emitted when upcharge > 0.
                _final_upcharge = round(
                    max(0.0, _size_final_price.get(sk, _canvas_final) - _canvas_final), 2
                )
                _vendor_upcharge = round(
                    max(0.0, _size_base_price.get(sk, _canvas_base) - _canvas_base), 2
                )
                if _final_upcharge > 0:
                    plan.append(_build_setProductsAttributePrice_step(
                        next_step, attr_step, 1, default_size_step,
                        attributes_price=_final_upcharge,
                        vendor_price=_vendor_upcharge,
                    ))
                    next_step += 1

    else:
        # Size-only / print mode: one setProductSize per variant (original behaviour)
        sku_type = "size_wise"
        enable_stock_management = "0"

        plan.append(_build_setProduct_step(
            ctx, push_mode, existing_ops_id, primary_image_url,
            enable_stock_management=enable_stock_management,
            category_id_override=category_id_override,
            large_image_url=large_image_url,
        ))

        for v, price in zip(ordered_variants, computed_prices):
            plan.append(_build_setProductSize_step(next_step, v, price.variant_sku))
            size_step_by_sku[price.variant_sku] = next_step
            next_step += 1

        for price in computed_prices:
            size_step = size_step_by_sku[price.variant_sku]
            plan.append(_build_setProductPrice_step(
                next_step, size_step, price.variant_sku,
                price.base_price, price.final_price,
            ))
            next_step += 1

        # Option steps — strategy-dependent (only applies in size-only/print mode)
        if option_strategy is OptionStrategy.MASTER_OPTION_ATTACH:
            for mapping in ctx.push_mapping_options:
                if mapping.target_ops_option_id is None:
                    continue
                plan.append(_build_setAssignOptions_step(next_step, mapping))
                next_step += 1
        else:  # PRODUCT_LOCAL_OPTION_CREATE
            for opt in ctx.options:
                option_step = next_step
                plan.append(_build_setAdditionalOption_step(option_step, opt))
                next_step += 1
                for attr in opt.attributes:
                    attr_step = next_step
                    plan.append(_build_setAdditionalOptionAttributes_step(
                        attr_step, option_step, opt.option_key, attr
                    ))
                    for val in (attr.title, attr.attribute_key):
                        if val:
                            attr_step_by_value.setdefault(val.strip().lower(), (option_step, attr_step))
                    next_step += 1

    import os as _os

    # Per-variant SKU assignment via setProductSku.
    # Always included for color products (size_option_wise) — OPS can't track
    # apparel stock without SKUs keyed on (size_id, color attribute). For size-only
    # products, opt in with OPS_PUSH_INCLUDE_SKU=1.
    if has_colors or _os.getenv("OPS_PUSH_INCLUDE_SKU", "0") == "1":
        for v, price in zip(ordered_variants, computed_prices):
            size_step = size_step_by_sku[price.variant_sku]
            # sku_type is the product-level decision above; option/attribute
            # placeholders are only meaningful in size_option_wise mode. In
            # apparel mode the variant maps to BOTH Color and Size additional-
            # option attributes — comma-joined by the gateway at execute time.
            pairs: list[tuple[int, int]] = []
            if sku_type == "size_option_wise":
                color_pair = (
                    attr_step_by_value.get((v.color or "").strip().lower())
                    if v.color else None
                )
                if color_pair:
                    pairs.append(color_pair)
                if has_colors:
                    size_pair = size_attr_step_by_value.get((v.size or "").strip().lower())
                    if size_pair:
                        pairs.append(size_pair)
            plan.append(
                _build_setProductSku_step(
                    next_step,
                    size_step,
                    price.variant_sku,
                    sku_type=sku_type,
                    option_attr_pairs=pairs or None,
                )
            )
            next_step += 1

    # Image gallery — pushes product images via setProductsImageGallery with
    # optimizeimg=1. OPS fetches and optimizes the images server-side from the
    # full supplier URLs (verified live against staging, scripts/ops_image_spike.py).
    # Always included when the product has images.
    # In apparel mode, hand the gallery step the Color attr-step map so each
    # color-tagged image gets option_id/attribute_id placeholders — OPS swaps
    # the storefront hero image when the customer picks that color.
    gallery_step = _build_setProductsImageGallery_step(
        next_step, ctx, products_id_step=1,
        color_attr_steps=(attr_step_by_value if has_colors else None),
    )
    if gallery_step is not None:
        plan.append(gallery_step)
        next_step += 1

    # Final N steps: updateProductStock × N (action=Reset, by product_sku).
    # Skipped when enable_stock_management="0" (decorated print apparel is
    # made-to-order, no stock tracking) — OPS would reject these with
    # "Invalid Product SKU or initial stock not added!" anyway.
    if enable_stock_management != "0" and _os.getenv("OPS_PUSH_INCLUDE_STOCK", "0") == "1":
        for v, price in zip(ordered_variants, computed_prices):
            plan.append(
                _build_updateProductStock_step(
                    next_step,
                    price.variant_sku,
                    v.inventory or 0,
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
