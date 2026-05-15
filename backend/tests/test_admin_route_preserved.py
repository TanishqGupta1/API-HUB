"""T19: POST /api/push/{customer_id}/{product_id} stays at the same URL with
the same response keys after the rewire, but the engine swap (n8n webhook →
integration gateway) flips the in-flight status from the legacy 'pending'
string to the gateway-native 'accepted'. Frontend status-map update lives in
T22.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database import async_session
from modules.catalog.models import Product, ProductVariant, CustomerProductSelection
from modules.customers.models import Customer
from modules.push_log.models import ProductPushLog
from modules.push_mappings.models import PushMapping


@pytest.fixture(autouse=True)
def _mock_preflight_ok():
    ok_result = MagicMock()
    ok_result.ok = True
    with patch("modules.ops_push.gateway.run_preflight", new=AsyncMock(return_value=ok_result)):
        yield


@pytest_asyncio.fixture
async def admin_push_scaffold(seed_supplier):
    async with async_session() as s:
        cust = Customer(
            name="Admin Push Co",
            ops_base_url="https://admin.ops.com",
            ops_token_url="https://admin.ops.com/token",
            ops_client_id="admin-client",
            ops_auth_config={"client_secret": "shh"},
            is_active=True,
        )
        s.add(cust)
        await s.flush()
        pid = (
            await s.execute(
                pg_insert(Product)
                .values(
                    supplier_id=seed_supplier.id,
                    supplier_sku="ADM-T19-1",
                    product_name="Admin Route Product",
                    product_type="apparel",
                )
                .on_conflict_do_nothing()
                .returning(Product.id)
            )
        ).scalar_one()
        s.add(
            ProductVariant(
                product_id=pid,
                sku="ADM-T19-1-RED-L",
                color="Red",
                size="L",
                base_price=10.50,
            )
        )
        await s.commit()
        await s.refresh(cust)
        s.expunge(cust)
        product = await s.get(Product, pid)
        s.expunge(product)
    try:
        yield {"customer": cust, "product": product, "supplier": seed_supplier}
    finally:
        async with async_session() as s:
            await s.execute(delete(PushMapping).where(PushMapping.customer_id == cust.id))
            await s.execute(delete(ProductPushLog).where(ProductPushLog.customer_id == cust.id))
            await s.execute(
                delete(CustomerProductSelection).where(
                    CustomerProductSelection.customer_id == cust.id
                )
            )
            await s.execute(delete(Customer).where(Customer.id == cust.id))
            await s.commit()


@pytest.mark.asyncio
async def test_admin_route_preserves_response_shape(client, admin_push_scaffold):
    """{status, push_log_id, message, payload} — every key the admin UI binds
    to today must still be present, with payload still carrying the OPS-shape
    merge so the preview pane keeps working."""
    cid = admin_push_scaffold["customer"].id
    pid = admin_push_scaffold["product"].id

    resp = await client.post(f"/api/push/{cid}/{pid}")
    assert resp.status_code in (200, 202), resp.text
    body = resp.json()

    assert set(["status", "push_log_id", "message", "payload"]).issubset(body.keys()), body
    assert isinstance(body["payload"], dict)
    # payload still carries the OPS-shape merge (admin preview pane reads this)
    assert "name" in body["payload"]


@pytest.mark.asyncio
async def test_admin_route_writes_gateway_native_push_log(client, admin_push_scaffold):
    """Internal dispatch must hit the gateway pipeline, so the push_log row
    has gateway-native fields populated (key_id, payload_hash, supplier_slug)
    and the status uses the new vocab ('accepted' not legacy 'pending')."""
    cid = admin_push_scaffold["customer"].id
    pid = admin_push_scaffold["product"].id

    resp = await client.post(f"/api/push/{cid}/{pid}")
    assert resp.status_code in (200, 202), resp.text
    body = resp.json()

    async with async_session() as s:
        log = await s.get(ProductPushLog, uuid.UUID(body["push_log_id"]))
        assert log is not None
        assert log.payload_hash, "gateway pipeline must record payload_hash"
        assert log.supplier_slug == admin_push_scaffold["supplier"].slug
        assert log.supplier_sku == admin_push_scaffold["product"].supplier_sku
        # Gateway vocab — 'accepted' (pre-processing) or any terminal state
        # if BackgroundTasks already executed in the test client.
        assert log.status in {
            "accepted",
            "processing",
            "pushed",
            "failed",
            "partial_failure",
        }, log.status


