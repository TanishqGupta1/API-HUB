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

from modules.ops_push.gateway import (
    _normalize_mutation_response,
    _MUTATION_ID_ALIAS,
)
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
