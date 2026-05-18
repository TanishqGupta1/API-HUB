"""T2 regression: catalog.ingest.require_ingest_secret must use a constant-time
secret compare (via auth.dependencies._ingest_secret_matches or hmac directly)
so the ingest endpoints have security parity with the routes hardened in PR #106.

Raw `==` leaks timing information about the secret one byte at a time; an
attacker on the same network can stitch the secret together by measuring
response latency for thousands of probe values. compare_digest does the same
work in constant time regardless of which byte differs.
"""
from __future__ import annotations

import inspect

import pytest

pytestmark = pytest.mark.no_db


def test_ingest_secret_matches_uses_compare_digest(monkeypatch):
    """The auth helper backs both the X-Ingest-Secret routes and (after T2)
    catalog/ingest.py — exercise it directly first so we know the contract."""
    from modules.auth.dependencies import _ingest_secret_matches

    monkeypatch.setenv("INGEST_SHARED_SECRET", "correct-secret")
    assert _ingest_secret_matches("correct-secret") is True
    assert _ingest_secret_matches("wrong-secret") is False
    assert _ingest_secret_matches(None) is False
    assert _ingest_secret_matches("") is False


def test_require_ingest_secret_does_not_use_raw_equality():
    """Source-level guard: the body of catalog.ingest.require_ingest_secret
    must NOT contain a raw `==` against the expected secret. It must route
    through the constant-time matcher or hmac.compare_digest directly."""
    from modules.catalog import ingest

    src = inspect.getsource(ingest.require_ingest_secret)
    assert (
        "_ingest_secret_matches" in src or "compare_digest" in src
    ), "require_ingest_secret must use a constant-time secret compare"
    assert " == expected" not in src, "raw == leaks timing info on the secret"
    assert " != expected" not in src, "raw != leaks timing info on the secret"


@pytest.mark.asyncio
async def test_require_ingest_secret_accepts_correct_secret(monkeypatch):
    from fastapi import HTTPException
    from modules.catalog.ingest import require_ingest_secret

    monkeypatch.setenv("INGEST_SHARED_SECRET", "correct-secret")
    # Returns None on success — no exception raised.
    await require_ingest_secret(x_ingest_secret="correct-secret")


@pytest.mark.asyncio
async def test_require_ingest_secret_rejects_wrong_secret(monkeypatch):
    from fastapi import HTTPException
    from modules.catalog.ingest import require_ingest_secret

    monkeypatch.setenv("INGEST_SHARED_SECRET", "correct-secret")
    with pytest.raises(HTTPException) as exc:
        await require_ingest_secret(x_ingest_secret="wrong")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_require_ingest_secret_rejects_missing_header(monkeypatch):
    from fastapi import HTTPException
    from modules.catalog.ingest import require_ingest_secret

    monkeypatch.setenv("INGEST_SHARED_SECRET", "correct-secret")
    with pytest.raises(HTTPException) as exc:
        await require_ingest_secret(x_ingest_secret=None)
    assert exc.value.status_code == 401
