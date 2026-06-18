"""Unit tests for response-normalization helpers added in the live-OPS alignment.

Covers:
  * `_normalize_mutation_response` — aliases OPS's canonical `id` field to the
    named field downstream placeholders expect (products_id, size_id, etc.).
  * `_unwrap_list` (in mutations.py) — array-input mutations return a list;
    wrappers unwrap to the first item.
  * `_check_result` — OPS application-level failure detection.

These code paths are only exercised end-to-end during live pushes, so
regressions here only surface in production. Targeted unit coverage closes
that gap (per PR review #171).
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from modules.ops_push.gateway import (
    _normalize_mutation_response,
    _MUTATION_ID_ALIAS,
)
from modules.ops_client.client import OpsAuth, OpsGraphQLClient, OpsResult
from modules.ops_client.mutations import (
    _check_result,
    _unwrap_list,
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
        resp = _normalize_mutation_response(
            "setProduct", {"id": 999, "products_id": 540}
        )
        assert resp["products_id"] == 540
        assert resp["id"] == 999

    def test_passthrough_when_no_id_field(self):
        resp = _normalize_mutation_response("setProduct", {"result": False, "message": "no good"})
        assert "products_id" not in resp
        assert resp["result"] is False

    def test_unknown_mutation_passthrough(self):
        resp = _normalize_mutation_response("notAMutation", {"id": 1})
        assert resp == {"id": 1}

    def test_dict_returned_is_safe_to_mutate(self):
        original = {"id": 5}
        resp = _normalize_mutation_response("setProduct", original)
        resp["extra"] = "field"
        assert "extra" not in _MUTATION_ID_ALIAS

    def test_alias_table_covers_all_array_input_mutations(self):
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
        data = {"setProduct": {"id": 540}}
        assert _unwrap_list(data, "setProduct") == {"id": 540}

    def test_returns_empty_dict_when_key_missing(self):
        assert _unwrap_list({}, "setProduct") == {}

    def test_returns_empty_dict_when_data_is_none(self):
        assert _unwrap_list(None, "setProduct") == {}


# ───────────────────────────────────────────────────────────────────────────
# _check_result — detect OPS application-level failures (Phase 1.1)
# ───────────────────────────────────────────────────────────────────────────


class TestCheckResult:
    """Without this check, OPS returning {result:false, id:null} would be
    silently treated as success — producing phantom 'pushed' products like
    PC54 (id 10001) that don't actually exist in OPS."""

    def test_returns_none_on_success(self):
        assert _check_result({"result": True, "id": 540}, "setProduct") is None

    def test_returns_none_when_no_result_field(self):
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
        for val in ["false", "False", "FALSE"]:
            err = _check_result({"result": val, "message": "bad"}, "setProduct")
            assert err is not None, f"Failed to detect string {val!r} as rejection"
            assert err.ok is False

    def test_does_not_false_positive_on_truthy_strings(self):
        assert _check_result({"result": "true"}, "setProduct") is None
        assert _check_result({"result": "ok"}, "setProduct") is None
        assert _check_result({"result": 1}, "setProduct") is None

    def test_includes_mutation_name_in_default_message(self):
        err = _check_result({"result": False}, "setProductSize")
        assert "setProductSize" in (err.ops_error_message or "")

    def test_truncates_long_messages(self):
        long_msg = "x" * 1000
        err = _check_result({"result": False, "message": long_msg}, "setProduct")
        assert err is not None
        assert len(err.ops_error_message) <= 400

    def test_preserves_raw_response_for_diagnostics(self):
        opsd = {"result": False, "message": "nope", "id": None, "extra": "data"}
        err = _check_result(opsd, "setProduct")
        assert err.raw is not None
        assert err.raw["mutation"] == "setProduct"
        assert err.raw["ops_response"] == opsd


# ───────────────────────────────────────────────────────────────────────────
# Gateway-level silent-failure detection (Phase 1.1 — second pass)
# ───────────────────────────────────────────────────────────────────────────
# OpsClientAdapter._invoke talks to OPS directly, bypassing the wrapper
# _check_result functions. The same check must live in _invoke or silent
# failures slip through the production push path.


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


# ───────────────────────────────────────────────────────────────────────────
# Phase 6 — stock_id read-back helper
# ───────────────────────────────────────────────────────────────────────────


