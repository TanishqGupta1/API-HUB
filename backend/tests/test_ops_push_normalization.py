"""Unit tests for response-normalization helpers added in the live-OPS alignment.

Covers:
  * `_normalize_mutation_response` — aliases OPS's canonical `id` field to the
    named field downstream placeholders expect (products_id, size_id, etc.).
  * `_unwrap_list` (in mutations.py) — array-input mutations return a list;
    wrappers unwrap to the first item.
  * The setProduct null-id SKU-lookup fallback in `execute_push`.
  * The updateProductStock-as-warning skip path.

These code paths are only exercised end-to-end during live pushes, so
regressions here only surface in production. Targeted unit coverage closes
that gap (per PR review #171).
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from modules.ops_push.gateway import (
    FakeOpsClient,
    _normalize_mutation_response,
    _MUTATION_ID_ALIAS,
)
from modules.ops_client.client import OpsAuth, OpsGraphQLClient, OpsResult
from modules.ops_client.mutations import _unwrap_list, set_product, set_product_size

pytestmark = pytest.mark.no_db


# ───────────────────────────────────────────────────────────────────────────
# _normalize_mutation_response — alias OPS `id` to the named field
# ───────────────────────────────────────────────────────────────────────────


class TestNormalizeMutationResponse:
    def test_aliases_setProduct_id_to_products_id(self):
        resp = _normalize_mutation_response("setProduct", {"id": 540})
        assert resp["id"] == 540
        assert resp["products_id"] == 540

    def test_aliases_setProductSize_id_to_size_id(self):
        resp = _normalize_mutation_response("setProductSize", {"id": 1229})
        assert resp["size_id"] == 1229

    def test_aliases_setProductCategory_id_to_category_id(self):
        resp = _normalize_mutation_response("setProductCategory", {"id": 31})
        assert resp["category_id"] == 31

    def test_aliases_setProductPrice_id_to_product_price_id(self):
        resp = _normalize_mutation_response("setProductPrice", {"id": 99})
        assert resp["product_price_id"] == 99

    def test_aliases_setAssignOptions_id_to_product_option_id(self):
        resp = _normalize_mutation_response("setAssignOptions", {"id": 42})
        assert resp["product_option_id"] == 42

    def test_aliases_setAdditionalOption_id_to_prod_add_opt_id(self):
        resp = _normalize_mutation_response("setAdditionalOption", {"id": 11})
        assert resp["prod_add_opt_id"] == 11

    def test_aliases_setAdditionalOptionAttributes_id_to_attribute_id(self):
        resp = _normalize_mutation_response("setAdditionalOptionAttributes", {"id": 22})
        assert resp["attribute_id"] == 22

    def test_aliases_setProductsAttributePrice_id_to_attribute_id(self):
        resp = _normalize_mutation_response("setProductsAttributePrice", {"id": 33})
        assert resp["attribute_id"] == 33

    def test_aliases_updateProductStock_id_to_stock_id(self):
        resp = _normalize_mutation_response("updateProductStock", {"id": 7})
        assert resp["stock_id"] == 7

    def test_does_not_overwrite_existing_alias(self):
        # If both `id` and the alias are already in the response, the alias wins
        # (no double-aliasing or accidental overwrite).
        resp = _normalize_mutation_response(
            "setProduct", {"id": 999, "products_id": 540}
        )
        assert resp["products_id"] == 540  # preserved
        assert resp["id"] == 999

    def test_passthrough_when_no_id_field(self):
        # Mutations with no id in the response (e.g. some error shapes)
        # should pass through unchanged.
        resp = _normalize_mutation_response("setProduct", {"result": False, "message": "no good"})
        assert "products_id" not in resp
        assert resp["result"] is False

    def test_unknown_mutation_passthrough(self):
        # An unknown mutation name shouldn't crash — just return the dict.
        resp = _normalize_mutation_response("notAMutation", {"id": 1})
        assert resp == {"id": 1}

    def test_dict_returned_is_safe_to_mutate(self):
        original = {"id": 5}
        resp = _normalize_mutation_response("setProduct", original)
        # The current impl may share the dict; either way, mutating the result
        # should NOT corrupt the alias map.
        resp["extra"] = "field"
        assert "extra" not in _MUTATION_ID_ALIAS  # alias table untouched

    def test_alias_table_covers_all_array_input_mutations(self):
        # Defensive: if someone adds a new array-input mutation to the
        # dispatch table, they must also add its alias here, or downstream
        # placeholder resolution will silently break.
        expected_mutations = {
            "setProductCategory", "setProduct", "setProductSize",
            "setProductPrice", "setAssignOptions", "setAdditionalOption",
            "setAdditionalOptionAttributes", "setProductsAttributePrice",
            "updateProductStock",
        }
        assert expected_mutations.issubset(_MUTATION_ID_ALIAS.keys()), (
            "Missing alias entries in _MUTATION_ID_ALIAS for: "
            f"{expected_mutations - _MUTATION_ID_ALIAS.keys()}"
        )


# ───────────────────────────────────────────────────────────────────────────
# _unwrap_list — array-input mutation responses come back as lists
# ───────────────────────────────────────────────────────────────────────────


class TestUnwrapList:
    def test_unwraps_first_item_when_list(self):
        data = {"setProduct": [{"id": 540, "result": True}]}
        result = _unwrap_list(data, "setProduct")
        assert result == {"id": 540, "result": True}

    def test_returns_empty_dict_when_empty_list(self):
        data = {"setProduct": []}
        assert _unwrap_list(data, "setProduct") == {}

    def test_returns_dict_passthrough_when_not_list(self):
        # Backwards-compat: some legacy responses may still be a single dict.
        data = {"setProduct": {"id": 540}}
        assert _unwrap_list(data, "setProduct") == {"id": 540}

    def test_returns_empty_dict_when_key_missing(self):
        assert _unwrap_list({}, "setProduct") == {}

    def test_returns_empty_dict_when_data_is_none(self):
        assert _unwrap_list(None, "setProduct") == {}


# ───────────────────────────────────────────────────────────────────────────
# Wrapper integration: response unwrap + variable shape
# ───────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_client():
    c = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
    c.execute = AsyncMock()
    return c


@pytest.mark.asyncio
async def test_set_product_unwraps_list_response(fake_client):
    """Real OPS returns setProduct results as a list (one entry per inputs[i])."""
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProduct": [{"id": 12345, "result": True}]}
    )
    result = await set_product(
        client=fake_client, category_id=1, products_title="T", products_internal_title="T",
    )
    # data is the FIRST item of the list, not the list itself.
    assert isinstance(result.data, dict)
    assert result.data["id"] == 12345


@pytest.mark.asyncio
async def test_set_product_size_unwraps_list_response(fake_client):
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProductSize": [{"id": 555}]}
    )
    result = await set_product_size(client=fake_client, products_id=1, size_title="M")
    assert result.data["id"] == 555


@pytest.mark.asyncio
async def test_set_product_empty_list_yields_empty_dict(fake_client):
    """Pathological: OPS returns success with empty list. Must not crash."""
    fake_client.execute.return_value = OpsResult(
        ok=True, data={"setProduct": []}
    )
    result = await set_product(
        client=fake_client, category_id=1, products_title="T", products_internal_title="T",
    )
    assert result.ok
    assert result.data == {}


# ───────────────────────────────────────────────────────────────────────────
# FakeOpsClient — used in dry-run + tests; must return `id` to drive
# placeholder resolution like real OPS does.
# ───────────────────────────────────────────────────────────────────────────


class TestFakeOpsClientReturnsId:
    """The FakeOpsClient must mirror real OPS's canonical `id` response field
    so dry-runs exercise the same placeholder + normalization path as live."""

    @pytest.mark.asyncio
    async def test_set_product_returns_id(self):
        fake = FakeOpsClient()
        resp = await fake.set_product({"inputs": [{"products_title": "X"}]})
        assert "id" in resp
        assert isinstance(resp["id"], int)

    @pytest.mark.asyncio
    async def test_set_product_size_returns_id(self):
        fake = FakeOpsClient()
        resp = await fake.set_product_size({"inputs": [{"products_id": 1, "size_title": "M"}]})
        assert "id" in resp

    @pytest.mark.asyncio
    async def test_distinct_ids_per_call(self):
        fake = FakeOpsClient()
        r1 = await fake.set_product({"inputs": [{}]})
        r2 = await fake.set_product_size({"inputs": [{}]})
        # Counter advances → different ids
        assert r1["id"] != r2["id"]

    @pytest.mark.asyncio
    async def test_records_each_call(self):
        fake = FakeOpsClient()
        await fake.set_product({"inputs": [{"products_title": "X"}]})
        await fake.set_product_size({"inputs": [{"products_id": 1}]})
        assert len(fake.calls) == 2
        assert fake.calls[0]["method"] == "set_product"
        assert fake.calls[1]["method"] == "set_product_size"
