"""T18: 4 auxiliary gateway endpoints under /api/integrations/v1/.

- POST /master-options/ingest      → snapshot upsert
- POST /push-mappings              → OPS↔hub ID map upsert
- POST /customers/{id}/ops/connection-test → real auth probe
- GET  /suppliers/{slug}/schema    → JSON Schema for ProductIngest
"""
from __future__ import annotations

import hashlib
import secrets
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from database import async_session
from modules.customers.models import Customer
from modules.integrations.models import IntegrationKey
from modules.master_options.models import MasterOption
from modules.push_mappings.models import PushMapping


@pytest_asyncio.fixture
async def integration_key():
    raw = secrets.token_urlsafe(24)
    key_id = f"t18-key-{uuid4().hex[:8]}"
    async with async_session() as s:
        k = IntegrationKey(
            id=key_id,
            key_hash=hashlib.sha256(raw.encode()).hexdigest(),
            name="T18 test key",
        )
        s.add(k)
        await s.commit()
        await s.refresh(k)
        s.expunge(k)
    try:
        yield {"key": k, "raw": raw}
    finally:
        async with async_session() as s:
            await s.execute(delete(IntegrationKey).where(IntegrationKey.id == key_id))
            await s.commit()


@pytest_asyncio.fixture
async def t18_customer():
    async with async_session() as s:
        c = Customer(
            name="T18 Customer",
            ops_base_url="https://t18.ops.com",
            ops_token_url="https://t18.ops.com/oauth/token",
            ops_client_id="t18-client",
            ops_auth_config={"client_secret": "t18-secret"},
            is_active=True,
        )
        s.add(c)
        await s.commit()
        await s.refresh(c)
        s.expunge(c)
    try:
        yield c
    finally:
        async with async_session() as s:
            await s.execute(delete(Customer).where(Customer.id == c.id))
            await s.commit()


# ---------------------------------------------------------------------------
# 1. Master Options Ingest
# ---------------------------------------------------------------------------

def _mo_item(ops_id: int, title: str = "Imprint Method") -> dict:
    return {
        "ops_master_option_id": ops_id,
        "title": title,
        "option_key": "imprint_method",
        "options_type": "radio",
        "status": 1,
        "sort_order": 0,
        "attributes": [
            {"ops_attribute_id": 9001, "title": "Screen Print", "sort_order": 0},
            {"ops_attribute_id": 9002, "title": "Embroidery", "sort_order": 1},
        ],
    }


