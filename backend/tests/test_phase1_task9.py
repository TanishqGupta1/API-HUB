"""TDD tests for Task 9: persist_product apparel path."""
import pytest
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from modules.suppliers.models import Supplier
from modules.catalog.models import Product, ApprelDetails, ProductVariant, VariantPrice
from modules.catalog.persistence import persist_product
from modules.catalog.schemas import (
    ProductIngest, 
    ApparelDetailsIngest, 
    VariantIngest, 
    VariantPriceIngest
)


@pytest.mark.asyncio
async def test_task9_persist_product_apparel(db):
    """Verify that persist_product correctly handles the apparel path."""
    # 1. Setup supplier
    sup_id = uuid4()
    supplier = Supplier(
        id=sup_id,
        name="Task9 Supplier",
        slug=f"t9-{uuid4().hex[:8]}",
        protocol="ops_graphql",
        is_active=True
    )
    db.add(supplier)
    await db.commit()

    # 2. Prepare apparel data
    ingest_data = ProductIngest(
        supplier_sku="T9-SHIRT",
        product_name="Apparel Product",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest(
            pricing_method="tiered_variant",
            raw_payload={"brand_code": " Gildan"}
        ),
        variants=[
            VariantIngest(
                part_id="V9",
                color="Black",
                size="XL",
                sku="T9-SHIRT-BLK-XL",
                base_price=Decimal("15.00"),
                prices=[
                    VariantPriceIngest(price_type="Net", quantity_min=1, price=Decimal("15.00")),
                    VariantPriceIngest(price_type="Net", quantity_min=12, price=Decimal("12.00"))
                ]
            )
        ]
    )

    # 3. Persist
    pid = await persist_product(db, sup_id, ingest_data)
    await db.commit()
    db.expire_all()

    # 4. Verify
    stmt = select(Product).where(Product.id == pid).options(
        selectinload(Product.apparel_details),
        selectinload(Product.variants).selectinload(ProductVariant.prices)
    )
    product = (await db.execute(stmt)).scalar_one()
    assert product.apparel_details.pricing_method == "tiered_variant"
    assert len(product.variants) == 1
    assert len(product.variants[0].prices) == 2

    # 5. Update (Check tiered prices update)
    ingest_data.variants[0].prices[1].price = Decimal("11.50")
    await persist_product(db, sup_id, ingest_data)
    await db.commit()
    db.expire_all()

    product = (await db.execute(stmt)).scalar_one()
    assert any(p.quantity_min == 12 and p.price == Decimal("11.50") for p in product.variants[0].prices)
    assert len(product.variants[0].prices) == 2
