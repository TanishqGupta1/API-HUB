"""Task 13 — Payload-hash idempotency ledger.

Hermetic — no DB. Mocks `AsyncSession.execute` to return a synthetic
ProductPushLog row (or None) so we can exercise the three decision
branches: proceed / return_existing / conflict.

Reuses `compute_payload_hash` from `modules.ops_push.payload_builder`
(RFC 8785 JCS) — single source of truth for canonicalisation. The
plan's simpler `sort_keys` snippet is superseded by spec Rev 1.
"""
from __future__ import annotations

import asyncio
import uuid as uuid_mod
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.no_db

from modules.integration_gateway.idempotency import (
    IdempotencyDecision,
    check_idempotency,
    compute_payload_hash,
)


# ── compute_payload_hash sanity ────────────────────────────────────────


def test_payload_hash_is_deterministic():
    body = {"a": 1, "b": [1, 2]}
    assert compute_payload_hash(body) == compute_payload_hash(
        {"b": [1, 2], "a": 1}
    )


def test_payload_hash_changes_on_diff():
    assert compute_payload_hash({"a": 1}) != compute_payload_hash({"a": 2})


def test_payload_hash_strips_explicit_nulls():
    """RFC 8785 rule: null object members removed before hashing."""
    assert compute_payload_hash({"a": 1}) == compute_payload_hash(
        {"a": 1, "b": None}
    )


# ── check_idempotency: 3 decision branches ──────────────────────────────


def _make_db(row):
    """Mock AsyncSession that returns `row` from `execute(...).scalar_one_or_none()`."""
    db = AsyncMock()
    result = AsyncMock()
    result.scalar_one_or_none = lambda: row
    db.execute = AsyncMock(return_value=result)
    return db


def _fake_push_log(payload_hash: str, push_log_id: str):
    return SimpleNamespace(
        id=uuid_mod.UUID(push_log_id),
        payload_hash=payload_hash,
    )


def test_idempotency_new_key_returns_proceed():
    """No existing row → proceed (new push)."""
    db = _make_db(None)
    decision = asyncio.run(
        check_idempotency(
            db=db,
            key_id="oh-test",
            idempotency_key="abc",
            payload_hash=compute_payload_hash({"x": 1}),
        )
    )
    assert decision.action == "proceed"
    assert decision.existing_push_log_id is None


def test_idempotency_same_key_same_payload_returns_existing():
    """Same (key_id, idempotency_key) + same hash → return_existing."""
    h = compute_payload_hash({"x": 1})
    row = _fake_push_log(h, "11111111-1111-1111-1111-111111111111")
    db = _make_db(row)
    decision = asyncio.run(
        check_idempotency(
            db=db,
            key_id="oh-test",
            idempotency_key="abc",
            payload_hash=h,
        )
    )
    assert decision.action == "return_existing"
    assert str(decision.existing_push_log_id) == "11111111-1111-1111-1111-111111111111"


def test_idempotency_same_key_different_payload_returns_conflict():
    """Same (key_id, idempotency_key) + different hash → conflict (409)."""
    row = _fake_push_log(
        compute_payload_hash({"x": 1}),
        "11111111-1111-1111-1111-111111111111",
    )
    db = _make_db(row)
    decision = asyncio.run(
        check_idempotency(
            db=db,
            key_id="oh-test",
            idempotency_key="abc",
            payload_hash=compute_payload_hash({"x": 2}),
        )
    )
    assert decision.action == "conflict"
    assert decision.existing_push_log_id is not None  # caller may want to log it


def test_idempotency_decision_is_frozen_dataclass():
    """Decision should be immutable (no accidental mutation by callers)."""
    d = IdempotencyDecision(action="proceed")
    try:
        d.action = "conflict"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("IdempotencyDecision should be frozen")
