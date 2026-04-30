"""TDD tests for Task 6: ProductIngest validator."""
import pytest
from pydantic import ValidationError
from modules.catalog.schemas import ProductIngest, ApparelDetailsIngest, PrintDetailsIngest


def test_task6_product_ingest_validation():
    """Verify that ProductIngest validates details based on product_type."""
    # 1. Valid apparel
    p1 = ProductIngest(
        supplier_sku="A1",
        product_name="Shirt",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest()
    )
    assert p1.product_type == "apparel"

    # 2. Valid print
    p2 = ProductIngest(
        supplier_sku="P1",
        product_name="Banner",
        product_type="print",
        print_details=PrintDetailsIngest()
    )
    assert p2.product_type == "print"

    # 3. Invalid print (missing details and sizes)
    with pytest.raises(ValidationError) as exc:
        ProductIngest(
            supplier_sku="P2",
            product_name="Banner Fail",
            product_type="print"
        )
    assert "print_details or sizes must be provided" in str(exc.value)

    # 4. Apparel with missing details (Now auto-fills for backward compatibility)
    p3 = ProductIngest(
        supplier_sku="A2",
        product_name="Shirt Auto",
        product_type="apparel"
    )
    assert p3.apparel_details is not None
    assert p3.apparel_details.pricing_method == "tiered_variant"
