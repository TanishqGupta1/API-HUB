import pytest
import uuid
from decimal import Decimal
from sqlalchemy import select
from modules.catalog.models import Product
from modules.suppliers.models import Supplier
from modules.import_jobs.service import run_import
from modules.import_jobs.base import DiscoveryMode, ProductRef
from modules.sync_jobs.models import SyncJob
from database import async_session

@pytest.mark.asyncio
async def test_run_import_orchestration_success(seed_supplier: Supplier):
    """run_import correctly coordinates discovery, hydration, and persistence."""
    async with async_session() as db:
        # Setup supplier
        loaded = await db.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "PromoStandardsAdapter"
        loaded.auth_config = {"id": "test", "password": "test"}
        await db.commit()
        await db.refresh(loaded)

        # Mock the adapter via monkeypatching the service's get_adapter
        import modules.import_jobs.service as service_mod
        from modules.import_jobs.base import BaseAdapter
        from modules.catalog.schemas import ProductIngest

        
        class MockAdapter(BaseAdapter):
            product_type = "apparel"
            async def discover(self, mode, limit=None, explicit_list=None):
                return [ProductRef(supplier_sku="SKU1")]
            async def hydrate_product(self, ref):
                return ProductIngest(
                    supplier_sku=ref.supplier_sku,
                    product_name="Test Product",
                    product_type="apparel",
                    variants=[]
                )
            async def discover_changed(self, since): return []
            async def discover_closeouts(self): return []

        original_get = service_mod.get_adapter
        service_mod.get_adapter = lambda sup, db: MockAdapter(sup, db)

        try:
            job_id = await run_import(
                supplier_id=loaded.id,
                mode=DiscoveryMode.FIRST_N,
                limit=1
            )

            # Verify job record
            job = await db.get(SyncJob, job_id)
            assert job.status == "success"
            assert job.records_processed == 1

            # Verify product persistence
            res = await db.execute(select(Product).where(Product.supplier_sku == "SKU1"))
            product = res.scalar_one_or_none()
            assert product is not None
            assert product.product_name == "Test Product"

        finally:
            service_mod.get_adapter = original_get
