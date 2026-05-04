import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from modules.catalog.models import Product
from modules.customers.models import Customer
from modules.suppliers.models import Supplier
from modules.decorations.models import CustomerProductDecoration
from modules.push_mappings.models import PushMapping
from modules.push_log.models import ProductPushLog
from .merge import merge_product_with_decorations

class MockOPSClient:
    """Mock OPS API Client for Phase 8 constraints."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        # Simulated remote state
        self._existing_names = set(["Essential Tee"]) # hardcoded conflict test
        
    async def check_name_exists(self, name: str) -> bool:
        return name in self._existing_names
        
    async def create_product(self, payload: dict) -> int:
        self._existing_names.add(payload["name"])
        return 99999 # Fake OPS product ID
        
    async def update_product(self, ops_id: int, payload: dict) -> bool:
        return True

async def push_product(db: AsyncSession, customer_id: uuid.UUID, product_id: uuid.UUID) -> dict:
    """
    Push a product to OPS (Create or Update).
    Handles both ready products and decorated products.
    """
    # 1. Load product + supplier
    product = (await db.execute(
        select(Product)
        .options(joinedload(Product.variants))
        .where(Product.id == product_id)
    )).unique().scalar_one_or_none()
    
    if not product:
        raise ValueError(f"Product {product_id} not found")
        
    supplier = (await db.execute(
        select(Supplier).where(Supplier.id == product.supplier_id)
    )).scalar_one_or_none()
    
    customer = (await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )).scalar_one_or_none()
    
    if not customer:
        raise ValueError(f"Customer {customer_id} not found")

    # 2. Check decorations
    decoration = (await db.execute(
        select(CustomerProductDecoration).where(
            CustomerProductDecoration.customer_id == customer_id,
            CustomerProductDecoration.product_id == product_id
        )
    )).scalar_one_or_none()
    
    dec_options = decoration.decoration_options if decoration else []
    
    # 3. Route (ready vs decorated) & merge
    # For Phase 8 we just merge using our helper
    payload = merge_product_with_decorations(product, dec_options)
    
    # 4. Handle name conflict
    ops_client = MockOPSClient("https://mock.ops.com")
    
    desired_name = payload["name"]
    name_exists = await ops_client.check_name_exists(desired_name)
    if name_exists:
        # Apply prefix
        prefix = "SM-" if (supplier.promostandards_code and supplier.promostandards_code.upper() == "SANMAR") else "VG-"
        payload["name"] = f"{prefix}{desired_name}"

    # 5. Check push_mappings for idempotency
    mapping = (await db.execute(
        select(PushMapping).where(
            PushMapping.source_product_id == product_id,
            PushMapping.customer_id == customer_id
        )
    )).scalar_one_or_none()
    
    # 6. Call OPS GraphQL (mocked)
    push_log = ProductPushLog(
        product_id=product_id,
        customer_id=customer_id,
        status="pending",
        pushed_at=datetime.now(timezone.utc)
    )
    db.add(push_log)
    
    try:
        if mapping:
            # Update existing
            await ops_client.update_product(mapping.target_ops_product_id, payload)
            push_log.ops_product_id = str(mapping.target_ops_product_id)
            push_log.status = "success"
        else:
            # Create new
            ops_product_id = await ops_client.create_product(payload)
            
            # 7. Save mapping
            new_mapping = PushMapping(
                source_system="api-hub",
                source_product_id=product_id,
                source_supplier_sku=product.supplier_sku,
                customer_id=customer_id,
                target_ops_base_url="https://mock.ops.com",
                target_ops_product_id=ops_product_id,
                pushed_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.add(new_mapping)
            
            push_log.ops_product_id = str(ops_product_id)
            push_log.status = "success"
            
        await db.commit()
        return {"status": "success", "message": "Product pushed to OPS successfully."}
        
    except Exception as e:
        push_log.status = "failed"
        push_log.error = str(e)
        await db.commit()
        return {"status": "failed", "message": str(e)}
