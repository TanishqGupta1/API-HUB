"""Integration Gateway M1 — preflight unit tests.

Hermetic — no DB, no real HTTP. Network-touching checks (4, 5, 6) are
tested with mocked httpx + injected ops_query_fn.

Covers the 8 checks + the new 4a `customer_ops_creds_present` split-out
+ the `to_error_envelope()` shape consumed by the gateway 422 response
+ the token cache behavior locked by Rev 1 §"OPS credential resolution".
"""
from __future__ import annotations

import time
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.no_db

from modules.ops_push.preflight import (
    CheckResult,
    PreflightResults,
    TOKEN_CACHE,
    _PreflightContext,
    _TokenCache,
    check_base_price_set,
    check_customer_ops_creds_present,
    check_decoration_attached,
    check_image_urls_reachable,
    check_markup_rule_resolves,
    check_ops_oauth2_reachable,
    check_prefix_collision,
    check_push_mappings_present,
    check_required_fields,
)


# ---------------------------------------------------------------------------
# Mock factories
# ---------------------------------------------------------------------------


def _supplier(
    slug: str = "sanmar", has_decoration_overlay: bool = False
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        slug=slug,
        push_name_prefix="VG-",
        has_decoration_overlay=has_decoration_overlay,
    )


def _customer(
    ops_base_url: str = "https://staging.visualgraphx.com",
    ops_token_url: str = "https://staging.visualgraphx.com/oauth/token",
    ops_client_id: str = "abcd1234",
    client_secret: str = "shh",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="Visual Graphics",
        ops_base_url=ops_base_url,
        ops_token_url=ops_token_url,
        ops_client_id=ops_client_id,
        ops_auth_config={"client_secret": client_secret} if client_secret else {},
        is_active=True,
    )


def _product(
    sku: str = "PC61",
    name: str = "Port & Co Essential T-Shirt",
    category: str | None = "T-Shirts",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        supplier_id=uuid.uuid4(),
        supplier_sku=sku,
        product_name=name,
        category=category,
        brand="Port & Company",
        description="",
        product_type="apparel",
        image_url=None,
        last_synced=None,
        archived_at=None,
    )


def _variant(
    sku: str,
    base_price: Decimal | None = Decimal("8.32"),
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        sku=sku,
        color="White",
        size="M",
        base_price=base_price,
        inventory=50,
    )


def _image(url: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), url=url, sort_order=0, image_type="front")


def _option(option_key: str, attribute_keys: list[str] | None = None) -> SimpleNamespace:
    attrs = [
        SimpleNamespace(id=uuid.uuid4(), attribute_key=k, title=k, ops_attribute_id=None)
        for k in (attribute_keys or [])
    ]
    return SimpleNamespace(
        id=uuid.uuid4(),
        option_key=option_key,
        title=option_key,
        attributes=attrs,
    )


def _mapping(
    source_option_key: str | None = None,
    source_attribute_key: str | None = None,
    target_option_id: int | None = None,
    target_attribute_id: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        source_option_key=source_option_key,
        source_attribute_key=source_attribute_key,
        target_ops_option_id=target_option_id,
        target_ops_attribute_id=target_attribute_id,
        price=None,
        sort_order=None,
    )


def _rule(
    scope: str = "all",
    markup_pct: float | None = 50.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        scope=scope,
        markup_pct=Decimal(str(markup_pct)) if markup_pct is not None else None,
        markup_amount=None,
        rounding="none",
        priority=0,
        is_active=True,
        min_price=None,
        max_price=None,
        min_margin=None,
        effective_from=None,
        effective_until=None,
    )


def _push_mapping(target_ops_product_id: int | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        target_ops_product_id=target_ops_product_id,
        options=[],
    )


_UNSET = object()


def _ctx(
    *,
    customer: SimpleNamespace | None = None,
    product: SimpleNamespace | None = None,
    supplier: SimpleNamespace | None = None,
    variants=_UNSET,
    images=_UNSET,
    options=_UNSET,
    markup_rules=_UNSET,
    push_mapping=None,
    push_mapping_options=_UNSET,
    decoration_options=_UNSET,
) -> _PreflightContext:
    return _PreflightContext(
        customer=customer or _customer(),
        product=product or _product(),
        supplier=supplier or _supplier(),
        variants=[_variant("PC61WHT-M")] if variants is _UNSET else variants,
        images=[_image("https://cdn/x.jpg")] if images is _UNSET else images,
        options=[] if options is _UNSET else options,
        markup_rules=[_rule()] if markup_rules is _UNSET else markup_rules,
        push_mapping=push_mapping,
        push_mapping_options=[] if push_mapping_options is _UNSET else push_mapping_options,
        decoration_options=[] if decoration_options is _UNSET else decoration_options,
    )


