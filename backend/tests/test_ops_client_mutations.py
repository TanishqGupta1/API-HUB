"""OPSClient mutation wrapper + OAuth2 refresh unit tests.

Task 4: every mutation must send the canonical GraphQL string (n8n custom
node is source of truth) and unwrap its response key. The query() path must
refresh-on-401 once when OAuth2 client_credentials creds are configured.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from modules.ops_inbound.ops_client import (
    MUTATION_SET_ASSIGN_OPTIONS,
    MUTATION_SET_PRODUCT,
    MUTATION_SET_PRODUCT_CATEGORY,
    MUTATION_SET_PRODUCT_DESIGN,
    MUTATION_SET_PRODUCT_PRICE,
    MUTATION_SET_PRODUCT_SIZE,
    OPSClient,
)
from modules.import_jobs.base import AuthError, SupplierError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _response(status: int, json_body: Any = None, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    if json_body is not None:
        resp.json.return_value = json_body
    else:
        resp.json.side_effect = ValueError("no json body")
    return resp


def _mock_http(*responses: MagicMock) -> AsyncMock:
    """Build an AsyncMock httpx client that returns `responses` in order across
    successive .post() calls."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    if len(responses) == 1:
        mock_client.post.return_value = responses[0]
    else:
        mock_client.post.side_effect = list(responses)
    return mock_client


def _client(http: AsyncMock, **extra) -> OPSClient:
    return OPSClient(
        base_url="https://vg.onprintshop.test",
        auth_token="tok-abc",
        http_client=http,
        **extra,
    )


# ---------------------------------------------------------------------------
# Mutation shape + unwrap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_product_category_sends_canonical_mutation_and_unwraps():
    http = _mock_http(
        _response(200, {"data": {"setProductCategory": {
            "result": "ok", "message": "", "category_id": 42,
        }}}),
    )
    client = _client(http)
    result = await client.set_product_category({"category_name": "T-Shirts", "parent_id": 0, "visible": 1})
    assert result == {"result": "ok", "message": "", "category_id": 42}

    call = http.post.call_args
    body = call.kwargs["json"]
    assert body["query"] == MUTATION_SET_PRODUCT_CATEGORY
    assert body["variables"] == {"input": {"category_name": "T-Shirts", "parent_id": 0, "visible": 1}}


@pytest.mark.asyncio
async def test_set_product_sends_canonical_mutation_and_unwraps():
    http = _mock_http(
        _response(200, {"data": {"setProduct": {
            "result": "ok", "message": "", "products_id": 10001,
        }}}),
    )
    client = _client(http)
    result = await client.set_product({"products_title": "PC61", "category_id": 42, "visible": 1})
    assert result["products_id"] == 10001
    assert http.post.call_args.kwargs["json"]["query"] == MUTATION_SET_PRODUCT


@pytest.mark.asyncio
async def test_set_product_size_sends_canonical_mutation_and_unwraps():
    http = _mock_http(
        _response(200, {"data": {"setProductSize": {
            "result": "ok", "message": "", "product_size_id": 7,
        }}}),
    )
    client = _client(http)
    result = await client.set_product_size({"products_id": 10001, "size_name": "M", "color_name": "Black"})
    assert result["product_size_id"] == 7
    assert http.post.call_args.kwargs["json"]["query"] == MUTATION_SET_PRODUCT_SIZE


@pytest.mark.asyncio
async def test_set_product_price_sends_canonical_mutation_and_unwraps():
    http = _mock_http(
        _response(200, {"data": {"setProductPrice": {
            "result": "ok", "message": "", "product_price_id": 99,
        }}}),
    )
    client = _client(http)
    result = await client.set_product_price({
        "products_id": 10001, "size_id": 7, "qty": 1, "qty_to": None,
        "price": 9.99, "vendor_price": 4.50, "visible": 1,
    })
    assert result["product_price_id"] == 99
    assert http.post.call_args.kwargs["json"]["query"] == MUTATION_SET_PRODUCT_PRICE


@pytest.mark.asyncio
async def test_set_assign_options_sends_canonical_mutation_and_unwraps():
    http = _mock_http(
        _response(200, {"data": {"setAssignOptions": {
            "result": "ok", "message": "", "product_option_id": 12,
        }}}),
    )
    client = _client(http)
    result = await client.set_assign_options({"products_id": 10001, "options": []})
    assert result["product_option_id"] == 12
    assert http.post.call_args.kwargs["json"]["query"] == MUTATION_SET_ASSIGN_OPTIONS


