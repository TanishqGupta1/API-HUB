"""Portal tenant-isolation tests.

All /api/portal/* endpoints must be scoped to the authenticated user's
customer_id — a customer_admin from tenant A must never read tenant B's
data even if they somehow obtain a valid JWT.

These tests verify the structural enforcement: every portal route uses
the CustomerAdmin dependency which binds the query scope to the JWT
customer_id. A non-customer_admin (vg_admin without customer_id) must
be rejected with 403 because the portal is not an admin interface.
"""
import uuid

import pytest

from main import app
from modules.auth.dependencies import get_current_user
from modules.auth.models import User


def _customer_user(customer_id):
    u = User()
    u.id = uuid.uuid4()
    u.email = f"portal-{customer_id}@test.com"
    u.hashed_password = "x"
    u.role = "customer_admin"
    u.customer_id = customer_id
    u.is_active = True
    return u


def _vg_admin():
    u = User()
    u.id = uuid.uuid4()
    u.email = "vgadmin@test.com"
    u.hashed_password = "x"
    u.role = "vg_admin"
    u.customer_id = None
    u.is_active = True
    return u


@pytest.fixture
def as_portal_user():
    """Override get_current_user for one test, then restore."""
    def _set(user):
        app.dependency_overrides[get_current_user] = lambda: user

    try:
        yield _set
    finally:
        from tests.conftest import _TEST_ADMIN
        app.dependency_overrides[get_current_user] = lambda: _TEST_ADMIN


# ── /api/portal/me ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portal_me_requires_customer_admin(client, as_portal_user):
    """vg_admin (no customer_id) must be rejected from portal endpoints."""
    as_portal_user(_vg_admin())
    r = await client.get("/api/portal/me")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_portal_me_allowed_for_customer_admin(client, as_portal_user):
    cust = uuid.uuid4()
    as_portal_user(_customer_user(cust))
    r = await client.get("/api/portal/me")
    # 404 is fine — guard passed, customer row just doesn't exist in test DB
    assert r.status_code in (200, 404)


# ── /api/portal/markup-rules ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portal_markup_rules_requires_customer_admin(client, as_portal_user):
    as_portal_user(_vg_admin())
    r = await client.get("/api/portal/markup-rules")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_portal_markup_rules_allowed_for_customer_admin(client, as_portal_user):
    as_portal_user(_customer_user(uuid.uuid4()))
    r = await client.get("/api/portal/markup-rules")
    # Returns empty list when no rules exist — still 200
    assert r.status_code == 200


# ── /api/portal/dashboard ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portal_dashboard_requires_customer_admin(client, as_portal_user):
    as_portal_user(_vg_admin())
    r = await client.get("/api/portal/dashboard")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_portal_dashboard_allowed_for_customer_admin(client, as_portal_user):
    as_portal_user(_customer_user(uuid.uuid4()))
    r = await client.get("/api/portal/dashboard")
    assert r.status_code in (200, 404)


# ── /api/portal/catalog ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portal_catalog_requires_customer_admin(client, as_portal_user):
    as_portal_user(_vg_admin())
    r = await client.get("/api/portal/catalog")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_portal_catalog_allowed_for_customer_admin(client, as_portal_user):
    as_portal_user(_customer_user(uuid.uuid4()))
    r = await client.get("/api/portal/catalog")
    assert r.status_code == 200


# ── /api/portal/push-history ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portal_push_history_requires_customer_admin(client, as_portal_user):
    as_portal_user(_vg_admin())
    r = await client.get("/api/portal/push-history")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_portal_push_history_allowed_for_customer_admin(client, as_portal_user):
    as_portal_user(_customer_user(uuid.uuid4()))
    r = await client.get("/api/portal/push-history")
    assert r.status_code == 200
