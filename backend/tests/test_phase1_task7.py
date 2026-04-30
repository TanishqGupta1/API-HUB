"""TDD tests for Task 7: persist_product basic upsert."""
import pytest
from uuid import uuid4
from sqlalchemy import select
from modules.suppliers.models import Supplier
from modules.catalog.models import Product
from modules.catalog.persistence import persist_product
from modules.catalog.schemas import ProductIngest, ApparelDetailsIngest


@pytest.mark.asyncio
async def test_task7_persist_product_basic(db):
    """Verify that persist_product correctly upserts the Product spine."""
    # 1. Setup supplier
    sup_id = uuid4()
    supplier = Supplier(
        id=sup_id,
        name="Task7 Supplier",
        slug=f"t7-{uuid4().hex[:8]}",
        protocol="ops_graphql",
        is_active=True
    )
    db.add(supplier)
    await db.commit()

    # 2. Prepare basic data
    ingest_data = ProductIngest(
        supplier_sku="T7-SKU",
        product_name="Basic Product",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest()
    )

    # 3. Persist
    pid = await persist_product(db, sup_id, ingest_data)
    await db.commit()

    # 4. Verify
    product = await db.get(Product, pid)
    assert product.supplier_sku == "T7-SKU"
    assert product.product_name == "Basic Product"

    # 5. Update
    ingest_data.product_name = "Updated Product"
    await persist_product(db, sup_id, ingest_data)
    await db.commit()
    await db.refresh(product)
    assert product.product_name == "Updated Product"
