"""Tests for P2.2 — OPS read-back / dedup helpers.

Covers the pure helpers in gateway.py without spinning up the full
execute_push pipeline:

- `_dedup_lookup_in_ops` returns the products_id when OPS reports one,
  None on every kind of failure (auth, network, non-numeric, missing).
- `_verify_post_push` is silent on match, logs a warning on mismatch,
  no-ops when the env flag is unset.
- `FakeOpsClient` ``existing_products_by_sku`` programs the dedup result.

End-to-end execute_push flow is exercised in test_e2e_inline_push and
test_sanmar_ops_smoke — adding a third E2E here would duplicate setup.
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest

from modules.ops_client.client import OpsResult
from modules.ops_client.fake import FakeOpsClient

pytestmark = [pytest.mark.no_db, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# find_product_id_by_main_sku (AI-1 — replaces the invented getProductBySku)
# ---------------------------------------------------------------------------


async def test_find_by_main_sku_returns_match_when_sku_pre_seeded():
    from modules.ops_client.mutations import find_product_id_by_main_sku

    c = FakeOpsClient(existing_products_by_sku={"PC61": 42})
    r = await find_product_id_by_main_sku(client=c, main_sku="PC61")
    assert r.ok is True
    assert r.data["products_id"] == 42


async def test_find_by_main_sku_returns_empty_when_sku_not_seeded():
    from modules.ops_client.mutations import find_product_id_by_main_sku

    c = FakeOpsClient(existing_products_by_sku={"OTHER": 99})
    r = await find_product_id_by_main_sku(client=c, main_sku="PC61")
    assert r.ok is True
    # No match → empty data; caller treats absence of products_id as 'not found'
    assert r.data == {}


async def test_find_by_main_sku_matches_correct_product_among_many():
    """Client-side scan must pick the row whose main_sku matches, not the first."""
    from modules.ops_client.mutations import find_product_id_by_main_sku

    c = FakeOpsClient(existing_products_by_sku={"AAA": 1, "PC61": 77, "ZZZ": 9})
    r = await find_product_id_by_main_sku(client=c, main_sku="PC61")
    assert r.data["products_id"] == 77


async def test_find_by_main_sku_propagates_query_error():
    """A failing page query surfaces as a non-OK result (caller logs + skips)."""
    from modules.ops_client.mutations import find_product_id_by_main_sku

    client = AsyncMock()
    client.execute = AsyncMock(return_value=OpsResult(
        ok=False, ops_error_code="AUTH_FAILED", ops_error_message="bad creds",
    ))
    r = await find_product_id_by_main_sku(client=client, main_sku="PC61")
    assert r.ok is False


# ---------------------------------------------------------------------------
# _dedup_lookup_in_ops
# ---------------------------------------------------------------------------


async def test_dedup_returns_int_when_ops_has_product():
    from modules.ops_push.gateway import _dedup_lookup_in_ops

    client = FakeOpsClient(existing_products_by_sku={"PC61": 9000})
    discovered = await _dedup_lookup_in_ops(client, "PC61")
    assert discovered == 9000


async def test_dedup_returns_none_when_ops_has_no_product():
    from modules.ops_push.gateway import _dedup_lookup_in_ops

    client = FakeOpsClient()
    discovered = await _dedup_lookup_in_ops(client, "UNKNOWN-SKU")
    assert discovered is None


async def test_dedup_swallows_query_exceptions(caplog):
    """Defensive: if the OPS query raises (e.g. transport error or
    schema-mismatch parse failure), dedup must not block the push."""
    from modules.ops_push.gateway import _dedup_lookup_in_ops

    bad_client = AsyncMock()
    bad_client.execute = AsyncMock(side_effect=RuntimeError("boom"))

    with patch(
        "modules.ops_client.mutations.find_product_id_by_main_sku",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        with caplog.at_level(logging.ERROR):
            discovered = await _dedup_lookup_in_ops(bad_client, "PC61")

    assert discovered is None
    assert any("raised" in r.message for r in caplog.records)


async def test_dedup_returns_none_on_ops_error_result(caplog):
    """OpsResult.ok=False is logged + treated as 'not found' — we
    don't want to block a push because the read-back path has an issue."""
    from modules.ops_push.gateway import _dedup_lookup_in_ops

    bad_result = OpsResult(
        ok=False, ops_error_code="AUTH_FAILED", ops_error_message="bad creds"
    )
    with patch(
        "modules.ops_client.mutations.find_product_id_by_main_sku",
        AsyncMock(return_value=bad_result),
    ):
        with caplog.at_level(logging.WARNING):
            discovered = await _dedup_lookup_in_ops(object(), "PC61")

    assert discovered is None
    assert any("not OK" in r.message for r in caplog.records)


