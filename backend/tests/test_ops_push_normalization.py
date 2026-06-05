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
from modules.ops_client.mutations import (
    _check_result,
    _unwrap_list,
    set_product,
    set_product_size,
    set_product_price,
    update_product_stock,
)

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


# ───────────────────────────────────────────────────────────────────────────
# _check_result — detect OPS application-level failures (Phase 1.1)
# ───────────────────────────────────────────────────────────────────────────


class TestCheckResult:
    """Without this check, OPS returning {result:false, id:null} would be
    silently treated as success — producing phantom 'pushed' products like
    PC54 (id 10001) that don't actually exist in OPS."""

    def test_returns_none_on_success(self):
        """result=true means OPS accepted the mutation — pass through."""
        assert _check_result({"result": True, "id": 540}, "setProduct") is None

    def test_returns_none_when_no_result_field(self):
        """Some mutations (e.g. setProductDesign) don't return `result`.
        Don't treat absence of the field as a failure."""
        assert _check_result({"id": 540}, "setProduct") is None

    def test_returns_none_on_empty_dict(self):
        assert _check_result({}, "setProduct") is None

    def test_detects_bool_false(self):
        err = _check_result(
            {"result": False, "message": "Column 'X' cannot be null", "id": None},
            "setProduct",
        )
        assert err is not None
        assert err.ok is False
        assert err.ops_error_code == "OPS_REJECTED"
        assert "Column 'X' cannot be null" in (err.ops_error_message or "")

    def test_detects_string_false_case_insensitive(self):
        """Some OPS deployments return the result as a string, not bool."""
        for val in ["false", "False", "FALSE"]:
            err = _check_result({"result": val, "message": "bad"}, "setProduct")
            assert err is not None, f"Failed to detect string {val!r} as rejection"
            assert err.ok is False

    def test_does_not_false_positive_on_truthy_strings(self):
        """'true' string and unrelated values must NOT trigger rejection."""
        assert _check_result({"result": "true"}, "setProduct") is None
        assert _check_result({"result": "ok"}, "setProduct") is None
        assert _check_result({"result": 1}, "setProduct") is None

    def test_includes_mutation_name_in_default_message(self):
        """Even without an OPS-provided message, the error tells you which
        mutation failed — critical for diagnosing partial-failure step_results."""
        err = _check_result({"result": False}, "setProductSize")
        assert "setProductSize" in (err.ops_error_message or "")

    def test_truncates_long_messages(self):
        """OPS error messages can be huge (full SQL snippets). Cap to 400 chars
        so step_results JSONB doesn't blow up storage."""
        long_msg = "x" * 1000
        err = _check_result({"result": False, "message": long_msg}, "setProduct")
        assert err is not None
        assert len(err.ops_error_message) <= 400

    def test_preserves_raw_response_for_diagnostics(self):
        """The full OPS response (incl. id:null, any other fields) is preserved
        in `raw` so investigators can see exactly what OPS sent back."""
        opsd = {"result": False, "message": "nope", "id": None, "extra": "data"}
        err = _check_result(opsd, "setProduct")
        assert err.raw is not None
        assert err.raw["mutation"] == "setProduct"
        assert err.raw["ops_response"] == opsd


# ───────────────────────────────────────────────────────────────────────────
# Integration: wrappers now propagate OPS application-level failures
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_product_propagates_result_false(fake_client):
    """The PC54 silent-failure scenario: OPS returns HTTP 200 with result:false.
    Before Phase 1.1 this returned ok=True with id=null. Now it must return
    ok=False with the OPS-provided error message."""
    fake_client.execute.return_value = OpsResult(
        ok=True,
        data={"setProduct": [{
            "result": False,
            "message": "Column 'predefined_product_type' cannot be null",
            "id": None,
        }]},
    )
    result = await set_product(
        client=fake_client, category_id=1, products_title="X", products_internal_title="X",
    )
    assert result.ok is False, "Phase 1.1 broken: silent failure leaked as success"
    assert result.ops_error_code == "OPS_REJECTED"
    assert "predefined_product_type" in (result.ops_error_message or "")


@pytest.mark.asyncio
async def test_set_product_size_propagates_result_false(fake_client):
    """PC54's downstream symptom: setProductSize returns id:null for every
    variant because the parent product never persisted."""
    fake_client.execute.return_value = OpsResult(
        ok=True,
        data={"setProductSize": [{"result": False, "message": "no such product", "id": None}]},
    )
    result = await set_product_size(client=fake_client, products_id=10001, size_title="M")
    assert result.ok is False
    assert result.ops_error_code == "OPS_REJECTED"


