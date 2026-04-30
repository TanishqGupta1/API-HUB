"""OPSAdapter + OPSClient unit tests. All HTTP mocked via AsyncMock — no live OPS hits."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest
import httpx

from modules.ops_inbound.ops_client import OPSClient
from modules.import_jobs.base import AuthError, SupplierError, TransientError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_http(status: int, json_body=None, text: str = "") -> AsyncMock:
    """Build a mock httpx.AsyncClient whose .post() returns a fake response."""
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    if json_body is not None:
        resp.json.return_value = json_body
    else:
        resp.json.side_effect = ValueError("no json body")
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = resp
    return mock_client


def _make_supplier(auth_token="tok", base_url="https://vg.onprintshop.test"):
    sup = MagicMock()
    sup.base_url = base_url
    sup.auth_config = {"auth_token": auth_token}
    sup.name = "Test OPS Supplier"
    sup.id = "test-id"
    return sup


# ---------------------------------------------------------------------------
# Task 3: OPSClient tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ops_client_executes_graphql_query():
    """OPSClient.query() POSTs JSON to /graphql with auth header."""
    mock_http = _mock_http(200, json_body={"data": {"products": [{"product_id": 1}]}})
    client = OPSClient(
        base_url="https://vg.onprintshop.test",
        auth_token="tok-abc",
        http_client=mock_http,
    )
    result = await client.query("query { products { product_id } }")
    assert result == {"products": [{"product_id": 1}]}
    # Verify auth header was passed
    call_kwargs = mock_http.post.call_args
    assert "tok-abc" in call_kwargs.kwargs.get("headers", {}).get("authorization", "")


@pytest.mark.asyncio
async def test_ops_client_raises_auth_error_on_401():
    """Client raises AuthError on 401."""
    mock_http = _mock_http(401, text="Unauthorized")
    client = OPSClient(
        base_url="https://vg.onprintshop.test",
        auth_token="bad",
        http_client=mock_http,
    )
    with pytest.raises(AuthError) as exc:
        await client.query("query {}")
    assert exc.value.code == "401"


@pytest.mark.asyncio
async def test_ops_client_raises_supplier_error_on_graphql_errors():
    """Client raises SupplierError when GraphQL errors[] is present."""
    mock_http = _mock_http(
        200,
        json_body={"errors": [{"message": "Product not found", "extensions": {"code": "NOT_FOUND"}}]},
    )
    client = OPSClient(
        base_url="https://vg.onprintshop.test",
        auth_token="t",
        http_client=mock_http,
    )
    with pytest.raises(SupplierError) as exc:
        await client.query("query {}")
    assert "Product not found" in str(exc.value)
    assert exc.value.code == "NOT_FOUND"


@pytest.mark.asyncio
async def test_ops_client_raises_transient_error_on_500():
    """Client raises TransientError on 5xx."""
    mock_http = _mock_http(503, text="Service Unavailable")
    client = OPSClient(
        base_url="https://vg.onprintshop.test",
        auth_token="t",
        http_client=mock_http,
    )
    with pytest.raises(TransientError):
        await client.query("query {}")


# ---------------------------------------------------------------------------
# Task 4: OPSAdapter.discover() tests
# ---------------------------------------------------------------------------

def _make_adapter(query_return: dict):
    """Create OPSAdapter with a mocked OPSClient.query."""
    from modules.ops_inbound.ops_adapter import OPSAdapter
    sup = _make_supplier()
    adapter = OPSAdapter(supplier=sup, db=None)
    adapter.client = AsyncMock(spec=OPSClient)
    adapter.client.query.return_value = query_return
    return adapter


@pytest.mark.asyncio
async def test_ops_adapter_discover_explicit_list_skips_graphql():
    """EXPLICIT_LIST mode returns refs without calling OPS at all."""
    from modules.import_jobs.base import DiscoveryMode
    from modules.ops_inbound.ops_adapter import OPSAdapter

    sup = _make_supplier()
    adapter = OPSAdapter(supplier=sup, db=None)
    adapter.client = AsyncMock(spec=OPSClient)  # no calls expected

    refs = await adapter.discover(
        DiscoveryMode.EXPLICIT_LIST,
        explicit_list=["131", "262"],
    )
    assert [r.supplier_sku for r in refs] == ["131", "262"]
    assert all(r.part_id is None for r in refs)
    adapter.client.query.assert_not_called()


@pytest.mark.asyncio
async def test_ops_adapter_discover_first_n_calls_list_products():
    """FIRST_N mode calls listProducts and slices to limit."""
    from modules.import_jobs.base import DiscoveryMode

    adapter = _make_adapter({
        "listProducts": [
            {"product_id": 131},
            {"product_id": 262},
            {"product_id": 444},
        ]
    })
    refs = await adapter.discover(DiscoveryMode.FIRST_N, limit=2)
    assert [r.supplier_sku for r in refs] == ["131", "262"]


@pytest.mark.asyncio
async def test_ops_adapter_discover_full_returns_all():
    """FULL mode returns all discovered products."""
    from modules.import_jobs.base import DiscoveryMode

    adapter = _make_adapter({
        "listProducts": [
            {"product_id": 1},
            {"product_id": 2},
            {"product_id": 3},
        ]
    })
    refs = await adapter.discover(DiscoveryMode.FULL)
    assert len(refs) == 3


@pytest.mark.asyncio
async def test_ops_adapter_missing_auth_token_raises():
    """OPSAdapter raises AuthError if auth_token missing from auth_config."""
    from modules.ops_inbound.ops_adapter import OPSAdapter

    sup = _make_supplier(auth_token="")  # empty token
    with pytest.raises(AuthError) as exc:
        OPSAdapter(supplier=sup, db=None)
    assert "auth_token" in str(exc.value)


@pytest.mark.asyncio
async def test_ops_adapter_self_registered_in_registry():
    """OPSAdapter self-registers as 'OPSAdapter' in the ADAPTERS registry."""
    import modules.ops_inbound.ops_adapter  # trigger self-registration
    from modules.import_jobs.registry import ADAPTERS
    from modules.ops_inbound.ops_adapter import OPSAdapter
    assert ADAPTERS.get("OPSAdapter") is OPSAdapter


import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"

@pytest.mark.asyncio
async def test_ops_adapter_hydrate_product_fetches_full_record():
    from modules.import_jobs.base import ProductRef
    from modules.ops_inbound.ops_adapter import OPSAdapter

    sup = _make_supplier()

    raw = json.loads((FIXTURES_DIR / "ops_decals.json").read_text())
    decal = raw[0]   # "Decals - General Performance" product_id=131
    # OPSClient.query returns the inner 'data' dictionary
    response = {"getProduct": decal}

    adapter = OPSAdapter(supplier=sup, db=None)
    adapter.client = AsyncMock(spec=OPSClient)
    adapter.client.query.return_value = response

    ingest = await adapter.hydrate_product(ProductRef(supplier_sku="131"))

    # Top-level product fields
    assert ingest.supplier_sku == "131"
    assert ingest.product_type == "print"
    assert ingest.product_name == "Decals - General Performance"
    assert ingest.ops_product_id == "131"

    # print_details routed correctly
    assert ingest.print_details is not None
    assert ingest.print_details.ops_product_id_int == 131
    assert ingest.print_details.default_category_id == 22
    assert ingest.print_details.external_catalogue == 1

    # sizes
    assert len(ingest.sizes) == len(decal.get("product_size", []))
    assert ingest.sizes[0].size_title == "Custom Size"

    # options: at least 30 in the Decals fixture
    assert len(ingest.options) >= 30
    lam = next(o for o in ingest.options if o.option_key == "lamMaterial")
    assert lam.master_option_id == 59
    assert isinstance(lam.attributes, list)
    assert len(lam.attributes) == 3
    assert all(a.multiplier is not None for a in lam.attributes)

    # images: large + small image present
    urls = [img.url for img in ingest.images]
    assert decal["large_image"] in urls

    # raw_payload preserved
    assert ingest.raw_payload == decal

@pytest.mark.asyncio
async def test_ops_adapter_discover_changed_filters_by_modified_at():
    from datetime import datetime, timezone
    from modules.import_jobs.base import ProductRef
    from modules.ops_inbound.ops_adapter import OPSAdapter

    sup = _make_supplier()

    response = {
        "listProductsModifiedSince": [
            {"product_id": 131},
            {"product_id": 262},
        ]
    }
    
    since = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    adapter = OPSAdapter(supplier=sup, db=None)
    adapter.client = AsyncMock(spec=OPSClient)
    adapter.client.query.return_value = response
    
    refs = await adapter.discover_changed(since)
    
    adapter.client.query.assert_called_once()
    call_args = adapter.client.query.call_args
    assert call_args.kwargs["variables"]["since"] == since.isoformat()
    assert [r.supplier_sku for r in refs] == ["131", "262"]
