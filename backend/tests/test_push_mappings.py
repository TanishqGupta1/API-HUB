import os
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.auth.dependencies import get_current_user as _get_current_user
from modules.auth.models import User as _AuthUser
from modules.catalog.models import Product
from modules.customers.models import Customer
from modules.push_mappings.models import PushMapping, PushMappingOption
from database import async_session
from main import app

@pytest.mark.asyncio
async def test_upsert_mapping_creates_row(client: AsyncClient, db: AsyncSession, seed_supplier):
    # Setup: Create a customer and a product
    async with async_session() as s:
        # Use the supplier from the fixture
        sup_id = seed_supplier.id
        
        cust = Customer(
            name="Test Customer",
            ops_base_url="https://test.ops.com",
            ops_token_url="https://test.ops.com/token",
            ops_client_id="test-client",
            ops_auth_config={}
        )
        s.add(cust); await s.commit(); await s.refresh(cust)
        
        prod = Product(
            supplier_id=sup_id,
            supplier_sku="SKU-1",
            product_name="Test Product"
        )
        s.add(prod); await s.commit(); await s.refresh(prod)
        
        cust_id = cust.id
        prod_id = prod.id

    secret = os.environ["INGEST_SHARED_SECRET"]
    payload = {
        "source_system": "test",
        "source_product_id": str(prod_id),
        "source_supplier_sku": "SKU-1",
        "customer_id": str(cust_id),
        "target_ops_base_url": "https://test.ops.com",
        "target_ops_product_id": 1234,
        "options": [
            {
                "source_master_option_id": 1,
                "source_master_attribute_id": 10,
                "source_option_key": "color",
                "source_attribute_key": "Red",
                "title": "Red",
                "price": "5.00",
                "sort_order": 1
            }
        ]
    }

    r = await client.post("/api/push-mappings", headers={"X-Ingest-Secret": secret}, json=payload)
    assert r.status_code == 200
    
    # Assert
    async with async_session() as s:
        stmt = select(PushMapping).where(PushMapping.source_product_id == prod_id, PushMapping.customer_id == cust_id)
        mapping = (await s.execute(stmt)).scalar_one()
        assert mapping.target_ops_product_id == 1234
        
        stmt_opt = select(PushMappingOption).where(PushMappingOption.push_mapping_id == mapping.id)
        options = (await s.execute(stmt_opt)).scalars().all()
        assert len(options) == 1
        assert options[0].title == "Red"
        assert float(options[0].price) == 5.0

@pytest.mark.asyncio
async def test_upsert_is_idempotent_on_product_customer_conflict(client: AsyncClient, db: AsyncSession, seed_supplier):
    # Setup
    async with async_session() as s:
        sup_id = seed_supplier.id
        
        cust = Customer(
            name="Test Customer 2",
            ops_base_url="https://test2.ops.com",
            ops_token_url="https://test2.ops.com/token",
            ops_client_id="test-client-2",
            ops_auth_config={}
        )
        s.add(cust); await s.commit(); await s.refresh(cust)
        
        prod = Product(
            supplier_id=sup_id,
            supplier_sku="SKU-2",
            product_name="Test Product 2"
        )
        s.add(prod); await s.commit(); await s.refresh(prod)
        
        cust_id = cust.id
        prod_id = prod.id

    secret = os.environ["INGEST_SHARED_SECRET"]
    payload = {
        "source_system": "test",
        "source_product_id": str(prod_id),
        "customer_id": str(cust_id),
        "target_ops_base_url": "https://test.ops.com",
        "target_ops_product_id": 1234,
        "options": []
    }

    # First push
    await client.post("/api/push-mappings", headers={"X-Ingest-Secret": secret}, json=payload)
    
    # Second push with different target ID
    payload["target_ops_product_id"] = 5678
    r = await client.post("/api/push-mappings", headers={"X-Ingest-Secret": secret}, json=payload)
    assert r.status_code == 200
    
    async with async_session() as s:
        stmt = select(PushMapping).where(PushMapping.source_product_id == prod_id, PushMapping.customer_id == cust_id)
        mappings = (await s.execute(stmt)).scalars().all()
        assert len(mappings) == 1
        assert mappings[0].target_ops_product_id == 5678

@pytest.mark.asyncio
async def test_ingest_rejects_bad_secret(client: AsyncClient):
    r = await client.post("/api/push-mappings", headers={"X-Ingest-Secret": "wrong"}, json={})
    assert r.status_code == 401

