"""T15: POST /api/integrations/v1/push-requests — flagship push endpoint.

Covers: X-Orchestrator-Key auth, product resolution by product_id OR supplier_sku,
inline dry_run execution, idempotent replay, in-flight concurrency guard,
preflight blockers, partial_failure cleanup_targets, and callback delivery.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete

from database import async_session
from modules.catalog.models import Product, CustomerProductSelection
from modules.customers.models import Customer
from modules.integrations.models import IntegrationKey
from modules.push_log.models import ProductPushLog
from modules.push_mappings.models import PushMapping
from modules.suppliers.models import Supplier


# ---------------------------------------------------------------------------
# Module-level autouse: mock preflight to ok=True so tests aren't blocked
# by missing markup rules / variants / images in the test product.
# Tests that specifically test preflight behaviour apply their own inner
# patch which overrides this one for the duration of that test.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_preflight_ok():
    ok_result = MagicMock()
    ok_result.ok = True
    with patch("modules.ops_push.gateway.run_preflight", new=AsyncMock(return_value=ok_result)):
        yield


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def integration_key():
    """Create an active IntegrationKey + return both the row and the raw header value."""
    raw = secrets.token_urlsafe(24)
    key_id = f"test-key-{uuid4().hex[:8]}"
    async with async_session() as s:
        k = IntegrationKey(
            id=key_id,
            key_hash=hashlib.sha256(raw.encode()).hexdigest(),
            name="T15 test key",
        )
        s.add(k)
        await s.commit()
        await s.refresh(k)
        s.expunge(k)
    try:
        yield {"key": k, "raw": raw}
    finally:
        async with async_session() as s:
            await s.execute(delete(IntegrationKey).where(IntegrationKey.id == key_id))
            await s.commit()


@pytest_asyncio.fixture
async def push_scaffold(seed_supplier):
    """Customer + product attached to seed_supplier, ready for a push request."""
    async with async_session() as s:
        cust = Customer(
            name="Push Test Co",
            ops_base_url="https://test.ops.com",
            ops_token_url="https://test.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
            is_active=True,
        )
        s.add(cust)
        await s.flush()
        prod = Product(
            supplier_id=seed_supplier.id,
            supplier_sku="PC61-T15",
            product_name="Push T15 Product",
            product_type="apparel",
        )
        s.add(prod)
        await s.commit()
        await s.refresh(cust)
        await s.refresh(prod)
        s.expunge_all()
    try:
        yield {"customer": cust, "product": prod, "supplier": seed_supplier}
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


def _body(customer_id: UUID, supplier_slug: str, *, product_id=None, supplier_sku=None, dry_run=False):
    pref = {}
    if product_id is not None:
        pref["product_id"] = str(product_id)
    if supplier_sku is not None:
        pref["supplier_sku"] = supplier_sku
    return {
        "target": {"customer_id": str(customer_id)},
        "source": {"supplier_slug": supplier_slug},
        "product_ref": pref,
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_push_without_orchestrator_key_returns_401(client, push_scaffold):
    resp = await client.post(
        "/api/integrations/v1/push-requests",
        json=_body(
            push_scaffold["customer"].id,
            push_scaffold["supplier"].slug,
            supplier_sku="PC61-T15",
        ),
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_push_with_bad_orchestrator_key_returns_401(client, push_scaffold):
    resp = await client.post(
        "/api/integrations/v1/push-requests",
        json=_body(
            push_scaffold["customer"].id,
            push_scaffold["supplier"].slug,
            supplier_sku="PC61-T15",
        ),
        headers={"X-Orchestrator-Key": "definitely-not-a-real-key"},
    )
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Product resolution — by supplier_sku or product_id (T14 envelope broadening)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_push_resolves_product_by_supplier_sku(client, push_scaffold, integration_key):
    resp = await client.post(
        "/api/integrations/v1/push-requests",
        json=_body(
            push_scaffold["customer"].id,
            push_scaffold["supplier"].slug,
            supplier_sku="PC61-T15",
            dry_run=True,
        ),
        headers={"X-Orchestrator-Key": integration_key["raw"]},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["dry_run"] is True
    assert body["supplier_sku"] == "PC61-T15"


@pytest.mark.asyncio
async def test_push_resolves_product_by_product_id(client, push_scaffold, integration_key):
    """T14 broadened PushRequestProductRef to accept product_id; T15 must consume it."""
    resp = await client.post(
        "/api/integrations/v1/push-requests",
        json=_body(
            push_scaffold["customer"].id,
            push_scaffold["supplier"].slug,
            product_id=push_scaffold["product"].id,
            dry_run=True,
        ),
        headers={"X-Orchestrator-Key": integration_key["raw"]},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["dry_run"] is True
    # Push_log should record the supplier_sku resolved from the product row
    assert body["supplier_sku"] == "PC61-T15"


@pytest.mark.asyncio
async def test_push_rejects_when_product_ref_empty(client, push_scaffold, integration_key):
    resp = await client.post(
        "/api/integrations/v1/push-requests",
        json={
            "target": {"customer_id": str(push_scaffold["customer"].id)},
            "source": {"supplier_slug": push_scaffold["supplier"].slug},
            "product_ref": {},
            "dry_run": True,
        },
        headers={"X-Orchestrator-Key": integration_key["raw"]},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Dry run — must execute inline so the 202 carries terminal status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_push_dry_run_returns_terminal_status_inline(client, push_scaffold, integration_key):
    """Spec push pipeline: dry_run runs FakeOpsClient in-memory and responds
    with status='dry_run_pushed'. The 202 must not require the client to poll."""
    resp = await client.post(
        "/api/integrations/v1/push-requests",
        json=_body(
            push_scaffold["customer"].id,
            push_scaffold["supplier"].slug,
            supplier_sku="PC61-T15",
            dry_run=True,
        ),
        headers={"X-Orchestrator-Key": integration_key["raw"]},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "dry_run_pushed", body
    assert body["dry_run"] is True


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_push_idempotent_replay_returns_same_push_log(client, push_scaffold, integration_key):
    """Same Idempotency-Key + same payload hash → same push_log_id, no new row."""
    body = _body(
        push_scaffold["customer"].id,
        push_scaffold["supplier"].slug,
        supplier_sku="PC61-T15",
        dry_run=True,
    )
    headers = {
        "X-Orchestrator-Key": integration_key["raw"],
        "Idempotency-Key": "t15-replay-001",
    }
    r1 = await client.post("/api/integrations/v1/push-requests", json=body, headers=headers)
    r2 = await client.post("/api/integrations/v1/push-requests", json=body, headers=headers)
    assert r1.status_code == 202 and r2.status_code == 202
    assert r1.json()["push_log_id"] == r2.json()["push_log_id"]


@pytest.mark.asyncio
async def test_push_idempotency_conflict_on_different_body(client, push_scaffold, integration_key):
    """Same Idempotency-Key but different payload hash → 409 IDEMPOTENCY_CONFLICT."""
    headers = {
        "X-Orchestrator-Key": integration_key["raw"],
        "Idempotency-Key": "t15-conflict-001",
    }
    r1 = await client.post(
        "/api/integrations/v1/push-requests",
        json=_body(
            push_scaffold["customer"].id,
            push_scaffold["supplier"].slug,
            supplier_sku="PC61-T15",
            dry_run=True,
        ),
        headers=headers,
    )
    assert r1.status_code == 202
    # Second call with same key but different body (live vs dry) → conflict
    r2 = await client.post(
        "/api/integrations/v1/push-requests",
        json=_body(
            push_scaffold["customer"].id,
            push_scaffold["supplier"].slug,
            supplier_sku="PC61-T15",
            dry_run=False,
        ),
        headers=headers,
    )
    assert r2.status_code == 409, r2.text
    assert "IDEMPOTENCY_CONFLICT" in r2.text


# ---------------------------------------------------------------------------
# IN_FLIGHT concurrency guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_push_in_flight_returns_409(client, push_scaffold, integration_key):
    """A processing row for same (customer, product) → 409 IN_FLIGHT."""
    async with async_session() as s:
        log = ProductPushLog(
            product_id=push_scaffold["product"].id,
            customer_id=push_scaffold["customer"].id,
            status="processing",
            pushed_at=datetime.now(timezone.utc),
            key_id=integration_key["key"].id,
            supplier_slug=push_scaffold["supplier"].slug,
            supplier_sku="PC61-T15",
            callback_status="not_requested",
        )
        s.add(log)
        await s.commit()
        log_id = log.id

    try:
        resp = await client.post(
            "/api/integrations/v1/push-requests",
            json=_body(
                push_scaffold["customer"].id,
                push_scaffold["supplier"].slug,
                supplier_sku="PC61-T15",
                dry_run=True,
            ),
            headers={"X-Orchestrator-Key": integration_key["raw"]},
        )
        assert resp.status_code == 409, resp.text
        assert "IN_FLIGHT" in resp.text
    finally:
        async with async_session() as s:
            await s.execute(delete(ProductPushLog).where(ProductPushLog.id == log_id))
            await s.commit()


# ---------------------------------------------------------------------------
# Preflight blocker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_push_preflight_blocker_returns_422(client, push_scaffold, integration_key):
    """Preflight blockers → 422 with code=PREFLIGHT_BLOCKER."""
    mock_result = MagicMock()
    mock_result.ok = False
    mock_result.to_error_envelope.return_value = {
        "status": "error",
        "code": "PREFLIGHT_BLOCKER",
        "message": "Preflight failed: no markup rule",
        "details": [{"check": "check_prices_set", "reason": "no markup rule for customer"}],
        "trace_id": "test-trace-001",
    }
    with patch("modules.ops_push.gateway.run_preflight", new=AsyncMock(return_value=mock_result)):
        resp = await client.post(
            "/api/integrations/v1/push-requests",
            json=_body(
                push_scaffold["customer"].id,
                push_scaffold["supplier"].slug,
                supplier_sku="PC61-T15",
            ),
            headers={"X-Orchestrator-Key": integration_key["raw"]},
        )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["code"] == "PREFLIGHT_BLOCKER"


# ---------------------------------------------------------------------------
# execute_push — partial failure records cleanup_targets
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_push_partial_failure_records_cleanup_targets(push_scaffold, integration_key):
    """execute_push halts mid-plan and records cleanup_targets on step failure."""
    from modules.ops_push.gateway import execute_push

    async with async_session() as s:
        log = ProductPushLog(
            product_id=push_scaffold["product"].id,
            customer_id=push_scaffold["customer"].id,
            status="accepted",
            pushed_at=datetime.now(timezone.utc),
            key_id=integration_key["key"].id,
            supplier_slug=push_scaffold["supplier"].slug,
            supplier_sku="PC61-T15",
            callback_status="not_requested",
            dry_run=False,
        )
        s.add(log)
        await s.commit()
        log_id = log.id

    step1 = MagicMock()
    step1.model_dump.return_value = {"mutation": "setProduct", "variables": {}}
    step2 = MagicMock()
    step2.model_dump.return_value = {"mutation": "setProductSize", "variables": {}}
    mock_payload = MagicMock()
    mock_payload.plan = [step1, step2]

    try:
        with patch("modules.ops_push.gateway.build_push_payload", new=AsyncMock(return_value=mock_payload)):
            with patch("modules.ops_push.gateway._StubOpsClient") as MockClient:
                instance = AsyncMock()
                instance.set_product.return_value = {"products_id": 99001}
                instance.set_product_size.side_effect = RuntimeError("OPS network error")
                MockClient.return_value = instance
                await execute_push(log_id)

        async with async_session() as s:
            row = await s.get(ProductPushLog, log_id)
            assert row.status == "partial_failure"
            assert row.cleanup_targets is not None
            assert row.cleanup_targets.get("ops_product_id") == "99001"
    finally:
        async with async_session() as s:
            await s.execute(delete(ProductPushLog).where(ProductPushLog.id == log_id))
            await s.commit()


# ---------------------------------------------------------------------------
# execute_push — callback fires on success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_push_fires_callback_on_success(push_scaffold, integration_key):
    """execute_push POSTs to callback_url when push completes successfully."""
    from modules.ops_push.gateway import execute_push

    async with async_session() as s:
        log = ProductPushLog(
            product_id=push_scaffold["product"].id,
            customer_id=push_scaffold["customer"].id,
            status="accepted",
            pushed_at=datetime.now(timezone.utc),
            key_id=integration_key["key"].id,
            supplier_slug=push_scaffold["supplier"].slug,
            supplier_sku="PC61-T15",
            callback_url="https://callback.example.com/webhook",
            callback_status="pending",
            dry_run=False,
        )
        s.add(log)
        await s.commit()
        log_id = log.id

    step1 = MagicMock()
    step1.model_dump.return_value = {"mutation": "setProduct", "variables": {}}
    mock_payload = MagicMock()
    mock_payload.plan = [step1]

    try:
        with patch("modules.ops_push.gateway.build_push_payload", new=AsyncMock(return_value=mock_payload)):
            with patch("modules.ops_push.gateway._StubOpsClient") as MockClient:
                instance = AsyncMock()
                instance.set_product.return_value = {"products_id": 99001}
                MockClient.return_value = instance
                with patch(
                    "modules.ops_push.gateway._fire_callback",
                    new=AsyncMock(return_value=True),
                ) as mock_cb:
                    await execute_push(log_id)

        async with async_session() as s:
            row = await s.get(ProductPushLog, log_id)
            assert row.status == "pushed"
            assert row.callback_status == "sent"
        assert mock_cb.called
    finally:
        async with async_session() as s:
            await s.execute(delete(ProductPushLog).where(ProductPushLog.id == log_id))
            await s.commit()
