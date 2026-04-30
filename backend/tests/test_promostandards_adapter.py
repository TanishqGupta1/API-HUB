"""PromoStandardsAdapter + SanMarAdapter tests.

All tests run against recorded XML fixtures — no live SOAP calls.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from modules.suppliers.models import Supplier


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_supplier_has_protocol_config(db: AsyncSession, seed_supplier: Supplier):
    """Supplier carries a JSONB protocol_config column for adapter settings."""
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.protocol_config = {
            "discovery_mode": "explicit_list",
            "explicit_list": ["PC61", "MM1000"],
            "max_products": 20,
        }
        await s.commit()
        await s.refresh(loaded)
        assert loaded.protocol_config["discovery_mode"] == "explicit_list"
        assert loaded.protocol_config["max_products"] == 20