# ===========================================================================
# 1 — base_price_set
# ===========================================================================


def test_base_price_set_pass_when_all_variants_have_price():
    ctx = _ctx(variants=[
        _variant("A", base_price=Decimal("5")),
        _variant("B", base_price=Decimal("10")),
    ])
    r = check_base_price_set(ctx)
    assert r.ok is True
    assert "2 variants" in r.detail


def test_base_price_set_fail_when_any_variant_has_none():
    ctx = _ctx(variants=[
        _variant("A", base_price=Decimal("5")),
        _variant("B", base_price=None),  # the Bug 1 case
    ])
    r = check_base_price_set(ctx)
    assert r.ok is False
    assert "B" in r.detail
    # New: fail results carry field + suggestion for the error envelope
    assert r.field == "product.variants[].base_price"
    assert r.suggestion is not None


def test_base_price_set_fail_when_variant_has_zero_price():
    ctx = _ctx(variants=[_variant("A", base_price=Decimal("0"))])
    r = check_base_price_set(ctx)
    assert r.ok is False


def test_base_price_set_pass_when_no_variants():
    ctx = _ctx(variants=[])
    r = check_base_price_set(ctx)
    assert r.ok is True


# ===========================================================================
# 2 — markup_rule_resolves
# ===========================================================================


def test_markup_rule_resolves_pass_with_global_rule():
    ctx = _ctx(markup_rules=[_rule(scope="all", markup_pct=50.0)])
    r = check_markup_rule_resolves(ctx)
    assert r.ok is True
    assert "50" in r.detail


def test_markup_rule_resolves_fail_when_no_rules():
    ctx = _ctx(markup_rules=[])
    r = check_markup_rule_resolves(ctx)
    assert r.ok is False
    assert "no markup rule" in r.detail.lower()
    assert r.field == "customer.markup_rules"


# ===========================================================================
# 3 — push_mappings_present
# ===========================================================================


def test_push_mappings_present_pass_when_no_options():
    ctx = _ctx(options=[], push_mapping_options=[])
    r = check_push_mappings_present(ctx)
    assert r.ok is True


def test_push_mappings_present_pass_when_all_options_mapped():
    opts = [_option("color"), _option("size")]
    mappings = [
        _mapping(source_option_key="color", target_option_id=42),
        _mapping(source_option_key="size", target_option_id=43),
    ]
    ctx = _ctx(options=opts, push_mapping_options=mappings)
    r = check_push_mappings_present(ctx)
    assert r.ok is True


def test_push_mappings_present_fail_when_no_mappings_at_all():
    opts = [_option("color"), _option("size")]
    ctx = _ctx(options=opts, push_mapping_options=[])
    r = check_push_mappings_present(ctx)
    assert r.ok is False
    assert "missing" in r.detail.lower()
    assert r.field == "push_mappings.target_ops_option_id"


def test_push_mappings_present_fail_when_target_option_id_is_null():
    opts = [_option("color")]
    mappings = [_mapping(source_option_key="color", target_option_id=None)]
    ctx = _ctx(options=opts, push_mapping_options=mappings)
    r = check_push_mappings_present(ctx)
    assert r.ok is False
    assert "color" in r.detail


def test_push_mappings_present_fail_on_unmapped_attribute():
    opts = [_option("color", attribute_keys=["white", "black"])]
    mappings = [
        _mapping(source_option_key="color", target_option_id=42),
        _mapping(
            source_option_key="color",
            source_attribute_key="white",
            target_option_id=42,
            target_attribute_id=101,
        ),
    ]
    ctx = _ctx(options=opts, push_mapping_options=mappings)
    r = check_push_mappings_present(ctx)
    assert r.ok is False
    assert "black" in r.detail


# ===========================================================================
# 4a — customer_ops_creds_present (NEW — split out from check 4)
# ===========================================================================


def test_customer_ops_creds_pass_when_all_fields_set():
    ctx = _ctx()
    r = check_customer_ops_creds_present(ctx)
    assert r.ok is True


