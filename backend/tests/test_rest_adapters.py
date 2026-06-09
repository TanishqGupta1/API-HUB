"""Unit tests for the REST supplier adapters — adapter-layer wiring only.

Plan ref: 2026-06-02-production-readiness.md, Phase 3 — "fourover_adapter.py
and ss_adapter.py have no direct unit tests (discover→hydrate→normalize
wiring)". The underlying FourOverClient / ss_normalizer are tested elsewhere;
here we exercise the adapter contract: credential validation, discovery
mapping + mode handling, HTTP-error → AdapterError classification, and the
normalize step that produces ProductIngest.

All tests are hermetic — the HTTP client is mocked, no network/DB.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from modules.import_jobs.base import (
    AuthError,
    DiscoveryMode,
    ProductRef,
    SupplierError,
    TransientError,
)


# ── helpers ──────────────────────────────────────────────────────────────

def _http_status_error(status: int) -> httpx.HTTPStatusError:
    """Build an httpx.HTTPStatusError whose .response.status_code == status."""
    req = httpx.Request("GET", "https://supplier.example/api")
    resp = httpx.Response(status, request=req)
    return httpx.HTTPStatusError(f"HTTP {status}", request=req, response=resp)


class _FakeResp:
    """Minimal stand-in for httpx.Response: .raise_for_status() + .json()."""

    def __init__(self, status: int, payload):
        self.status_code = status
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise _http_status_error(self.status_code)

    def json(self):
        return self._payload


def _supplier(**auth) -> SimpleNamespace:
    import uuid as _uuid
    return SimpleNamespace(
        id=_uuid.uuid4(),
        name="Test Supplier",
        auth_config=auth or {},
        base_url=None,
        last_delta_sync=None,
        last_full_sync=None,
    )


# ── FourOverAdapter ──────────────────────────────────────────────────────

def _fourover(monkeypatch):
    """Construct a FourOverAdapter with the real FourOverClient patched out."""
    import modules.rest_connector.fourover_adapter as mod

    monkeypatch.setattr(mod, "FourOverClient", lambda **kw: SimpleNamespace())
    adapter = mod.FourOverAdapter(
        _supplier(api_key="k", private_key="p"), db=None
    )
    adapter.client = SimpleNamespace()  # methods set per-test as AsyncMocks
    return adapter


def test_fourover_init_requires_both_keys(monkeypatch):
    import modules.rest_connector.fourover_adapter as mod

    monkeypatch.setattr(mod, "FourOverClient", lambda **kw: SimpleNamespace())
    with pytest.raises(AuthError):
        mod.FourOverAdapter(_supplier(), db=None)            # no creds
    with pytest.raises(AuthError):
        mod.FourOverAdapter(_supplier(api_key="k"), db=None)  # private_key missing


@pytest.mark.asyncio
async def test_fourover_discover_explicit_list(monkeypatch):
    a = _fourover(monkeypatch)
    refs = await a.discover(DiscoveryMode.EXPLICIT_LIST, explicit_list=["U1", "U2"])
    assert [r.supplier_sku for r in refs] == ["U1", "U2"]
    with pytest.raises(ValueError):
        await a.discover(DiscoveryMode.EXPLICIT_LIST, explicit_list=[])


@pytest.mark.asyncio
async def test_fourover_discover_full_maps_uuid_id_index(monkeypatch):
    a = _fourover(monkeypatch)
    a.client.get_products = AsyncMock(
        return_value=[{"uuid": "u1"}, {"id": "i2"}, {"name": "no-id"}]
    )
    refs = await a.discover(DiscoveryMode.FULL_SELLABLE)
    # uuid wins, then id, then falls back to the enumerate index (2)
    assert [r.supplier_sku for r in refs] == ["u1", "i2", "2"]


@pytest.mark.asyncio
async def test_fourover_discover_first_n_slices(monkeypatch):
    a = _fourover(monkeypatch)
    a.client.get_products = AsyncMock(
        return_value=[{"uuid": f"u{i}"} for i in range(5)]
    )
    refs = await a.discover(DiscoveryMode.FIRST_N, limit=2)
    assert len(refs) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status,exc", [(401, AuthError), (403, AuthError), (500, TransientError)])
async def test_fourover_discover_http_error_classification(monkeypatch, status, exc):
    a = _fourover(monkeypatch)
    a.client.get_products = AsyncMock(side_effect=_http_status_error(status))
    with pytest.raises(exc):
        await a.discover(DiscoveryMode.FULL_SELLABLE)


@pytest.mark.asyncio
async def test_fourover_discover_network_error_is_transient(monkeypatch):
    a = _fourover(monkeypatch)
    a.client.get_products = AsyncMock(side_effect=httpx.RequestError("boom"))
    with pytest.raises(TransientError):
        await a.discover(DiscoveryMode.FULL_SELLABLE)


@pytest.mark.asyncio
async def test_fourover_hydrate_normalizes_print_product(monkeypatch):
    a = _fourover(monkeypatch)
    a.client.get_product_options = AsyncMock(return_value={
        "name": "Business Cards",
        "description": "premium stock",
        "brand": "PrintCo",
        "size_constraints": {"min_width": 1, "max_width": 10,
                             "min_height": 2, "max_height": 8, "unit": "in"},
        "size_options": [
            {"width": 3.5, "height": 2, "unit": "in", "label": "Standard"},
            {"width": None, "height": 2},  # skipped — no width
        ],
        "option_groups": [
            {"id": "paper", "name": "Paper", "options": [
                {"name": "Glossy", "price_multiplier": "1.20"},
                {"title": "Matte"},
            ]},
        ],
    })
    p = await a.hydrate_product(ProductRef(supplier_sku="UUID-1"))
    assert p.supplier_sku == "UUID-1"
    assert p.product_name == "Business Cards"
    assert p.brand == "PrintCo"
    assert p.product_type == "print"
    assert p.print_details.min_width == 1
    assert len(p.sizes) == 1 and p.sizes[0].label == "Standard"
    assert len(p.options) == 1
    assert p.options[0].option_key == "paper"
    assert len(p.options[0].attributes) == 2
    assert str(p.options[0].attributes[0].multiplier) == "1.20"  # schema coerces to Decimal


@pytest.mark.asyncio
async def test_fourover_hydrate_404_is_supplier_error(monkeypatch):
    a = _fourover(monkeypatch)
    a.client.get_product_options = AsyncMock(side_effect=_http_status_error(404))
    with pytest.raises(SupplierError):
        await a.hydrate_product(ProductRef(supplier_sku="missing"))


@pytest.mark.asyncio
async def test_fourover_normalize_fallbacks_on_sparse_payload(monkeypatch):
    a = _fourover(monkeypatch)
    a.client.get_product_options = AsyncMock(return_value={})
    p = await a.hydrate_product(ProductRef(supplier_sku="UUID-X"))
    assert p.product_name == "4Over UUID-X"   # name fallback
    assert p.brand == "4Over"                 # brand fallback
    assert p.sizes == [] and p.options == []


@pytest.mark.asyncio
async def test_fourover_discover_changed_skips_fresh_skus(monkeypatch):
    """discover_changed filters out SKUs already synced more recently than `since`."""
    from datetime import datetime, timezone
    a = _fourover(monkeypatch)
    a.client.get_products = AsyncMock(return_value=[{"uuid": "u1"}, {"uuid": "u2"}])
    # u1 is fresh in DB (last_synced > since) — should be skipped
    mock_db = AsyncMock()
    mock_db.execute.return_value = [("u1",)]
    a.db = mock_db
    refs = await a.discover_changed(datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert [r.supplier_sku for r in refs] == ["u2"]


@pytest.mark.asyncio
async def test_fourover_discover_changed_returns_all_when_none_fresh(monkeypatch):
    """discover_changed returns every ref when DB has no freshly-synced SKUs."""
    from datetime import datetime, timezone
    a = _fourover(monkeypatch)
    a.client.get_products = AsyncMock(return_value=[{"uuid": "u1"}])
    mock_db = AsyncMock()
    mock_db.execute.return_value = []  # nothing fresh
    a.db = mock_db
    refs = await a.discover_changed(datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert [r.supplier_sku for r in refs] == ["u1"]


# ── SSAdapter ────────────────────────────────────────────────────────────

def _ss(monkeypatch):
    """Construct an SSAdapter, then replace its httpx client with a mock."""
    import modules.rest_connector.ss_adapter as mod

    adapter = mod.SSAdapter(
        _supplier(account_number="123", api_key="key"), db=None
    )
    adapter._client = SimpleNamespace(get=AsyncMock(), aclose=AsyncMock())
    return adapter


def test_ss_init_requires_account_and_key():
    import modules.rest_connector.ss_adapter as mod
    with pytest.raises(AuthError):
        mod.SSAdapter(_supplier(), db=None)
    with pytest.raises(AuthError):
        mod.SSAdapter(_supplier(account_number="123"), db=None)  # api_key missing


@pytest.mark.asyncio
async def test_ss_discover_explicit_list(monkeypatch):
    a = _ss(monkeypatch)
    refs = await a.discover(DiscoveryMode.EXPLICIT_LIST, explicit_list=["39", "40"])
    assert [r.supplier_sku for r in refs] == ["39", "40"]
    with pytest.raises(ValueError):
        await a.discover(DiscoveryMode.EXPLICIT_LIST, explicit_list=[])


@pytest.mark.asyncio
async def test_ss_discover_maps_styleids_and_skips_malformed(monkeypatch):
    a = _ss(monkeypatch)
    a._client.get = AsyncMock(return_value=_FakeResp(200, [
        {"styleID": "39"}, {"id": "40"}, {"foo": "x"},  # third has no id → skipped
    ]))
    refs = await a.discover(DiscoveryMode.FULL)
    assert [r.supplier_sku for r in refs] == ["39", "40"]


@pytest.mark.asyncio
async def test_ss_discover_first_n_slices(monkeypatch):
    a = _ss(monkeypatch)
    a._client.get = AsyncMock(return_value=_FakeResp(200, [
        {"styleID": str(i)} for i in range(5)
    ]))
    refs = await a.discover(DiscoveryMode.FIRST_N, limit=3)
    assert len(refs) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("status,exc", [(401, AuthError), (403, AuthError), (500, TransientError)])
async def test_ss_discover_http_error_classification(monkeypatch, status, exc):
    a = _ss(monkeypatch)
    a._client.get = AsyncMock(return_value=_FakeResp(status, None))
    with pytest.raises(exc):
        await a.discover(DiscoveryMode.FULL)


@pytest.mark.asyncio
async def test_ss_discover_network_error_is_transient(monkeypatch):
    a = _ss(monkeypatch)
    a._client.get = AsyncMock(side_effect=httpx.RequestError("boom"))
    with pytest.raises(TransientError):
        await a.discover(DiscoveryMode.FULL)


@pytest.mark.asyncio
async def test_ss_hydrate_normalizes_apparel_product(monkeypatch):
    import modules.rest_connector.ss_adapter as mod
    a = _ss(monkeypatch)
    a._client.get = AsyncMock(return_value=_FakeResp(200, [{"styleID": "B15453"}]))

    ps_product = SimpleNamespace(
        product_id="B15453",
        product_name="Gildan Heavy Cotton Tee",
        brand="Gildan",
        description="soft",
        categories=["T-Shirts"],
        primary_image_url="https://img/front.jpg",
        parts=[
            SimpleNamespace(part_id="B15453_S_BLK", color_name="Black", size_name="S"),
            SimpleNamespace(part_id="B15453_M_BLK", color_name="Black", size_name="M"),
        ],
    )
    prices = [SimpleNamespace(part_id="B15453_S_BLK", price_type="Net", quantity_min=1, price=3.50)]
    inventories = [SimpleNamespace(part_id="B15453_S_BLK", quantity_available=120, product_id="B15453")]
    media = [SimpleNamespace(url="https://img/blk.jpg", media_type="front",
                             color_name="Black", product_id="B15453")]

    monkeypatch.setattr(mod, "ss_to_ps_format",
                        lambda rows: ([ps_product], inventories, prices, media))

    p = await a.hydrate_product(ProductRef(supplier_sku="B15453"))
    assert p.supplier_sku == "B15453"
    assert p.product_type == "apparel"
    assert p.category_name == "T-Shirts"
    assert len(p.variants) == 2
    v0 = next(v for v in p.variants if v.part_id == "B15453_S_BLK")
    assert v0.inventory == 120
    assert len(v0.prices) == 1 and str(v0.prices[0].price) == "3.5"
    assert len(p.images) == 1 and p.images[0].url == "https://img/blk.jpg"


@pytest.mark.asyncio
async def test_ss_hydrate_404_is_supplier_error(monkeypatch):
    a = _ss(monkeypatch)
    a._client.get = AsyncMock(return_value=_FakeResp(404, None))
    with pytest.raises(SupplierError):
        await a.hydrate_product(ProductRef(supplier_sku="nope"))


@pytest.mark.asyncio
async def test_ss_hydrate_empty_rows_is_supplier_error(monkeypatch):
    a = _ss(monkeypatch)
    a._client.get = AsyncMock(return_value=_FakeResp(200, []))
    with pytest.raises(SupplierError):
        await a.hydrate_product(ProductRef(supplier_sku="B0"))


@pytest.mark.asyncio
async def test_ss_hydrate_normalizer_empty_is_supplier_error(monkeypatch):
    import modules.rest_connector.ss_adapter as mod
    a = _ss(monkeypatch)
    a._client.get = AsyncMock(return_value=_FakeResp(200, [{"styleID": "B1"}]))
    monkeypatch.setattr(mod, "ss_to_ps_format", lambda rows: ([], [], [], []))
    with pytest.raises(SupplierError):
        await a.hydrate_product(ProductRef(supplier_sku="B1"))


@pytest.mark.asyncio
async def test_ss_hydrate_through_real_normalizer_contract(monkeypatch):
    """REAL-CONTRACT test: ss_to_ps_format is NOT patched here. Realistic S&S
    /products rows (field shapes proven in test_ss_normalizer.py) flow through
    the actual normalizer → _ps_product_to_ingest → ProductIngest. This is the
    only adapter test that verifies the adapter<->normalizer contract instead
    of the adapter wiring in isolation.

    NOTE (honest scope limit): even this can't prove the rows match what the
    LIVE S&S API returns — that needs real creds or a recorded API capture,
    which the repo does not have for S&S/4Over.
    """
    a = _ss(monkeypatch)
    rows = [
        {"styleID": "39", "sku": "B0076_S_BLK", "styleName": "Gildan Ultra Cotton Tee",
         "brandName": "Gildan", "categoryName": "T-Shirts", "colorName": "Black",
         "sizeName": "S", "qty": 120, "yourPrice": 3.42, "warehouseAbbr": "IL",
         "colorFrontImage": "https://ss/img/black.jpg"},
        {"styleID": "39", "sku": "B0076_M_BLK", "styleName": "Gildan Ultra Cotton Tee",
         "brandName": "Gildan", "categoryName": "T-Shirts", "colorName": "Black",
         "sizeName": "M", "qty": 80, "yourPrice": 3.42, "warehouseAbbr": "IL",
         "colorFrontImage": "https://ss/img/black.jpg"},
    ]
    a._client.get = AsyncMock(return_value=_FakeResp(200, rows))

    p = await a.hydrate_product(ProductRef(supplier_sku="39"))

    assert p.supplier_sku == "39"
    assert p.product_type == "apparel"
    assert p.brand == "Gildan"
    assert p.category_name == "T-Shirts"
    assert len(p.variants) == 2
    v_s = next(v for v in p.variants if v.size == "S")
    assert v_s.color == "Black"
    assert v_s.inventory == 120
    assert len(v_s.prices) == 1 and str(v_s.prices[0].price) == "3.42"
    assert len(p.images) == 1  # two Black rows share one image → deduped


@pytest.mark.asyncio
async def test_ss_discover_changed_skips_fresh_skus(monkeypatch):
    """discover_changed filters out SKUs already synced more recently than `since`."""
    from datetime import datetime, timezone
    a = _ss(monkeypatch)
    a._client.get = AsyncMock(return_value=_FakeResp(200, [
        {"styleID": "39"}, {"styleID": "40"}
    ]))
    # style 39 is fresh in DB (last_synced > since) — should be skipped
    mock_db = AsyncMock()
    mock_db.execute.return_value = [("39",)]
    a.db = mock_db
    refs = await a.discover_changed(datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert [r.supplier_sku for r in refs] == ["40"]


@pytest.mark.asyncio
async def test_ss_discover_changed_returns_all_when_none_fresh(monkeypatch):
    """discover_changed returns every ref when DB has no freshly-synced SKUs."""
    from datetime import datetime, timezone
    a = _ss(monkeypatch)
    a._client.get = AsyncMock(return_value=_FakeResp(200, [{"styleID": "39"}]))
    mock_db = AsyncMock()
    mock_db.execute.return_value = []  # nothing fresh
    a.db = mock_db
    refs = await a.discover_changed(datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert [r.supplier_sku for r in refs] == ["39"]
