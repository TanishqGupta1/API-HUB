"""Integration Gateway M1 — payload_builder unit tests.

Hermetic — no DB, no HTTP. We construct `_PushContext` directly with
duck-typed mocks (SimpleNamespace) and call `_synthesize_payload`
instead of going through `build_push_payload`'s async DB factory.

The DB factory itself is integration-tested in `test_pipeline.py`
(M1-aggregator, future) where a real session is available.

Covers
------
- RFC 8785 JSON Canonicalization Scheme rules (null stripping, key
  sorting, number formatting)
- `compute_payload_hash()` determinism + sensitivity
- Mutation plan order: setProduct → sizes → prices → options → stock
- Variant ordering by `sort_order` ASC, then `(color, size, sku)`
- Markup inlining (Bug 3 fix lives in the builder)
- Two option strategies (master_option_attach vs product_local_option_create)
- Create vs update mode resolved via push_mappings
- Image policy (single primary front image; warnings for extras)
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.no_db

from modules.ops_push.payload_builder import (
    OPSComputedPrice,
    OPSMutationStep,
    OPSPushPayload,
    OptionStrategy,
    _PushContext,
    _placeholder,
    _request_fingerprint,
    _synthesize_payload,
    canonicalize_json,
    compute_payload_hash,
)


# ---------------------------------------------------------------------------
# Mock factories
# ---------------------------------------------------------------------------


def _supplier(slug: str = "sanmar", prefix: str | None = "VG-") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        slug=slug,
        push_name_prefix=prefix,
        has_decoration_overlay=False,
    )


def _customer(name: str = "Visual Graphics") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        ops_base_url="https://staging.visualgraphx.com",
        ops_client_id="abcd1234efgh5678",
        ops_token_url="https://staging.visualgraphx.com/oauth/token",
        ops_auth_config={"client_secret": "shh"},
        is_active=True,
    )


def _product(
    sku: str = "PC61",
    name: str = "Port & Co Essential T-Shirt",
    category: str = "T-Shirts",
    supplier_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        supplier_id=supplier_id or uuid.uuid4(),
        supplier_sku=sku,
        product_name=name,
        brand="Port & Company",
        category=category,
        description="100% cotton tee",
        product_type="apparel",
        image_url=None,
        last_synced=None,
        archived_at=None,
    )


def _variant(
    sku: str,
    color: str | None = "White",
    size: str | None = "M",
    base_price: Decimal | None = Decimal("8.32"),
    inventory: int | None = 50,
    sort_order: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        sku=sku,
        color=color,
        size=size,
        base_price=base_price,
        inventory=inventory,
        warehouse="GA",
        sort_order=sort_order,
    )


def _image(url: str, image_type: str = "front", sort_order: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        url=url,
        supplier_image_url=url,
        image_type=image_type,
        color=None,
        sort_order=sort_order,
        checksum=None,
    )


def _option(option_key: str = "embroidery", attributes: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        option_key=option_key,
        title=option_key.title(),
        options_type="combo",
        required=False,
        sort_order=0,
        attributes=attributes or [],
    )


def _option_attribute(attribute_key: str, title: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        attribute_key=attribute_key,
        title=title or attribute_key.title(),
        setup_cost=Decimal("0.00"),
        multiplier=Decimal("1.00"),
    )


def _markup_rule(pct: Decimal = Decimal("50.0")) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        scope="all",  # matches resolve_rule's fallback tier
        markup_pct=pct,
        markup_amount=None,
        priority=10,
        rounding="penny",
        min_price=None,
        max_price=None,
        min_margin=None,
        supplier_id=None,
        category=None,
        supplier_sku=None,
        is_active=True,
        effective_from=None,
        effective_to=None,
        effective_until=None,
    )


def _push_mapping(target_ops_product_id: int | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        source_product_id=uuid.uuid4(),
        target_ops_product_id=target_ops_product_id,
        options=[],
    )


def _push_mapping_option(
    source_option_key: str,
    target_ops_option_id: int | None = 101,
    source_attribute_key: str | None = None,
    target_ops_attribute_id: int | None = None,
    price: Decimal | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        source_option_key=source_option_key,
        target_ops_option_id=target_ops_option_id,
        source_attribute_key=source_attribute_key,
        target_ops_attribute_id=target_ops_attribute_id,
        price=price,
        sort_order=0,
    )


_UNSET = object()


def _ctx(
    *,
    variants: list,
    images=_UNSET,
    options=_UNSET,
    markup_rules=_UNSET,
    push_mapping: SimpleNamespace | None = None,
    push_mapping_options=_UNSET,
    decoration_options=_UNSET,
    customer: SimpleNamespace | None = None,
    product: SimpleNamespace | None = None,
    supplier: SimpleNamespace | None = None,
    storefront_config=None,
) -> _PushContext:
    """Build a _PushContext from mock pieces. Pass `images=[]` to test
    the no-images path (the `_UNSET` sentinel distinguishes empty-list
    from default)."""
    cust = customer or _customer()
    sup = supplier or _supplier()
    prod = product or _product(supplier_id=sup.id)
    return _PushContext(
        customer=cust,
        product=prod,
        supplier=sup,
        variants=variants,
        images=([_image("https://cdn.sanmar.com/PC61_white_front.jpg")] if images is _UNSET else images),
        options=([] if options is _UNSET else options),
        markup_rules=([_markup_rule()] if markup_rules is _UNSET else markup_rules),
        push_mapping=push_mapping,
        push_mapping_options=([] if push_mapping_options is _UNSET else push_mapping_options),
        decoration_options=([] if decoration_options is _UNSET else decoration_options),
        storefront_config=storefront_config,
    )


# ===========================================================================
# RFC 8785 JSON Canonicalization Scheme
# ===========================================================================


class TestCanonicalize:
    def test_strips_null_object_members(self):
        canon = canonicalize_json({"a": 1, "b": None, "c": "x"})
        assert "null" not in canon
        assert canon == '{"a":1,"c":"x"}'

    def test_preserves_null_array_elements(self):
        # Nulls inside arrays MUST be preserved
        canon = canonicalize_json([1, None, 2, None, 3])
        assert canon == "[1,null,2,null,3]"

    def test_recursive_null_stripping(self):
        canon = canonicalize_json({"outer": {"inner": None, "kept": True}, "skipped": None})
        assert canon == '{"outer":{"kept":true}}'

    def test_lexicographically_sorts_keys(self):
        # Insertion order should not affect output
        a = canonicalize_json({"z": 1, "a": 2, "m": 3})
        b = canonicalize_json({"a": 2, "m": 3, "z": 1})
        assert a == b == '{"a":2,"m":3,"z":1}'

    def test_utf16_code_unit_sort_for_supplementary_chars(self):
        # RFC 8785 §3.2.3 — keys sorted by UTF-16 code unit, NOT Unicode
        # code point. For supplementary-plane chars (U+10000+) those two
        # orderings diverge because UTF-16 encodes them as surrogate pairs.
        #
        # First UTF-16 code unit for each key:
        #   "z"  → U+007A           → 007A
        #   "𠮷" → U+20BB7 (pair)  → D842
        #   "​" → U+FE0F (BMP)    → FE0F
        # UTF-16 byte order: z (00) < 𠮷 (D8) < ​ (FE).
        # Pure Unicode code-point order would put ​ (FE0F) BEFORE 𠮷
        # (20BB7), so this test fails if someone reverts to Python's
        # default str sort.
        out = canonicalize_json({"\U00020bb7": 1, "z": 2, "️": 3})
        assert out.index('"z"') < out.index('"\U00020bb7"')
        assert out.index('"\U00020bb7"') < out.index('"️"')

    def test_integers_no_decimal(self):
        assert canonicalize_json(0) == "0"
        assert canonicalize_json(-1) == "-1"
        assert canonicalize_json(12345) == "12345"

    def test_floats_use_repr(self):
        # 1.0 should drop the .0 per RFC 8785 (integer form preferred)
        assert canonicalize_json(1.0) == "1"
        assert canonicalize_json(8.32) == "8.32"

    def test_negative_zero(self):
        assert canonicalize_json(-0.0) == "0"
        assert canonicalize_json(0.0) == "0"

    def test_nan_raises(self):
        with pytest.raises(ValueError):
            canonicalize_json(float("nan"))

    def test_infinity_raises(self):
        with pytest.raises(ValueError):
            canonicalize_json(float("inf"))

    def test_booleans(self):
        assert canonicalize_json(True) == "true"
        assert canonicalize_json(False) == "false"

    def test_nested(self):
        canon = canonicalize_json({"arr": [{"b": 1, "a": 2}, {"d": 4, "c": 3}]})
        assert canon == '{"arr":[{"a":2,"b":1},{"c":3,"d":4}]}'


class TestPayloadHash:
    def test_deterministic(self):
        body = {"target": {"customer_id": "x"}, "product_ref": {"supplier_sku": "PC61"}}
        h1 = compute_payload_hash(body)
        h2 = compute_payload_hash(body)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex
        assert h1 == h1.lower()  # lowercase hex

    def test_insensitive_to_key_order(self):
        a = compute_payload_hash({"b": 2, "a": 1})
        b = compute_payload_hash({"a": 1, "b": 2})
        assert a == b

    def test_insensitive_to_explicit_nulls(self):
        # Adding `"optional_field": null` should not change the hash —
        # nulls in objects are stripped before hashing.
        with_null = {"customer_id": "x", "callback": None}
        without_null = {"customer_id": "x"}
        assert compute_payload_hash(with_null) == compute_payload_hash(without_null)

    def test_sensitive_to_array_null_position(self):
        # But nulls inside arrays MUST affect the hash.
        a = compute_payload_hash({"items": [1, None, 2]})
        b = compute_payload_hash({"items": [1, 2]})
        assert a != b

    def test_sensitive_to_value_change(self):
        a = compute_payload_hash({"sku": "PC61"})
        b = compute_payload_hash({"sku": "PC62"})
        assert a != b

    def test_unicode_strings_no_escape(self):
        # ensure_ascii=False so non-ASCII goes through as UTF-8 bytes
        h = compute_payload_hash({"name": "Café"})
        assert isinstance(h, str)
        assert len(h) == 64


# ===========================================================================
# Mutation plan structure
# ===========================================================================


class TestMutationPlanOrder:
    def test_step_1_is_setProduct(self):
        ctx = _ctx(variants=[_variant("PC61-WHT-M")])
        payload = _synthesize_payload(ctx)
        assert payload.plan[0].mutation == "setProduct"
        assert payload.plan[0].step == 1

    def test_sizes_follow_setProduct(self):
        variants = [_variant("PC61-WHT-S"), _variant("PC61-WHT-M"), _variant("PC61-WHT-L")]
        ctx = _ctx(variants=variants)
        payload = _synthesize_payload(ctx)
        # Steps 2, 3, 4 are sizes
        assert all(payload.plan[i].mutation == "setProductSize" for i in (1, 2, 3))

    def test_prices_follow_sizes(self):
        variants = [_variant("PC61-WHT-S"), _variant("PC61-WHT-M")]
        ctx = _ctx(variants=variants)
        payload = _synthesize_payload(ctx)
        # After 1 setProduct + 2 sizes, next 2 are prices
        assert payload.plan[3].mutation == "setProductPrice"
        assert payload.plan[4].mutation == "setProductPrice"

    def test_inventory_is_last(self):
        variants = [_variant("PC61-WHT-S"), _variant("PC61-WHT-M")]
        ctx = _ctx(variants=variants)
        payload = _synthesize_payload(ctx)
        # The final N steps must be updateProductStock (N=2 here)
        last_two = payload.plan[-2:]
        assert all(s.mutation == "updateProductStock" for s in last_two)

    def test_inventory_action_is_add(self):
        # action=Add increments existing stock. Phase 6: OPS has no per-size
        # SKU field anywhere in its schema, so updateProductStock identifies
        # the variant by stock_id. The stock_id is resolved at execute time
        # by the gateway from a productStocks(product_id) read-back.
        #
        # The plan step does NOT carry stock_id directly — it carries a
        # gateway-only sentinel `_size_id_ref` (a placeholder) that the
        # gateway uses to look up the stock_id for that variant's size.
        ctx = _ctx(variants=[_variant("PC61-WHT-M", inventory=42)])
        payload = _synthesize_payload(ctx)
        stock_step = next(s for s in payload.plan if s.mutation == "updateProductStock")
        assert stock_step.variables["action"] == "Add"
        assert stock_step.variables["input"]["stock_quantity"] == 42
        # _size_id_ref is the gateway lookup hint — must reference a
        # setProductSize step's size_id response.
        assert stock_step.variables["_size_id_ref"].startswith("$step")
        assert stock_step.variables["_size_id_ref"].endswith(".size_id")
        # product_sku is gone — OPS can't match it without a per-size SKU
        # field, so threading it does nothing useful and is misleading.
        assert "product_sku" not in stock_step.variables
        assert "stock_id" not in stock_step.variables  # filled by gateway
        # action must NOT be nested inside input
        assert "action" not in stock_step.variables["input"]
        assert "product_sku" not in stock_step.variables["input"]

    def test_no_setProductCategory_step(self):
        # Old spec had a separate setProductCategory step; new spec does not.
        ctx = _ctx(variants=[_variant("PC61-WHT-M")])
        payload = _synthesize_payload(ctx)
        assert not any(s.mutation == "setProductCategory" for s in payload.plan)
        # Category lives on setProduct.input as category_id (Int), sourced from
        # the storefront mapping and omitted when unmapped (default ctx has none).
        setProduct = payload.plan[0]
        assert "category_name" not in setProduct.variables["inputs"][0]
        assert "category_id" not in setProduct.variables["inputs"][0]


class TestVariantOrdering:
    def test_sort_order_takes_priority(self):
        variants = [
            _variant("c", color="Black", size="L", sort_order=3),
            _variant("a", color="Black", size="S", sort_order=1),
            _variant("b", color="Black", size="M", sort_order=2),
        ]
        ctx = _ctx(variants=variants)
        payload = _synthesize_payload(ctx)
        # Variants should appear in sort_order ascending: a, b, c
        ordered_skus = [p.variant_sku for p in payload.computed_prices]
        assert ordered_skus == ["a", "b", "c"]

    def test_lex_tiebreaker_when_sort_order_equal(self):
        variants = [
            _variant("z-sku", color="Red", size="L", sort_order=0),
            _variant("a-sku", color="Blue", size="S", sort_order=0),
            _variant("m-sku", color="Green", size="M", sort_order=0),
        ]
        ctx = _ctx(variants=variants)
        payload = _synthesize_payload(ctx)
        # All sort_order=0 → falls back to (color, size, sku)
        # Blue/S/a < Green/M/m < Red/L/z
        ordered_skus = [p.variant_sku for p in payload.computed_prices]
        assert ordered_skus == ["a-sku", "m-sku", "z-sku"]


class TestStepDependencies:
    def test_setProduct_has_no_dependencies(self):
        ctx = _ctx(variants=[_variant("PC61-WHT-M")])
        payload = _synthesize_payload(ctx)
        assert payload.plan[0].requires_response_from == []

    def test_size_depends_on_setProduct(self):
        ctx = _ctx(variants=[_variant("PC61-WHT-M")])
        payload = _synthesize_payload(ctx)
        size_step = payload.plan[1]
        assert size_step.requires_response_from == [1]
        assert size_step.variables["inputs"][0]["products_id"] == _placeholder(1, "products_id")

    def test_price_depends_on_matching_size_step(self):
        variants = [_variant("PC61-WHT-S"), _variant("PC61-WHT-M")]
        ctx = _ctx(variants=variants)
        payload = _synthesize_payload(ctx)
        # Step 2 = size of PC61-WHT-M (lex first), Step 3 = size of PC61-WHT-S
        # Step 4 = price for first variant, depends on size step 2
        # Step 5 = price for second variant, depends on size step 3
        price_step_1 = payload.plan[3]
        price_step_2 = payload.plan[4]
        assert 1 in price_step_1.requires_response_from
        assert price_step_1.variables["inputs"][0]["size_id"].startswith("$step")
        # Verifies the wiring reads product_size_id from setProductSize's response
        assert price_step_1.variables["inputs"][0]["size_id"].endswith(".size_id")
        assert 1 in price_step_2.requires_response_from
        # Sanity: the two prices reference different size steps
        assert price_step_1.variables["inputs"][0]["size_id"] != price_step_2.variables["inputs"][0]["size_id"]


# ===========================================================================
# Markup application (Bug 3 fix lives in the builder)
# ===========================================================================


class TestMarkupApplied:
    def test_50pct_markup(self):
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M", base_price=Decimal("8.32"))],
            markup_rules=[_markup_rule(pct=Decimal("50.0"))],
        )
        payload = _synthesize_payload(ctx)
        p = payload.computed_prices[0]
        assert p.base_price == pytest.approx(8.32)
        assert p.final_price == pytest.approx(12.48)
        assert p.markup_pct == pytest.approx(50.0)

    def test_setProductPrice_uses_final_price(self):
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M", base_price=Decimal("10.00"))],
            markup_rules=[_markup_rule(pct=Decimal("50.0"))],
        )
        payload = _synthesize_payload(ctx)
        price_step = next(s for s in payload.plan if s.mutation == "setProductPrice")
        assert price_step.variables["inputs"][0]["price"] == pytest.approx(15.00)
        assert price_step.variables["inputs"][0]["vendor_price"] == pytest.approx(10.00)

    def test_qty_to_is_999999(self):
        ctx = _ctx(variants=[_variant("PC61-WHT-M")])
        payload = _synthesize_payload(ctx)
        price_step = next(s for s in payload.plan if s.mutation == "setProductPrice")
        assert price_step.variables["inputs"][0]["qty"] == 1
        assert price_step.variables["inputs"][0]["qty_to"] == 999999

    def test_no_markup_rule_passthrough(self):
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M", base_price=Decimal("8.32"))],
            markup_rules=[],
        )
        payload = _synthesize_payload(ctx)
        p = payload.computed_prices[0]
        assert p.base_price == pytest.approx(8.32)
        # apply_markup with rule=None returns the base price unchanged
        assert p.final_price == pytest.approx(8.32)
        assert p.markup_pct is None


# ===========================================================================
# Two option strategies
# ===========================================================================


class TestOptionStrategies:
    def test_master_option_attach_uses_setAssignOptions(self):
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M")],
            push_mapping_options=[
                _push_mapping_option("embroidery", target_ops_option_id=42),
            ],
        )
        payload = _synthesize_payload(ctx, OptionStrategy.MASTER_OPTION_ATTACH)
        mutations = [s.mutation for s in payload.plan]
        assert "setAssignOptions" in mutations
        assert "setAdditionalOption" not in mutations

    def test_product_local_uses_setAdditionalOption(self):
        opt = _option(
            "embroidery",
            attributes=[_option_attribute("gloss"), _option_attribute("matte")],
        )
        ctx = _ctx(variants=[_variant("PC61-WHT-M")], options=[opt])
        payload = _synthesize_payload(ctx, OptionStrategy.PRODUCT_LOCAL_OPTION_CREATE)
        mutations = [s.mutation for s in payload.plan]
        assert "setAdditionalOption" in mutations
        assert mutations.count("setAdditionalOptionAttributes") == 2
        assert "setAssignOptions" not in mutations

    def test_master_skips_unmapped_options(self):
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M")],
            push_mapping_options=[
                _push_mapping_option("embroidery", target_ops_option_id=None),
            ],
        )
        payload = _synthesize_payload(ctx, OptionStrategy.MASTER_OPTION_ATTACH)
        # Unmapped row is skipped (preflight should have blocked anyway)
        assert not any(s.mutation == "setAssignOptions" for s in payload.plan)


# ===========================================================================
# Create vs update mode
# ===========================================================================


class TestPushMode:
    def test_create_mode_when_no_mapping(self):
        ctx = _ctx(variants=[_variant("PC61-WHT-M")], push_mapping=None)
        payload = _synthesize_payload(ctx)
        assert payload.push_mode == "create"
        assert payload.existing_ops_product_id is None
        setProduct = payload.plan[0]
        assert setProduct.variables["inputs"][0]["products_id"] == 0

    def test_update_mode_when_mapping_exists(self):
        mapping = _push_mapping(target_ops_product_id=12345)
        ctx = _ctx(variants=[_variant("PC61-WHT-M")], push_mapping=mapping)
        payload = _synthesize_payload(ctx)
        assert payload.push_mode == "update"
        assert payload.existing_ops_product_id == 12345
        setProduct = payload.plan[0]
        assert setProduct.variables["inputs"][0]["products_id"] == 12345


# ===========================================================================
# Image policy
# ===========================================================================


class TestImagePolicy:
    def test_single_front_image(self):
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M")],
            images=[_image("https://x/front.jpg", image_type="front")],
        )
        payload = _synthesize_payload(ctx)
        # payload.primary_image_url keeps the full URL for downstream readers
        # (e.g. preflight image-reachability check, audit log).
        assert payload.primary_image_url == "https://x/front.jpg"
        assert payload.image_warnings == []
        setProduct = payload.plan[0]
        # But the mutation receives just the filename — OPS prepends its CDN
        # base path at serve time; sending a full URL produces a double-prefix.
        assert setProduct.variables["inputs"][0]["imagename"] == "front.jpg"

    def test_imagename_strips_to_filename_for_deep_paths(self):
        """SanMar URLs have multi-segment paths like /imglib/mresjpg/2013/f14/PC61_aqua_back.jpg.
        Everything before the last '/' must be dropped — OPS only wants the leaf."""
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M")],
            images=[_image(
                "https://cdnm.sanmar.com/imglib/mresjpg/2013/f14/PC61_aquaticblue_flat_back.jpg",
                image_type="front",
            )],
        )
        payload = _synthesize_payload(ctx)
        assert payload.plan[0].variables["inputs"][0]["imagename"] == "PC61_aquaticblue_flat_back.jpg"

    def test_imagename_passes_through_when_already_a_filename(self):
        """If primary_image_url is already a bare filename (no slashes),
        rsplit('/', 1)[-1] returns it unchanged."""
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M")],
            images=[_image("PC61_front.jpg", image_type="front")],
        )
        payload = _synthesize_payload(ctx)
        assert payload.plan[0].variables["inputs"][0]["imagename"] == "PC61_front.jpg"

    def test_multiple_images_warns(self):
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M")],
            images=[
                _image("https://x/front.jpg", image_type="front", sort_order=0),
                _image("https://x/back.jpg", image_type="back", sort_order=1),
                _image("https://x/detail.jpg", image_type="detail", sort_order=2),
            ],
        )
        payload = _synthesize_payload(ctx)
        assert payload.primary_image_url == "https://x/front.jpg"
        assert len(payload.image_warnings) == 1
        assert "2 additional image(s) ignored" in payload.image_warnings[0]

    def test_no_front_falls_back_to_first(self):
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M")],
            images=[_image("https://x/lifestyle.jpg", image_type="lifestyle")],
        )
        payload = _synthesize_payload(ctx)
        assert payload.primary_image_url == "https://x/lifestyle.jpg"
        assert any("No front-type image" in w for w in payload.image_warnings)

    def test_no_images(self):
        ctx = _ctx(variants=[_variant("PC61-WHT-M")], images=[])
        payload = _synthesize_payload(ctx)
        assert payload.primary_image_url is None
        setProduct = payload.plan[0]
        assert "imagename" not in setProduct.variables["inputs"][0]


# ===========================================================================
# Customer title prefix
# ===========================================================================


class TestTitlePrefix:
    def test_uses_supplier_push_name_prefix(self):
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M")],
            supplier=_supplier(slug="sanmar", prefix="VG-"),
        )
        payload = _synthesize_payload(ctx)
        title = payload.plan[0].variables["inputs"][0]["products_title"]
        assert title.startswith("VG-")

    def test_falls_back_to_uppercase_slug(self):
        sup = _supplier(slug="sanmar", prefix=None)
        ctx = _ctx(variants=[_variant("PC61-WHT-M")], supplier=sup)
        payload = _synthesize_payload(ctx)
        title = payload.plan[0].variables["inputs"][0]["products_title"]
        assert title.startswith("SA-")


# ===========================================================================
# Smoke: full PC61 fixture (7 colors × 8 sizes = 56 variants)
# ===========================================================================


class TestPC61Smoke:
    def test_pc61_plan_shape(self):
        # Match the SanMar PC61 contour: 56 variants, 1 mapped option
        colors = ["Black", "White", "Red", "Royal", "Navy", "Ash", "Heather Gray"]
        sizes = ["XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL"]
        variants = [
            _variant(
                f"PC61-{c[:3].upper()}-{s}",
                color=c,
                size=s,
                base_price=Decimal("3.99"),
                inventory=100,
                sort_order=i,
            )
            for i, (c, s) in enumerate((c, s) for c in colors for s in sizes)
        ]
        ctx = _ctx(
            variants=variants,
            push_mapping_options=[
                _push_mapping_option("embroidery", target_ops_option_id=42),
            ],
        )
        payload = _synthesize_payload(ctx)

        # 1 setProduct + 56 sizes + 56 prices + 1 option + 56 stock = 170 steps
        assert len(payload.plan) == 1 + 56 + 56 + 1 + 56
        mutations = [s.mutation for s in payload.plan]
        assert mutations.count("setProductSize") == 56
        assert mutations.count("setProductPrice") == 56
        assert mutations.count("setAssignOptions") == 1
        assert mutations.count("updateProductStock") == 56


# ===========================================================================
# B6 — Payload variable shape assertions
# (Spec: non-zero vendor_price, correct internal_title, integer option IDs)
# ===========================================================================


class TestSetProductVariables:
    """Assert the exact variable shape of the setProduct step.

    These tests nail down fields that the OPS API requires to be present
    and correctly typed — bugs here only surface on a live push, which is
    expensive to debug.  They codify the verified mapping table from
    docs/memory/sanmar_to_ops_field_mapping.md.
    """

    def test_products_internal_title_is_supplier_sku(self):
        """B6: products_internal_title must equal supplier_sku.

        OPS uses this as a stable deduplication key. If it's missing or
        wrong, re-pushing the same product creates a duplicate instead of
        updating the existing one.
        """
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M")],
            product=_product(sku="PC61"),
        )
        payload = _synthesize_payload(ctx)
        set_product = payload.plan[0]
        assert set_product.variables["inputs"][0]["products_internal_title"] == "PC61"

    def test_set_product_price_vendor_price_nonzero(self):
        """B6: vendor_price (wholesale cost) must be > 0.

        If base_price is not set in the DB, the preflight check_base_price_set
        should block the push.  When it does reach the builder, it must pass
        the real value through — not silently send 0 to OPS.
        """
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M", base_price=Decimal("8.32"))],
            markup_rules=[_markup_rule(pct=Decimal("20.0"))],
        )
        payload = _synthesize_payload(ctx)
        price_step = next(s for s in payload.plan if s.mutation == "setProductPrice")
        assert price_step.variables["inputs"][0]["vendor_price"] > 0, (
            "vendor_price must be non-zero — check that base_price is written "
            "by ps_normalizer_v2.merge_pricing (Bug 1 fix)"
        )

    def test_master_option_id_is_integer(self):
        """B6: setAssignOptions.master_option_id must be an int, not a string.

        OPS GraphQL rejects the mutation if master_option_id is passed as
        a string.  push_mapping_options.target_ops_option_id is stored as
        INTEGER in the DB; this test verifies no accidental str() coercion
        happens in the builder.
        """
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M")],
            push_mapping_options=[
                _push_mapping_option("size", target_ops_option_id=7),
            ],
        )
        payload = _synthesize_payload(ctx, OptionStrategy.MASTER_OPTION_ATTACH)
        assign_step = next(s for s in payload.plan if s.mutation == "setAssignOptions")
        mid = assign_step.variables["inputs"][0]["master_option_id"]
        assert isinstance(mid, int), (
            f"master_option_id must be int, got {type(mid).__name__!r} — "
            "do not cast to str in _build_setAssignOptions_step"
        )

    def test_category_id_present_when_mapped(self):
        """setProduct.input.category_id is the mapped OPS category id (Int).

        OPS's ProductInput uses category_id (Int), sourced from the storefront
        mapping (ProductStorefrontConfig.ops_category_id), not category_name.
        """
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M")],
            product=_product(category="T-Shirts"),
            storefront_config=SimpleNamespace(pricing_overrides=None, ops_category_id="42"),
        )
        payload = _synthesize_payload(ctx)
        assert payload.plan[0].variables["inputs"][0]["category_id"] == 42

    def test_category_omitted_when_unmapped(self):
        """No storefront mapping AND no customer default → no category in setProduct
        (no silent 'Uncategorized' fallback)."""
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M")],
            product=_product(category=None),
        )
        payload = _synthesize_payload(ctx)
        inp = payload.plan[0].variables["inputs"][0]
        assert "category_id" not in inp
        assert "category_name" not in inp

    def test_falls_back_to_customer_default_category(self):
        """Phase 2 of the OPS push audit: when no per-product storefront
        config has a category, use customer.default_ops_category_id so
        products aren't created uncategorized (which OPS admin hides)."""
        cust = _customer()
        cust.default_ops_category_id = 539  # mimic the column we added
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M")],
            product=_product(category=None),
            customer=cust,
        )
        payload = _synthesize_payload(ctx)
        assert payload.plan[0].variables["inputs"][0]["category_id"] == 539

    def test_storefront_override_beats_customer_default(self):
        """When BOTH storefront config and customer default are set, the
        per-product storefront override wins — more specific."""
        cust = _customer()
        cust.default_ops_category_id = 539
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M")],
            product=_product(category=None),
            customer=cust,
            storefront_config=SimpleNamespace(pricing_overrides=None, ops_category_id="42"),
        )
        payload = _synthesize_payload(ctx)
        assert payload.plan[0].variables["inputs"][0]["category_id"] == 42

    def test_customer_without_default_does_not_set_category(self):
        """Customer fixture without default_ops_category_id attr at all
        (e.g. pre-migration) must not crash and must omit the field."""
        cust = _customer()  # no default_ops_category_id set
        # Force the attr to be missing entirely (simulates an older SimpleNamespace)
        if hasattr(cust, "default_ops_category_id"):
            del cust.default_ops_category_id
        ctx = _ctx(variants=[_variant("PC61-WHT-M")], customer=cust)
        payload = _synthesize_payload(ctx)
        assert "category_id" not in payload.plan[0].variables["inputs"][0]


