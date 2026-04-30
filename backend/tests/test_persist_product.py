"""TDD tests for Phase 1 polymorphic models and persistence service."""
import pytest
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from modules.catalog.models import (
    Product, 
    ApprelDetails, 
    PrintDetails, 
    VariantPrice, 
    ProductSize,
    ProductVariant
)
from modules.suppliers.models import Supplier
from modules.catalog.persistence import persist_product
from modules.catalog.schemas import (
    ProductIngest, 
    VariantIngest, 
    ApparelDetailsIngest, 
    VariantPriceIngest
)


@pytest.mark.asyncio
async def test_persist_product_apparel_end_to_end(db):
    """Verify that persist_product correctly upserts an apparel product with tiered prices."""
    # 1. Setup supplier
    sup_id = uuid4()
    supplier = Supplier(
        id=sup_id,
        name="Test Supplier",
        slug=f"test-{uuid4().hex[:8]}",
        protocol="ops_graphql",
        is_active=True
    )
    db.add(supplier)
    await db.commit()

    # 2. Prepare ingest data
    ingest_data = ProductIngest(
        supplier_sku="TS-001",
        product_name="Test T-Shirt",
        brand="Brand X",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest(
            pricing_method="tiered_variant",
            raw_payload={"meta": "data"}
        ),
        variants=[
            VariantIngest(
                part_id="V1",
                color="Red",
                size="L",
                sku="TS-001-RED-L",
                base_price=Decimal("10.00"),
                prices=[
                    VariantPriceIngest(price_type="Net", quantity_min=1, price=Decimal("10.00")),
                    VariantPriceIngest(price_type="Net", quantity_min=12, price=Decimal("8.00")),
                ]
            )
        ]
    )

    # 3. First persist
    pid = await persist_product(db, sup_id, ingest_data)
    await db.commit()
    db.expire_all() 

    # 4. Verify
    stmt = (
        select(Product)
        .where(Product.id == pid)
        .options(selectinload(Product.apparel_details))
    )
    product = (await db.execute(stmt)).scalar_one()
    assert product.product_name == "Test T-Shirt"
    assert product.apparel_details.pricing_method == "tiered_variant"
    
    v_stmt = (
        select(ProductVariant)
        .where(ProductVariant.product_id == pid)
        .options(selectinload(ProductVariant.prices))
    )
    variant = (await db.execute(v_stmt)).scalar_one()
    assert len(variant.prices) == 2
    assert any(p.quantity_min == 12 and p.price == Decimal("8.00") for p in variant.prices)

    # 5. Update (Idempotency check)
    ingest_data.product_name = "Updated T-Shirt"
    ingest_data.variants[0].prices[1].price = Decimal("7.50")
    
    await persist_product(db, sup_id, ingest_data)
    await db.commit()
    db.expire_all() 

    # 6. Verify update
    product = (await db.execute(stmt)).scalar_one()
    assert product.product_name == "Updated T-Shirt"
    
    variant = (await db.execute(v_stmt)).scalar_one()
    assert any(p.quantity_min == 12 and p.price == Decimal("7.50") for p in variant.prices)
    assert len(variant.prices) == 2


@pytest.mark.asyncio
async def test_polymorphic_models_metadata_check(db):
    """Verify table structure for all new models."""
    apparel_cols = {c.name for c in ApprelDetails.__table__.columns}
    assert "product_id" in apparel_cols
    
    print_cols = {c.name for c in PrintDetails.__table__.columns}
    assert "product_id" in print_cols
    
    vprice_cols = {c.name for c in VariantPrice.__table__.columns}
    assert "variant_id" in vprice_cols
    
    psize_cols = {c.name for c in ProductSize.__table__.columns}
    assert "product_id" in psize_cols
