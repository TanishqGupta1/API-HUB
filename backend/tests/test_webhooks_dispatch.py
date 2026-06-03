"""DB-backed tests for fire_webhooks() — the actual delivery orchestrator.

Phase 3 gap-closure: the earlier test_webhooks.py only covered the helpers
(_fire_one / _sign_payload / fire_test). This covers the real entry point
called from execute_push: endpoint selection by event subscription + customer
scope, HMAC signing, and persistence of failure state after the commit.

The HTTP layer is mocked (no network); everything else — the DB query,
event filtering, customer scoping, signing, and the commit — is real.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from database import async_session
from modules.webhooks import service as svc
from modules.webhooks.models import WebhookEndpoint


@pytest.fixture
def http_capture(monkeypatch):
    """Patch the webhook HTTP layer; capture posted (url, headers). holder['status']
    controls the simulated response code."""
    posted: list[tuple[str, dict]] = []
    holder = {"status": 200}

    monkeypatch.setattr(svc, "_resolve_and_check", lambda h: None)

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, content=None, headers=None):
            posted.append((url, headers, content))
            return SimpleNamespace(status_code=holder["status"])

    monkeypatch.setattr(svc.httpx, "AsyncClient", lambda **kw: _Client())
    return SimpleNamespace(posted=posted, holder=holder)


@pytest_asyncio.fixture
async def wh_cleanup():
    ids: list = []
    yield ids
    async with async_session() as s:
        if ids:
            await s.execute(delete(WebhookEndpoint).where(WebhookEndpoint.id.in_(ids)))
            await s.commit()


async def _make_endpoint(ids, **fields) -> WebhookEndpoint:
    async with async_session() as s:
        ep = WebhookEndpoint(**fields)
        s.add(ep)
        await s.commit()
        await s.refresh(ep)
        ids.append(ep.id)
        s.expunge(ep)
        return ep


@pytest.mark.asyncio
async def test_fire_webhooks_only_subscribed_active_endpoints_fire(http_capture, wh_cleanup):
    base = f"https://hook-{uuid4().hex}.example.com"
    a = await _make_endpoint(wh_cleanup, url=f"{base}/a", events="push.completed", is_active=True)
    await _make_endpoint(wh_cleanup, url=f"{base}/b", events="push.failed", is_active=True)       # not subscribed
    await _make_endpoint(wh_cleanup, url=f"{base}/c", events="push.completed", is_active=False)    # inactive

    await svc.fire_webhooks(customer_id=None, event="push.completed", payload={"push_log_id": "1"})

    fired = {u for (u, _h, _c) in http_capture.posted}
    assert fired == {a.url}  # only the active, subscribed endpoint


@pytest.mark.asyncio
async def test_fire_webhooks_unsupported_event_is_noop(http_capture, wh_cleanup):
    await _make_endpoint(wh_cleanup, url=f"https://hook-{uuid4().hex}.example.com",
                         events="push.completed", is_active=True)
    await svc.fire_webhooks(customer_id=None, event="push.bogus", payload={})
    assert http_capture.posted == []  # returns before any DB work


@pytest.mark.asyncio
async def test_fire_webhooks_signs_payload_with_endpoint_secret(http_capture, wh_cleanup):
    url = f"https://hook-{uuid4().hex}.example.com"
    await _make_endpoint(wh_cleanup, url=url, events="push.completed", is_active=True,
                         secret={"value": "topsecret"})
    payload = {"push_log_id": "abc", "status": "pushed"}

    await svc.fire_webhooks(customer_id=None, event="push.completed", payload=payload)

    assert len(http_capture.posted) == 1
    _url, headers, content = http_capture.posted[0]
    assert headers["X-ApiHub-Event"] == "push.completed"
    assert "X-ApiHub-Delivery" in headers
    expected_body = json.dumps({**payload, "event": "push.completed"}, default=str).encode()
    expected_sig = "sha256=" + hmac.new(b"topsecret", expected_body, hashlib.sha256).hexdigest()
    assert headers["X-ApiHub-Signature"] == expected_sig
    assert json.loads(content)["event"] == "push.completed"


@pytest.mark.asyncio
async def test_fire_webhooks_customer_scoping(http_capture, wh_cleanup):
    from modules.customers.models import Customer

    # Two real customers (FK to customers requires real rows). Both ops URLs are
    # in TEST_CUSTOMER_OPS_URLS so the autouse fixture cleans them up.
    async with async_session() as s:
        c1 = Customer(name="WH Cust 1", ops_base_url="https://test.ops.com",
                      ops_token_url="https://test.ops.com/token", ops_client_id="x",
                      ops_auth_config={"client_secret": "x"})
        c2 = Customer(name="WH Cust 2", ops_base_url="https://test2.ops.com",
                      ops_token_url="https://test2.ops.com/token", ops_client_id="x",
                      ops_auth_config={"client_secret": "x"})
        s.add_all([c1, c2])
        await s.commit()
        cust_id, other_id = c1.id, c2.id

    base = f"https://hook-{uuid4().hex}.example.com"
    mine = await _make_endpoint(wh_cleanup, url=f"{base}/mine", events="push.completed",
                                is_active=True, customer_id=cust_id)
    glob = await _make_endpoint(wh_cleanup, url=f"{base}/global", events="push.completed",
                                is_active=True, customer_id=None)
    await _make_endpoint(wh_cleanup, url=f"{base}/other", events="push.completed",
                         is_active=True, customer_id=other_id)  # a DIFFERENT real customer

    await svc.fire_webhooks(customer_id=cust_id, event="push.completed", payload={"x": 1})

    fired = {u for (u, _h, _c) in http_capture.posted}
    assert fired == {mine.url, glob.url}  # customer-specific + global, NOT the other customer's


@pytest.mark.asyncio
async def test_fire_webhooks_persists_failure_count(http_capture, wh_cleanup):
    http_capture.holder["status"] = 500  # simulate endpoint returning an error
    ep = await _make_endpoint(wh_cleanup, url=f"https://hook-{uuid4().hex}.example.com",
                              events="push.completed", is_active=True, failure_count=0)

    await svc.fire_webhooks(customer_id=None, event="push.completed", payload={})

    async with async_session() as s:
        refreshed = (await s.execute(
            select(WebhookEndpoint).where(WebhookEndpoint.id == ep.id)
        )).scalar_one()
        assert refreshed.failure_count == 1          # incremented + committed
        assert refreshed.last_failure_at is not None