@pytest.mark.asyncio
async def test_delete_marks_status(client: AsyncClient, db: AsyncSession, seed_supplier):
    async with async_session() as s:
        sup_id = seed_supplier.id
        cust = Customer(
            name="Test Customer 3",
            ops_base_url="https://test3.ops.com",
            ops_token_url="https://test3.ops.com/token",
            ops_client_id="test-client-3",
            ops_auth_config={}
        )
        s.add(cust); await s.commit(); await s.refresh(cust)
        prod = Product(
            supplier_id=sup_id,
            supplier_sku="SKU-3",
            product_name="Test Product 3"
        )
        s.add(prod); await s.commit(); await s.refresh(prod)
        
        mapping = PushMapping(
            source_system="test",
            source_product_id=prod.id,
            customer_id=cust.id,
            target_ops_base_url="https://test.com",
            target_ops_product_id=999,
            pushed_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            status="active"
        )
        s.add(mapping); await s.commit(); await s.refresh(mapping)
        mapping_id = mapping.id

    r = await client.delete(f"/api/push-mappings/{mapping_id}")
    assert r.status_code == 200

    async with async_session() as s:
        stmt = select(PushMapping).where(PushMapping.id == mapping_id)
        mapping = (await s.execute(stmt)).scalar_one()
        assert mapping.status == "deleted"


# ─── GET /api/push-mappings/{id} — verification + cross-tenant authz ─────────

def _make_user(role: str, customer_id=None) -> _AuthUser:
    return _AuthUser(
        id=uuid.uuid4(),
        email=f"{role}@test.vg",
        hashed_password="x",
        role=role,
        is_active=True,
        customer_id=customer_id,
    )


async def _seed_mapping(sup_id, ops_url: str, sku: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a Customer + Product + PushMapping; return (customer_id, mapping_id)."""
    async with async_session() as s:
        cust = Customer(
            name=f"Cust-{sku}",
            ops_base_url=ops_url,
            ops_token_url=f"{ops_url}/token",
            ops_client_id="cli",
            ops_auth_config={},
        )
        s.add(cust)
        await s.commit()
        await s.refresh(cust)

        prod = Product(supplier_id=sup_id, supplier_sku=sku, product_name=f"Prod-{sku}")
        s.add(prod)
        await s.commit()
        await s.refresh(prod)

        mapping = PushMapping(
            source_system="test",
            source_product_id=prod.id,
            customer_id=cust.id,
            target_ops_base_url=ops_url,
            target_ops_product_id=42,
            pushed_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            status="active",
        )
        s.add(mapping)
        await s.commit()
        await s.refresh(mapping)
        return cust.id, mapping.id


@pytest.mark.asyncio
async def test_get_mapping_vg_admin_sees_any_tenant(client: AsyncClient, seed_supplier):
    """vg_admin can fetch a mapping belonging to any customer."""
    _, mapping_id = await _seed_mapping(
        seed_supplier.id, "https://mock.ops", "SKU-GM-1"
    )
    r = await client.get(f"/api/push-mappings/{mapping_id}")
    assert r.status_code == 200
    data = r.json()
    assert str(data["id"]) == str(mapping_id)
    assert data["target_ops_product_id"] == 42


@pytest.mark.asyncio
async def test_get_mapping_not_found(client: AsyncClient):
    """Non-existent mapping ID returns 404."""
    r = await client.get(f"/api/push-mappings/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_mapping_customer_admin_own_tenant(client: AsyncClient, seed_supplier):
    """customer_admin with matching customer_id can read their own mapping."""
    cust_id, mapping_id = await _seed_mapping(
        seed_supplier.id, "http://ops.test", "SKU-GM-2"
    )
    customer_admin = _make_user("customer_admin", customer_id=cust_id)
    app.dependency_overrides[_get_current_user] = lambda: customer_admin
    try:
        r = await client.get(f"/api/push-mappings/{mapping_id}")
        assert r.status_code == 200
        assert r.json()["id"] == str(mapping_id)
    finally:
        from tests.conftest import _TEST_ADMIN
        app.dependency_overrides[_get_current_user] = lambda: _TEST_ADMIN


@pytest.mark.asyncio
async def test_get_mapping_customer_admin_cross_tenant_forbidden(client: AsyncClient, seed_supplier):
    """customer_admin from a different tenant gets 403 on another's mapping."""
    _, mapping_id = await _seed_mapping(
        seed_supplier.id, "https://test1.ops.com", "SKU-GM-3"
    )
    other_customer_id = uuid.uuid4()
    foreign_admin = _make_user("customer_admin", customer_id=other_customer_id)
    app.dependency_overrides[_get_current_user] = lambda: foreign_admin
    try:
        r = await client.get(f"/api/push-mappings/{mapping_id}")
        assert r.status_code == 403
    finally:
        from tests.conftest import _TEST_ADMIN
        app.dependency_overrides[_get_current_user] = lambda: _TEST_ADMIN
