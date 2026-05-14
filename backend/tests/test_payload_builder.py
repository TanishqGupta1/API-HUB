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

    def test_inventory_action_is_reset(self):
        ctx = _ctx(variants=[_variant("PC61-WHT-M", inventory=42)])
        payload = _synthesize_payload(ctx)
        stock_step = next(s for s in payload.plan if s.mutation == "updateProductStock")
        assert stock_step.variables["input"]["action"] == "Reset"
        assert stock_step.variables["input"]["stock_quantity"] == 42

    def test_no_setProductCategory_step(self):
        # Old spec had a separate setProductCategory step; new spec does not.
        ctx = _ctx(variants=[_variant("PC61-WHT-M")])
        payload = _synthesize_payload(ctx)
        assert not any(s.mutation == "setProductCategory" for s in payload.plan)
        # Category lives on setProduct.input instead.
        setProduct = payload.plan[0]
        assert "category_name" in setProduct.variables["input"]


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
        assert size_step.variables["input"]["products_id"] == _placeholder(1, "products_id")

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
        assert price_step_1.variables["input"]["size_id"].startswith("$step")
        assert 1 in price_step_2.requires_response_from
        # Sanity: the two prices reference different size steps
        assert price_step_1.variables["input"]["size_id"] != price_step_2.variables["input"]["size_id"]


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
        assert price_step.variables["input"]["price"] == pytest.approx(15.00)
        assert price_step.variables["input"]["vendor_price"] == pytest.approx(10.00)

    def test_qty_to_is_999999(self):
        ctx = _ctx(variants=[_variant("PC61-WHT-M")])
        payload = _synthesize_payload(ctx)
        price_step = next(s for s in payload.plan if s.mutation == "setProductPrice")
        assert price_step.variables["input"]["qty"] == 1
        assert price_step.variables["input"]["qty_to"] == 999999

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
        assert setProduct.variables["input"]["products_id"] == 0

    def test_update_mode_when_mapping_exists(self):
        mapping = _push_mapping(target_ops_product_id=12345)
        ctx = _ctx(variants=[_variant("PC61-WHT-M")], push_mapping=mapping)
        payload = _synthesize_payload(ctx)
        assert payload.push_mode == "update"
        assert payload.existing_ops_product_id == 12345
        setProduct = payload.plan[0]
        assert setProduct.variables["input"]["products_id"] == 12345


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
        assert payload.primary_image_url == "https://x/front.jpg"
        assert payload.image_warnings == []
        setProduct = payload.plan[0]
        assert setProduct.variables["input"]["products_image"] == "https://x/front.jpg"

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
        assert "products_image" not in setProduct.variables["input"]


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
        title = payload.plan[0].variables["input"]["products_title"]
        assert title.startswith("VG-")

    def test_falls_back_to_uppercase_slug(self):
        sup = _supplier(slug="sanmar", prefix=None)
        ctx = _ctx(variants=[_variant("PC61-WHT-M")], supplier=sup)
        payload = _synthesize_payload(ctx)
        title = payload.plan[0].variables["input"]["products_title"]
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
