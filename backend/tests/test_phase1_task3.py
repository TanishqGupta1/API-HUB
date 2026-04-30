"""TDD tests for Task 3: Supplier model updates."""
import pytest
from modules.suppliers.models import Supplier


@pytest.mark.asyncio
async def test_task3_supplier_columns(db):
    """Verify that Supplier has adapter_class and sync timestamp columns."""
    cols = {c.name for c in Supplier.__table__.columns}
    assert "adapter_class" in cols
    assert "last_full_sync" in cols
    assert "last_delta_sync" in cols