class TestResolveStockIdForSize:
    """Verifies the gateway's read-back step resolves the right stock_id
    from a productStocks query before sending updateProductStock."""

    @pytest.mark.asyncio
    async def test_returns_none_when_product_id_missing(self):
        from modules.ops_push.gateway import _resolve_stock_id_for_size
        from unittest.mock import AsyncMock
        client = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
        client.execute = AsyncMock()
        result = await _resolve_stock_id_for_size(client, product_id=None, size_id=10)
        assert result is None
        client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_synthetic_id_for_fake_client(self):
        """Dry-run uses FakeOpsClient which has per-mutation methods but
        no .execute() — return a deterministic synthetic id so dry-runs
        exercise the full plan rather than warning on every stock step."""
        from modules.ops_push.gateway import _resolve_stock_id_for_size, FakeOpsClient
        fake = FakeOpsClient()
        result = await _resolve_stock_id_for_size(fake, product_id=540, size_id=42)
        assert result == 99042  # 99000 + size_id
        # Different size_id → different synthetic id (distinct per variant)
        result2 = await _resolve_stock_id_for_size(fake, product_id=540, size_id=43)
        assert result2 != result

    @pytest.mark.asyncio
    async def test_resolves_from_ops_stocks(self):
        """Live path: query OPS, build size_id->stock_id map, return match."""
        from modules.ops_push.gateway import _resolve_stock_id_for_size, _clear_stock_lookup_cache
        from unittest.mock import AsyncMock
        client = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
        client.execute = AsyncMock(return_value=OpsResult(
            ok=True,
            data={"productStocks": {"productStocks": [
                {"stock_id": 1, "size_id": 230, "stock_quantity": 5},
                {"stock_id": 3, "size_id": 231, "stock_quantity": 0},
            ]}},
        ))
        _clear_stock_lookup_cache(218)
        result = await _resolve_stock_id_for_size(client, product_id=218, size_id=230)
        assert result == 1
        # Same product → cached, no second query
        result2 = await _resolve_stock_id_for_size(client, product_id=218, size_id=231)
        assert result2 == 3
        assert client.execute.call_count == 1, "Stock map must be cached per product"
        _clear_stock_lookup_cache(218)

    @pytest.mark.asyncio
    async def test_returns_none_when_no_match(self):
        """When OPS has stock entries for the product but not for THIS
        size_id (i.e. admin hasn't initialized stock for this variant),
        return None so caller records a clear warning."""
        from modules.ops_push.gateway import _resolve_stock_id_for_size, _clear_stock_lookup_cache
        from unittest.mock import AsyncMock
        client = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
        client.execute = AsyncMock(return_value=OpsResult(
            ok=True,
            data={"productStocks": {"productStocks": [{"stock_id": 1, "size_id": 230}]}},
        ))
        _clear_stock_lookup_cache(999)
        result = await _resolve_stock_id_for_size(client, product_id=999, size_id=42)
        assert result is None
        _clear_stock_lookup_cache(999)

    @pytest.mark.asyncio
    async def test_data_not_found_treated_as_empty(self):
        """OPS returns DATA_NOT_FOUND when product has zero stock entries.
        Must NOT propagate as an error — treat as 'no match' so the push
        proceeds with a clean warning instead of crashing."""
        from modules.ops_client.mutations import get_product_stocks
        from unittest.mock import AsyncMock
        client = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
        client.execute = AsyncMock(return_value=OpsResult(
            ok=False, ops_error_code="DATA_NOT_FOUND",
            ops_error_message="Data not found!",
        ))
        result = await get_product_stocks(client=client, product_id=544)
        assert result.ok is True
        assert result.data["productStocks"] == []


# ───────────────────────────────────────────────────────────────────────────
# AI-2 — getProductSkuMatrix (valid size/option combos before setProductSku)
# ───────────────────────────────────────────────────────────────────────────


