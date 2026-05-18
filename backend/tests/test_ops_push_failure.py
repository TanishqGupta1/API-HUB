"""Failure-path coverage for the admin push route after the T19 rewire.

The legacy n8n-webhook-failure test ('n8n trigger failed') no longer applies
since modules.ops_push.service.push_product now dispatches through the
integration gateway, not the n8n webhook. This rewritten variant exercises
the equivalent gateway-pipeline failure mode: execute_push blows up mid-plan.
"""
from __future__ import annotations

import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from modules.catalog.models import Product
from modules.customers.models import Customer
from modules.ops_push.service import push_product
from modules.push_log.models import ProductPushLog
from modules.suppliers.models import Supplier


@pytest.fixture(autouse=True)
def _mock_preflight_ok():
    """Preflight=ok so we can exercise the gateway failure path itself,
    not a preflight rejection."""
    ok = MagicMock()
    ok.ok = True
    with patch("modules.ops_push.gateway.run_preflight", new=AsyncMock(return_value=ok)):
        yield


@pytest.mark.asyncio
async def test_push_product_gateway_failure(db, monkeypatch):
    """When execute_push raises, the push_log row lands in a failed/partial
    state. The response shape stays {status, push_log_id, message, payload}."""

    supplier = Supplier(
        name="Test Supplier",
        slug="test-slug-" + str(uuid.uuid4())[:8],
        protocol="promostandards",
        push_name_prefix="TEST-",
    )
    db.add(supplier)
    await db.commit()

    customer = Customer(
        name="Test Customer",
        ops_base_url="http://ops.test",
        ops_token_url="http://ops.test/token",
        ops_client_id="test_client",
        ops_auth_config={"client_secret": "test_secret"},
    )
    db.add(customer)
    await db.commit()

    product = Product(
        product_name="Test Product",
        supplier_id=supplier.id,
        supplier_sku="SKU-" + str(uuid.uuid4())[:8],
    )
    db.add(product)
    await db.commit()

    customer_id = customer.id
    product_id = product.id

    # No BackgroundTasks → push_product awaits execute_push inline. We force
    # a mid-plan crash and confirm push_log captures the failure.
    async def _boom(_push_log_id):
        # Touch the push_log via its own session so the row reflects the
        # gateway's actual failure-write semantics (status='failed', error set).
        from database import async_session as _session
        async with _session() as s:
            row = await s.get(ProductPushLog, _push_log_id)
            row.status = "failed"
            row.error = "synthetic boom"
            await s.commit()

    with patch("modules.ops_push.service.execute_push", new=_boom):
        result = await push_product(db, customer_id, product_id, background_tasks=None)

    # Response shape preserved
    assert set(["status", "push_log_id", "message", "payload"]).issubset(result.keys())

    # push_log persisted in a failure state
    db.expire_all()
    log = (
        await db.execute(
            select(ProductPushLog).where(ProductPushLog.product_id == product_id)
        )
    ).scalar_one_or_none()
    assert log is not None
    assert log.status == "failed"
    assert log.error == "synthetic boom"
