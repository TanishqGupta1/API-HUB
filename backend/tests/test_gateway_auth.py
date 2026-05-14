"""Task 12 — Integration Gateway X-Orchestrator-Key dependency.

Env-driven key registry: `INTEGRATION_KEY_<id>=<raw_secret>`.
Constant-time compare via hmac.compare_digest. Returns OrchestratorContext
(key_id + raw_key) to handlers.

NOTE: parallel to Vidhi's existing DB-backed `modules/integrations/auth.py`.
Per M1 spec, env is the source of truth for V1; DB-backed lookup is
deferred. Reconciliation between the two is out-of-scope for T12.
"""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from modules.integration_gateway.auth import (
    OrchestratorContext,
    require_orchestrator_key,
)


@pytest.fixture
def app(monkeypatch):
    # Clean slate — clear any pre-existing keys then plant one.
    for k in list(__import__("os").environ.keys()):
        if k.startswith("INTEGRATION_KEY_"):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("INTEGRATION_KEY_oh-test", "raw-key-abc")

    app = FastAPI()

    @app.get("/x")
    async def x(ctx: OrchestratorContext = Depends(require_orchestrator_key)):
        return {"key_id": ctx.key_id}

    return app


def test_missing_header_returns_401(app):
    client = TestClient(app)
    r = client.get("/x")
    assert r.status_code == 401


def test_wrong_key_returns_403(app):
    client = TestClient(app)
    r = client.get("/x", headers={"X-Orchestrator-Key": "wrong"})
    assert r.status_code == 403


def test_correct_key_returns_context(app):
    client = TestClient(app)
    r = client.get("/x", headers={"X-Orchestrator-Key": "raw-key-abc"})
    assert r.status_code == 200
    # Case-insensitive compare — Windows env vars get upper-cased, so
    # `INTEGRATION_KEY_oh-test` becomes `OH-TEST` on Win, `oh-test` on Linux.
    # The returned key_id is whatever the OS stored.
    assert r.json()["key_id"].lower() == "oh-test"


def test_empty_header_returns_401(app):
    """Empty string in the header is treated as missing."""
    client = TestClient(app)
    r = client.get("/x", headers={"X-Orchestrator-Key": ""})
    assert r.status_code == 401
