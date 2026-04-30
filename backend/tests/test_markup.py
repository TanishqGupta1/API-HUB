"""Tests for /api/markup-rules, /api/push payload, and the markup engine."""
from decimal import Decimal
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import delete

from database import async_session
from modules.customers.models import Customer
from modules.markup.engine import apply_markup, resolve_rule
from modules.markup.models import MarkupRule


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

INGEST_SECRET = "test-secret-do-not-use-in-prod"  # set in conftest.py

CUSTOMER_PAYLOAD = {
    "name": "Markup Test Corp",
    "ops_base_url": "https://markupcorp.onprintshop.com/api",
    "ops_token_url": "https://markupcorp.onprintshop.com/oauth/token",
    "ops_client_id": "markup-client",
    "ops_client_secret": "markup-secret",
}


async def _delete_markup_customers() -> None:
    async with async_session() as s:
        await s.execute(
            delete(Customer).where(Customer.name.in_(["Markup Test Corp"]))
        )
        await s.commit()


def _rule(scope="all", markup_pct=30.0, priority=0, min_margin=None, rounding="none"):
    return SimpleNamespace(
        scope=scope,
        markup_pct=markup_pct,
        priority=priority,
        min_margin=min_margin,
        rounding=rounding,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def _cleanup():
    await _delete_markup_customers()
    yield
    await _delete_markup_customers()


@pytest_asyncio.fixture
async def seed_customer(client):
    resp = await client.post("/api/customers", json=CUSTOMER_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def seed_product(client, seed_supplier):
    """Create one product + variant via the ingest endpoint."""
    payload = [
        {
            "supplier_sku": "TEST-SKU-001",
            "product_name": "Test Tee",
            "brand": "TestBrand",
            "category": "T-Shirts",
            "product_type": "apparel",
            "description": "A test tee",
            "variants": [
                {
                    "part_id": "v1",
                    "color": "Navy",
                    "size": "M",
                    "sku": "TEST-SKU-001-NAVY-M",
                    "base_price": 10.00,
                    "inventory": 50,
                    "warehouse": "WH1",
                }
            ],
            "images": [
                {"url": "https://example.com/img.jpg", "image_type": "front", "color": "Navy", "sort_order": 0}
            ],
        }
    ]
    resp = await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        json=payload,
        headers={"X-Ingest-Secret": INGEST_SECRET},
    )
    assert resp.status_code == 200

    # Fetch the product so we have its UUID
    products = await client.get(f"/api/products?supplier_id={seed_supplier.id}")
    assert products.status_code == 200
    items = products.json()
    assert len(items) >= 1
    return items[0]


# ---------------------------------------------------------------------------
# Unit tests — resolve_rule
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestResolveRule:
    async def test_no_rules_returns_none(self):
        assert resolve_rule([], "PC61", "T-Shirts") is None

    async def test_all_scope_matches(self):
        rules = [_rule("all", 30.0, priority=0)]
        assert resolve_rule(rules, "PC61", "T-Shirts") is rules[0]

    async def test_product_scope_beats_all(self):
        all_rule = _rule("all", 30.0, priority=10)
        product_rule = _rule("product:PC61", 45.0, priority=0)
        result = resolve_rule([all_rule, product_rule], "PC61", "T-Shirts")
        assert result is product_rule

    async def test_category_scope_beats_all(self):
        all_rule = _rule("all", 30.0, priority=0)
        cat_rule = _rule("category:T-Shirts", 40.0, priority=0)
        result = resolve_rule([all_rule, cat_rule], "PC61", "T-Shirts")
        assert result is cat_rule

    async def test_product_scope_beats_category(self):
        cat_rule = _rule("category:T-Shirts", 40.0, priority=10)
        product_rule = _rule("product:PC61", 45.0, priority=0)
        result = resolve_rule([cat_rule, product_rule], "PC61", "T-Shirts")
        assert result is product_rule

    async def test_higher_priority_wins_same_scope(self):
        low = _rule("all", 30.0, priority=0)
        high = _rule("all", 45.0, priority=5)
        result = resolve_rule([low, high], "PC61", "T-Shirts")
        assert result is high

    async def test_no_category_skips_category_scope(self):
        cat_rule = _rule("category:T-Shirts", 40.0, priority=0)
        all_rule = _rule("all", 30.0, priority=0)
        result = resolve_rule([cat_rule, all_rule], "PC61", None)
        assert result is all_rule

    async def test_product_sku_mismatch_falls_through(self):
        product_rule = _rule("product:OTHER-SKU", 45.0, priority=10)
        all_rule = _rule("all", 30.0, priority=0)
        result = resolve_rule([product_rule, all_rule], "PC61", "T-Shirts")
        assert result is all_rule


# ---------------------------------------------------------------------------
# Unit tests — apply_markup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestApplyMarkup:
    async def test_no_rule_returns_base_price(self):
        result = apply_markup(Decimal("10.00"), None)
        assert result == Decimal("10.00")

    async def test_none_base_price_returns_none(self):
        assert apply_markup(None, _rule("all", 30.0)) is None

    async def test_basic_markup(self):
        rule = _rule("all", 30.0)
        result = apply_markup(Decimal("10.00"), rule)
        assert result == Decimal("13.00")

    async def test_markup_rounds_to_cents(self):
        rule = _rule("all", 33.0)  # 10 * 1.33 = 13.30
        result = apply_markup(Decimal("10.00"), rule)
        assert result == Decimal("13.30")

    async def test_min_margin_floor_applied(self):
        rule = _rule("all", markup_pct=10.0, min_margin=50.0)
        result = apply_markup(Decimal("10.00"), rule)
        assert result == Decimal("15.00")

    async def test_min_margin_not_applied_when_markup_sufficient(self):
        rule = _rule("all", markup_pct=60.0, min_margin=50.0)
        result = apply_markup(Decimal("10.00"), rule)
        assert result == Decimal("16.00")

    async def test_rounding_nearest_99(self):
        rule = _rule("all", markup_pct=45.0, rounding="nearest_99")
        result = apply_markup(Decimal("10.00"), rule)
        assert result == Decimal("14.99")

    async def test_rounding_nearest_dollar(self):
        rule = _rule("all", markup_pct=45.0, rounding="nearest_dollar")
        result = apply_markup(Decimal("10.00"), rule)
        assert result == Decimal("14.00")

    async def test_rounding_none_keeps_exact_cents(self):
        rule = _rule("all", markup_pct=30.0, rounding="none")
        result = apply_markup(Decimal("10.00"), rule)
        assert result == Decimal("13.00")

    async def test_zero_markup(self):
        rule = _rule("all", markup_pct=0.0)
        result = apply_markup(Decimal("10.00"), rule)
        assert result == Decimal("10.00")

    async def test_float_base_price_coercion(self):
        rule = _rule("all", markup_pct=30.0)
        result = apply_markup(10.0, rule)
        assert result == Decimal("13.00")


# ---------------------------------------------------------------------------
# API tests — GET/POST/DELETE /api/markup-rules
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_markup_rules_empty(client, seed_customer):
    resp = await client.get(f"/api/markup-rules/{seed_customer['id']}")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_markup_rule(client, seed_customer):
    payload = {
        "customer_id": seed_customer["id"],
        "scope": "all",
        "markup_pct": 30.0,
        "rounding": "none",
        "priority": 0,
    }
    resp = await client.post("/api/markup-rules", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["scope"] == "all"
    assert data["markup_pct"] == 30.0
    assert data["customer_id"] == seed_customer["id"]


@pytest.mark.asyncio
async def test_rules_ordered_by_priority_desc(client, seed_customer):
    cid = seed_customer["id"]
    for priority in (0, 5, 2):
        await client.post(
            "/api/markup-rules",
            json={"customer_id": cid, "scope": "all", "markup_pct": 30.0, "priority": priority},
        )
    resp = await client.get(f"/api/markup-rules/{cid}")
    priorities = [r["priority"] for r in resp.json()]
    assert priorities == sorted(priorities, reverse=True)


@pytest.mark.asyncio
async def test_delete_markup_rule(client, seed_customer):
    cid = seed_customer["id"]
    create = await client.post(
        "/api/markup-rules",
        json={"customer_id": cid, "scope": "all", "markup_pct": 30.0},
    )
    rule_id = create.json()["id"]

    resp = await client.delete(f"/api/markup-rules/{rule_id}")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}

    # Confirm gone
    rules = await client.get(f"/api/markup-rules/{cid}")
    ids = [r["id"] for r in rules.json()]
    assert rule_id not in ids


@pytest.mark.asyncio
async def test_delete_markup_rule_404(client):
    resp = await client.delete("/api/markup-rules/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API tests — GET /api/push/{customer_id}/product/{product_id}/payload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_push_payload_requires_ingest_secret(client, seed_customer, seed_product):
    resp = await client.get(
        f"/api/push/{seed_customer['id']}/product/{seed_product['id']}/payload"
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_push_payload_no_rule_returns_base_prices(client, seed_customer, seed_product):
    resp = await client.get(
        f"/api/push/{seed_customer['id']}/product/{seed_product['id']}/payload",
        headers={"X-Ingest-Secret": INGEST_SECRET},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["markup_rule"] is None
    for v in data["variants"]:
        if v["base_price"] is not None:
            assert v["final_price"] == v["base_price"]


@pytest.mark.asyncio
async def test_push_payload_with_all_scope_rule(client, seed_customer, seed_product):
    cid = seed_customer["id"]
    await client.post(
        "/api/markup-rules",
        json={"customer_id": cid, "scope": "all", "markup_pct": 30.0},
    )

    resp = await client.get(
        f"/api/push/{cid}/product/{seed_product['id']}/payload",
        headers={"X-Ingest-Secret": INGEST_SECRET},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["markup_rule"] is not None
    assert data["markup_rule"]["markup_pct"] == 30.0

    for v in data["variants"]:
        if v["base_price"] is not None:
            expected = round(float(v["base_price"]) * 1.30, 2)
            assert abs(float(v["final_price"]) - expected) < 0.01


@pytest.mark.asyncio
async def test_push_payload_product_scope_beats_all(client, seed_customer, seed_product):
    cid = seed_customer["id"]
    sku = seed_product["supplier_sku"]

    await client.post(
        "/api/markup-rules",
        json={"customer_id": cid, "scope": "all", "markup_pct": 30.0, "priority": 0},
    )
    await client.post(
        "/api/markup-rules",
        json={"customer_id": cid, "scope": f"product:{sku}", "markup_pct": 50.0, "priority": 1},
    )

    resp = await client.get(
        f"/api/push/{cid}/product/{seed_product['id']}/payload",
        headers={"X-Ingest-Secret": INGEST_SECRET},
    )
    data = resp.json()
    assert data["markup_rule"]["markup_pct"] == 50.0


@pytest.mark.asyncio
async def test_push_payload_inactive_customer_returns_409(client, seed_product):
    create = await client.post("/api/customers", json={
        **CUSTOMER_PAYLOAD, "name": "Inactive Corp"
    })
    cid = create.json()["id"]
    await client.patch(f"/api/customers/{cid}", json={"is_active": False})

    resp = await client.get(
        f"/api/push/{cid}/product/{seed_product['id']}/payload",
        headers={"X-Ingest-Secret": INGEST_SECRET},
    )
    assert resp.status_code == 409

    async with async_session() as s:
        await s.execute(delete(Customer).where(Customer.name == "Inactive Corp"))
        await s.commit()


@pytest.mark.asyncio
async def test_push_payload_unknown_product_returns_404(client, seed_customer):
    resp = await client.get(
        f"/api/push/{seed_customer['id']}/product/00000000-0000-0000-0000-000000000000/payload",
        headers={"X-Ingest-Secret": INGEST_SECRET},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_push_payload_includes_images(client, seed_customer, seed_product):
    resp = await client.get(
        f"/api/push/{seed_customer['id']}/product/{seed_product['id']}/payload",
        headers={"X-Ingest-Secret": INGEST_SECRET},
    )
    data = resp.json()
    assert len(data["images"]) >= 1
    assert data["images"][0]["url"] == "https://example.com/img.jpg"
    assert data["images"][0]["image_type"] == "front"