@pytest.mark.asyncio
async def test_set_product_design_passes_flat_variables_not_input_wrapper():
    """setProductDesign uses inline scalar args, not an Input wrapper."""
    http = _mock_http(
        _response(200, {"data": {"setProductDesign": {"result": "ok", "message": ""}}}),
    )
    client = _client(http)
    args = {
        "order_product_id": 555,
        "ziflow_link": "https://ziflow/123",
        "ziflow_preflight_link": "https://ziflow/preflight/123",
    }
    await client.set_product_design(args)

    body = http.post.call_args.kwargs["json"]
    assert body["query"] == MUTATION_SET_PRODUCT_DESIGN
    # Variables flat — NOT wrapped in {"input": ...}
    assert body["variables"] == args
    assert "input" not in body["variables"]


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mutation_raises_supplier_error_when_response_key_missing():
    """OPS returned 200 but no setProduct field => SupplierError."""
    http = _mock_http(_response(200, {"data": {}}))
    client = _client(http)
    with pytest.raises(SupplierError) as exc:
        await client.set_product({"products_title": "X"})
    assert "setProduct" in str(exc.value)


@pytest.mark.asyncio
async def test_mutation_propagates_graphql_errors_as_supplier_error():
    http = _mock_http(
        _response(200, {"errors": [
            {"message": "products_title required", "extensions": {"code": "VALIDATION"}}
        ]}),
    )
    client = _client(http)
    with pytest.raises(SupplierError) as exc:
        await client.set_product({})
    assert exc.value.code == "VALIDATION"


# ---------------------------------------------------------------------------
# OAuth2 refresh-on-401
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_refreshes_token_on_401_and_retries_once():
    """When OAuth2 creds configured, 401 triggers a token refresh and one retry."""
    http = _mock_http(
        _response(401, text="Unauthorized"),                              # 1st query → 401
        _response(200, {"access_token": "new-tok-xyz"}),                  # token refresh
        _response(200, {"data": {"setProduct": {                          # retry succeeds
            "result": "ok", "message": "", "products_id": 555,
        }}}),
    )
    client = _client(
        http,
        token_url="https://vg.onprintshop.test/oauth/token",
        client_id="cid",
        client_secret="csecret",
    )
    result = await client.set_product({"products_title": "X"})

    assert result["products_id"] == 555
    assert client.auth_token == "new-tok-xyz"
    assert http.post.call_count == 3

    token_call = http.post.call_args_list[1]
    assert token_call.args[0] == "https://vg.onprintshop.test/oauth/token"
    assert token_call.kwargs["data"]["grant_type"] == "client_credentials"
    assert token_call.kwargs["data"]["client_id"] == "cid"


@pytest.mark.asyncio
async def test_query_does_not_refresh_when_oauth_creds_missing():
    """No token_url => AuthError propagates without refresh attempt."""
    http = _mock_http(_response(401, text="Unauthorized"))
    client = _client(http)  # no OAuth2 creds
    with pytest.raises(AuthError):
        await client.set_product({"products_title": "X"})
    assert http.post.call_count == 1  # no refresh, no retry


@pytest.mark.asyncio
async def test_query_re_raises_when_retry_also_fails_401():
    """Refresh succeeds but retry still 401 => AuthError surfaces (no infinite loop)."""
    http = _mock_http(
        _response(401, text="Unauthorized"),                  # 1st query
        _response(200, {"access_token": "fresh"}),            # token refresh
        _response(401, text="Still unauthorized"),            # retry also 401
    )
    client = _client(
        http,
        token_url="https://x/oauth/token",
        client_id="cid",
        client_secret="csecret",
    )
    with pytest.raises(AuthError):
        await client.set_product({"products_title": "X"})
    assert http.post.call_count == 3  # only one retry; does not loop


@pytest.mark.asyncio
async def test_refresh_raises_auth_error_when_token_endpoint_fails():
    http = _mock_http(
        _response(401, text="Unauthorized"),
        _response(400, text="invalid_client"),
    )
    client = _client(
        http,
        token_url="https://x/oauth/token",
        client_id="cid",
        client_secret="csecret",
    )
    with pytest.raises(AuthError) as exc:
        await client.set_product({"products_title": "X"})
    assert "token refresh failed" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_refresh_raises_when_token_response_missing_access_token():
    http = _mock_http(
        _response(401, text="Unauthorized"),
        _response(200, {"token_type": "Bearer"}),  # no access_token
    )
    client = _client(
        http,
        token_url="https://x/oauth/token",
        client_id="cid",
        client_secret="csecret",
    )
    with pytest.raises(AuthError) as exc:
        await client.set_product({"products_title": "X"})
    assert "missing access_token" in str(exc.value).lower()
