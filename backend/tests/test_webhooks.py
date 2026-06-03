"""Unit tests for the outbound webhook dispatch service.

Plan ref: 2026-06-02-production-readiness.md, Phase 3 — "Webhooks: delivery +
retry + payload-shape tests (silent-loss risk)".

Covers the parts that decide whether a delivery silently disappears:
  - HMAC signing of the payload
  - SSRF guards (registration-time string check + fire-time DNS resolution)
  - _fire_one failure accounting: increment on failure, reset on success,
    auto-disable after 10 consecutive failures, and the SSRF-block path
  - fire_test result shape + signature header

All hermetic — httpx + DNS are mocked, no network/DB.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest

import modules.webhooks.service as svc


# ── helpers ──────────────────────────────────────────────────────────────

def _endpoint(**over) -> SimpleNamespace:
    base = dict(
        id="ep-1",
        url="https://hooks.example.com/in",
        secret=None,
        events="push.completed",
        is_active=True,
        failure_count=0,
        last_failure_at=None,
        last_fired_at=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _patch_client(monkeypatch, *, status=200, raise_exc=None) -> dict:
    """Patch svc.httpx.AsyncClient with a fake; return a dict capturing the post."""
    captured: dict = {}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, content=None, headers=None):
            captured["url"] = url
            captured["content"] = content
            captured["headers"] = headers
            if raise_exc:
                raise raise_exc
            return SimpleNamespace(status_code=status)

    monkeypatch.setattr(svc.httpx, "AsyncClient", lambda **kw: _Client())
    return captured


# ── _sign_payload ────────────────────────────────────────────────────────

def test_sign_payload_matches_hmac_sha256():
    body = b'{"event":"push.completed"}'
    sig = svc._sign_payload("topsecret", body)
    expected = hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()
    assert sig == expected
    assert len(sig) == 64


def test_sign_payload_changes_with_body():
    a = svc._sign_payload("s", b"one")
    b = svc._sign_payload("s", b"two")
    assert a != b


# ── _validate_webhook_url (registration-time SSRF guard) ───────────────────

@pytest.mark.parametrize("url", [
    "ftp://example.com/x",          # bad scheme
    "http://localhost/hook",        # loopback hostname
    "http://127.0.0.1/hook",        # loopback IP
    "http://10.0.0.5/hook",         # private IP
    "http://169.254.1.1/hook",      # link-local
    "https:///nohost",              # missing hostname
])
def test_validate_webhook_url_rejects_unsafe(url):
    with pytest.raises(ValueError):
        svc._validate_webhook_url(url)


@pytest.mark.parametrize("url", [
    "https://hooks.example.com/in",
    "http://api.partner.io/webhooks/ops",
])
def test_validate_webhook_url_allows_public(url):
    assert svc._validate_webhook_url(url) == url


# ── _resolve_and_check (fire-time DNS SSRF guard) ──────────────────────────

def test_resolve_and_check_allows_public_ip(monkeypatch):
    monkeypatch.setattr(svc.socket, "gethostbyname", lambda h: "93.184.216.34")
    svc._resolve_and_check("example.com")  # no raise


def test_resolve_and_check_blocks_private_ip(monkeypatch):
    monkeypatch.setattr(svc.socket, "gethostbyname", lambda h: "10.1.2.3")
    with pytest.raises(ValueError):
        svc._resolve_and_check("rebind.evil.test")


def test_resolve_and_check_blocks_unresolvable(monkeypatch):
    import socket as _socket

    def _boom(h):
        raise _socket.gaierror("nope")

    monkeypatch.setattr(svc.socket, "gethostbyname", _boom)
    with pytest.raises(ValueError):
        svc._resolve_and_check("no-such-host.test")


# ── _fire_one (delivery + failure accounting) ──────────────────────────────

@pytest.mark.asyncio
async def test_fire_one_success_resets_failure_count(monkeypatch):
    monkeypatch.setattr(svc, "_resolve_and_check", lambda h: None)
    cap = _patch_client(monkeypatch, status=200)
    ep = _endpoint(failure_count=4)
    now = datetime.now(timezone.utc)

    ok = await svc._fire_one(ep, b'{"x":1}', {"X-ApiHub-Event": "push.completed"}, now)

    assert ok is True
    assert ep.failure_count == 0          # reset on success
    assert ep.last_fired_at == now
    assert cap["url"] == ep.url            # POST actually attempted


@pytest.mark.asyncio
async def test_fire_one_non_2xx_increments_failure(monkeypatch):
    monkeypatch.setattr(svc, "_resolve_and_check", lambda h: None)
    _patch_client(monkeypatch, status=500)
    ep = _endpoint(failure_count=2)

    ok = await svc._fire_one(ep, b"{}", {}, datetime.now(timezone.utc))

    assert ok is False
    assert ep.failure_count == 3
    assert ep.last_failure_at is not None


@pytest.mark.asyncio
async def test_fire_one_exception_increments_failure(monkeypatch):
    monkeypatch.setattr(svc, "_resolve_and_check", lambda h: None)
    _patch_client(monkeypatch, raise_exc=httpx.ConnectError("refused"))
    ep = _endpoint(failure_count=0)

    ok = await svc._fire_one(ep, b"{}", {}, datetime.now(timezone.utc))

    assert ok is False
    assert ep.failure_count == 1


@pytest.mark.asyncio
async def test_fire_one_auto_disables_after_10_failures(monkeypatch):
    monkeypatch.setattr(svc, "_resolve_and_check", lambda h: None)
    _patch_client(monkeypatch, status=503)
    ep = _endpoint(failure_count=9, is_active=True)

    ok = await svc._fire_one(ep, b"{}", {}, datetime.now(timezone.utc))

    assert ok is False
    assert ep.failure_count == 10
    assert ep.is_active is False           # auto-disabled


@pytest.mark.asyncio
async def test_fire_one_ssrf_block_skips_post(monkeypatch):
    def _block(h):
        raise ValueError("private IP")

    monkeypatch.setattr(svc, "_resolve_and_check", _block)
    cap = _patch_client(monkeypatch, status=200)
    ep = _endpoint(failure_count=0)

    ok = await svc._fire_one(ep, b"{}", {}, datetime.now(timezone.utc))

    assert ok is False
    assert ep.failure_count == 1
    assert cap == {}                       # POST never attempted


# ── fire_test (manual test-delivery) ───────────────────────────────────────

@pytest.mark.asyncio
async def test_fire_test_success_shape_and_signature(monkeypatch):
    monkeypatch.setattr(svc, "_resolve_and_check", lambda h: None)
    cap = _patch_client(monkeypatch, status=200)
    ep = _endpoint(secret={"value": "shhh"})

    result = await svc.fire_test(ep)

    assert result == {"success": True, "status_code": 200, "error": None}
    # payload shape + signature header present and correct
    headers = cap["headers"]
    assert headers["X-ApiHub-Event"] == "test"
    assert "X-ApiHub-Delivery" in headers
    expected_sig = "sha256=" + hmac.new(b"shhh", cap["content"], hashlib.sha256).hexdigest()
    assert headers["X-ApiHub-Signature"] == expected_sig
    assert json.loads(cap["content"])["event"] == "test"


@pytest.mark.asyncio
async def test_fire_test_ssrf_block_returns_error(monkeypatch):
    def _block(h):
        raise ValueError("blocked")

    monkeypatch.setattr(svc, "_resolve_and_check", _block)
    _patch_client(monkeypatch, status=200)
    ep = _endpoint(secret=None)

    result = await svc.fire_test(ep)
    assert result["success"] is False
    assert result["status_code"] is None
    assert "blocked" in result["error"]
