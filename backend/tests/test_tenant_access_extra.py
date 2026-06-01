"""Cross-tenant IDOR guards added in fix/security-leaks."""
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
    original = app.dependency_overrides.get(get_current_user)
    def _set(user):
        app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield _set
    finally:
        if original is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = original


@pytest.mark.asyncio
async def test_markup_create_blocks_other_customer(client, as_user):
    a, b = uuid.uuid4(), uuid.uuid4()
    as_user(_user("customer_admin", customer_id=a))
    r = await client.post("/api/markup-rules", json={
        "customer_id": str(b), "scope": "all", "markup_pct": 10,
    })
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_push_log_list_forbidden_for_customer_admin(client, as_user):
    as_user(_user("customer_admin", customer_id=uuid.uuid4()))
    r = await client.get("/api/push-log")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_push_mappings_list_blocks_other_customer(client, as_user):
    a, b = uuid.uuid4(), uuid.uuid4()
    as_user(_user("customer_admin", customer_id=a))
    r = await client.get(f"/api/push-mappings?customer_id={b}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_products_customer_filter_blocks_other_customer(client, as_user):
    a, b = uuid.uuid4(), uuid.uuid4()
    as_user(_user("customer_admin", customer_id=a))
    r = await client.get(f"/api/products?customer_id={b}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_n8n_proxy_forbidden_for_customer_admin(client, as_user):
    as_user(_user("customer_admin", customer_id=uuid.uuid4()))
    r = await client.get("/api/n8n/workflows")
    # 403 if mounted+guarded, 404 if not mounted — both acceptable (NOT 200)
    assert r.status_code in (403, 404)
