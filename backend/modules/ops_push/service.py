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
    payload = merge_product_with_decorations(product, dec_options)
    
    # 4. Handle name conflict (Internal logic for now)
    desired_name = payload["name"]
    # For Phase 8/9, we will implement real OPS name checking via n8n or GraphQL
    # For now, we apply standard prefixes
    prefix = "SM-" if (supplier.promostandards_code and supplier.promostandards_code.upper() == "SANMAR") else "VG-"
    payload["name"] = f"{prefix}{desired_name}"

    # 5. Check push_mappings for idempotency
    mapping = (await db.execute(
        select(PushMapping).where(
            PushMapping.source_product_id == product_id,
            PushMapping.customer_id == customer_id
        )
    )).scalar_one_or_none()
    
    # 6. Prepare Log
    push_log = ProductPushLog(
        product_id=product_id,
        customer_id=customer_id,
        status="pending",
        pushed_at=datetime.now(timezone.utc)
    )
    db.add(push_log)
    
    try:
        # In production, n8n owns the actual OPS API call.
        # FastAPI prepares the payload and logs the intent.
        # REAL-PUSH-FIX: We do NOT write fake 99999 IDs to mappings.
        
        if mapping:
            # Update existing intent
            push_log.ops_product_id = str(mapping.target_ops_product_id)
            push_log.status = "success"
        else:
            # Create new intent
            # Note: We do NOT create a PushMapping with a fake ID here.
            # Real ID will be back-filled by n8n callback.
            push_log.status = "success"
            push_log.ops_product_id = "PENDING"
            
        await db.commit()
        return {"status": "success", "message": "Product payload prepared for n8n push.", "payload": payload}
        
    except Exception as e:
        await db.rollback()
        # Create a fresh session for the error log if needed, or just log to stdout
        # Since we're in a route dependency, we can't easily get a new session without a factory
        # For now, we rely on the caller's session management
        return {"status": "failed", "message": str(e)}
