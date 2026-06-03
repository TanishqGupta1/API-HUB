"""Unit tests for integration-key scoping + rate-limit fallback.

Plan ref: 2026-06-02-production-readiness.md, Phase 3 — "integrations
key-scope: direct unit tests for check_key_scope edge cases + Redis-outage
fallback in integrations/auth.py".

check_key_scope is the per-key authorization boundary (which customers /
suppliers a key may push to). _check_rate_limit must fail OPEN to the
in-process bucket when Redis is down — never 500, never silently unlimited.

All hermetic — no DB; Redis is patched.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

import modules.integrations.auth as auth


# ── check_key_scope ────────────────────────────────────────────────────────

def _key(*, customers=None, suppliers=None, rate=0) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        allowed_customer_ids=customers,
        allowed_supplier_slugs=suppliers,
        rate_limit_per_minute=rate,
    )


def test_scope_unrestricted_key_allows_anything():
    # No allow-lists → key may push for any customer/supplier
    auth.check_key_scope(_key(), "cust-1", "sanmar")  # no raise


def test_scope_allows_listed_customer_and_supplier():
    k = _key(customers=["cust-1", "cust-2"], suppliers=["sanmar"])
    auth.check_key_scope(k, "cust-1", "sanmar")  # no raise


def test_scope_blocks_unlisted_customer():
    k = _key(customers=["cust-1"], suppliers=None)
    with pytest.raises(HTTPException) as ei:
        auth.check_key_scope(k, "cust-999", "sanmar")
    assert ei.value.status_code == 403
    assert ei.value.detail["code"] == "KEY_NOT_ALLOWED"
    assert "customer" in ei.value.detail["message"]


def test_scope_blocks_unlisted_supplier():
    k = _key(customers=None, suppliers=["sanmar"])
    with pytest.raises(HTTPException) as ei:
        auth.check_key_scope(k, "cust-1", "alphabroder")
    assert ei.value.status_code == 403
    assert "supplier" in ei.value.detail["message"]


def test_scope_customer_ok_but_supplier_blocked():
    # Customer passes; supplier check still fires
    k = _key(customers=["cust-1"], suppliers=["sanmar"])
    with pytest.raises(HTTPException) as ei:
        auth.check_key_scope(k, "cust-1", "ssactivewear")
    assert ei.value.detail["code"] == "KEY_NOT_ALLOWED"
    assert "supplier" in ei.value.detail["message"]


# ── _check_rate_limit ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clear_buckets():
    auth._RATE_BUCKETS.clear()
    yield
    auth._RATE_BUCKETS.clear()


@pytest.mark.asyncio
async def test_rate_limit_disabled_when_limit_zero(monkeypatch):
    # limit <= 0 → no limiting, returns immediately regardless of Redis
    monkeypatch.setattr("cache.get_redis", lambda: None)
    k = _key(rate=0)
    for _ in range(100):
        await auth._check_rate_limit(k)  # never raises


@pytest.mark.asyncio
async def test_rate_limit_in_process_enforced_when_no_redis(monkeypatch):
    # Redis unavailable → in-process token bucket enforces the limit
    monkeypatch.setattr("cache.get_redis", lambda: None)
    k = _key(rate=3)
    for _ in range(3):
        await auth._check_rate_limit(k)         # first 3 allowed
    with pytest.raises(HTTPException) as ei:
        await auth._check_rate_limit(k)         # 4th blocked
    assert ei.value.status_code == 429
    assert ei.value.detail["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_rate_limit_fails_open_to_in_process_when_redis_errors(monkeypatch):
    # Redis present but the check raises → must NOT 500; falls back to the
    # in-process bucket and still enforces the limit (fail-open-to-limited).
    monkeypatch.setattr("cache.get_redis", lambda: object())  # truthy → Redis "available"

    async def _boom(key_str, limit):
        raise RuntimeError("redis timeout")

    monkeypatch.setattr(auth, "_check_rate_limit_redis", _boom)

    k = _key(rate=2)
    await auth._check_rate_limit(k)             # ok (Redis error swallowed)
    await auth._check_rate_limit(k)             # ok
    with pytest.raises(HTTPException) as ei:    # in-process bucket still limits
        await auth._check_rate_limit(k)
    assert ei.value.status_code == 429
