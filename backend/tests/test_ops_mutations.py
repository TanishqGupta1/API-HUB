"""Tests for OPS mutation wrappers (T6–T9).

Uses unittest.mock.AsyncMock so no HTTP calls are made.
Verifies:
- Correct GraphQL variables are sent (field names match OPS spec)
- Returned OpsResult.data is unwrapped (e.g. {"category_id": 42}, not {"setProductCategory": ...})
- Error pass-through works
- qty_to is included in set_product_price when provided
"""
import pytest
from unittest.mock import AsyncMock

from modules.ops_client.client import OpsAuth, OpsGraphQLClient, OpsResult
from modules.ops_client import mutations as m


@pytest.fixture
def fake_client():
    c = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
    c.execute = AsyncMock()
    return c


# ── T6: set_product_category ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_product_category_sends_canonical_fields(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProductCategory": {"category_id": 42}}
    )
    result = await m.set_product_category(
        client=fake_client, category_name="T-Shirts", parent_id=0, visible=1,
    )
    assert result.ok
    _, kwargs = fake_client.execute.call_args
    v = kwargs["variables"]["input"]
    assert v["category_name"] == "T-Shirts"
    assert v["parent_id"] == 0
    assert v["visible"] == 1


@pytest.mark.asyncio
async def test_set_product_category_extracts_id(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProductCategory": {"category_id": 99}}
    )
    result = await m.set_product_category(
        client=fake_client, category_name="Polos", parent_id=0, visible=1,
    )
    assert result.ok
    assert result.data["category_id"] == 99


@pytest.mark.asyncio
async def test_set_product_category_passes_through_error(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=False, ops_error_code="DUPLICATE", ops_error_message="already exists"
    )
    result = await m.set_product_category(client=fake_client, category_name="X")
    assert not result.ok
    assert result.ops_error_code == "DUPLICATE"


# ── T7: set_product ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_product_threads_category_id(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProduct": {"products_id": 12345}}
    )
    result = await m.set_product(
        client=fake_client,
        category_id=42,
        products_title="Port & Company PC61",
        products_internal_title="PC61",
        visible=1,
    )
    _, kwargs = fake_client.execute.call_args
    v = kwargs["variables"]["input"]
    assert v["category_id"] == 42
    assert v["products_title"] == "Port & Company PC61"
    assert v["products_internal_title"] == "PC61"
    assert v["visible"] == 1
    assert result.ok
    assert result.data["products_id"] == 12345


@pytest.mark.asyncio
async def test_set_product_passes_through_error(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=False, ops_error_code="BAD_INPUT", ops_error_message="invalid category"
    )
    result = await m.set_product(
        client=fake_client, category_id=999, products_title="X", products_internal_title="X"
    )
    assert not result.ok
    assert result.ops_error_code == "BAD_INPUT"


# ── T8: set_product_size ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_product_size_threads_products_id(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProductSize": {"size_id": 555}}
    )
    result = await m.set_product_size(
        client=fake_client,
        products_id=12345,
        size_name="M",
        color_name="Navy",
        products_sku="PC61-NAV-M",
        visible=1,
    )
    _, kwargs = fake_client.execute.call_args
    v = kwargs["variables"]["input"]
    assert v["products_id"] == 12345
    assert v["size_name"] == "M"
    assert v["color_name"] == "Navy"
    assert v["products_sku"] == "PC61-NAV-M"
    assert result.ok
    assert result.data["size_id"] == 555


# ── T9: set_product_price ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_product_price_threads_products_id_and_size_id(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProductPrice": {"product_price_id": 7777}}
    )
    result = await m.set_product_price(
        client=fake_client,
        products_id=12345,
        size_id=555,
        qty=1,
        qty_to=None,
        price="9.99",
        vendor_price="3.99",
        visible=1,
    )
    _, kwargs = fake_client.execute.call_args
    v = kwargs["variables"]["input"]
    assert v["products_id"] == 12345
    assert v["size_id"] == 555
    assert v["price"] == "9.99"
    assert v["vendor_price"] == "3.99"
    assert "qty_to" not in v
    assert result.ok
    assert result.data["product_price_id"] == 7777


@pytest.mark.asyncio
async def test_set_product_price_includes_qty_to_when_provided(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProductPrice": {"product_price_id": 8888}}
    )
    await m.set_product_price(
        client=fake_client,
        products_id=1,
        size_id=2,
        price="9.99",
        vendor_price="5.00",
        qty=1,
        qty_to=11,
    )
    _, kwargs = fake_client.execute.call_args
    assert kwargs["variables"]["input"]["qty_to"] == 11
