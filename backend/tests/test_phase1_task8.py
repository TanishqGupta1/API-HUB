"""TDD tests for Task 8: persist_product print path."""
import pytest
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from modules.suppliers.models import Supplier
from modules.catalog.models import Product, PrintDetails, ProductSize
from modules.catalog.persistence import persist_product
from modules.catalog.schemas import ProductIngest, PrintDetailsIngest, ProductSizeIngest


@pytest.mark.asyncio
async def test_task8_persist_product_print(db):
    """Verify that persist_product correctly handles the print path."""
    # 1. Setup supplier
    sup_id = uuid4()
    supplier = Supplier(
        id=sup_id,
        name="Task8 Supplier",
        slug=f"t8-{uuid4().hex[:8]}",
        protocol="ops_graphql",
        is_active=True
    )
    db.add(supplier)
    await db.commit()

    # 2. Prepare print data
    ingest_data = ProductIngest(
        supplier_sku="T8-PRINT",
        product_name="Print Product",
        product_type="print",
        print_details=PrintDetailsIngest(
            pricing_method="formula",
            min_width=Decimal("12.00"),
            max_width=Decimal("24.00")
        ),
        sizes=[
            ProductSizeIngest(width=Decimal("12.00"), height=Decimal("18.00"), label="Small Poster")
        ]
    )

    # 3. Persist
    pid = await persist_product(db, sup_id, ingest_data)
    await db.commit()
    db.expire_all()

    # 4. Verify
    stmt = select(Product).where(Product.id == pid).options(
        selectinload(Product.print_details),
        selectinload(Product.sizes)
    )
    product = (await db.execute(stmt)).scalar_one()
    assert product.print_details.min_width == Decimal("12.00")
    assert len(product.sizes) == 1
    assert product.sizes[0].label == "Small Poster"

    # 5. Update sizes (Check delete-and-reinsert logic)
    ingest_data.sizes = [
        ProductSizeIngest(width=Decimal("24.00"), height=Decimal("36.00"), label="Large Poster")
    ]
    await persist_product(db, sup_id, ingest_data)
    await db.commit()
    db.expire_all()

    product = (await db.execute(stmt)).scalar_one()
    assert len(product.sizes) == 1
    assert product.sizes[0].label == "Large Poster"