class TestGetProductSkuMatrix:
    """The getProductSkuMatrix query wrapper — OPS's authoritative list of
    assignable (size, option) slots, fetched before setProductSku so we don't
    assign SKUs OPS will reject."""

    @pytest.mark.asyncio
    async def test_unwraps_matrix_and_total(self):
        from modules.ops_client.mutations import get_product_sku_matrix
        client = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
        client.execute = AsyncMock(return_value=OpsResult(
            ok=True,
            data={"getProductSkuMatrix": {
                "matrix": [
                    {"size_id": 611, "prod_add_opt_ids": "6557", "attribute_ids": "11481"},
                    {"size_id": 508, "prod_add_opt_ids": "6557", "attribute_ids": "11481"},
                ],
                "totalRecords": 2,
            }},
        ))
        result = await get_product_sku_matrix(client=client, products_id=288, prod_add_opt_ids="6557")
        assert result.ok is True
        assert result.data["totalRecords"] == 2
        assert {r["size_id"] for r in result.data["matrix"]} == {611, 508}

    @pytest.mark.asyncio
    async def test_size_wise_passes_empty_opt_ids(self):
        """Size-wise call (no options) must still send prod_add_opt_ids — it's
        String! (required) in the live schema — as an empty string."""
        from modules.ops_client.mutations import get_product_sku_matrix
        client = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
        client.execute = AsyncMock(return_value=OpsResult(
            ok=True, data={"getProductSkuMatrix": {"matrix": [], "totalRecords": 0}},
        ))
        await get_product_sku_matrix(client=client, products_id=350)
        _, kwargs = client.execute.call_args
        assert kwargs["variables"]["prod_add_opt_ids"] == ""
        assert kwargs["variables"]["products_id"] == 350

    @pytest.mark.asyncio
    async def test_data_not_found_treated_as_empty(self):
        """A product with no configured combinations returns DATA_NOT_FOUND;
        map to an empty matrix so callers don't crash (mirrors stocks)."""
        from modules.ops_client.mutations import get_product_sku_matrix
        client = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
        client.execute = AsyncMock(return_value=OpsResult(
            ok=False, ops_error_code="DATA_NOT_FOUND", ops_error_message="Data not found!",
        ))
        result = await get_product_sku_matrix(client=client, products_id=544)
        assert result.ok is True
        assert result.data == {"matrix": [], "totalRecords": 0}


class TestFetchValidSkuSizeIds:
    """The gateway helper that turns the matrix into a set of valid size_ids
    used to validate the setProductSku batch before sending."""

    @pytest.mark.asyncio
    async def test_returns_none_when_product_id_missing(self):
        from modules.ops_push.gateway import _fetch_valid_sku_size_ids
        client = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
        client.execute = AsyncMock()
        assert await _fetch_valid_sku_size_ids(client, product_id=None) is None
        client.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_fake_skips_query(self):
        """The Fake (is_dry_run) has no real product to describe — return
        None ('skip validation') without querying."""
        from modules.ops_push.gateway import _fetch_valid_sku_size_ids, FakeOpsClient
        assert await _fetch_valid_sku_size_ids(FakeOpsClient(), product_id=540) is None

    @pytest.mark.asyncio
    async def test_collects_size_ids_and_caches(self):
        from modules.ops_push.gateway import _fetch_valid_sku_size_ids, _clear_sku_matrix_cache
        client = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
        client.execute = AsyncMock(return_value=OpsResult(
            ok=True,
            data={"getProductSkuMatrix": {
                "matrix": [{"size_id": 611}, {"size_id": 508}], "totalRecords": 2,
            }},
        ))
        _clear_sku_matrix_cache(288)
        ids = await _fetch_valid_sku_size_ids(client, product_id=288)
        assert ids == {611, 508}
        # Second call for same product is cached — no extra query.
        ids2 = await _fetch_valid_sku_size_ids(client, product_id=288)
        assert ids2 == {611, 508}
        assert client.execute.call_count == 1
        _clear_sku_matrix_cache(288)

    @pytest.mark.asyncio
    async def test_empty_matrix_is_advisory_none(self):
        """An empty matrix (OPS may not have indexed new sizes yet) → None so
        we DON'T drop every variant; validation is advisory this pass."""
        from modules.ops_push.gateway import _fetch_valid_sku_size_ids, _clear_sku_matrix_cache
        client = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
        client.execute = AsyncMock(return_value=OpsResult(
            ok=True, data={"getProductSkuMatrix": {"matrix": [], "totalRecords": 0}},
        ))
        _clear_sku_matrix_cache(999)
        assert await _fetch_valid_sku_size_ids(client, product_id=999) is None
        _clear_sku_matrix_cache(999)

    @pytest.mark.asyncio
    async def test_query_error_returns_none(self):
        """A non-OK matrix query must not block the push — return None."""
        from modules.ops_push.gateway import _fetch_valid_sku_size_ids, _clear_sku_matrix_cache
        client = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
        client.execute = AsyncMock(return_value=OpsResult(
            ok=False, ops_error_code="OPS_ERROR", ops_error_message="boom",
        ))
        _clear_sku_matrix_cache(777)
        assert await _fetch_valid_sku_size_ids(client, product_id=777) is None
        _clear_sku_matrix_cache(777)