def test_customer_ops_creds_fail_when_base_url_missing():
    ctx = _ctx(customer=_customer(ops_base_url=""))
    r = check_customer_ops_creds_present(ctx)
    assert r.ok is False
    assert "ops_base_url" in r.detail
    assert r.field == "customer.ops_base_url"


def test_customer_ops_creds_fail_when_token_url_missing():
    ctx = _ctx(customer=_customer(ops_token_url=""))
    r = check_customer_ops_creds_present(ctx)
    assert r.ok is False
    assert "ops_token_url" in r.detail


def test_customer_ops_creds_fail_when_client_secret_missing():
    ctx = _ctx(customer=_customer(client_secret=""))
    r = check_customer_ops_creds_present(ctx)
    assert r.ok is False
    assert "client_secret" in r.detail


# ===========================================================================
# 4 — ops_oauth2_reachable + token cache
# ===========================================================================


@pytest.mark.asyncio
async def test_ops_oauth2_fail_when_token_url_missing():
    ctx = _ctx(customer=_customer(ops_token_url=""))
    cache = _TokenCache()
    r = await check_ops_oauth2_reachable(ctx, token_cache=cache)
    assert r.ok is False
    assert "missing" in r.detail.lower()


@pytest.mark.asyncio
async def test_ops_oauth2_pass_on_200_response():
    ctx = _ctx()
    cache = _TokenCache()

    class _FakeResp:
        status_code = 200
        headers = {"content-type": "application/json"}
        def json(self): return {"access_token": "x", "expires_in": 3600}

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): return _FakeResp()

    with patch("modules.ops_push.preflight.httpx.AsyncClient", _FakeClient):
        r = await check_ops_oauth2_reachable(ctx, token_cache=cache)
    assert r.ok is True
    assert "3600" in r.detail


@pytest.mark.asyncio
async def test_ops_oauth2_fail_on_401_response():
    ctx = _ctx()
    cache = _TokenCache()

    class _FakeResp:
        status_code = 401
        headers = {}
        def json(self): return {}

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): return _FakeResp()

    with patch("modules.ops_push.preflight.httpx.AsyncClient", _FakeClient):
        r = await check_ops_oauth2_reachable(ctx, token_cache=cache)
    assert r.ok is False
    assert "401" in r.detail
    assert r.field == "customer.ops_auth_config.client_secret"


@pytest.mark.asyncio
async def test_ops_oauth2_cache_hit_skips_http_call():
    """Second call within TTL must not hit the network."""
    ctx = _ctx()
    cache = _TokenCache()

    call_count = {"n": 0}

    class _FakeResp:
        status_code = 200
        headers = {"content-type": "application/json"}
        def json(self): return {"access_token": "x", "expires_in": 3600}

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw):
            call_count["n"] += 1
            return _FakeResp()

    with patch("modules.ops_push.preflight.httpx.AsyncClient", _FakeClient):
        r1 = await check_ops_oauth2_reachable(ctx, token_cache=cache)
        r2 = await check_ops_oauth2_reachable(ctx, token_cache=cache)

    assert r1.ok is True
    assert r2.ok is True
    assert call_count["n"] == 1  # second call served from cache
    assert "cache hit" in r2.detail.lower()


# ===========================================================================
# Token cache unit tests
# ===========================================================================


def test_token_cache_set_get():
    cache = _TokenCache()
    key = ("cust-1", "https://x", "client-a")
    cache.set(key, "tok-abc", expires_in=3600)
    assert cache.get(key) == "tok-abc"


def test_token_cache_returns_none_when_expired():
    cache = _TokenCache()
    key = ("cust-1", "https://x", "client-a")
    # expires_in=1, safety margin=60 → effective TTL of max(1-60, 1) = 1s
    cache.set(key, "tok-abc", expires_in=1)
    # Force expiry by mutating internal state
    cache._store[key].expires_at = time.time() - 1
    assert cache.get(key) is None


def test_token_cache_evict():
    cache = _TokenCache()
    key = ("cust-1", "https://x", "client-a")
    cache.set(key, "tok-abc", expires_in=3600)
    cache.evict(key)
    assert cache.get(key) is None


def test_token_cache_clear():
    cache = _TokenCache()
    cache.set(("a", "b", "c"), "tok-1", expires_in=3600)
    cache.set(("d", "e", "f"), "tok-2", expires_in=3600)
    cache.clear()
    assert cache.get(("a", "b", "c")) is None
    assert cache.get(("d", "e", "f")) is None