async def test_dedup_handles_non_numeric_products_id(caplog):
    """If OPS hands back something un-int-able, log + return None."""
    from modules.ops_push.gateway import _dedup_lookup_in_ops

    weird_result = OpsResult(ok=True, data={"products_id": "not-a-number"})
    with patch(
        "modules.ops_client.mutations.find_product_id_by_main_sku",
        AsyncMock(return_value=weird_result),
    ):
        with caplog.at_level(logging.WARNING):
            discovered = await _dedup_lookup_in_ops(object(), "PC61")

    assert discovered is None
    assert any("non-numeric" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# _verify_post_push
# ---------------------------------------------------------------------------


async def test_verify_noop_when_env_flag_unset(monkeypatch, caplog):
    """OPS_POST_PUSH_VERIFY unset → function must not even query OPS."""
    from modules.ops_push.gateway import _verify_post_push

    monkeypatch.delenv("OPS_POST_PUSH_VERIFY", raising=False)

    mock_query = AsyncMock()
    with patch(
        "modules.ops_client.mutations.find_product_id_by_main_sku", mock_query
    ):
        await _verify_post_push(object(), "PC61", "12345")

    mock_query.assert_not_called()


async def test_verify_logs_match_when_ids_align(monkeypatch, caplog):
    from modules.ops_push.gateway import _verify_post_push

    monkeypatch.setenv("OPS_POST_PUSH_VERIFY", "1")

    matching = OpsResult(ok=True, data={"products_id": 12345})
    with patch(
        "modules.ops_client.mutations.find_product_id_by_main_sku",
        AsyncMock(return_value=matching),
    ):
        with caplog.at_level(logging.INFO):
            await _verify_post_push(object(), "PC61", "12345")

    assert any("confirmed" in r.message for r in caplog.records)
    assert not any("mismatch" in r.message for r in caplog.records)


async def test_verify_warns_on_id_mismatch(monkeypatch, caplog):
    from modules.ops_push.gateway import _verify_post_push

    monkeypatch.setenv("OPS_POST_PUSH_VERIFY", "1")

    drifted = OpsResult(ok=True, data={"products_id": 99999})
    with patch(
        "modules.ops_client.mutations.find_product_id_by_main_sku",
        AsyncMock(return_value=drifted),
    ):
        with caplog.at_level(logging.WARNING):
            await _verify_post_push(object(), "PC61", "12345")

    assert any(
        "mismatch" in r.message and "12345" in r.message and "99999" in r.message
        for r in caplog.records
    )


async def test_verify_warns_when_ops_returns_no_products_id(monkeypatch, caplog):
    from modules.ops_push.gateway import _verify_post_push

    monkeypatch.setenv("OPS_POST_PUSH_VERIFY", "1")

    empty = OpsResult(ok=True, data={})
    with patch(
        "modules.ops_client.mutations.find_product_id_by_main_sku",
        AsyncMock(return_value=empty),
    ):
        with caplog.at_level(logging.WARNING):
            await _verify_post_push(object(), "PC61", "12345")

    assert any("no products_id" in r.message for r in caplog.records)


async def test_verify_swallows_exceptions(monkeypatch, caplog):
    """A flaky verify must never crash a successful push."""
    from modules.ops_push.gateway import _verify_post_push

    monkeypatch.setenv("OPS_POST_PUSH_VERIFY", "1")

    with patch(
        "modules.ops_client.mutations.find_product_id_by_main_sku",
        AsyncMock(side_effect=RuntimeError("transport")),
    ):
        with caplog.at_level(logging.ERROR):
            # Must not raise
            await _verify_post_push(object(), "PC61", "12345")

    assert any("raised" in r.message for r in caplog.records)
