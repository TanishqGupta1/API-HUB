"""Redis-backed rate-limiter and token-cache tests (PR #156 hardening).

Hermetic — uses fakeredis in place of a real Redis server, no DB, no HTTP.
Covers the four fixes:
  1. rate limiter fails OPEN (to in-process bucket) when Redis raises
  2. ZADD members are unique — concurrent same-instant requests don't collide
  3. rejected (429'd) requests are NOT recorded — accept-then-record
  4. token cache reads the real pttl instead of fabricating a 1h expiry
"""
import asyncio
import time
import uuid

import pytest

pytestmark = pytest.mark.no_db

fakeredis = pytest.importorskip("fakeredis")
import fakeredis.aioredis as faioredis  # noqa: E402

import cache  # noqa: E402
from modules.integrations import auth as auth_mod  # noqa: E402
from modules.integrations.auth import (  # noqa: E402
    _check_rate_limit,
    _check_rate_limit_redis,
)
from modules.ops_client.client import OpsAuth, OpsGraphQLClient, _token_cache_key  # noqa: E402


@pytest.fixture
def fake_redis(monkeypatch):
    """Install a fresh fakeredis client as the module-level Redis singleton."""
    client = faioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache, "_redis", client)
    return client


class _FakeKey:
    """Minimal stand-in for IntegrationKey for rate-limit tests."""

    def __init__(self, limit: int):
        self.id = uuid.uuid4()
        self.rate_limit_per_minute = limit


# ── Fix 2: ZADD unique members don't collide ─────────────────────────────────
@pytest.mark.asyncio
async def test_zadd_members_are_unique_same_instant(fake_redis, monkeypatch):
    """Many requests at the same frozen timestamp must each occupy a slot.

    Pre-fix the member was f'{now:.6f}' so identical-instant requests
    collapsed to one member and ZCARD undercounted, leaking the limit.
    """
    # Freeze time so every call shares the same `now`.
    monkeypatch.setattr(auth_mod.time, "time", lambda: 1_000_000.0)

    key_str = "collision-test"
    limit = 100
    for _ in range(5):
        assert await _check_rate_limit_redis(key_str, limit) is True

    # All 5 should be distinct members despite the identical score.
    count = await fake_redis.zcard(f"rl:{key_str}")
    assert count == 5, f"expected 5 distinct members, got {count}"


@pytest.mark.asyncio
async def test_concurrent_requests_each_counted(fake_redis):
    """Concurrent (real-time) requests should each be recorded once."""
    key_str = "concurrent-test"
    limit = 50
    results = await asyncio.gather(
        *[_check_rate_limit_redis(key_str, limit) for _ in range(20)]
    )
    assert all(results)
    assert await fake_redis.zcard(f"rl:{key_str}") == 20


# ── Fix 3: rejected requests are NOT recorded ────────────────────────────────
@pytest.mark.asyncio
async def test_rejected_request_not_recorded(fake_redis):
    """Once at the limit, rejected calls must not inflate the window."""
    key_str = "reject-test"
    limit = 3

    for _ in range(limit):
        assert await _check_rate_limit_redis(key_str, limit) is True

    rkey = f"rl:{key_str}"
    assert await fake_redis.zcard(rkey) == limit

    # Further calls are rejected AND leave the count untouched.
    for _ in range(5):
        assert await _check_rate_limit_redis(key_str, limit) is False
        assert await fake_redis.zcard(rkey) == limit


@pytest.mark.asyncio
async def test_limit_boundary_exact(fake_redis):
    """Exactly `limit` requests pass; the next is rejected."""
    key_str = "boundary-test"
    limit = 4
    allowed = [await _check_rate_limit_redis(key_str, limit) for _ in range(limit)]
    assert allowed == [True] * limit
    assert await _check_rate_limit_redis(key_str, limit) is False


# ── Fix 1: fail-open fallback when Redis raises ──────────────────────────────
@pytest.mark.asyncio
async def test_rate_limit_fails_open_to_in_process_on_redis_error(monkeypatch, caplog):
    """A Redis error must fall back to in-process limiting, never 500."""

    class _BoomRedis:
        def pipeline(self):
            raise ConnectionError("redis flap")

    monkeypatch.setattr(cache, "_redis", _BoomRedis())
    # Reset in-process bucket state for a clean window.
    auth_mod._RATE_BUCKETS.clear()

    key = _FakeKey(limit=2)
    # First two requests pass via the in-process fallback.
    await _check_rate_limit(key)
    await _check_rate_limit(key)
    # Third exceeds the in-process bucket → 429 (proves limiting still active).
    with pytest.raises(auth_mod.HTTPException) as exc:
        await _check_rate_limit(key)
    assert exc.value.status_code == 429
    assert any("falling back to in-process" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_rate_limit_fails_open_does_not_500(monkeypatch):
    """Redis error on the very first request must not raise a non-429 error."""

    class _BoomRedis:
        def pipeline(self):
            raise TimeoutError("redis timeout")

    monkeypatch.setattr(cache, "_redis", _BoomRedis())
    auth_mod._RATE_BUCKETS.clear()
    key = _FakeKey(limit=10)
    # Should pass silently using the in-process bucket (no exception).
    await _check_rate_limit(key)


# ── Fix 4: token cache respects pttl ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_token_cache_respects_pttl(fake_redis):
    """On a Redis hit the local expiry must come from the real TTL, not +3600."""
    auth = OpsAuth(
        base_url="https://shop.example.com",
        token_url="https://shop.example.com/oauth/token",
        client_id="cid",
        client_secret="secret",
    )
    # Seed Redis with a token that has only 120s left.
    await fake_redis.set(_token_cache_key(auth), "cached-token", ex=120)

    client = OpsGraphQLClient(auth)
    now = time.time()
    token = await client._get_token()
    assert token == "cached-token"

    remaining = client._token_expires_at - now
    # Must reflect the ~120s TTL, never a fabricated ~3600s.
    assert 100 <= remaining <= 130, f"expected ~120s, got {remaining:.1f}s"
    await client.aclose()


@pytest.mark.asyncio
async def test_token_cache_no_ttl_forces_recheck(fake_redis):
    """A cached key with no expiry (-1) must force a re-check (expiry=0)."""
    auth = OpsAuth(
        base_url="https://shop.example.com",
        token_url="https://shop.example.com/oauth/token",
        client_id="cid2",
        client_secret="secret2",
    )
    await fake_redis.set(_token_cache_key(auth), "no-ttl-token")  # no expiry

    client = OpsGraphQLClient(auth)
    token = await client._get_token()
    assert token == "no-ttl-token"
    assert client._token_expires_at == 0.0
    await client.aclose()


@pytest.mark.asyncio
async def test_invalidate_token_awaits_redis_delete(fake_redis):
    """_invalidate_token is async and deterministically evicts the Redis key."""
    auth = OpsAuth(
        base_url="https://shop.example.com",
        token_url="https://shop.example.com/oauth/token",
        client_id="cid3",
        client_secret="secret3",
    )
    cache_key = _token_cache_key(auth)
    await fake_redis.set(cache_key, "revoked-token", ex=300)

    client = OpsGraphQLClient(auth)
    client._token = "revoked-token"
    await client._invalidate_token()

    assert client._token is None
    assert client._token_expires_at == 0.0
    # Eviction is deterministic — the key is gone immediately after the await.
    assert await fake_redis.get(cache_key) is None
    await client.aclose()
