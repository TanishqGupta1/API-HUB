"""Cross-tenant IDOR guard tests for require_customer_access."""
import uuid

import pytest

from main import app
from modules.auth.dependencies import get_current_user
from modules.auth.models import User


def _user(role, customer_id=None):
    u = User()
    u.id = uuid.uuid4()
    u.email = f"{role}@vg.test"
    u.hashed_password = "x"
    u.role = role
    u.customer_id = customer_id
    u.is_active = True
    return u


@pytest.fixture
def as_user():
    """Override get_current_user for one test, then restore."""
    def _set(user):
        app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield _set
    finally:
        # conftest installs a vg_admin override at import — restore it.
        from tests.conftest import _TEST_ADMIN
        app.dependency_overrides[get_current_user] = lambda: _TEST_ADMIN


@pytest.mark.asyncio
async def test_customer_admin_blocked_from_other_customer(client, as_user):
    cust_a, cust_b = uuid.uuid4(), uuid.uuid4()
    as_user(_user("customer_admin", customer_id=cust_a))
    r = await client.get(f"/api/markup-rules/{cust_b}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_customer_admin_allowed_own_customer(client, as_user):
    cust_a = uuid.uuid4()
    as_user(_user("customer_admin", customer_id=cust_a))
    r = await client.get(f"/api/markup-rules/{cust_a}")
    assert r.status_code == 200  # empty list, but authorized


@pytest.mark.asyncio
async def test_vg_admin_allowed_any_customer(client, as_user):
    as_user(_user("vg_admin"))
    r = await client.get(f"/api/markup-rules/{uuid.uuid4()}")
    assert r.status_code == 200


# ── customer_catalog (/api/customers/{customer_id}/selections) ────────────────

@pytest.mark.asyncio
async def test_customer_catalog_blocked_from_other_customer(client, as_user):
    cust_a, cust_b = uuid.uuid4(), uuid.uuid4()
    as_user(_user("customer_admin", customer_id=cust_a))
    r = await client.get(f"/api/customers/{cust_b}/selections")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_customer_catalog_allowed_own_customer(client, as_user):
    cust_a = uuid.uuid4()
    as_user(_user("customer_admin", customer_id=cust_a))
    r = await client.get(f"/api/customers/{cust_a}/selections")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_customer_catalog_vg_admin_allowed_any(client, as_user):
    as_user(_user("vg_admin"))
    r = await client.get(f"/api/customers/{uuid.uuid4()}/selections")
    assert r.status_code == 200


# ── customers detail (/api/customers/{customer_id}) ───────────────────────────

@pytest.mark.asyncio
async def test_customers_detail_blocked_from_other_customer(client, as_user):
    cust_a, cust_b = uuid.uuid4(), uuid.uuid4()
    as_user(_user("customer_admin", customer_id=cust_a))
    r = await client.get(f"/api/customers/{cust_b}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_customers_detail_allowed_own_customer(client, as_user):
    cust_a = uuid.uuid4()
    as_user(_user("customer_admin", customer_id=cust_a))
    r = await client.get(f"/api/customers/{cust_a}")
    # 404 is fine — guard passed, customer just doesn't exist in test DB
    assert r.status_code in (200, 404)


@pytest.mark.asyncio
async def test_customers_detail_vg_admin_allowed_any(client, as_user):
    as_user(_user("vg_admin"))
    r = await client.get(f"/api/customers/{uuid.uuid4()}")
    assert r.status_code in (200, 404)


# ── decorations (/api/customers/{customer_id}/products/{product_id}/decorations)

@pytest.mark.asyncio
async def test_decorations_blocked_from_other_customer(client, as_user):
    cust_a, cust_b = uuid.uuid4(), uuid.uuid4()
    as_user(_user("customer_admin", customer_id=cust_a))
    r = await client.get(f"/api/customers/{cust_b}/products/{uuid.uuid4()}/decorations")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_decorations_allowed_own_customer(client, as_user):
    cust_a = uuid.uuid4()
    as_user(_user("customer_admin", customer_id=cust_a))
    r = await client.get(f"/api/customers/{cust_a}/products/{uuid.uuid4()}/decorations")
    assert r.status_code in (200, 404)


@pytest.mark.asyncio
async def test_decorations_vg_admin_allowed_any(client, as_user):
    as_user(_user("vg_admin"))
    r = await client.get(
        f"/api/customers/{uuid.uuid4()}/products/{uuid.uuid4()}/decorations"
    )
    assert r.status_code in (200, 404)


# ── pricing (/api/customers/{customer_id}/pricing/quote) ─────────────────────

@pytest.mark.asyncio
async def test_pricing_blocked_from_other_customer(client, as_user):
    cust_a, cust_b = uuid.uuid4(), uuid.uuid4()
    as_user(_user("customer_admin", customer_id=cust_a))
    r = await client.post(
        f"/api/customers/{cust_b}/pricing/quote",
        json={"product_id": str(uuid.uuid4()), "variants": []},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_pricing_vg_admin_allowed_any(client, as_user):
    as_user(_user("vg_admin"))
    r = await client.post(
        f"/api/customers/{uuid.uuid4()}/pricing/quote",
        json={"product_id": str(uuid.uuid4()), "variants": []},
    )
    # 404/422 fine — guard passed, product just doesn't exist
    assert r.status_code in (200, 404, 422)


# ── ops_config (/api/ops-config/{customer_id}/product/{product_id}) ──────────

@pytest.mark.asyncio
async def test_ops_config_blocked_from_other_customer(client, as_user):
    cust_a, cust_b = uuid.uuid4(), uuid.uuid4()
    as_user(_user("customer_admin", customer_id=cust_a))
    r = await client.get(f"/api/ops-config/{cust_b}/product/{uuid.uuid4()}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_ops_config_allowed_own_customer(client, as_user):
    cust_a = uuid.uuid4()
    as_user(_user("customer_admin", customer_id=cust_a))
    r = await client.get(f"/api/ops-config/{cust_a}/product/{uuid.uuid4()}")
    assert r.status_code in (200, 404)


@pytest.mark.asyncio
async def test_ops_config_vg_admin_allowed_any(client, as_user):
    as_user(_user("vg_admin"))
    r = await client.get(f"/api/ops-config/{uuid.uuid4()}/product/{uuid.uuid4()}")
    assert r.status_code in (200, 404)


# ── ops_push history (/api/push/history/{customer_id}/{product_id}) ──────────

@pytest.mark.asyncio
async def test_ops_push_history_blocked_from_other_customer(client, as_user):
    cust_a, cust_b = uuid.uuid4(), uuid.uuid4()
    as_user(_user("customer_admin", customer_id=cust_a))
    r = await client.get(f"/api/push/history/{cust_b}/{uuid.uuid4()}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_ops_push_history_allowed_own_customer(client, as_user):
    cust_a = uuid.uuid4()
    as_user(_user("customer_admin", customer_id=cust_a))
    r = await client.get(f"/api/push/history/{cust_a}/{uuid.uuid4()}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_ops_push_history_vg_admin_allowed_any(client, as_user):
    as_user(_user("vg_admin"))
    r = await client.get(f"/api/push/history/{uuid.uuid4()}/{uuid.uuid4()}")
    assert r.status_code == 200
