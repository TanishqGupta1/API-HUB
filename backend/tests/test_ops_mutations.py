"""Tests for OPS mutation wrappers (T6–T11).

Updated for the live-OPS array-input contract:
- All mutations except updateProductStock use `inputs: [XInput!]!` (plural)
- Responses return `id` (canonical), unwrapped from the list

Uses unittest.mock.AsyncMock so no HTTP calls are made.
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
        ok=True, data={"setProductCategory": [{"id": 42}]}
    )
    result = await m.set_product_category(
        client=fake_client, category_name="T-Shirts", parent_id=0, visible=1,
    )
    assert result.ok
    _, kwargs = fake_client.execute.call_args
    # Array-input contract: variables.inputs is a list with one dict
    inputs = kwargs["variables"]["inputs"]
    assert isinstance(inputs, list) and len(inputs) == 1
    v = inputs[0]
    assert v["category_name"] == "T-Shirts"
    assert v["parent_id"] == 0
    assert v["visible"] == 1


@pytest.mark.asyncio
async def test_set_product_category_extracts_id(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProductCategory": [{"id": 99}]}
    )
    result = await m.set_product_category(
        client=fake_client, category_name="Polos", parent_id=0, visible=1,
    )
    assert result.ok
    # Wrapper unwraps the list and returns the first item's fields
    assert result.data["id"] == 99


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
        ok=True, data={"setProduct": [{"id": 12345}]}
    )
    result = await m.set_product(
        client=fake_client,
        category_id=42,
        products_title="Port & Company PC61",
        products_internal_title="PC61",
        visible=1,
    )
    _, kwargs = fake_client.execute.call_args
    inputs = kwargs["variables"]["inputs"]
    assert isinstance(inputs, list) and len(inputs) == 1
    v = inputs[0]
    assert v["category_id"] == 42
    assert v["products_title"] == "Port & Company PC61"
    assert v["products_internal_title"] == "PC61"
    assert v["visible"] == 1
    assert result.ok
    assert result.data["id"] == 12345


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
# Signature changed: OPS's ProductSizeInput has size_title (not size_name +
# color_name), and no products_sku field. Color is folded into size_title.

@pytest.mark.asyncio
async def test_set_product_size_threads_products_id(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProductSize": [{"id": 555}]}
    )
    result = await m.set_product_size(
        client=fake_client,
        products_id=12345,
        size_title="Navy / M",
        visible=1,
    )
    _, kwargs = fake_client.execute.call_args
    inputs = kwargs["variables"]["inputs"]
    assert isinstance(inputs, list) and len(inputs) == 1
    v = inputs[0]
    assert v["products_id"] == 12345
    assert v["size_title"] == "Navy / M"
    assert v["visible"] == 1
    assert result.ok
    assert result.data["id"] == 555


# ── T9: set_product_price ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_product_price_threads_products_id_and_size_id(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProductPrice": [{"id": 7777}]}
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
    inputs = kwargs["variables"]["inputs"]
    assert isinstance(inputs, list) and len(inputs) == 1
    v = inputs[0]
    assert v["products_id"] == 12345
    assert v["size_id"] == 555
    assert v["price"] == "9.99"
    assert v["vendor_price"] == "3.99"
    assert "qty_to" not in v
    assert result.ok
    assert result.data["id"] == 7777


@pytest.mark.asyncio
async def test_set_product_price_includes_qty_to_when_provided(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProductPrice": [{"id": 8888}]}
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
    assert kwargs["variables"]["inputs"][0]["qty_to"] == 11


# ── set_assign_options ───────────────────────────────────────────────────────
# Signature changed: AssignOptionsInput uses master_option_id (single Int),
# not options_id (list). The old multi-option attach is no longer supported.

@pytest.mark.asyncio
async def test_set_assign_options_sends_products_id_and_master_option_id(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setAssignOptions": [{"id": 222}]}
    )
    result = await m.set_assign_options(
        client=fake_client, products_id=12345, master_option_id=42,
    )
    assert result.ok
    assert result.data["id"] == 222
    _, kwargs = fake_client.execute.call_args
    v = kwargs["variables"]["inputs"][0]
    assert v["products_id"] == 12345
    assert v["master_option_id"] == 42


@pytest.mark.asyncio
async def test_set_assign_options_passes_through_error(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=False, ops_error_code="BAD_INPUT", ops_error_message="invalid master_option_id"
    )
    result = await m.set_assign_options(client=fake_client, products_id=1, master_option_id=999)
    assert not result.ok
    assert result.ops_error_code == "BAD_INPUT"


# ── set_additional_option ────────────────────────────────────────────────────
# Signature changed: AdditionalOptionInput requires products_id + option_key +
# title; no more "options_name"/"visible" fields.

@pytest.mark.asyncio
async def test_set_additional_option_sends_fields(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setAdditionalOption": [{"id": 77}]}
    )
    result = await m.set_additional_option(
        client=fake_client,
        products_id=12345,
        option_key="color",
        title="Color",
        options_type="combo",
        sort_order=0,
    )
    assert result.ok
    assert result.data["id"] == 77
    _, kwargs = fake_client.execute.call_args
    v = kwargs["variables"]["inputs"][0]
    assert v["products_id"] == 12345
    assert v["option_key"] == "color"
    assert v["title"] == "Color"
    assert v["options_type"] == "combo"


# ── set_additional_option_attributes ─────────────────────────────────────────
# Signature changed: takes prod_add_opt_id + attribute_key + label (no more
# options_values_name).

@pytest.mark.asyncio
async def test_set_additional_option_attributes_sends_fields(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setAdditionalOptionAttributes": [{"id": 55}]}
    )
    result = await m.set_additional_option_attributes(
        client=fake_client,
        prod_add_opt_id=77,
        attribute_key="navy",
        label="Navy",
        setup_cost=1.5,
        multiplier=1.0,
    )
    assert result.ok
    assert result.data["id"] == 55
    _, kwargs = fake_client.execute.call_args
    v = kwargs["variables"]["inputs"][0]
    assert v["prod_add_opt_id"] == 77
    assert v["attribute_key"] == "navy"
    assert v["label"] == "Navy"
    assert v["setup_cost"] == 1.5
    assert v["multiplier"] == 1.0


# ── set_products_attribute_price ─────────────────────────────────────────────
# Signature changed: takes product_id + attribute_id + size_id + attributes_price
# (no more options_id/options_values_id/price).

@pytest.mark.asyncio
async def test_set_products_attribute_price_sends_fields(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProductsAttributePrice": [{"id": 33}]}
    )
    result = await m.set_products_attribute_price(
        client=fake_client,
        product_id=12345,
        attribute_id=55,
        size_id=200,
        attributes_price="2.00",
    )
    assert result.ok
    assert result.data["id"] == 33
    _, kwargs = fake_client.execute.call_args
    v = kwargs["variables"]["inputs"][0]
    assert v["product_id"] == 12345
    assert v["attribute_id"] == 55
    assert v["size_id"] == 200
    assert v["attributes_price"] == "2.00"
    assert "vendor_price" not in v


@pytest.mark.asyncio
async def test_set_products_attribute_price_includes_vendor_price(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProductsAttributePrice": [{"id": 34}]}
    )
    await m.set_products_attribute_price(
        client=fake_client,
        product_id=1, attribute_id=1, size_id=1,
        attributes_price="2.00", vendor_price="1.00",
    )
    _, kwargs = fake_client.execute.call_args
    assert kwargs["variables"]["inputs"][0]["vendor_price"] == "1.00"


# ── update_product_stock ─────────────────────────────────────────────────────
# Unchanged contract: updateProductStock uses singular `input` and
# top-level args (stock_id, product_sku, action). It's the only mutation
# that doesn't use the array-input shape — that's intentional on OPS's side.

@pytest.mark.asyncio
async def test_update_product_stock_sends_fields(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"updateProductStock": {"id": 88, "stock_quantity": 200}}
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
        ok=True, data={"updateProductStock": {"id": None, "stock_quantity": 50}}
    )
    await m.update_product_stock(client=fake_client, action="Reset", stock_quantity=50)
    _, kwargs = fake_client.execute.call_args
    assert "stock_id" not in kwargs["variables"]
    assert "product_sku" not in kwargs["variables"]
    assert "comment" not in kwargs["variables"]["input"]


# ── set_product_design ───────────────────────────────────────────────────────
# Unchanged contract for now — this mutation is dormant (real OPS schema
# differs; needs a rewrite before use). Tests preserved for the existing
# signature so removing the function would visibly break these.

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
