"""TDD tests for Task 11: ingest refactor."""
import pytest
from uuid import uuid4
from modules.catalog.models import Product
from sqlalchemy import select


@pytest.mark.asyncio
async def test_task11_ingest_endpoint_refactor(client, seed_supplier, db):
    """Verify that the ingest endpoint correctly persists products using the new logic."""
    payload = [
        {
            "supplier_sku": "T11-API",
            "product_name": "API Product",
            "brand": "API Brand",
            "category": "API Cat",
            "product_type": "apparel",
            "description": "API Desc",
            "apparel_details": {"pricing_method": "tiered_variant"},
            "variants": [
                {
                    "part_id": "v11",
                    "color": "White",
                    "size": "S",
                    "sku": "T11-API-WHT-S",
                    "base_price": 10.00
                }
            ]
        }
    ]
    
    # 1. Call endpoint
    resp = await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        json=payload,
        headers={"X-Ingest-Secret": "test-secret-do-not-use-in-prod"}
    )
    assert resp.status_code == 200
    
    # 2. Verify in DB
    stmt = select(Product).where(Product.supplier_sku == "T11-API")
    product = (await db.execute(stmt)).scalar_one()
    assert product.product_name == "API Product"
