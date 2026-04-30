"""TDD tests for Task 5: Pydantic ingest schemas."""
import pytest
from decimal import Decimal
from modules.catalog.schemas import (
    PrintDetailsIngest, 
    ApparelDetailsIngest, 
    VariantPriceIngest, 
    ProductSizeIngest,
    ProductIngest,
    VariantIngest
)


def test_task5_ingest_schemas_exist():
    """Verify that all required ingest schemas are defined."""
    # Apparel
    apparel = ApparelDetailsIngest(pricing_method="tiered_variant")
    assert apparel.pricing_method == "tiered_variant"

    # Print
    print_det = PrintDetailsIngest(min_width=Decimal("10.0"), min_height=Decimal("10.0"))
    assert print_det.min_width == Decimal("10.0")

    # Variant Price
    vprice = VariantPriceIngest(price_type="Net", quantity_min=1, price=Decimal("15.00"))
    assert vprice.price == Decimal("15.00")

    # Product Size
    psize = ProductSizeIngest(width=Decimal("5.0"), height=Decimal("5.0"), label="Small")
    assert psize.width == Decimal("5.0")

    # Check nesting in VariantIngest
    v = VariantIngest(part_id="V1", prices=[vprice])
    assert len(v.prices) == 1

    # Check nesting in ProductIngest
    p = ProductIngest(
        supplier_sku="S1", 
        product_name="P1", 
        apparel_details=apparel,
        sizes=[psize]
    )
    assert p.apparel_details.pricing_method == "tiered_variant"
    assert len(p.sizes) == 1