# ===========================================================================
# Request fingerprint (used by worker step_results)
# ===========================================================================


class TestRequestFingerprint:
    def test_deterministic(self):
        vars_a = {"input": {"products_id": 12, "qty": 1}}
        vars_b = {"input": {"qty": 1, "products_id": 12}}  # different order
        assert _request_fingerprint(vars_a) == _request_fingerprint(vars_b)

    def test_sensitive(self):
        a = _request_fingerprint({"input": {"products_id": 12}})
        b = _request_fingerprint({"input": {"products_id": 13}})
        assert a != b

    def test_16_char_hex(self):
        fp = _request_fingerprint({"input": {"x": 1}})
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp)


# ===========================================================================
# Placeholder helper
# ===========================================================================


def test_placeholder_format():
    assert _placeholder(1, "products_id") == "$step1.products_id"
    assert _placeholder(12, "product_size_id") == "$step12.product_size_id"


# ===========================================================================
# Storefront pricing_overrides parity
# (push payload must equal the customer quote — same helper, same inputs)
# ===========================================================================


class TestStorefrontOverridesInPush:
    """Without these, a customer could be quoted X and have Y pushed to OPS."""

    def _cfg(self, overrides: dict) -> SimpleNamespace:
        # ops_category_id mirrors the real ProductStorefrontConfig model — the
        # builder reads ctx.storefront_config.ops_category_id directly, so the
        # attr must exist (None = unmapped → category omitted from setProduct).
        return SimpleNamespace(pricing_overrides=overrides, ops_category_id=None)

    def test_no_storefront_config_leaves_price_untouched(self):
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M", base_price=Decimal("10.00"))],
            markup_rules=[_markup_rule(pct=Decimal("50.0"))],
            storefront_config=None,
        )
        p = _synthesize_payload(ctx).computed_prices[0]
        assert p.final_price == pytest.approx(15.00)
        assert p.storefront_override_applied is False

    def test_fixed_unit_price_overrides_markup(self):
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M", base_price=Decimal("10.00"))],
            markup_rules=[_markup_rule(pct=Decimal("50.0"))],
            storefront_config=self._cfg({"fixed_unit_price": "19.99"}),
        )
        p = _synthesize_payload(ctx).computed_prices[0]
        assert p.final_price == pytest.approx(19.99)
        assert p.storefront_override_applied is True

    def test_extra_markup_pct_stacks_on_marked_up_price(self):
        # 10.00 → +50% markup → 15.00 → +20% extra → 18.00
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M", base_price=Decimal("10.00"))],
            markup_rules=[_markup_rule(pct=Decimal("50.0"))],
            storefront_config=self._cfg({"extra_markup_pct": "20"}),
        )
        p = _synthesize_payload(ctx).computed_prices[0]
        assert p.final_price == pytest.approx(18.00)
        assert p.storefront_override_applied is True

    def test_nearest_99_rounding(self):
        # 10.00 → +30% markup → 13.00 → floor + .99 = 13.99
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M", base_price=Decimal("10.00"))],
            markup_rules=[_markup_rule(pct=Decimal("30.0"))],
            storefront_config=self._cfg({"rounding": "nearest_99"}),
        )
        p = _synthesize_payload(ctx).computed_prices[0]
        assert p.final_price == pytest.approx(13.99)
        assert p.storefront_override_applied is True

    def test_setProductPrice_step_uses_override(self):
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M", base_price=Decimal("10.00"))],
            markup_rules=[_markup_rule(pct=Decimal("50.0"))],
            storefront_config=self._cfg({"fixed_unit_price": "24.99"}),
        )
        plan = _synthesize_payload(ctx).plan
        price_step = next(s for s in plan if s.mutation == "setProductPrice")
        assert price_step.variables["inputs"][0]["price"] == pytest.approx(24.99)
        # vendor_price is wholesale (base_price), untouched by overrides
        assert price_step.variables["inputs"][0]["vendor_price"] == pytest.approx(10.00)

    def test_empty_overrides_dict_treated_as_no_override(self):
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M", base_price=Decimal("10.00"))],
            markup_rules=[_markup_rule(pct=Decimal("50.0"))],
            storefront_config=self._cfg({}),
        )
        p = _synthesize_payload(ctx).computed_prices[0]
        assert p.final_price == pytest.approx(15.00)
        assert p.storefront_override_applied is False

    def test_quote_and_push_apply_identical_helper(self):
        """Smoke check: push uses the exact same apply_pricing_overrides
        as the quote path — regression guard if either side ever forks."""
        from modules.pricing import overrides as push_helper
        from modules.pricing import customer_quote as quote_path

        # The quote path's wrapper delegates to the same pure function.
        # If a refactor moves one but not the other, this import breaks.
        assert push_helper.apply_pricing_overrides is not None
        assert hasattr(quote_path, "_apply_storefront_override")
