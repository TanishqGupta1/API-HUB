"""TDD tests for Task 2: VariantPrice and ProductSize."""
import pytest
from sqlalchemy import select
from modules.catalog.models import VariantPrice, ProductSize


@pytest.mark.asyncio
async def test_task2_models_structure(db):
    """Verify that VariantPrice and ProductSize have the correct columns."""
    # Check VariantPrice
    vprice_cols = {c.name for c in VariantPrice.__table__.columns}
    assert "variant_id" in vprice_cols
    assert "price_type" in vprice_cols
    assert "quantity_min" in vprice_cols
    assert "quantity_max" in vprice_cols
    assert "price" in vprice_cols

    # Check ProductSize
    psize_cols = {c.name for c in ProductSize.__table__.columns}
    assert "product_id" in psize_cols
    assert "width" in psize_cols
    assert "height" in psize_cols
    assert "unit" in psize_cols
    assert "label" in psize_cols
