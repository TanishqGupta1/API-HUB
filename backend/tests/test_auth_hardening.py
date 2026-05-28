"""Phase A auth-foundation hardening tests."""
import types

import pytest
from sqlalchemy import delete, func, select

from modules.integrations import auth as gw_auth


def _fake_key(limit: int, key_id: str = "k1"):
    # Limiter only reads .id and .rate_limit_per_minute off the key.
    return types.SimpleNamespace(id=key_id, rate_limit_per_minute=limit)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_rate_limiter_allows_up_to_limit_then_429():
    gw_auth._RATE_BUCKETS.clear()
    key = _fake_key(limit=3, key_id="rl-allow")
    for _ in range(3):
        await gw_auth._check_rate_limit(key)
    with pytest.raises(gw_auth.HTTPException) as exc:
        await gw_auth._check_rate_limit(key)
    assert exc.value.status_code == 429


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_rate_limiter_noop_when_limit_unset():
    gw_auth._RATE_BUCKETS.clear()
    key = _fake_key(limit=0, key_id="rl-none")
    for _ in range(50):
        await gw_auth._check_rate_limit(key)
    assert "rl-none" not in gw_auth._RATE_BUCKETS


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_rate_limiter_keys_independent():
    gw_auth._RATE_BUCKETS.clear()
    a, b = _fake_key(1, "rl-a"), _fake_key(1, "rl-b")
    await gw_auth._check_rate_limit(a)
    await gw_auth._check_rate_limit(b)
    with pytest.raises(gw_auth.HTTPException):
        await gw_auth._check_rate_limit(a)


async def _delete_all_users():
    from tests.conftest import async_session
    from modules.auth.models import User
    async with async_session() as s:
        await s.execute(delete(User))
        await s.commit()


async def _user_count() -> int:
    from tests.conftest import async_session
    from modules.auth.models import User
    async with async_session() as s:
        return (await s.execute(select(func.count()).select_from(User))).scalar() or 0


@pytest.mark.asyncio
async def test_register_bootstrap_then_closed(client):
    await _delete_all_users()
    try:
        r = await client.post(
            "/api/auth/register",
            json={"email": "first-admin@vg.test", "password": "s3cret-pw-123"},
        )
        assert r.status_code == 201, r.text
        assert r.json()["role"] == "vg_admin"

        r2 = await client.post(
            "/api/auth/register",
            json={"email": "second@vg.test", "password": "s3cret-pw-123"},
        )
        assert r2.status_code == 409
        assert await _user_count() == 1
    finally:
        await _delete_all_users()


@pytest.mark.asyncio
async def test_signup_status_open_only_during_bootstrap(client):
    await _delete_all_users()
    try:
        r = await client.get("/api/auth/signup-status")
        assert r.json() == {"open": True, "reason": "bootstrap"}
        await client.post(
            "/api/auth/register",
            json={"email": "admin@vg.test", "password": "s3cret-pw-123"},
        )
        r2 = await client.get("/api/auth/signup-status")
        assert r2.json() == {"open": False, "reason": "closed"}
    finally:
        await _delete_all_users()
