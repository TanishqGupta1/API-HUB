"""Tests for ops_client transport layer (T5).

Verifies:
- OpsAuth is frozen (immutable after creation)
- OpsResult carries success and error info correctly
- OpsGraphQLClient can be constructed with an OpsAuth
"""
import pytest
from modules.ops_client.client import OpsAuth, OpsResult, OpsGraphQLClient


# ── OpsAuth tests ────────────────────────────────────────────────────────────

def test_ops_auth_is_frozen_dataclass():
    """OpsAuth should be immutable — no accidental credential overwrites."""
    auth = OpsAuth(
        base_url="https://store.test",
        token_url="https://store.test/oauth/token",
        client_id="cid",
        client_secret="csec",
    )
    # All fields should be accessible
    assert auth.base_url == "https://store.test"
    assert auth.token_url == "https://store.test/oauth/token"
    assert auth.client_id == "cid"
    assert auth.client_secret == "csec"

    # Attempting to modify a frozen dataclass should raise
    with pytest.raises(Exception):  # FrozenInstanceError
        auth.base_url = "https://hacked.test"  # type: ignore


# ── OpsResult tests ──────────────────────────────────────────────────────────

def test_ops_result_success():
    """A successful result should have ok=True and carry data."""
    r = OpsResult(ok=True, data={"setProduct": {"products_id": 123}})
    assert r.ok is True
    assert r.data["setProduct"]["products_id"] == 123
    assert r.ops_error_code is None
    assert r.ops_error_message is None


def test_ops_result_error():
    """A failed result should have ok=False and carry error details."""
    r = OpsResult(
        ok=False,
        data=None,
        ops_error_code="GRAPHQL_ERROR",
        ops_error_message="bad input",
        raw={"errors": [{"message": "bad input"}]},
    )
    assert r.ok is False
    assert r.ops_error_code == "GRAPHQL_ERROR"
    assert r.ops_error_message == "bad input"
    assert r.raw is not None


def test_ops_result_is_frozen():
    """OpsResult should be immutable — results are facts, not mutable state."""
    r = OpsResult(ok=True, data={"x": 1})
    with pytest.raises(Exception):
        r.ok = False  # type: ignore


# ── OpsGraphQLClient tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_client_constructable():
    """Client should be constructable with an OpsAuth instance."""
    auth = OpsAuth(
        base_url="https://x",
        token_url="https://x/t",
        client_id="a",
        client_secret="b",
    )
    client = OpsGraphQLClient(auth=auth)
    assert client.auth is auth


@pytest.mark.asyncio
async def test_client_has_graphql_path():
    """Client should expose the OPS GraphQL path.

    OPS serves GraphQL at /api/ (matches the n8n OnPrintShop node); the old
    /graphql path returns the storefront HTML page, not the API.
    """
    auth = OpsAuth(
        base_url="https://x",
        token_url="https://x/t",
        client_id="a",
        client_secret="b",
    )
    client = OpsGraphQLClient(auth=auth)
    assert client.GRAPHQL_PATH == "/api/"
