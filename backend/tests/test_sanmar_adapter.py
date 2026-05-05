"""SanMarAdapter override tests."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from modules.suppliers.models import Supplier
from modules.promostandards.sanmar_adapter import SanMarAdapter
from modules.import_jobs.base import DiscoveryMode

FIXTURES_DIR = Path(__file__).parent / "fixtures"

@pytest.mark.asyncio
async def test_sanmar_adapter_wsdl_resolution(db: AsyncSession, seed_supplier: Supplier):
    """SanMarAdapter uses its own WSDL resolution logic (Hardcoded/Constants)."""
    from database import async_session
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.promostandards_code = "SANMAR"
        await s.commit()
        await s.refresh(loaded)
        
        adapter = SanMarAdapter(supplier=loaded, db=s)
        # Should return SanMar specific WSDLs
        assert "sanmar.com" in adapter._wsdl_for("PRODUCT")
        assert "sanmar.com" in adapter._wsdl_for("MEDIA")
