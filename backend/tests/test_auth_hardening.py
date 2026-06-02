"""Phase A auth-foundation hardening tests."""
import asyncio
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


_TEST_EMAILS = [
    "first-admin@example.com",
    "second@example.com",
    "admin-bootstrap@example.com",
    "race-a@example.com",
    "race-b@example.com",
]


async def _delete_test_users():
    """Remove only the emails this test file creates — keep the suite hermetic."""
    from tests.conftest import async_session
    from modules.auth.models import User
    async with async_session() as s:
        await s.execute(delete(User).where(User.email.in_(_TEST_EMAILS)))
        await s.commit()


async def _user_count() -> int:
    from tests.conftest import async_session
    from modules.auth.models import User
    async with async_session() as s:
        return (await s.execute(select(func.count()).select_from(User))).scalar() or 0


@pytest.mark.asyncio
async def test_register_bootstrap_then_closed(client):
    """Bootstrap: first register creates vg_admin; second returns 409."""
    await _delete_test_users()
    # This test requires a completely empty users table. Skip gracefully when
    # a pre-existing admin (e.g. dev DB) is present — the behaviour is already
    # correct (register returns 409 for any user when DB is non-empty).
    if await _user_count() > 0:
        pytest.skip("Dev DB has existing users — bootstrap test requires empty DB")
    try:
        r = await client.post(
            "/api/auth/register",
            json={"email": "first-admin@example.com", "password": "s3cret-pw-123"},
        )
        assert r.status_code == 201, r.text
        assert r.json()["role"] == "vg_admin"

        r2 = await client.post(
            "/api/auth/register",
            json={"email": "second@example.com", "password": "s3cret-pw-123"},
        )
        assert r2.status_code == 409
    finally:
        await _delete_test_users()


@pytest.mark.asyncio
async def test_signup_status_open_only_during_bootstrap(client):
    """signup-status returns bootstrap when DB is empty, closed otherwise."""
    await _delete_test_users()
    if await _user_count() > 0:
        # DB already has users — only verify the "closed" half of the contract.
        r = await client.get("/api/auth/signup-status")
        assert r.json() == {"open": False, "reason": "closed"}
        return
    try:
        r = await client.get("/api/auth/signup-status")
        assert r.json() == {"open": True, "reason": "bootstrap"}
        await client.post(
            "/api/auth/register",
            json={"email": "admin-bootstrap@example.com", "password": "s3cret-pw-123"},
        )
        r2 = await client.get("/api/auth/signup-status")
        assert r2.json() == {"open": False, "reason": "closed"}
    finally:
        await _delete_test_users()


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_get_orchestrator_key_awaits_rate_limit(monkeypatch):
    """Task 1b — verify _check_rate_limit is awaited inside get_orchestrator_key.

    Regression guard: if someone accidentally drops the `await _check_rate_limit`
    call (or makes it fire-and-forget) the rate limiter silently stops working.

    We patch the real `_get_key_from_db` helper so the DB is never touched, then
    patch `_check_rate_limit` with a coroutine that records the call. Because the
    helper returns a fully-formed key, get_orchestrator_key runs to completion and
    `called` must be populated — no bare except masking failures.
    """
    from unittest.mock import AsyncMock, MagicMock
    from modules.integrations import auth as gw_auth

    called = []
    mock_check = AsyncMock(side_effect=lambda key: called.append(key.id))

    fake_key = types.SimpleNamespace(
        id="test-key-id",
        is_active=True,
        revoked_at=None,
        rate_limit_per_minute=10,
        scopes=["push"],
        customer_id=None,
    )

    monkeypatch.setattr(gw_auth, "_check_rate_limit", mock_check)

    # Patch the real DB-lookup helper to return our fake key without a DB.
    async def fake_get_key(db, key_hash):
        return fake_key

    monkeypatch.setattr(gw_auth, "_get_key_from_db", fake_get_key)

    # If _check_rate_limit is awaited, 'called' is populated before return.
    returned = await gw_auth.get_orchestrator_key(
        x_orchestrator_key="any-value",
        db=MagicMock(),
    )

    assert returned is fake_key
    assert called == ["test-key-id"], (
        "_check_rate_limit was not awaited inside get_orchestrator_key — "
        "rate limiting is silently broken"
    )


@pytest.mark.asyncio
async def test_register_bootstrap_is_race_safe(client):
    """Concurrent registers: exactly one 201 and one 409 — no double-admin."""
    await _delete_test_users()
    if await _user_count() > 0:
        pytest.skip("Dev DB has existing users — bootstrap test requires empty DB")
    try:
        r1, r2 = await asyncio.gather(
            client.post("/api/auth/register", json={"email": "race-a@example.com", "password": "s3cret-pw-123"}),
            client.post("/api/auth/register", json={"email": "race-b@example.com", "password": "s3cret-pw-123"}),
        )
        statuses = sorted([r1.status_code, r2.status_code])
        assert statuses == [201, 409], f"expected one 201 + one 409, got {statuses}"
    finally:
        await _delete_test_users()
