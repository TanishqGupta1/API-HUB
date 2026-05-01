import pytest
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from database import async_session
from modules.suppliers.models import Supplier
from modules.sync_jobs.models import SyncJob
from modules.import_jobs.service import run_import
from modules.import_jobs.base import DiscoveryMode, TransientError, ProductRef
from modules.import_jobs.registry import ADAPTERS

class FlakyAdapter:
    def __init__(self, supplier, db):
        self.supplier = supplier
        self.db = db
        self.product_type = "apparel"

    async def discover(self, mode, **kwargs):
        return [ProductRef(supplier_sku="FLAKY-SKU")]

    async def hydrate_product(self, ref):
        # Always raise TransientError to test exhaustion
        raise TransientError("Connection timeout (simulated)")

@pytest.mark.asyncio
async def test_retry_exhaustion_results_in_partial_success(seed_supplier: Supplier):
    """If all retries fail, the job should continue but be marked partial_success/failed."""
    from modules.import_jobs.service import run_import
    import modules.import_jobs.service as service_mod
    
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        
        # Monkeypatch the adapter registry
        ADAPTERS["FlakyAdapter"] = FlakyAdapter
        loaded.adapter_class = "FlakyAdapter"
        await s.commit()

        # Run import
        job_id = await run_import(
            supplier_id=loaded.id,
            mode=DiscoveryMode.EXPLICIT_LIST,
            explicit_list=["FLAKY-SKU"]
        )
        
        # Verify job status
        job = await s.get(SyncJob, job_id)
        assert job.status == "failed" # Because success_count is 0
        assert job.failed_count == 1
        assert len(job.errors) == 1
        assert job.errors[0]["phase"] == "hydrate"
        assert "Connection timeout" in job.errors[0]["msg"]
