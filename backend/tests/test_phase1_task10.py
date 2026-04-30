"""TDD tests for Task 10: Multi-type fixture test."""
import pytest
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from modules.suppliers.models import Supplier
from modules.catalog.models import Product
from modules.catalog.persistence import persist_product
from modules.catalog.schemas import (
    ProductIngest, 
    ApparelDetailsIngest, 
    PrintDetailsIngest,
    VariantIngest
)


@pytest.mark.asyncio
async def test_task10_multi_type_isolation(db):
    """Verify that apparel and print products coexist and persist correctly."""
    # 1. Setup supplier
    sup_id = uuid4()
    supplier = Supplier(
        id=sup_id,
        name="Task10 Supplier",
        slug=f"t10-{uuid4().hex[:8]}",
        protocol="ops_graphql",
        is_active=True
    )
    db.add(supplier)
    await db.commit()

    # 2. Ingest Apparel
    apparel_data = ProductIngest(
        supplier_sku="T10-APP",
        product_name="Mixed Apparel",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest()
    )
    await persist_product(db, sup_id, apparel_data)

    # 3. Ingest Print
    print_data = ProductIngest(
        supplier_sku="T10-PRN",
        product_name="Mixed Print",
        product_type="print",
        print_details=PrintDetailsIngest()
    )
    await persist_product(db, sup_id, print_data)
    await db.commit()
    db.expire_all()

    # 4. Verify both exist and have correct details
    stmt = select(Product).where(Product.supplier_id == sup_id).options(
        selectinload(Product.apparel_details),
        selectinload(Product.print_details)
    )
    products = (await db.execute(stmt)).scalars().all()
    assert len(products) == 2
    
    app_prod = next(p for p in products if p.supplier_sku == "T10-APP")
    prn_prod = next(p for p in products if p.supplier_sku == "T10-PRN")
    
    assert app_prod.apparel_details is not None
    assert app_prod.print_details is None
    
    assert prn_prod.print_details is not None
    assert prn_prod.apparel_details is None
