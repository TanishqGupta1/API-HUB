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
    VariantPrice,
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
                selectinload(Product.variants).selectinload(ProductVariant.prices),
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
    inp: dict[str, Any] = {
        "products_id": existing_ops_id if push_mode == "update" else 0,
        "products_title": title,
        "products_internal_title": ctx.product.supplier_sku,
        "external_ref": ctx.product.supplier_sku,
        # NOTE: products_sku is NOT in OPS ProductInput (INVALID_USER_INPUT if sent).
        # external_ref IS in the schema — it maps to "External Reference / SKU" in OPS admin.
        # products_url slug is auto-generated by OPS from products_title; not settable via API.
        "visible": 1,
        "product_description": ctx.product.description or "",
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
        # OPS stores imagename/product_desc_image as bare filenames and prepends
        # its own CDN base path at serve time. Strip to filename only.
        # The file must exist at ctmediaon_staging/images/product/{filename}
        # in the shared S3 bucket — sync_images_to_s3.py uploads it there.
        _img_filename = primary_image_url.rsplit("/", 1)[-1]
        inp["imagename"] = _img_filename          # Small Image (admin thumb + listing)
        inp["product_desc_image"] = _img_filename  # Large Image (storefront product page)
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


def _build_setProductSize_default_step(step_num: int) -> OPSMutationStep:
    """Single 'Default' size entry used when all variants share the same pricing.

    OPS uses the size_title as the section header on the Product Price page.
    A title of 'Default' produces the same display as manually-configured
    products (e.g. YST470LS #568) instead of N per-color/size sections.
    """
    return OPSMutationStep(
        step=step_num,
        mutation="setProductSize",
        source_key="default_size",
        variables={
            "inputs": [{
                "products_id": _placeholder(1, "products_id"),
                "size_title": "Default",
                "visible": "1",
            }]
        },
        requires_response_from=[1],
    )


def _build_setProductSize_for_size(step_num: int, size_label: str) -> OPSMutationStep:
    """One setProductSize per unique physical size for size-grouped pricing.

    Used when variants of the same size share identical pricing but differ
    across sizes (e.g. 2XL/3XL/4XL carry an extended-size surcharge vs XS–XL).
    """
    key = re.sub(r"[^a-z0-9]+", "_", size_label.lower()).strip("_") or "size"
    return OPSMutationStep(
        step=step_num,
        mutation="setProductSize",
        source_key=f"size_group:{key}",
        variables={
            "inputs": [{
                "products_id": _placeholder(1, "products_id"),
                "size_title": size_label,
                "visible": "1",
            }]
        },
        requires_response_from=[1],
    )


def _build_setProductPrice_step(
    step_num: int,
    size_step: Optional[int],
    variant_sku: str,
    base_price: float,
    final_price: float,
    *,
    qty: int = 1,
    qty_to: int = 999999,
) -> OPSMutationStep:
    """One setProductPrice step — either Default or per-variant.

    size_step=None  → Default pricing (size_id=0 in OPS); OPS shows a single
                      "Default" section covering all variants. Use when all
                      variants share the same price/tier structure.
    size_step=N     → per-variant pricing tied to the size returned by step N.
                      Use only when variants genuinely have different prices.
    """
    if size_step is None:
        size_id_var: Any = 0
        requires_from = [1]
    else:
        size_id_var = _placeholder(size_step, "size_id")
        requires_from = [1, size_step]
    return OPSMutationStep(
        step=step_num,
        mutation="setProductPrice",
        source_key=f"variant_sku:{variant_sku}",
        variables={
            "inputs": [{
                "products_id": _placeholder(1, "products_id"),
                "size_id": size_id_var,
                "qty": qty,
                "qty_to": qty_to,
                "price": final_price,
                "vendor_price": base_price,
                "visible": "1",
                "user_type_id": "1",
                "price_defining_method": "1",
            }]
        },
        requires_response_from=requires_from,
    )


def _effective_tiers(variant: Any) -> list:
    """Return the variant's meaningful quantity-break tiers.

    When ALL variant_prices rows have quantity_max=NULL the rows represent
    price types (SanMar list/net/wholesale), not real quantity breaks. In that
    case we discard them and let the caller fall back to flat base_price.
    Tiers are sorted deterministically by (quantity_min, price) so comparisons
    are stable even when two rows share the same quantity_min.
    """
    raw = getattr(variant, "prices", None) or []
    if not raw or all(t.quantity_max is None for t in raw):
        return []
    return sorted(raw, key=lambda t: (t.quantity_min, float(t.price or 0)))


def _all_variants_same_price(
    ordered_variants: list,
    computed_prices: list,
) -> bool:
    """True if every variant shares an identical price/tier structure.

    When this returns True the caller should emit a single Default price set
    instead of N per-variant rows — OPS will show it as "Default" rather than
    one section per color/size combination.
    """
    if not ordered_variants:
        return False
    first_tiers = _effective_tiers(ordered_variants[0])
    first_base = float(computed_prices[0].base_price or 0)
    for v, price in zip(ordered_variants[1:], computed_prices[1:]):
        vtiers = _effective_tiers(v)
        if len(vtiers) != len(first_tiers):
            return False
        for a, b in zip(first_tiers, vtiers):
            if (
                a.quantity_min != b.quantity_min
                or a.quantity_max != b.quantity_max
                or float(a.price or 0) != float(b.price or 0)
            ):
                return False
        if not first_tiers and float(price.base_price or 0) != first_base:
            return False
    return True


def _group_variants_by_size(
    ordered_variants: list,
    computed_prices: list,
) -> "Optional[dict[str, list]]":
    """Try to group variants by physical size label.

    Returns an ordered dict ``{size_label: [(variant, computed_price), ...]}``
    where every size group has a consistent price/tier structure across its
    variants (all colours of size M have the same prices, all colours of 3XL
    have the same prices, etc.).

    Returns None if any size group has diverging prices — in that case the
    caller must fall back to per-variant sizing.
    """
    groups: dict[str, list] = {}
    for v, price in zip(ordered_variants, computed_prices):
        label = (v.size or "").strip() or "Standard"
        groups.setdefault(label, []).append((v, price))

    for label, vp_pairs in groups.items():
        ref_v, ref_price = vp_pairs[0]
        ref_tiers = _effective_tiers(ref_v)
        ref_base = float(ref_price.base_price or 0)
        for v, price in vp_pairs[1:]:
            vtiers = _effective_tiers(v)
            if len(vtiers) != len(ref_tiers):
                return None
            for a, b in zip(ref_tiers, vtiers):
                if (
                    a.quantity_min != b.quantity_min
                    or a.quantity_max != b.quantity_max
                    or float(a.price or 0) != float(b.price or 0)
                ):
                    return None
            if not ref_tiers and float(price.base_price or 0) != ref_base:
                return None

    return groups


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
                "prod_add_opt_id": 0,
                "products_id": _placeholder(1, "products_id"),
                "option_key": opt.option_key,
                "title": opt.title or opt.option_key,
                "options_type": getattr(opt, "options_type", "textmp"),
                "price_calculate_type": "0",   # required by OPS; 0 = no surcharge
                "hire_designer_option": "0",    # required by OPS; 0 = disabled
                "status": "1",
                "sort_order": opt.sort_order or 0,
                "delete": 0,
            }]
        },
        requires_response_from=[1],
    )


