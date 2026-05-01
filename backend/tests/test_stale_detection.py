import pytest
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select
from database import async_session
from modules.catalog.models import Product, CustomerProductSelection
from modules.catalog.persistence import persist_product
from modules.catalog.schemas import ProductIngest, ApparelDetailsIngest
from modules.import_jobs.service import _finalize_job, run_existing_import_job
from modules.import_jobs.base import DiscoveryMode
from modules.sync_jobs.models import SyncJob
from modules.suppliers.models import Supplier

@pytest.mark.asyncio
async def test_stale_detection_after_import(db, seed_supplier):
    """
    Test that products are marked as 'stale' if updated after being pushed to a customer.
    """
    async with async_session() as s:
        # 1. Create a product and a selection marked as 'pushed'
        payload = ProductIngest(
            supplier_sku="STALE-TEST-1",
            product_name="Initial Name",
            product_type="apparel",
            apparel_details=ApparelDetailsIngest()
        )
        product_id = await persist_product(s, seed_supplier.id, payload)
        
        customer_id = uuid.uuid4()
        from modules.customers.models import Customer
        from tests.conftest import TEST_CUSTOMER_OPS_URLS
        customer = Customer(
            id=customer_id, 
            name="Test Customer", 
            ops_base_url=TEST_CUSTOMER_OPS_URLS[0], 
            ops_token_url=TEST_CUSTOMER_OPS_URLS[0], 
            ops_client_id="abc"
        )
        s.add(customer)
        await s.flush() # Ensure customer exists for FK
        
        # Pushed yesterday
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        selection = CustomerProductSelection(
            customer_id=customer_id,
            product_id=product_id,
            status="pushed",
            pushed_at=yesterday
        )
        s.add(selection)
        await s.commit()

    # 2. Run a "sync" that updates this product
    async with async_session() as s:
        # Create a job
        job = SyncJob(
            supplier_id=seed_supplier.id,
            supplier_name=seed_supplier.name,
            job_type="import:delta",
            status="running",
            started_at=datetime.now(timezone.utc)
        )
        s.add(job)
        await s.commit()
        await s.refresh(job)
        
        # Update product name via persist_product (this sets last_synced to 'now')
        payload.product_name = "Updated Name"
        await persist_product(s, seed_supplier.id, payload)
        await s.commit()
        
        # 3. Finalize the job (this should trigger stale detection)
        # We need to refresh supplier to pass it to _finalize_job
        supplier = await s.get(Supplier, seed_supplier.id)
        await _finalize_job(
            s, job, status="success", success_count=1, supplier=supplier, mode=DiscoveryMode.DELTA
        )
        await s.commit()

    # 4. Verify selection is now 'stale'
    async with async_session() as s:
        stmt = select(CustomerProductSelection).where(CustomerProductSelection.product_id == product_id)
        res = await s.execute(stmt)
        updated_selection = res.scalar_one()
        
        assert updated_selection.status == "stale"
        log_msg = f"Product {product_id} was updated, selection status is now {updated_selection.status}"
        print(log_msg)