@pytest.mark.asyncio
async def test_master_options_ingest_requires_key(client):
    resp = await client.post(
        "/api/integrations/v1/master-options/ingest", json=[_mo_item(80001)]
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_master_options_ingest_persists_snapshot(client, integration_key):
    item = _mo_item(80002, "Tee Style")
    resp = await client.post(
        "/api/integrations/v1/master-options/ingest",
        json=[item],
        headers={"X-Orchestrator-Key": integration_key["raw"]},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["records_processed"] == 1

    async with async_session() as s:
        rows = (
            await s.execute(
                select(MasterOption).where(MasterOption.ops_master_option_id == 80002)
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].title == "Tee Style"

        # Cleanup so re-running the suite stays clean
        await s.execute(
            delete(MasterOption).where(MasterOption.ops_master_option_id == 80002)
        )
        await s.commit()


# ---------------------------------------------------------------------------
# 2. Push Mappings Upsert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_push_mappings_upsert_requires_key(client, t18_customer):
    resp = await client.post(
        "/api/integrations/v1/push-mappings",
        json={
            "source_system": "vg-hub",
            "source_product_id": str(uuid4()),
            "customer_id": str(t18_customer.id),
            "target_ops_base_url": "https://t18.ops.com",
            "target_ops_product_id": 12345,
            "options": [],
        },
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_push_mappings_upsert_persists(
    client, t18_customer, seed_supplier, integration_key
):
    # A push_mapping needs a real source_product — seed one.
    from modules.catalog.models import Product
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async with async_session() as s:
        pid = (
            await s.execute(
                pg_insert(Product)
                .values(
                    supplier_id=seed_supplier.id,
                    supplier_sku="T18-PM-1",
                    product_name="T18 Mapping Product",
                    product_type="apparel",
                )
                .on_conflict_do_nothing()
                .returning(Product.id)
            )
        ).scalar_one()
        await s.commit()

    resp = await client.post(
        "/api/integrations/v1/push-mappings",
        json={
            "source_system": "vg-hub",
            "source_product_id": str(pid),
            "source_supplier_sku": "T18-PM-1",
            "customer_id": str(t18_customer.id),
            "target_ops_base_url": "https://t18.ops.com",
            "target_ops_product_id": 54321,
            "options": [],
        },
        headers={"X-Orchestrator-Key": integration_key["raw"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["id"]

    async with async_session() as s:
        m = (
            await s.execute(
                select(PushMapping).where(PushMapping.customer_id == t18_customer.id)
            )
        ).scalar_one_or_none()
        assert m is not None
        assert m.target_ops_product_id == 54321


# ---------------------------------------------------------------------------
# 3. OPS Connection Test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connection_test_requires_key(client, t18_customer):
    resp = await client.post(
        f"/api/integrations/v1/customers/{t18_customer.id}/ops/connection-test"
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_connection_test_404_unknown_customer(client, integration_key):
    resp = await client.post(
        f"/api/integrations/v1/customers/{uuid4()}/ops/connection-test",
        headers={"X-Orchestrator-Key": integration_key["raw"]},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_connection_test_succeeds_with_valid_creds(
    client, t18_customer, integration_key
):
    """OAuth token fetch + GraphQL ping both succeed → ok: True."""
    with patch(
        "modules.integrations.routes._fetch_oauth_token",
        new=AsyncMock(return_value="mock-access-token"),
    ), patch(
        "modules.integrations.routes._ops_graphql_ping",
        new=AsyncMock(return_value=True),
    ):
        resp = await client.post(
            f"/api/integrations/v1/customers/{t18_customer.id}/ops/connection-test",
            headers={"X-Orchestrator-Key": integration_key["raw"]},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert "connected" in body.get("message", "").lower()


@pytest.mark.asyncio
async def test_connection_test_fails_on_bad_oauth(
    client, t18_customer, integration_key
):
    with patch(
        "modules.integrations.routes._fetch_oauth_token",
        new=AsyncMock(side_effect=Exception("invalid_client")),
    ):
        resp = await client.post(
            f"/api/integrations/v1/customers/{t18_customer.id}/ops/connection-test",
            headers={"X-Orchestrator-Key": integration_key["raw"]},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is False
    assert "auth" in body["error"].lower() or "invalid_client" in body["error"]


@pytest.mark.asyncio
async def test_connection_test_fails_on_graphql_error(
    client, t18_customer, integration_key
):
    with patch(
        "modules.integrations.routes._fetch_oauth_token",
        new=AsyncMock(return_value="mock-access-token"),
    ), patch(
        "modules.integrations.routes._ops_graphql_ping",
        new=AsyncMock(side_effect=Exception("schema introspection failed")),
    ):
        resp = await client.post(
            f"/api/integrations/v1/customers/{t18_customer.id}/ops/connection-test",
            headers={"X-Orchestrator-Key": integration_key["raw"]},
        )
    body = resp.json()
    assert body["ok"] is False
    assert "graphql" in body["error"].lower() or "introspection" in body["error"]


# ---------------------------------------------------------------------------
# 4. Supplier Schema
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_supplier_schema_requires_key(client, seed_supplier):
    resp = await client.get(f"/api/integrations/v1/suppliers/{seed_supplier.slug}/schema")
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_supplier_schema_returns_json_schema_for_product_ingest(
    client, seed_supplier, integration_key
):
    """Spec says: return JSON Schema for ProductIngest. The response should
    contain the strict schema plus the existing required/optional hint dict."""
    resp = await client.get(
        f"/api/integrations/v1/suppliers/{seed_supplier.slug}/schema",
        headers={"X-Orchestrator-Key": integration_key["raw"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["supplier_slug"] == seed_supplier.slug
    assert "json_schema" in body
    schema = body["json_schema"]
    assert schema["type"] == "object"
    # Pydantic's emitted JSON Schema uses 'title' and 'properties' for class shape
    assert "supplier_sku" in schema["properties"]
    assert "supplier_sku" in schema.get("required", [])
    # Existing summary fields preserved
    assert "supplier_sku" in body["required"]
    assert "variants" in body["required"]
