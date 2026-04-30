"""TDD tests for Task 13: Route eager loading."""
import pytest
from uuid import uuid4
from decimal import Decimal
from modules.catalog.persistence import persist_product
from modules.catalog.schemas import ProductIngest, ApparelDetailsIngest


@pytest.mark.asyncio
async def test_task13_product_detail_route_polymorphic(client, seed_supplier, db):
    """Verify that the product detail route returns polymorphic details correctly."""
    # 1. Persist an apparel product
    ingest_data = ProductIngest(
        supplier_sku="T13-APP",
        product_name="Route Test Apparel",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest(pricing_method="tiered_variant")
    )
    pid = await persist_product(db, seed_supplier.id, ingest_data)
    await db.commit()

    # 2. Call the GET /api/products/{id} route
    resp = await client.get(f"/api/products/{pid}")
    assert resp.status_code == 200
    data = resp.json()
    
    # 3. Verify apparel_details are present
    assert data["apparel_details"] is not None
    assert data["apparel_details"]["pricing_method"] == "tiered_variant"
    assert data["product_type"] == "apparel"
