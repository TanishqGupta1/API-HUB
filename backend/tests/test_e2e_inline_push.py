"""E2E: mint key (DB) -> inline LIVE push (mocked OPS) -> poll terminal -> callback.

Task 7 of the n8n inline-push plan (Phase 5). Exercises the full live path:
dry_run=False, so prepare_push_intent upserts the inline product and the route
schedules run_push_task -> execute_push as a BackgroundTask. Under httpx
ASGITransport, background tasks complete before the POST returns, so the poll
sees a terminal status immediately.

OPS is mocked by reusing FakeOpsClient (the dry-run client) as the LIVE client
via _build_live_client — it returns the same dict shapes the dispatcher expects
(set_product -> {"products_id": ...}), so status resolves to "pushed". The plan's
suggested `fake.execute = AsyncMock(...)` mock shape is WRONG: execute_push calls
the adapter's mutation methods (client.set_product(vars)), not client.execute().
"""
from __future__ import annotations

import hashlib
import secrets
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from database import async_session
from modules.catalog.models import Product
from modules.customers.models import Customer
from modules.integrations.models import IntegrationKey
from modules.ops_push.gateway import FakeOpsClient
from modules.push_log.models import ProductPushLog


def _inline_product(sku="E2E-1", variants=1):
    return {
        "supplier_sku": sku,
        "product_name": "E2E One",
        "product_type": "apparel",
        "apparel_details": {"pricing_method": "tiered_variant"},
        "variants": [
            {"part_id": f"E2E-V{i}", "color": "Black", "size": ["L", "XL", "M"][i],
             "base_price": "10.00", "inventory": 10,
             "prices": [{"price_type": "Net", "quantity_min": 1, "quantity_max": 2147483647, "price": "10.00"}]}
            for i in range(variants)
        ],
    }


@pytest_asyncio.fixture
async def scaffold(seed_supplier):
    raw = secrets.token_urlsafe(24)
    kid = f"e2e-{uuid4().hex[:8]}"
    async with async_session() as s:
        s.add(IntegrationKey(id=kid, key_hash=hashlib.sha256(raw.encode()).hexdigest(), name="e2e"))
        cust = Customer(name="E2E Co", ops_base_url="https://t.ops", ops_token_url="https://t.ops/tok",
                        ops_client_id="x", ops_auth_config={"client_secret": "x"}, is_active=True)
        s.add(cust)
        await s.commit()
        await s.refresh(cust)
        cid = cust.id
    try:
        yield {"raw": raw, "customer_id": cid, "supplier": seed_supplier}
    finally:
        async with async_session() as s:
            await s.execute(delete(ProductPushLog).where(ProductPushLog.customer_id == cid))
            await s.execute(delete(Product).where(Product.supplier_id == seed_supplier.id,
                                                  Product.supplier_sku.in_(["E2E-1", "E2E-PF"])))
            await s.execute(delete(Customer).where(Customer.id == cid))
            await s.execute(delete(IntegrationKey).where(IntegrationKey.id == kid))
            await s.commit()


@pytest.fixture
def _preflight_ok():
    from unittest.mock import MagicMock
    ok = MagicMock(ok=True, warnings=[])
    with patch("modules.ops_push.gateway.run_preflight", new=AsyncMock(return_value=ok)):
        yield


@pytest.mark.asyncio
async def test_inline_live_push_polls_terminal_and_fires_callback(client, scaffold, _preflight_ok):
    """mint -> inline live push (mocked OPS=pushed) -> poll terminal -> callback fired."""
    ctx = scaffold
    body = {
        "target": {"customer_id": str(ctx["customer_id"])},
        "source": {"supplier_slug": ctx["supplier"].slug},
        "product": _inline_product("E2E-1", variants=2),
        "dry_run": False,
        "callback": {"url": "https://example.com/n8n/webhook", "secret": "shh"},
    }
    fake_callback = AsyncMock(return_value=True)
    with patch("modules.ops_push.gateway._build_live_client", return_value=FakeOpsClient()), \
         patch("modules.ops_push.gateway._fire_callback", new=fake_callback):
        r = await client.post("/api/integrations/v1/push-requests", json=body,
                              headers={"X-Orchestrator-Key": ctx["raw"]})
        assert r.status_code == 202, r.text
        pid = r.json()["push_log_id"]
        poll = await client.get(f"/api/integrations/v1/push-requests/{pid}",
                                headers={"X-Orchestrator-Key": ctx["raw"]})

    assert poll.status_code == 200, poll.text
    assert poll.json()["status"] == "pushed", poll.text
    # Webhook callback fired exactly once with this push_log id.
    assert fake_callback.await_count == 1
    assert str(pid) in str(fake_callback.await_args.args)


@pytest.mark.asyncio
async def test_inline_live_push_partial_failure_keeps_catalog(client, scaffold, _preflight_ok):
    """A mid-chain OPS failure -> partial_failure, but the inline product stays
    in the catalog (upsert is committed before the push runs)."""
    ctx = scaffold

    class _PartialFailClient(FakeOpsClient):
        async def set_product_size(self, variables):
            raise RuntimeError("OPS_SIZE_ERROR: simulated size failure")

    body = {
        "target": {"customer_id": str(ctx["customer_id"])},
        "source": {"supplier_slug": ctx["supplier"].slug},
        "product": _inline_product("E2E-PF", variants=1),
        "dry_run": False,
    }
    with patch("modules.ops_push.gateway._build_live_client", return_value=_PartialFailClient()):
        r = await client.post("/api/integrations/v1/push-requests", json=body,
                              headers={"X-Orchestrator-Key": ctx["raw"]})
        assert r.status_code == 202, r.text
        pid = r.json()["push_log_id"]
        poll = await client.get(f"/api/integrations/v1/push-requests/{pid}",
                                headers={"X-Orchestrator-Key": ctx["raw"]})

    assert poll.status_code == 200, poll.text
    # set_product set products_id, then set_product_size failed -> partial_failure.
    assert poll.json()["status"] == "partial_failure", poll.text
    # Catalog still has the inline product despite the OPS-side failure.
    async with async_session() as s:
        prod = (await s.execute(
            select(Product).where(Product.supplier_id == ctx["supplier"].id,
                                   Product.supplier_sku == "E2E-PF")
        )).scalar_one_or_none()
    assert prod is not None, "inline product must remain in catalog on partial failure"
