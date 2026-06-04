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
    # Field names match the live OPS `ProductInput` schema (verified via GraphQL
    # introspection 2026-06-04). OPS ProductInput has NO `category_name`, `brand`,
    # or `products_image` — description is `product_description`, category is an
    # int `category_id` (nullable; deferred), and the product image is uploaded
    # via a separate flow. Sending the old names made setProduct return
    # INVALID_USER_INPUT. Keep only fields OPS accepts.
    variables: dict[str, Any] = {
        "input": {
            "products_id": existing_ops_id if push_mode == "update" else 0,
            "products_title": title,
            "products_internal_title": ctx.product.supplier_sku,
            "visible": 1,
            "product_description": ctx.product.description or "",
        }
    }

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
    """One setProductSize per variant. Depends on step 1 for products_id.

    Field names match the live OPS `ProductSizeInput` schema (introspected
    2026-06-04): the id field is `size_id` (0 = create), the label is
    `size_title`, and `visible` is a String. ProductSizeInput has NO color or
    SKU field, so the color/size pair is encoded into `size_title` to keep each
    variant a distinct OPS size row. (Proper color modelling via OPS
    options/attributes is a later enhancement.)
    """
    color = (variant.color or "").strip()
    size = (variant.size or "").strip()
    size_title = " / ".join(p for p in (color, size) if p) or variant_sku
    return OPSMutationStep(
        step=step_num,
        mutation="setProductSize",
        source_key=f"variant_sku:{variant_sku}",
        variables={
            "input": {
                "size_id": 0,
                "products_id": _placeholder(1, "products_id"),
                "size_title": size_title,
                "visible": "1",
            }
        },
        requires_response_from=[1],
    )


def _build_setProductPrice_step(
    step_num: int,
    size_step: int,
    variant_sku: str,
    base_price: float,
    final_price: float,
) -> OPSMutationStep:
    """One setProductPrice per variant. Spec contract for beta:
    qty=1, qty_to=999999, single visible price row. Depends on the
    matching setProductSize step for `size_id`."""
    return OPSMutationStep(
        step=step_num,
        mutation="setProductPrice",
        source_key=f"variant_sku:{variant_sku}",
        variables={
            "input": {
                "product_price_id": 0,
                "products_id": _placeholder(1, "products_id"),
                # Input field is `size_id`; value is threaded from the
                # setProductSize response, which selects `product_size_id`.
                "size_id": _placeholder(size_step, "product_size_id"),
                "qty": 1,
                "qty_to": 999999,
                "price": final_price,
                "vendor_price": base_price,
                "visible": "1",
            }
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
            "input": {
                "products_id": _placeholder(1, "products_id"),
                "master_option_id": mapping.target_ops_option_id,
                "master_attribute_id": mapping.target_ops_attribute_id,
                "price": _to_float(mapping.price) or 0.0,
                "sort_order": getattr(mapping, "sort_order", 0) or 0,
            }
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
            "input": {
                "products_id": _placeholder(1, "products_id"),
                "option_key": opt.option_key,
                "title": opt.title or opt.option_key,
                "options_type": getattr(opt, "options_type", "combo"),
                "required": getattr(opt, "required", False),
                "sort_order": opt.sort_order or 0,
            }
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
            "input": {
                "products_id": _placeholder(1, "products_id"),
                # setAdditionalOption response selects `prod_add_opt_id`.
                "option_id": _placeholder(option_step, "prod_add_opt_id"),
                "attribute_key": attr.attribute_key,
                "title": attr.title or attr.attribute_key,
                "setup_cost": _to_float(getattr(attr, "setup_cost", None)) or 0.0,
                "multiplier": _to_float(getattr(attr, "multiplier", None)) or 1.0,
            }
        },
        requires_response_from=[1, option_step],
    )


def _build_updateProductStock_step(
    step_num: int, variant_sku: str, inventory: int
) -> OPSMutationStep:
    """Inventory LAST step per Rev 1 §"PC61 outbound mutation sequence".

    action=Reset because API-HUB owns the absolute on-hand number.
    product_sku is the stable identifier (preferred over stock_id which
    only exists after a prior successful inventory write).
    """
    return OPSMutationStep(
        step=step_num,
        mutation="updateProductStock",
        source_key=f"variant_sku:{variant_sku}",
        variables={
            "action": "Reset",
            "product_sku": variant_sku,
            "input": {
                "stock_quantity": inventory,
            },
        },
        requires_response_from=[1],
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

    # Steps 2..1+N: setProductSize × N
    next_step = 2
    size_step_by_sku: dict[str, int] = {}
    for v, price in zip(ordered_variants, computed_prices):
        plan.append(_build_setProductSize_step(next_step, v, price.variant_sku))
        size_step_by_sku[price.variant_sku] = next_step
        next_step += 1

    # Steps 2+N..1+2N: setProductPrice × N (depends on matching size step)
    for price in computed_prices:
        size_step = size_step_by_sku[price.variant_sku]
        plan.append(
            _build_setProductPrice_step(
                next_step, size_step, price.variant_sku, price.base_price, price.final_price
            )
        )
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

    # Final N steps: updateProductStock × N (action=Reset).
    # Deferred by default: updateProductStock targets a stock row by
    # `product_sku`, but OPS `ProductSizeInput` carries no SKU, so a freshly
    # created variant has no OPS-side SKU/stock_id to match in a single push —
    # the Reset would no-op/fail. Opt in with OPS_PUSH_INCLUDE_STOCK=1 once
    # per-variant stock targeting (read-back of OPS SKUs/stock_ids) is wired.
    import os as _os
    if _os.getenv("OPS_PUSH_INCLUDE_STOCK", "0") == "1":
        for v, price in zip(ordered_variants, computed_prices):
            plan.append(
                _build_updateProductStock_step(
                    next_step, price.variant_sku, v.inventory or 0
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