def _build_setAdditionalOption_for_variant(
    step_num: int,
    dimension: str,   # "color" or "size"
    value: str,
    sort_order: int,
) -> OPSMutationStep:
    """setAdditionalOption for a product colour or size variant.

    Each unique colour and each unique size from the push payload becomes
    a separate Additional Option in OPS, making the product customer-
    selectable (visible in the Additional Options tab on the product page).
    Without these calls the product exists in OPS but has no purchasable
    options and cannot be ordered.

    options_type="radio" renders as radio-button selectors (choose-one-of-N),
    which is appropriate for standard retail colour/size pickers.  Change to
    "2" (Textbox-Price-with-Multiplication) for the wholesale textbox-per-
    variant ordering pattern (e.g. product #556 reference shape).
    """
    key = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    option_key = f"{dimension}_{key}"
    return OPSMutationStep(
        step=step_num,
        mutation="setAdditionalOption",
        source_key=f"{dimension}_option:{key}",
        variables={
            "inputs": [{
                "prod_add_opt_id": 0,          # 0 = create; OPS upserts on option_key
                "products_id": _placeholder(1, "products_id"),
                "option_key": option_key,
                "title": value,
                "options_type": "textmp",       # textbox-multiplication-price; confirmed from product 556
                "price_calculate_type": "0",    # required by OPS; 0 = no surcharge
                "hire_designer_option": "0",    # required by OPS; 0 = disabled
                "status": "1",
                "sort_order": sort_order,
                "delete": 0,                    # 0=create/update, 1=delete
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
                "attribute_id": 0,
                "prod_add_opt_id": _placeholder(option_step, "prod_add_opt_id"),
                "attribute_key": attr.attribute_key,
                "label": attr.title or attr.attribute_key,
                "setup_cost": _to_float(getattr(attr, "setup_cost", None)) or 0.0,
                "multiplier": _to_float(getattr(attr, "multiplier", None)) or 1.0,
                "status": "1",
                "delete": 0,
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

    Image name resolution (priority order):
      1. ops_filename — bare filename assigned by OPS after a manual admin upload
         (Approach B). Takes precedence so manually-curated names are preserved.
      2. img.url — supplier CDN URL passed directly to OPS with optimizeimg=1.
         OPS fetches and stores the image server-side (Approach A automation).

    Images with neither ops_filename nor url are skipped.
    Returns None when no images are pushable (nothing to push).
    """
    if not ctx.images:
        return None
    title = ctx.product.product_name or ctx.product.supplier_sku
    image_arr = [
        {
            "products_image_gallery_id": 0,  # 0 = create
            "delete": 0,
            "title": title,
            "products_large_image_name": img.ops_filename or img.url,
            "sort_order": (img.sort_order or idx),
            "status": "1",
        }
        for idx, img in enumerate(ctx.images)
        if (img.ops_filename or img.url)
        and not (img.url or "").lower().endswith(".gif")  # skip swatch GIFs
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
    is the customer-facing sell price; the mutation plan embeds those
    values directly into each `setProductPrice.price` variable.

    Mutation order (locked, Rev 1 + variant-options extension):
       step 1            : setProduct
       steps 2 .. 1+N    : setProductSize × N (sorted)
       steps 2+N .. 1+2N : setProductPrice × N (depends on matching size step)
       variant options   : setAdditionalOption × (unique colours + unique sizes)
                            — populates OPS Additional Options tab, makes product orderable
       decoration steps  : setAssignOptions × M   (master_option_attach mode)
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
    plan: list[OPSMutationStep] = []

    # Step 1: setProduct
    plan.append(_build_setProduct_step(ctx, push_mode, existing_ops_id, primary_image_url))

    # Pricing strategy — three modes in priority order:
    #   Default       — all variants share identical prices → 1 "Default" size, shared tier rows
    #   Size-grouped  — same-size variants match but sizes differ in price (e.g. extended-size
    #                   surcharge on 2XL/3XL) → 1 OPS size per unique physical size label
    #   Per-variant   — fallback when neither holds (rare for SanMar products)
    use_default_pricing = _all_variants_same_price(ordered_variants, computed_prices)
    size_groups: Optional[dict] = None
    use_size_grouped_pricing = False
    if not use_default_pricing:
        size_groups = _group_variants_by_size(ordered_variants, computed_prices)
        use_size_grouped_pricing = size_groups is not None

    # Steps 2..1+K: setProductSize
    next_step = 2
    size_step_by_sku: dict[str, int] = {}

    if use_default_pricing:
        default_size_step = next_step
        plan.append(_build_setProductSize_default_step(next_step))
        for price in computed_prices:
            size_step_by_sku[price.variant_sku] = default_size_step
        next_step += 1
    elif use_size_grouped_pricing:
        assert size_groups is not None
        for size_label, vp_pairs in size_groups.items():
            sz_step = next_step
            plan.append(_build_setProductSize_for_size(next_step, size_label))
            for _, price_obj in vp_pairs:
                size_step_by_sku[price_obj.variant_sku] = sz_step
            next_step += 1
    else:
        for v, price in zip(ordered_variants, computed_prices):
            plan.append(_build_setProductSize_step(next_step, v, price.variant_sku))
            size_step_by_sku[price.variant_sku] = next_step
            next_step += 1

    # Price steps — one set for Default size, or per-variant when prices differ
    def _emit_price_steps(v: Any, price: Any, size_step: Optional[int]) -> None:
        nonlocal next_step
        tiers: list[VariantPrice] = _effective_tiers(v)
        if tiers:
            for tier in tiers:
                tier_base = _to_float(tier.price) or 0.0
                tier_final_raw = apply_markup(tier.price, rule)
                if tier_final_raw is not None and overrides_dict:
                    tier_final_raw, _ = apply_pricing_overrides(tier_final_raw, overrides_dict)
                    tier_final_raw = to_cents(tier_final_raw)
                tier_final = _to_float(tier_final_raw) or tier_base
                plan.append(
                    _build_setProductPrice_step(
                        next_step, size_step, price.variant_sku,
                        tier_base, tier_final,
                        qty=tier.quantity_min,
                        qty_to=tier.quantity_max or 999999,
                    )
                )
                next_step += 1
        else:
            plan.append(
                _build_setProductPrice_step(
                    next_step, size_step, price.variant_sku,
                    price.base_price, price.final_price,
                )
            )
            next_step += 1

    if use_default_pricing:
        _emit_price_steps(ordered_variants[0], computed_prices[0], size_step=default_size_step)
    elif use_size_grouped_pricing:
        assert size_groups is not None
        for _sz_label, vp_pairs in size_groups.items():
            rep_v, rep_price = vp_pairs[0]
            _emit_price_steps(rep_v, rep_price, size_step=size_step_by_sku[rep_price.variant_sku])
    else:
        for v, price in zip(ordered_variants, computed_prices):
            _emit_price_steps(v, price, size_step_by_sku[price.variant_sku])

    # ── Variant Additional Options (colours + sizes) ───────────────────────
    # One setAdditionalOption per unique colour, then one per unique size.
    # This populates the "Additional Options" tab in OPS so customers can
    # actually select colour/size when ordering (see product #556 for the
    # reference shape).  Colours preserve variant order; sizes likewise.
    _seen_colors: dict[str, int] = {}
    _seen_sizes: dict[str, int] = {}
    _c_sort = 0
    _s_sort = 0
    for _v in ordered_variants:
        _c = (_v.color or "").strip()
        _s = (_v.size or "").strip()
        if _c and _c not in _seen_colors:
            _seen_colors[_c] = _c_sort
            _c_sort += 1
        if _s and _s not in _seen_sizes:
            _seen_sizes[_s] = _s_sort
            _s_sort += 1
    for _color, _sort in _seen_colors.items():
        plan.append(_build_setAdditionalOption_for_variant(next_step, "color", _color, _sort))
        next_step += 1
    for _size, _sort in _seen_sizes.items():
        plan.append(_build_setAdditionalOption_for_variant(next_step, "size", _size, _sort))
        next_step += 1

    # Option steps — strategy-dependent
    if option_strategy is OptionStrategy.MASTER_OPTION_ATTACH:
        for mapping in ctx.push_mapping_options:
            if mapping.target_ops_option_id is None:
                # Preflight should have caught this; skip defensively.
                continue
            plan.append(_build_setAssignOptions_step(next_step, mapping))
            next_step += 1
    else:  # PRODUCT_LOCAL_OPTION_CREATE
        for opt in ctx.options:
            option_step = next_step
            plan.append(_build_setAdditionalOption_step(option_step, opt))
            next_step += 1
            for attr in opt.attributes:
                plan.append(
                    _build_setAdditionalOptionAttributes_step(
                        next_step, option_step, opt.option_key, attr
                    )
                )
                next_step += 1

    # Image gallery — pushes product images via setProductsImageGallery.
    # Opt in with OPS_PUSH_INCLUDE_IMAGES=1.
    #
    # Name resolution (see _build_setProductsImageGallery_step):
    #   ops_filename (manual OPS admin upload) → takes priority
    #   img.url (supplier CDN URL)             → automation fallback with optimizeimg=1
    #
    # NOTE: Earlier testing (ops_image_readback.py on #547) found OPS may treat
    # products_large_image_name as a bare filename rather than fetching the URL.
    # The url fallback path is under active verification on staging — enable and
    # check OPS gallery results before enabling in production.
    # Placed before stock so inventory stays the final step (Rev 1 contract).
    # Best-effort/warn-only in the gateway.
    import os as _os

    if _os.getenv("OPS_PUSH_INCLUDE_IMAGES", "0") == "1":
        gallery_step = _build_setProductsImageGallery_step(next_step, ctx, products_id_step=1)
        if gallery_step is not None:
            plan.append(gallery_step)
            next_step += 1

    # Final N steps: updateProductStock × N (action=Add, with stock_id
    # resolved by gateway read-back — see _build_updateProductStock_step).
    # Deferred by default: opt in with OPS_PUSH_INCLUDE_STOCK=1.
    if _os.getenv("OPS_PUSH_INCLUDE_STOCK", "0") == "1":
        if use_default_pricing:
            # Single stock step for the Default size; aggregate inventory across variants
            total_inventory = sum(v.inventory or 0 for v in ordered_variants)
            plan.append(
                _build_updateProductStock_step(
                    next_step,
                    default_size_step,
                    "default",
                    total_inventory,
                )
            )
            next_step += 1
        elif use_size_grouped_pricing:
            assert size_groups is not None
            for _sz_label, vp_pairs in size_groups.items():
                rep_price = vp_pairs[0][1]
                size_inventory = sum(v.inventory or 0 for v, _ in vp_pairs)
                plan.append(
                    _build_updateProductStock_step(
                        next_step,
                        size_step_by_sku[rep_price.variant_sku],
                        rep_price.variant_sku,
                        size_inventory,
                    )
                )
                next_step += 1
        else:
            for v, price in zip(ordered_variants, computed_prices):
                plan.append(
                    _build_updateProductStock_step(
                        next_step,
                        size_step_by_sku[price.variant_sku],
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
