import pytest
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from database import async_session
from modules.sync_jobs.models import SyncJob
from modules.import_jobs.service import create_pending_import_job, run_existing_import_job
from modules.import_jobs.base import DiscoveryMode, ProductRef
from modules.suppliers.models import Supplier

@pytest.mark.asyncio
async def test_sync_job_counts_and_status(db, seed_supplier, monkeypatch):
    """
    Test that SyncJob correctly tracks total, success, and failed counts.
    """
    # Mock adapter.discover and adapter.hydrate_product
    async def mock_discover(*args, **kwargs):
        return [
            ProductRef(supplier_sku="S1"),
            ProductRef(supplier_sku="S2"),
            ProductRef(supplier_sku="S3"),
        ]
    
    async def mock_hydrate(self, ref):
        from modules.catalog.schemas import ProductIngest, ApparelDetailsIngest
        if ref.supplier_sku == "S3":
            from modules.import_jobs.base import SupplierError
            raise SupplierError("Failed to hydrate S3")
        return ProductIngest(
            supplier_sku=ref.supplier_sku,
            product_name=f"Product {ref.supplier_sku}",
            product_type="apparel",
            apparel_details=ApparelDetailsIngest()
        )

    # We need to monkeypatch the adapter returned by get_adapter
    from modules.import_jobs.registry import get_adapter
    class MockAdapter:
        def __init__(self, *args, **kwargs): pass
        async def discover(self, *args, **kwargs): return await mock_discover()
        async def hydrate_product(self, ref): return await mock_hydrate(None, ref)
        
    monkeypatch.setattr("modules.import_jobs.service.get_adapter", lambda *args: MockAdapter())

    # 1. Create and run job
    job_id = await create_pending_import_job(supplier_id=seed_supplier.id, mode=DiscoveryMode.FULL)
    
    await run_existing_import_job(
        job_id=job_id,
        supplier_id=seed_supplier.id,
        mode=DiscoveryMode.FULL
    )
    
    # 2. Verify SyncJob fields
    async with async_session() as s:
        job = await s.get(SyncJob, job_id)
        assert job.status == "partial_success"
        assert job.total_products == 3
        assert job.success_count == 2
        assert job.failed_count == 1
        assert job.completed_at is not None
        assert len(job.errors) == 1
        assert job.errors[0]["ref"] == "S3"
        assert job.discovery_mode == "full"
