import asyncio
import logging
from datetime import datetime, timezone
from scripts.run_scheduled_import import run_all_active_imports

log = logging.getLogger("import_scheduler")

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

if __name__ == "__main__":
    # For standalone testing
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_scheduler(interval_hours=1))
