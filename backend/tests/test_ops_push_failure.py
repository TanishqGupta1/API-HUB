import pytest
import httpx
import uuid
import os
import logging
from unittest.mock import AsyncMock, patch
from modules.ops_push.service import push_product
from modules.push_log.models import ProductPushLog
from modules.catalog.models import Product
from modules.customers.models import Customer
from modules.suppliers.models import Supplier
from sqlalchemy import select

@pytest.mark.asyncio
async def test_push_product_n8n_failure(db, monkeypatch):
    """Test that n8n webhook failure results in 'failed' status in DB and response."""
    
    # 1. Create real records in DB to satisfy FK constraints
    supplier = Supplier(
        name="Test Supplier",
        slug="test-slug-" + str(uuid.uuid4())[:8],
        protocol="promostandards",
        push_name_prefix="TEST-"
    )
    db.add(supplier)
    await db.commit()
    
    customer = Customer(
        name="Test Customer",
        ops_base_url="http://ops.test",
        ops_token_url="http://ops.test/token",
        ops_client_id="test_client",
        ops_auth_config={"client_secret": "test_secret"}
    )
    db.add(customer)
    await db.commit()
    
    product = Product(
        product_name="Test Product",
        supplier_id=supplier.id,
        supplier_sku="SKU-" + str(uuid.uuid4())[:8]
    )
    db.add(product)
    await db.commit()
    
    customer_id = customer.id
    product_id = product.id

    # 2. Mock httpx failure
    mock_response = httpx.Response(500, content=b"Internal Server Error")
    
    with patch("httpx.AsyncClient.post", side_effect=httpx.HTTPStatusError("500 Error", request=None, response=mock_response)):
        monkeypatch.setenv("N8N_PUSH_WEBHOOK_URL", "http://n8n.test")
        
        result = await push_product(db, customer_id, product_id)
        
        assert result["status"] == "failed"
        assert "n8n trigger failed" in result["message"]
        
        # Verify push_log was updated in DB
        # Refresh the session to see changes from the fresh session inside push_product
        db.expire_all()
        stmt = select(ProductPushLog).where(ProductPushLog.product_id == product_id)
        log = (await db.execute(stmt)).scalar_one_or_none()
        
        assert log is not None
        assert log.status == "failed"
        assert "500 Error" in log.error
