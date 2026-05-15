"""Task 16 — GET /api/integrations/v1/push-requests/{push_log_id}.

Hermetic — no real DB. Patches `db.get(ProductPushLog, ...)` to return
a synthetic row, then asserts the route shape matches PushStatusOut.

Note: Vidhi's existing `modules/integrations/routes.py` already has an
equivalent endpoint. T16's GET lives in the new `integration_gateway`
module (per M1 plan), using env-var auth from T12. T14 (Urvashi) will
later consolidate schemas; for now we reuse Vidhi's PushStatusOut.
"""
from __future__ import annotations

import os
import uuid as uuid_mod
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.no_db


def _setup_env():
    """Plant a single integration key for the env-driven auth."""
    for k in list(os.environ.keys()):
        if k.startswith("INTEGRATION_KEY_"):
            del os.environ[k]
    os.environ["INTEGRATION_KEY_test-orch"] = "secret-1"


def _build_app(fake_row):
    """Build a FastAPI app with the gateway router + an injected fake DB."""
    from modules.integration_gateway.routes import router
    from database import get_db

    app = FastAPI()
    app.include_router(router)

    async def fake_db():
        # Mock db.get(ProductPushLog, push_log_id) → fake_row (or None)
        db = AsyncMock()
        db.get = AsyncMock(return_value=fake_row)
        yield db

    app.dependency_overrides[get_db] = fake_db
    return app


def _fake_push_log(**overrides):
    """Synthetic ProductPushLog row — only the fields the route reads."""
    base = dict(
        id=uuid_mod.UUID("11111111-1111-1111-1111-111111111111"),
        status="pushed",
        customer_id=uuid_mod.UUID("22222222-2222-2222-2222-222222222222"),
        supplier_slug="sanmar",
        supplier_sku="PC61",
        ops_product_id="12345",
        error=None,
        step_results=None,
        cleanup_targets=None,
        callback_status="not_requested",
        callback_attempts=0,
        pushed_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_get_push_request_returns_terminal_status():
    """Happy path — push_log exists and is in terminal state."""
    _setup_env()
    row = _fake_push_log(status="pushed")
    client = TestClient(_build_app(row))

    r = client.get(
        f"/api/integrations/v1/push-requests/{row.id}",
        headers={"X-Orchestrator-Key": "secret-1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["push_log_id"] == str(row.id)
    assert body["status"] == "pushed"
    assert body["ops_product_id"] == "12345"
    assert body["supplier_sku"] == "PC61"


def test_get_push_request_missing_returns_404():
    """No row found → 404 UNKNOWN_REF."""
    _setup_env()
    client = TestClient(_build_app(None))

    r = client.get(
        f"/api/integrations/v1/push-requests/{uuid_mod.uuid4()}",
        headers={"X-Orchestrator-Key": "secret-1"},
    )
    assert r.status_code == 404


def test_get_push_request_unauthorized_without_key():
    """No header → 401 from T12 dependency."""
    _setup_env()
    row = _fake_push_log()
    client = TestClient(_build_app(row))

    r = client.get(f"/api/integrations/v1/push-requests/{row.id}")
    assert r.status_code == 401


def test_get_push_request_forbidden_with_wrong_key():
    """Wrong key → 403."""
    _setup_env()
    row = _fake_push_log()
    client = TestClient(_build_app(row))

    r = client.get(
        f"/api/integrations/v1/push-requests/{row.id}",
        headers={"X-Orchestrator-Key": "wrong-key"},
    )
    assert r.status_code == 403


def test_get_push_request_includes_step_results():
    """When step_results are populated, they're surfaced in the response."""
    _setup_env()
    row = _fake_push_log(
        status="partial_failure",
        step_results=[
            {"step": "setProduct", "ok": True, "ops_id": "12345"},
            {"step": "setProductSize", "ok": False, "error": "size_not_found"},
        ],
        cleanup_targets={"ops_product_id": "12345"},
        error="size lookup failed",
    )
    client = TestClient(_build_app(row))

    r = client.get(
        f"/api/integrations/v1/push-requests/{row.id}",
        headers={"X-Orchestrator-Key": "secret-1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "partial_failure"
    assert body["error"] == "size lookup failed"
    assert len(body["step_results"]) == 2
    assert body["step_results"][0]["ok"] is True
    assert body["step_results"][1]["ok"] is False
    assert body["cleanup_targets"] == {"ops_product_id": "12345"}
