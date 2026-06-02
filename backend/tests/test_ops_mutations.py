"""Tests for OPS mutation wrappers (T6–T11).

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

pytestmark = pytest.mark.no_db


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


# ── set_assign_options ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_assign_options_sends_products_id_and_options(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setAssignOptions": {"products_id": 12345}}
    )
    result = await m.set_assign_options(client=fake_client, products_id=12345, options_id=[1, 2, 3])
    assert result.ok
    assert result.data["products_id"] == 12345
    _, kwargs = fake_client.execute.call_args
    v = kwargs["variables"]["input"]
    assert v["products_id"] == 12345
    assert v["options_id"] == [1, 2, 3]


@pytest.mark.asyncio
async def test_set_assign_options_passes_through_error(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=False, ops_error_code="BAD_INPUT", ops_error_message="invalid options_id"
    )
    result = await m.set_assign_options(client=fake_client, products_id=1, options_id=[999])
    assert not result.ok
    assert result.ops_error_code == "BAD_INPUT"


# ── set_additional_option ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_additional_option_sends_fields(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setAdditionalOption": {"options_id": 77}}
    )
    result = await m.set_additional_option(
        client=fake_client, options_name="Color", options_type="dropdown", visible=1
    )
    assert result.ok
    assert result.data["options_id"] == 77
    _, kwargs = fake_client.execute.call_args
    v = kwargs["variables"]["input"]
    assert v["options_name"] == "Color"
    assert v["options_type"] == "dropdown"


# ── set_additional_option_attributes ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_additional_option_attributes_sends_fields(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setAdditionalOptionAttributes": {"options_values_id": 55}}
    )
    result = await m.set_additional_option_attributes(
        client=fake_client, options_id=77, options_values_name="Navy", visible=1
    )
    assert result.ok
    assert result.data["options_values_id"] == 55
    _, kwargs = fake_client.execute.call_args
    v = kwargs["variables"]["input"]
    assert v["options_id"] == 77
    assert v["options_values_name"] == "Navy"


# ── set_products_attribute_price ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_products_attribute_price_sends_fields(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProductsAttributePrice": {"products_attributes_id": 33}}
    )
    result = await m.set_products_attribute_price(
        client=fake_client,
        products_id=12345,
        options_id=77,
        options_values_id=55,
        price="2.00",
    )
    assert result.ok
    assert result.data["products_attributes_id"] == 33
    _, kwargs = fake_client.execute.call_args
    v = kwargs["variables"]["input"]
    assert v["products_id"] == 12345
    assert v["price"] == "2.00"


# ── update_product_stock ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_product_stock_sends_fields(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"updateProductStock": {"stock_id": 88, "stock_quantity": 200}}
    )
    result = await m.update_product_stock(
        client=fake_client, action="Add", stock_quantity=100, stock_id=88, comment="New stock."
    )
    assert result.ok
    _, kwargs = fake_client.execute.call_args
    assert kwargs["variables"]["action"] == "Add"
    assert kwargs["variables"]["stock_id"] == 88
    assert kwargs["variables"]["input"]["stock_quantity"] == 100
    assert kwargs["variables"]["input"]["comment"] == "New stock."


@pytest.mark.asyncio
async def test_update_product_stock_omits_optional_args_when_none(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"updateProductStock": {"stock_id": None, "stock_quantity": 50}}
    )
    await m.update_product_stock(client=fake_client, action="Reset", stock_quantity=50)
    _, kwargs = fake_client.execute.call_args
    assert "stock_id" not in kwargs["variables"]
    assert "product_sku" not in kwargs["variables"]
    assert "comment" not in kwargs["variables"]["input"]


# ── set_product_design ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_product_design_sends_fields(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProductDesign": {"products_id": 12345}}
    )
    result = await m.set_product_design(
        client=fake_client, products_id=12345, design_url="https://cdn.example.com/design.png"
    )
    assert result.ok
    _, kwargs = fake_client.execute.call_args
    v = kwargs["variables"]["input"]
    assert v["products_id"] == 12345
    assert v["design_url"] == "https://cdn.example.com/design.png"
    assert "design_type" not in v


@pytest.mark.asyncio
async def test_set_product_design_includes_design_type_when_provided(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProductDesign": {"products_id": 12345}}
    )
    await m.set_product_design(
        client=fake_client, products_id=12345, design_url="https://cdn.example.com/d.png", design_type="pdf"
    )
    _, kwargs = fake_client.execute.call_args
    assert kwargs["variables"]["input"]["design_type"] == "pdf"
