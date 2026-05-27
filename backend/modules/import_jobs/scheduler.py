"""Background import scheduler.

NOTE: PR #71 shipped n8n cron workflows (inventory-sync-hourly.json,
pricing-sync-daily.json, catalog-sync-weekly.json) that cover the same
job. If those n8n workflows are active, disable this scheduler to avoid
duplicate jobs by setting DISABLE_SCHEDULER=true in your environment.

The scheduler sleeps FIRST before running to avoid a bulk DELTA sync on
every app restart, which would hammer suppliers unnecessarily.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from database import async_session
from modules.suppliers.models import Supplier
from modules.import_jobs.service import run_import
from modules.import_jobs.base import DiscoveryMode

log = logging.getLogger("import_scheduler")

# Gap 4 fix: read interval from env so it can be tuned without a redeploy.
# Defaults to 1 hour. Override with SCHEDULER_INTERVAL_HOURS in .env.
SCHEDULER_INTERVAL_HOURS = int(os.getenv("SCHEDULER_INTERVAL_HOURS", "1"))


async def _write_heartbeat(interval_hours: int) -> None:
    """Upsert a single-row heartbeat so the alerting checker can detect
    whether the scheduler has stopped running."""
    try:
        from modules.alerting.models import SchedulerHeartbeat
        now = datetime.now(timezone.utc)
        async with async_session() as db:
            stmt = (
                pg_insert(SchedulerHeartbeat)
                .values(id=1, last_ran_at=now, interval_hours=interval_hours, updated_at=now)
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={"last_ran_at": now, "interval_hours": interval_hours, "updated_at": now},
                )
            )
            await db.execute(stmt)
            await db.commit()
        log.debug("Scheduler heartbeat written at %s", now.isoformat())
    except Exception as exc:
        # Heartbeat failure must never kill the scheduler loop
        log.warning("Failed to write scheduler heartbeat: %s", exc)


async def run_all_active_imports():
    """Trigger a delta sync for all active suppliers that have an adapter configured."""
    async with async_session() as db:
        stmt = select(Supplier).where(
            Supplier.is_active == True,
            Supplier.adapter_class != None,
        )
        result = await db.execute(stmt)
        suppliers = result.scalars().all()

    log.info("Found %d active suppliers for scheduled import", len(suppliers))

    for s in suppliers:
        log.info("Starting import for supplier: %s (%s)", s.name, s.id)
        try:
            job_id = await run_import(supplier_id=s.id, mode=DiscoveryMode.DELTA)
            log.info("Started sync job %s for %s", job_id, s.name)
        except Exception as e:
            log.error("Failed to start import for %s: %s", s.name, e)


async def start_scheduler(interval_hours: int = SCHEDULER_INTERVAL_HOURS):
    """Background scheduler loop.

    Sleeps FIRST to avoid triggering a bulk sync on every app restart.
    Respects the DISABLE_SCHEDULER env var — set to 'true' if n8n cron
    workflows are managing syncs instead.

    Writes a heartbeat to scheduler_heartbeat after each successful cycle
    so the alerting checker can detect whether the scheduler has stopped.
    """
    if os.getenv("DISABLE_SCHEDULER", "").lower() in ("1", "true", "yes"):
        log.info("Import scheduler disabled via DISABLE_SCHEDULER env var (n8n handles cron).")
        return

    log.info(
        "Import scheduler ready — first run in %d hour(s) (sleeping to avoid restart storms). "
        "Override interval with SCHEDULER_INTERVAL_HOURS env var.",
        interval_hours,
    )
    while True:
        # Sleep FIRST — prevents bulk DELTA on every restart
        await asyncio.sleep(interval_hours * 3600)
        try:
            log.info("Triggering scheduled imports at %s", datetime.now(timezone.utc))
            # Write heartbeat at cycle START so a long-running sync doesn't
            # trigger a false "scheduler may be down" alert before it finishes.
            await _write_heartbeat(interval_hours)
            await run_all_active_imports()
        except Exception as e:
            log.error("Error in scheduler loop: %s", e)
