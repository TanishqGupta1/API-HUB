"""E2E tests for Phase 1 Polymorphic Product Model."""
import pytest
from uuid import uuid4
from decimal import Decimal


@pytest.mark.asyncio
async def test_phase1_e2e_lifecycle(client, seed_supplier, db):
    """Full lifecycle: Ingest → Get Detail."""
    sku = f"E2E-{uuid4().hex[:6]}"
    
    # 1. Ingest
    payload = [
        {
            "supplier_sku": sku,
            "product_name": "E2E Product",
            "product_type": "apparel",
            "apparel_details": {"pricing_method": "tiered_variant"},
            "variants": [
                {
                    "part_id": "v1",
                    "color": "Red",
                    "size": "L",
                    "sku": f"{sku}-R-L",
                    "base_price": 10.00,
                    "prices": [
                        {"price_type": "Net", "quantity_min": 1, "price": 10.00},
                        {"price_type": "Net", "quantity_min": 12, "price": 8.50}
                    ]
                }
            ]
        }
    ]
    
    ingest_resp = await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        json=payload,
        headers={"X-Ingest-Secret": "test-secret-do-not-use-in-prod"}
    )
    assert ingest_resp.status_code == 200
    
    # 2. Get from list to find the ID
    list_resp = await client.get(f"/api/products?supplier_id={seed_supplier.id}")
    assert list_resp.status_code == 200
    products = list_resp.json()
    product = next(p for p in products if p["supplier_sku"] == sku)
    pid = product["id"]
    
    # 3. Get Detail
    detail_resp = await client.get(f"/api/products/{pid}")
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    
    # 4. Verify everything
    assert data["apparel_details"]["pricing_method"] == "tiered_variant"
    assert len(data["variants"]) == 1
    assert len(data["variants"][0]["prices"]) == 2
    assert any(p["quantity_min"] == 12 and float(p["price"]) == 8.50 for p in data["variants"][0]["prices"])
