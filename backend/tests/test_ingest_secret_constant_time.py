"""Task 2 — catalog/ingest.py must use constant-time secret compare.

Carries the PR #106 X-Ingest-Secret hardening into catalog/ingest.py so
no module in the repo still does raw `==` comparison on a shared secret
(timing-oracle vulnerability).
"""
from __future__ import annotations

import inspect

import pytest

pytestmark = pytest.mark.no_db


def test_ingest_secret_matches_uses_hmac(monkeypatch):
    """The matcher helper accepts the right value, rejects wrong / null / empty."""
    from modules.auth.dependencies import _ingest_secret_matches

    monkeypatch.setenv("INGEST_SHARED_SECRET", "correct-secret")
    assert _ingest_secret_matches("correct-secret") is True
    assert _ingest_secret_matches("wrong-secret") is False
    assert _ingest_secret_matches(None) is False
    assert _ingest_secret_matches("") is False


def test_require_ingest_secret_uses_constant_time_compare():
    """catalog/ingest.py::require_ingest_secret must delegate to the auth helper
    or call hmac.compare_digest — never use raw `== expected`."""
    from modules.catalog import ingest

    src = inspect.getsource(ingest.require_ingest_secret)
    # Function body must reach for the auth.dependencies matcher or
    # hmac.compare_digest directly.
    assert "_ingest_secret_matches" in src or "compare_digest" in src, (
        "require_ingest_secret should use _ingest_secret_matches() or "
        "hmac.compare_digest, not raw equality"
    )
    # And the timing-vulnerable comparison must be gone.
    assert " == expected" not in src
    assert "!= expected" not in src
