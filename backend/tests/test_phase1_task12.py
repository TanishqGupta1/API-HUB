"""TDD tests for Task 12: ProductRead schema update."""
import pytest
from decimal import Decimal
from datetime import datetime
from uuid import uuid4
from modules.catalog.schemas import (
    ProductRead, 
    ApparelDetailsRead, 
    PrintDetailsRead,
    ProductSizeRead
)


def test_task12_product_read_schema():
    """Verify that ProductRead schema supports new polymorphic fields."""
    # 1. Apparel Read
    app = ApparelDetailsRead(pricing_method="tiered_variant")
    
    # 2. Print Read
    prn = PrintDetailsRead(pricing_method="formula", min_width=Decimal("10.0"))
    
    # 3. Product Size Read
    size = ProductSizeRead(width=Decimal("10.0"), height=Decimal("10.0"), unit="in", label="S")
    
    # 4. Main Product Read
    p = ProductRead(
        id=uuid4(),
        supplier_id=uuid4(),
        supplier_sku="S1",
        product_name="P1",
        product_type="apparel",
        last_synced=datetime.now(),
        apparel_details=app,
        sizes=[size]
    )
    assert p.apparel_details.pricing_method == "tiered_variant"
    assert len(p.sizes) == 1
