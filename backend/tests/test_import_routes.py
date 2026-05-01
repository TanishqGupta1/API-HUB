import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from modules.suppliers.models import Supplier
from database import async_session

@pytest.mark.asyncio
async def test_trigger_import_route(seed_supplier: Supplier):
    """POST /api/suppliers/{id}/import triggers an import and returns job_id."""
    async with async_session() as db:
        loaded = await db.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "PromoStandardsAdapter"
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            f"/api/suppliers/{seed_supplier.id}/import",
            json={"mode": "first_n", "limit": 5}
        )
        
    assert response.status_code == 202
    data = response.json()
    assert "sync_job_id" in data
    assert data["mode"] == "first_n"

@pytest.mark.asyncio
async def test_get_sync_job_status_route(seed_supplier: Supplier):
    """GET /api/sync_jobs/{id} returns the status of an import job."""
    from modules.sync_jobs.models import SyncJob
    import uuid
    
    async with async_session() as db:
        job = SyncJob(
            id=uuid.uuid4(),
            supplier_id=seed_supplier.id,
            supplier_name=seed_supplier.name,
            job_type="import:first_n",
            status="running"
        )
        db.add(job)
        await db.commit()
        job_id = job.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/api/sync_jobs/{job_id}")
        
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(job_id)
    assert data["status"] == "running"
