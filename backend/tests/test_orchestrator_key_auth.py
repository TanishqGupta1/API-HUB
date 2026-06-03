"""DB-backed tests for the Integration Gateway auth front door.

Phase 3 gap-closure: test_integration_key_scope.py covered check_key_scope
(the per-call guard) in isolation. This covers get_orchestrator_key — the
actual X-Orchestrator-Key dependency an external orchestrator hits — and the
REAL Redis sliding-window limiter (against the live Redis container, skipped
if Redis is unavailable).
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete

import modules.integrations.auth as auth
from database import async_session
from modules.integrations.models import IntegrationKey


@pytest_asyncio.fixture
async def key_cleanup():
    ids: list[str] = []
    yield ids
    async with async_session() as s:
        if ids:
            await s.execute(delete(IntegrationKey).where(IntegrationKey.id.in_(ids)))
            await s.commit()


async def _make_key(ids, raw: str, **fields) -> str:
    key_id = fields.pop("id", f"test-key-{uuid4().hex[:8]}")
    async with async_session() as s:
        s.add(IntegrationKey(
            id=key_id,
            key_hash=auth._hash_key(raw),
            name=fields.pop("name", "test key"),
            **fields,
        ))
        await s.commit()
    ids.append(key_id)
    return key_id


# ── get_orchestrator_key ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_header_401():
    async with async_session() as s:
        with pytest.raises(HTTPException) as ei:
            await auth.get_orchestrator_key(x_orchestrator_key=None, db=s)
    assert ei.value.status_code == 401
    assert ei.value.detail["code"] == "BAD_SIGNATURE"


@pytest.mark.asyncio
async def test_unknown_key_401():
    async with async_session() as s:
        with pytest.raises(HTTPException) as ei:
            await auth.get_orchestrator_key(x_orchestrator_key="nope-not-a-real-key", db=s)
    assert ei.value.status_code == 401
    assert ei.value.detail["code"] == "BAD_SIGNATURE"


@pytest.mark.asyncio
async def test_valid_key_returns_record(key_cleanup):
    kid = await _make_key(key_cleanup, "rawsecret-valid", rate_limit_per_minute=60, is_active=True)
    async with async_session() as s:
        key = await auth.get_orchestrator_key(x_orchestrator_key="rawsecret-valid", db=s)
    assert key.id == kid
    assert key.is_active is True


@pytest.mark.asyncio
async def test_revoked_key_403(key_cleanup):
    await _make_key(key_cleanup, "rawsecret-revoked", is_active=True,
                    revoked_at=datetime.now(timezone.utc))
    async with async_session() as s:
        with pytest.raises(HTTPException) as ei:
            await auth.get_orchestrator_key(x_orchestrator_key="rawsecret-revoked", db=s)
    assert ei.value.status_code == 403
    assert ei.value.detail["code"] == "KEY_REVOKED"


@pytest.mark.asyncio
async def test_inactive_key_403(key_cleanup):
    await _make_key(key_cleanup, "rawsecret-inactive", is_active=False)
    async with async_session() as s:
        with pytest.raises(HTTPException) as ei:
            await auth.get_orchestrator_key(x_orchestrator_key="rawsecret-inactive", db=s)
    assert ei.value.status_code == 403
    assert ei.value.detail["code"] == "KEY_REVOKED"


@pytest.mark.asyncio
async def test_synthetic_key_not_reachable_via_header(key_cleanup):
    # Synthetic admin-proxy keys must NOT be usable via X-Orchestrator-Key,
    # even with the correct raw value — the DB lookup filters is_synthetic.
    await _make_key(key_cleanup, "rawsecret-synthetic", is_active=True, is_synthetic=True)
    async with async_session() as s:
        with pytest.raises(HTTPException) as ei:
            await auth.get_orchestrator_key(x_orchestrator_key="rawsecret-synthetic", db=s)
    assert ei.value.status_code == 401  # looked up as if it doesn't exist


# ── real Redis sliding-window limiter ──────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_redis_real_sliding_window():
    """Exercise the ACTUAL Redis sorted-set limiter against the live Redis
    container. Skips cleanly when Redis is not configured."""
    from cache import close_redis, get_redis, init_redis

    await init_redis()  # connect using REDIS_URL (no-op when unset)
    redis = get_redis()
    if redis is None:
        pytest.skip("Redis not configured (REDIS_URL unset/unreachable)")

    key_str = f"test-rl-{uuid4().hex}"
    try:
        results = [await auth._check_rate_limit_redis(key_str, 3) for _ in range(4)]
        assert results == [True, True, True, False]  # 3 allowed, 4th rejected in-window
    finally:
        await redis.delete(f"rl:{key_str}")
        await close_redis()  # restore the no-Redis default for other tests