def test_token_cache_default_ttl_when_expires_in_missing():
    cache = _TokenCache()
    key = ("x", "y", "z")
    cache.set(key, "tok", expires_in=None)
    # Default TTL is 300s, so should still be cached now
    assert cache.get(key) == "tok"


# ===========================================================================
# 5 — image_urls_reachable
# ===========================================================================


@pytest.mark.asyncio
async def test_image_urls_reachable_fail_with_no_images():
    """NEW: empty images is now a BLOCKER per Rev 1 §'Preflight gates'."""
    ctx = _ctx(images=[])
    r = await check_image_urls_reachable(ctx)
    assert r.ok is False
    assert "no images" in r.detail.lower()


@pytest.mark.asyncio
async def test_image_urls_reachable_pass_all_2xx():
    ctx = _ctx(images=[_image("https://cdn/a.jpg"), _image("https://cdn/b.jpg")])

    class _FakeResp:
        def __init__(self, code): self.status_code = code

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def head(self, *a, **kw): return _FakeResp(200)

    with patch("modules.ops_push.preflight.httpx.AsyncClient", _FakeClient):
        r = await check_image_urls_reachable(ctx, timeout_seconds=0.5)
    assert r.ok is True
    assert "2/2" in r.detail


@pytest.mark.asyncio
async def test_image_urls_reachable_fail_any_non_2xx():
    ctx = _ctx(images=[_image("https://cdn/a.jpg"), _image("https://cdn/dead.jpg")])

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def head(self, url, **kw):
            class _R: pass
            r = _R()
            r.status_code = 404 if "dead" in url else 200
            return r

    with patch("modules.ops_push.preflight.httpx.AsyncClient", _FakeClient):
        r = await check_image_urls_reachable(ctx, timeout_seconds=0.5)
    assert r.ok is False
    assert "1/2" in r.detail


# ===========================================================================
# 6 — prefix_collision
# ===========================================================================


@pytest.mark.asyncio
async def test_prefix_collision_pass_when_no_ops_query_wired():
    ctx = _ctx()
    r = await check_prefix_collision(ctx, ops_query_fn=None)
    assert r.ok is True
    assert "skipped" in r.detail.lower()


@pytest.mark.asyncio
async def test_prefix_collision_pass_when_ops_has_no_match():
    ctx = _ctx()
    async def fake_fn(*, internal_title): return None
    r = await check_prefix_collision(ctx, ops_query_fn=fake_fn)
    assert r.ok is True


@pytest.mark.asyncio
async def test_prefix_collision_fail_when_ops_has_unclaimed_match():
    ctx = _ctx()
    async def fake_fn(*, internal_title):
        return {"products_id": 12345, "internal_title": internal_title}
    r = await check_prefix_collision(ctx, ops_query_fn=fake_fn)
    assert r.ok is False
    assert "already has" in r.detail.lower()


@pytest.mark.asyncio
async def test_prefix_collision_pass_when_existing_claimed_by_push_mapping():
    """NEW: if our push_mapping already claims the existing OPS product,
    that's an update — not a blocker."""
    ctx = _ctx(push_mapping=_push_mapping(target_ops_product_id=12345))
    async def fake_fn(*, internal_title):
        return {"products_id": 12345, "internal_title": internal_title}
    r = await check_prefix_collision(ctx, ops_query_fn=fake_fn)
    assert r.ok is True
    assert "update mode" in r.detail


@pytest.mark.asyncio
async def test_prefix_collision_fail_when_ops_query_raises():
    ctx = _ctx()
    async def fake_fn(*, internal_title):
        raise RuntimeError("ops down")
    r = await check_prefix_collision(ctx, ops_query_fn=fake_fn)
    assert r.ok is False
    assert "could not query" in r.detail.lower()


# ===========================================================================
# 7 — required_fields
# ===========================================================================


def test_required_fields_pass_with_all_required():
    ctx = _ctx()
    r = check_required_fields(ctx)
    assert r.ok is True


def test_required_fields_fail_when_product_name_empty():
    ctx = _ctx(product=_product(name=""))
    r = check_required_fields(ctx)
    assert r.ok is False
    assert "product_name" in r.detail


def test_required_fields_fail_when_supplier_sku_empty():
    ctx = _ctx(product=_product(sku=""))
    r = check_required_fields(ctx)
    assert r.ok is False
    assert "supplier_sku" in r.detail


def test_required_fields_fail_when_no_variants():
    ctx = _ctx(variants=[])
    r = check_required_fields(ctx)
    assert r.ok is False
    assert "variant" in r.detail


