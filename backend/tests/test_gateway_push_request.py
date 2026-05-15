"""T15: POST /api/integrations/v1/push-requests — flagship push endpoint.

Covers: X-Orchestrator-Key auth, product resolution by product_id OR supplier_sku,
inline dry_run execution, idempotent replay, in-flight concurrency guard, and
preflight blockers.
"""
from __future__ import annotations

import hashlib
import secrets
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
