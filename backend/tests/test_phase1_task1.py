"""TDD tests for Task 1: ApparelDetails and PrintDetails."""
import pytest
from sqlalchemy import select
from modules.catalog.models import ApprelDetails, PrintDetails


@pytest.mark.asyncio
async def test_task1_models_structure(db):
    """Verify that ApparelDetails and PrintDetails have the correct columns."""
    # Check ApparelDetails
    apparel_cols = {c.name for c in ApprelDetails.__table__.columns}
    assert "product_id" in apparel_cols
    assert "pricing_method" in apparel_cols
    assert "raw_payload" in apparel_cols

    # Check PrintDetails
    print_cols = {c.name for c in PrintDetails.__table__.columns}
    assert "product_id" in print_cols
    assert "pricing_method" in print_cols
    assert "min_width" in print_cols
    assert "max_width" in print_cols
    assert "min_height" in print_cols
    assert "max_height" in print_cols
    assert "size_unit" in print_cols
    assert "base_price_per_sq_unit" in print_cols
    assert "raw_payload" in print_cols