# Note: image presence is now check 5's job (image_urls_reachable), not 7.


# ===========================================================================
# 8 — decoration_attached
# ===========================================================================


def test_decoration_pass_when_supplier_doesnt_require_overlay():
    ctx = _ctx(supplier=_supplier(has_decoration_overlay=False))
    r = check_decoration_attached(ctx)
    assert r.ok is True
    assert "doesn't require" in r.detail


def test_decoration_pass_when_overlay_required_and_attached():
    ctx = _ctx(
        supplier=_supplier(has_decoration_overlay=True),
        decoration_options=[{"placement": "front", "method": "screen-print"}],
    )
    r = check_decoration_attached(ctx)
    assert r.ok is True
    assert "1 decoration option" in r.detail


def test_decoration_fail_when_overlay_required_but_no_options():
    ctx = _ctx(
        supplier=_supplier(has_decoration_overlay=True),
        decoration_options=[],
    )
    r = check_decoration_attached(ctx)
    assert r.ok is False
    assert "no decoration_options" in r.detail


# ===========================================================================
# Aggregate result shape + new error envelope
# ===========================================================================


def test_preflight_results_blockers_lists_failed_check_names():
    results = PreflightResults(
        checks=[
            CheckResult("base_price_set", True, "ok"),
            CheckResult("push_mappings_present", False, "missing target_ops_option_id"),
            CheckResult("required_fields", False, "missing image"),
        ]
    )
    assert results.blockers == ["push_mappings_present", "required_fields"]
    assert results.ok is False


def test_preflight_results_ok_true_when_all_pass():
    results = PreflightResults(
        checks=[
            CheckResult("base_price_set", True, "ok"),
            CheckResult("required_fields", True, "ok"),
        ]
    )
    assert results.ok is True
    assert results.blockers == []


def test_preflight_results_first_failure_returns_first_blocker():
    results = PreflightResults(
        checks=[
            CheckResult("base_price_set", True, "ok"),
            CheckResult("push_mappings_present", False, "missing X"),
            CheckResult("required_fields", False, "missing Y"),
        ]
    )
    first = results.first_failure
    assert first is not None
    assert first.name == "push_mappings_present"


def test_preflight_results_first_failure_is_none_when_all_pass():
    results = PreflightResults(checks=[CheckResult("base_price_set", True, "ok")])
    assert results.first_failure is None


def test_to_error_envelope_shape_with_blockers():
    results = PreflightResults(
        checks=[
            CheckResult(
                "base_price_set",
                False,
                "2 variants missing base_price",
                field="product.variants[].base_price",
                suggestion="Re-sync supplier inventory",
            ),
            CheckResult("required_fields", True, "ok"),
        ]
    )
    env = results.to_error_envelope(trace_id="push-log-uuid")
    assert env["status"] == "error"
    assert env["code"] == "PREFLIGHT_BLOCKER"
    assert env["message"] == "2 variants missing base_price"
    assert env["details"]["field"] == "product.variants[].base_price"
    assert env["details"]["suggestion"] == "Re-sync supplier inventory"
    assert env["details"]["blockers"] == ["base_price_set"]
    assert env["trace_id"] == "push-log-uuid"


def test_to_error_envelope_when_passing():
    results = PreflightResults(checks=[CheckResult("required_fields", True, "ok")])
    env = results.to_error_envelope()
    assert env["status"] == "error"  # envelope shape is always 'error' code form
    assert env["message"] == "Preflight passed."
    assert env["details"]["blockers"] == []
    assert env["trace_id"] is None


def test_preflight_results_to_dict_matches_spec_shape():
    results = PreflightResults(
        checks=[
            CheckResult("base_price_set", True, "all 12 variants have base_price > 0")
        ]
    )
    d = results.to_dict()
    assert set(d.keys()) == {"checks", "blockers", "warnings", "computed_at"}
    # New: each check now also has field + suggestion (nullable)
    assert d["checks"][0]["name"] == "base_price_set"
    assert d["checks"][0]["ok"] is True
    assert d["blockers"] == []
    assert isinstance(d["computed_at"], str)
    assert "T" in d["computed_at"]


# ===========================================================================
# Module-level TOKEN_CACHE singleton sanity
# ===========================================================================


def test_module_token_cache_is_singleton_token_cache():
    # Ensure exports include the singleton and it's of the expected type
    assert isinstance(TOKEN_CACHE, _TokenCache)
