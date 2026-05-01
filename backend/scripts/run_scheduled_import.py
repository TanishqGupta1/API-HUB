import asyncio
import logging
import sys
import os

# Add backend to sys.path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from database import async_session
from modules.suppliers.models import Supplier
from modules.import_jobs.service import run_import
from modules.import_jobs.base import DiscoveryMode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
log = logging.getLogger("scheduled_import")

async def run_all_active_imports():
    async with async_session() as db:
        stmt = select(Supplier).where(Supplier.is_active == True)
        result = await db.execute(stmt)
        suppliers = result.scalars().all()
        
    log.info("Found %d active suppliers for scheduled import", len(suppliers))
    
    for s in suppliers:
        log.info("Starting import for supplier: %s (%s)", s.name, s.id)
        try:
            # We default to DELTA for scheduled imports to be efficient.
            # If never synced before, the adapter handles the fallback.
            job_id = await run_import(supplier_id=s.id, mode=DiscoveryMode.DELTA)
            log.info("Started sync job %s for %s", job_id, s.name)
        except Exception as e:
            log.error("Failed to start import for %s: %s", s.name, e)

if __name__ == "__main__":
    asyncio.run(run_all_active_imports())
