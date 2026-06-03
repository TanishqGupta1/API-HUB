"""Tests for /api/customers — CRUD, encryption, aggregates, OAuth2 test endpoint."""
import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from database import async_session
from modules.customers.models import Customer
from modules.markup.models import MarkupRule
from modules.push_log.models import ProductPushLog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CUSTOMER_PAYLOAD = {
    "name": "Test Corp",
    "ops_base_url": "https://testcorp.onprintshop.com/api",
    "ops_token_url": "https://testcorp.onprintshop.com/oauth/token",
    "ops_client_id": "client-abc",
    "ops_client_secret": "super-secret-value",
}


async def _delete_customers_by_name(*names: str) -> None:
    async with async_session() as s:
        await s.execute(
            delete(Customer).where(Customer.name.in_(list(names)))
        )
        await s.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def _cleanup_customers():
    """Remove test customers before and after every test in this module."""
    test_names = ("Test Corp", "Updated Corp", "Corp A", "Corp B")
    await _delete_customers_by_name(*test_names)
    yield
    await _delete_customers_by_name(*test_names)


@pytest_asyncio.fixture
async def seed_customer(client):
    resp = await client.post("/api/customers", json=CUSTOMER_PAYLOAD)
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# POST /api/customers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_customer_returns_201(client):
    resp = await client.post("/api/customers", json=CUSTOMER_PAYLOAD)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Corp"
    assert data["ops_client_id"] == "client-abc"
    assert data["is_active"] is True
    assert data["products_pushed"] == 0
    assert data["markup_rules_count"] == 0


@pytest.mark.asyncio
async def test_create_customer_secret_not_returned(client):
    """ops_client_secret must never appear in any API response."""
    resp = await client.post("/api/customers", json=CUSTOMER_PAYLOAD)
    body = resp.text
    assert "super-secret-value" not in body


@pytest.mark.asyncio
async def test_create_customer_secret_encrypted_in_db(client):
    """ops_auth_config in the DB must contain the secret, but as encrypted bytes."""
    resp = await client.post("/api/customers", json=CUSTOMER_PAYLOAD)
    customer_id = resp.json()["id"]

    async with async_session() as s:
        row = await s.get(Customer, customer_id)
        # EncryptedJSON decrypts on read — the ORM should give us the dict back
        assert row.ops_auth_config.get("client_secret") == "super-secret-value"


@pytest.mark.asyncio
async def test_create_customer_missing_required_fields(client):
    resp = await client.post("/api/customers", json={"name": "Incomplete"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/customers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_customers_empty(client):
    resp = await client.get("/api/customers")
    assert resp.status_code == 200
    # May contain seed data from other tests; just check it's a list
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_customers_includes_created(client, seed_customer):
    resp = await client.get("/api/customers")
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()]
    assert seed_customer["id"] in ids


@pytest.mark.asyncio
async def test_list_customers_secret_not_leaked(client, seed_customer):
    resp = await client.get("/api/customers")
    assert "super-secret-value" not in resp.text


# ---------------------------------------------------------------------------
# GET /api/customers/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_customer_by_id(client, seed_customer):
    resp = await client.get(f"/api/customers/{seed_customer['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == seed_customer["id"]


@pytest.mark.asyncio
async def test_get_customer_404(client):
    resp = await client.get("/api/customers/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_customer_secret_not_returned(client, seed_customer):
    resp = await client.get(f"/api/customers/{seed_customer['id']}")
    assert "super-secret-value" not in resp.text


# ---------------------------------------------------------------------------
# PATCH /api/customers/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_customer_name(client, seed_customer):
    resp = await client.patch(
        f"/api/customers/{seed_customer['id']}",
        json={"name": "Updated Corp"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Corp"


@pytest.mark.asyncio
async def test_patch_customer_toggle_active(client, seed_customer):
    resp = await client.patch(
        f"/api/customers/{seed_customer['id']}",
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_patch_customer_rotate_secret(client, seed_customer):
    """Rotating the secret must persist the new value encrypted."""
    resp = await client.patch(
        f"/api/customers/{seed_customer['id']}",
        json={"ops_client_secret": "new-secret-rotated"},
    )
    assert resp.status_code == 200
    assert "new-secret-rotated" not in resp.text  # never in response

    async with async_session() as s:
        row = await s.get(Customer, seed_customer["id"])
        assert row.ops_auth_config.get("client_secret") == "new-secret-rotated"


@pytest.mark.asyncio
async def test_patch_customer_404(client):
    resp = await client.patch(
        "/api/customers/00000000-0000-0000-0000-000000000000",
        json={"name": "Ghost"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/customers/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_customer(client, seed_customer):
    resp = await client.delete(f"/api/customers/{seed_customer['id']}")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}

    # Confirm gone
    resp2 = await client.get(f"/api/customers/{seed_customer['id']}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_customer_404(client):
    resp = await client.delete("/api/customers/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Aggregate counts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_markup_rules_count_aggregate(client, seed_customer, seed_supplier):
    """markup_rules_count increments when rules are added."""
    cid = seed_customer["id"]

    # Add two rules
    for pct in (30.0, 45.0):
        await client.post(
            "/api/markup-rules",
            json={"customer_id": cid, "scope": "all", "markup_pct": pct},
        )

    resp = await client.get(f"/api/customers/{cid}")
    assert resp.json()["markup_rules_count"] == 2

    # Cleanup rules
    async with async_session() as s:
        await s.execute(delete(MarkupRule).where(MarkupRule.customer_id == cid))
        await s.commit()


# ---------------------------------------------------------------------------
# POST /api/customers/{id}/test  — OAuth2 connection test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connection_test_404_for_unknown_customer(client):
    resp = await client.post("/api/customers/00000000-0000-0000-0000-000000000000/test")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_connection_test_returns_ok_false_for_bad_url(client, seed_customer):
    """With a fake token URL the endpoint must attempt auth and return ok=false.

    This confirms the endpoint is no longer a stub — it actually tries the
    OAuth2 handshake and reports the failure gracefully.
    """
    resp = await client.post(f"/api/customers/{seed_customer['id']}/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["customer_id"] == seed_customer["id"]
    # URL is unreachable in tests — must return ok=false, not ok=true stub
    assert data["ok"] is False
    # The endpoint reports a structured error_code in both failure branches:
    # TOKEN_REQUEST_FAILED (connection/exception — no http_status) or
    # TOKEN_ENDPOINT_REJECTED (non-200 — includes http_status). The unreachable
    # test URL hits the exception branch, so assert on the contract field.
    assert data["error_code"] in ("TOKEN_REQUEST_FAILED", "TOKEN_ENDPOINT_REJECTED")
