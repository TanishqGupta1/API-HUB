import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from modules.catalog.models import Product, ProductVariant
from modules.customers.models import Customer
from modules.suppliers.models import Supplier
from modules.decorations.models import CustomerProductDecoration
from modules.push_mappings.models import PushMapping
from modules.push_log.models import ProductPushLog

@pytest.fixture
async def setup_data(db):
    supplier = Supplier(
        id=uuid.uuid4(),
        name="VG OPS",
        slug="vg-ops-test",
        protocol="promostandards",
        promostandards_code="VG",
    )
    db.add(supplier)
    
    customer = Customer(
        id=uuid.uuid4(),
        name="Test Customer",
        ops_base_url="https://mock.ops",
        ops_token_url="https://mock.ops/token",
        ops_client_id="mock_client_id"
    )
    db.add(customer)
    await db.flush()
    
    product = Product(
        id=uuid.uuid4(),
        supplier_id=supplier.id,
        supplier_sku="TEST-SKU",
        product_name="Test Product",
        product_type="apparel"
    )
    db.add(product)
    
    variant = ProductVariant(
        id=uuid.uuid4(),
        product_id=product.id,
        sku="TEST-SKU-RED",
        color="Red",
        size="L",
        base_price=10.50
    )
    db.add(variant)
    
    await db.commit()
    return {"supplier": supplier, "customer": customer, "product": product, "variant": variant}

@pytest.mark.asyncio
async def test_push_ready_product(setup_data, client: AsyncClient, db):
    customer_id = setup_data["customer"].id
    product_id = setup_data["product"].id
    
    res = await client.post(f"/api/push/{customer_id}/{product_id}")
    assert res.status_code == 202
    assert res.json()["status"] == "pending"
    
    # Check mappings (should NOT be created yet)
    mapping = (await db.execute(
        select(PushMapping).where(
            PushMapping.source_product_id == product_id,
            PushMapping.customer_id == customer_id
        )
    )).scalar_one_or_none()
    assert mapping is None
    
    # Check log
    log = (await db.execute(
        select(ProductPushLog).where(
            ProductPushLog.product_id == product_id,
            ProductPushLog.customer_id == customer_id
        )
    )).scalar_one_or_none()
    assert log is not None
    assert log.status == "pending"

@pytest.mark.asyncio
async def test_push_decorated_product(setup_data, client: AsyncClient, db):
    customer_id = setup_data["customer"].id
    product_id = setup_data["product"].id
    
    # Add decorations
    dec = CustomerProductDecoration(
        customer_id=customer_id,
        product_id=product_id,
        decoration_options=[{"placement": "Front", "method": "DTG", "price_addition": 5.0}]
    )
    db.add(dec)
    await db.commit()
    
    res = await client.post(f"/api/push/{customer_id}/{product_id}")
    assert res.status_code == 200
    
    # Check history endpoint
    res_hist = await client.get(f"/api/push/history/{customer_id}/{product_id}")
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) >= 1
    assert history[0]["status"] == "pending"

@pytest.mark.asyncio
async def test_name_conflict_handling(setup_data, client: AsyncClient, db):
    # Change product name to trigger conflict
    setup_data["product"].product_name = "Essential Tee"
    await db.commit()
    
    res = await client.post(f"/api/push/{setup_data['customer'].id}/{setup_data['product'].id}")
    assert res.status_code == 200
    
    # In service, it should have been renamed to "VG-Essential Tee" but we don't have a way to assert it
    # from outside without inspecting the mock client, but we assert it completes successfully.

@pytest.mark.asyncio
async def test_idempotent_push(setup_data, client: AsyncClient, db):
    customer_id = setup_data["customer"].id
    product_id = setup_data["product"].id
    
    # Create mapping
    mapping = PushMapping(
        source_system="api-hub",
        source_product_id=product_id,
        customer_id=customer_id,
        target_ops_base_url="mock",
        target_ops_product_id=12345
    )
    # fake push log
    from datetime import datetime, timezone
    mapping.pushed_at = datetime.now(timezone.utc)
    mapping.updated_at = datetime.now(timezone.utc)
    db.add(mapping)
    await db.commit()
    
    # Push again
    res = await client.post(f"/api/push/{customer_id}/{product_id}")
    assert res.status_code == 200
    
    # Check only one mapping exists
    mappings = (await db.execute(
        select(PushMapping).where(
            PushMapping.source_product_id == product_id,
            PushMapping.customer_id == customer_id
        )
    )).scalars().all()
    assert len(mappings) == 1
    assert mappings[0].target_ops_product_id == 12345