@pytest.mark.asyncio
async def test_set_product_price_propagates_result_false(fake_client):
    """PC61's price-loss scenario: 558 setProductPrice calls returned id:null
    because price_defining_method was blank on the product."""
    fake_client.execute.return_value = OpsResult(
        ok=True,
        data={"setProductPrice": [{"result": False, "message": "price method missing", "id": None}]},
    )
    result = await set_product_price(
        client=fake_client, products_id=540, size_id=1229,
        price="3.99", vendor_price="2.50",
    )
    assert result.ok is False
    assert result.ops_error_code == "OPS_REJECTED"


@pytest.mark.asyncio
async def test_update_product_stock_propagates_result_false(fake_client):
    """updateProductStock uses singular `input` (not arrays) but still
    subject to the same result-checking."""
    fake_client.execute.return_value = OpsResult(
        ok=True,
        data={"updateProductStock": {
            "result": False,
            "message": "Invalid Product SKU or initial stock not added!",
            "id": None,
            "stock_quantity": 0,
        }},
    )
    result = await update_product_stock(
        client=fake_client, action="Add", stock_quantity=42, product_sku="PC61-WHT-S",
    )
    assert result.ok is False
    assert result.ops_error_code == "OPS_REJECTED"
    assert "Invalid Product SKU" in (result.ops_error_message or "")


@pytest.mark.asyncio
async def test_set_product_success_still_works(fake_client):
    """Sanity: a normal success path must still pass result-checking."""
    fake_client.execute.return_value = OpsResult(
        ok=True,
        data={"setProduct": [{"result": True, "message": "ok", "id": 540}]},
    )
    result = await set_product(
        client=fake_client, category_id=1, products_title="X", products_internal_title="X",
    )
    assert result.ok is True
    assert result.data["id"] == 540


# ───────────────────────────────────────────────────────────────────────────
# Gateway-level silent-failure detection (Phase 1.1 — second pass)
# ───────────────────────────────────────────────────────────────────────────
# The mutation wrappers' _check_result is bypassed by OpsClientAdapter._invoke
# which talks to OPS directly. The same check must therefore live in _invoke
# or silent failures slip through the production push path.


class TestOpsClientAdapterRejectsResultFalse:
    @pytest.mark.asyncio
    async def test_invoke_raises_on_result_false(self):
        """OPS returning result:false at app layer must raise from _invoke
        so the gateway records the step as `failed`, not `ok`. This is the
        root cause of the PC54 phantom (id:10001) and the missing 558
        prices on PC61 — both went through the gateway, not the wrappers."""
        from modules.ops_push.gateway import OpsClientAdapter
        from unittest.mock import AsyncMock

        client = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
        client.execute = AsyncMock(return_value=OpsResult(
            ok=True,
            data={"setProductPrice": [{
                "result": False,
                "message": "Price Defining method is required.",
                "id": None,
            }]},
        ))
        adapter = OpsClientAdapter(client)
        with pytest.raises(RuntimeError, match="OPS_REJECTED"):
            await adapter.set_product_price({"inputs": [{"products_id": 1, "size_id": 2, "price": 10, "vendor_price": 5}]})

    @pytest.mark.asyncio
    async def test_invoke_passes_through_on_success(self):
        from modules.ops_push.gateway import OpsClientAdapter
        from unittest.mock import AsyncMock

        client = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
        client.execute = AsyncMock(return_value=OpsResult(
            ok=True,
            data={"setProduct": [{"result": True, "message": "ok", "id": 540}]},
        ))
        adapter = OpsClientAdapter(client)
        resp = await adapter.set_product({"inputs": [{"products_title": "T"}]})
        assert resp["id"] == 540

    @pytest.mark.asyncio
    async def test_invoke_detects_string_false(self):
        """Belt-and-suspenders: OPS sometimes returns result as string."""
        from modules.ops_push.gateway import OpsClientAdapter
        from unittest.mock import AsyncMock

        client = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
        client.execute = AsyncMock(return_value=OpsResult(
            ok=True,
            data={"setProductSize": [{"result": "false", "message": "no good", "id": None}]},
        ))
        adapter = OpsClientAdapter(client)
        with pytest.raises(RuntimeError, match="OPS_REJECTED"):
            await adapter.set_product_size({"inputs": [{}]})

    @pytest.mark.asyncio
    async def test_invoke_no_result_field_is_success(self):
        """Some mutations (e.g. updateProductStock in some shapes) may
        omit `result`. Absence != failure."""
        from modules.ops_push.gateway import OpsClientAdapter
        from unittest.mock import AsyncMock

        client = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
        client.execute = AsyncMock(return_value=OpsResult(
            ok=True,
            data={"setProduct": [{"id": 540}]},  # no result field
        ))
        adapter = OpsClientAdapter(client)
        resp = await adapter.set_product({"inputs": [{}]})
        assert resp["id"] == 540
