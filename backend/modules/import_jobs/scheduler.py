import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from database import async_session
from modules.suppliers.models import Supplier
from modules.import_jobs.service import run_import
from modules.import_jobs.base import DiscoveryMode

log = logging.getLogger("import_scheduler")

async def run_all_active_imports():
    """Logic to trigger a delta sync for all active suppliers."""
    async with async_session() as db:
        stmt = select(Supplier).where(Supplier.is_active == True)
        result = await db.execute(stmt)
        suppliers = result.scalars().all()
        
    log.info("Found %d active suppliers for scheduled import", len(suppliers))
    
    for s in suppliers:
        log.info("Starting import for supplier: %s (%s)", s.name, s.id)
        try:
            # Default to DELTA for scheduled imports
            job_id = await run_import(supplier_id=s.id, mode=DiscoveryMode.DELTA)
            log.info("Started sync job %s for %s", job_id, s.name)
        except Exception as e:
            log.error("Failed to start import for %s: %s", s.name, e)

async def start_scheduler(interval_hours: int = 24):
    """Simple background scheduler loop."""
    log.info("Starting import scheduler with %d hour interval", interval_hours)
    while True:
        try:
            log.info("Triggering scheduled imports at %s", datetime.now(timezone.utc))
            await run_all_active_imports()
        except Exception as e:
            log.error("Error in scheduler loop: %s", e)
            
        log.info("Sleeping for %d hours...", interval_hours)
        await asyncio.sleep(interval_hours * 3600)
