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
# FakeOpsClient `products` dedup scan
# ---------------------------------------------------------------------------


async def test_fake_client_products_returns_seeded_catalog():
    c = FakeOpsClient(existing_products_by_sku={"PC61": 42})
    r = await c.execute(
        "query products ($limit: Int, $offset: Int) { products (limit: $limit, offset: $offset) { products { product_id main_sku external_ref } totalProducts currentCount } }",
        variables={"limit": 200, "offset": 0},
    )
    assert r.ok is True
    block = r.data["products"]
    assert block["totalProducts"] == 1
    row = block["products"][0]
    assert row["product_id"] == 42
    assert row["external_ref"] == "PC61"
    assert row["main_sku"] == "PC61"


async def test_fake_client_products_empty_when_not_seeded():
    c = FakeOpsClient()  # no existing_products_by_sku
    r = await c.execute(
        "query products ($limit: Int, $offset: Int) { products (limit: $limit, offset: $offset) { products { product_id } totalProducts } }",
        variables={"limit": 200, "offset": 0},
    )
    assert r.ok is True
    assert r.data["products"]["products"] == []
    assert r.data["products"]["totalProducts"] == 0


async def test_fake_client_products_paginates():
    """offset/limit are honored so the dedup scan's pagination is exercised."""
    c = FakeOpsClient(existing_products_by_sku={"A": 1, "B": 2, "C": 3})
    page1 = await c.execute("query products{x}", variables={"limit": 2, "offset": 0})
    page2 = await c.execute("query products{x}", variables={"limit": 2, "offset": 2})
    assert len(page1.data["products"]["products"]) == 2
    assert len(page2.data["products"]["products"]) == 1
    assert page1.data["products"]["totalProducts"] == 3


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


async def test_get_product_by_sku_paginates_to_find_match():
    """Target on a later page is still found — proves the scan pages through
    the catalog (page_size=1 forces one product per page)."""
    from modules.ops_client import mutations as _m

    client = FakeOpsClient(existing_products_by_sku={"A": 1, "B": 2, "PC61": 9000})
    result = await _m.get_product_by_sku(client=client, products_sku="PC61", page_size=1)
    assert result.ok is True
    assert result.data["products_id"] == 9000


async def test_get_product_by_sku_returns_empty_when_absent():
    from modules.ops_client import mutations as _m

    client = FakeOpsClient(existing_products_by_sku={"A": 1, "B": 2})
    result = await _m.get_product_by_sku(client=client, products_sku="MISSING", page_size=1)
    assert result.ok is True
    assert result.data == {}


async def test_dedup_swallows_query_exceptions(caplog):
    """Defensive: if the OPS query raises (e.g. transport error or
    schema-mismatch parse failure), dedup must not block the push."""
    from modules.ops_push.gateway import _dedup_lookup_in_ops

    bad_client = AsyncMock()
    bad_client.execute = AsyncMock(side_effect=RuntimeError("boom"))

    with patch(
        "modules.ops_client.mutations.get_product_by_sku",
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
        "modules.ops_client.mutations.get_product_by_sku",
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
        "modules.ops_client.mutations.get_product_by_sku",
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
        "modules.ops_client.mutations.get_product_by_sku", mock_query
    ):
        await _verify_post_push(object(), "PC61", "12345")

    mock_query.assert_not_called()


async def test_verify_logs_match_when_ids_align(monkeypatch, caplog):
    from modules.ops_push.gateway import _verify_post_push

    monkeypatch.setenv("OPS_POST_PUSH_VERIFY", "1")

    matching = OpsResult(ok=True, data={"products_id": 12345})
    with patch(
        "modules.ops_client.mutations.get_product_by_sku",
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
        "modules.ops_client.mutations.get_product_by_sku",
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
        "modules.ops_client.mutations.get_product_by_sku",
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
        "modules.ops_client.mutations.get_product_by_sku",
        AsyncMock(side_effect=RuntimeError("transport")),
    ):
        with caplog.at_level(logging.ERROR):
            # Must not raise
            await _verify_post_push(object(), "PC61", "12345")

    assert any("raised" in r.message for r in caplog.records)
