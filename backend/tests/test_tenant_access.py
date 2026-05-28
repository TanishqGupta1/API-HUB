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
    yield _set
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
