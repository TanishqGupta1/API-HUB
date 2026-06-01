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
INVENTORY_SYNC_INTERVAL_MINUTES = int(os.getenv("INVENTORY_SYNC_INTERVAL_MINUTES", "15"))


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


async def run_all_inventory_syncs():
    """Trigger an inventory-only sync for all active suppliers that support it."""
    async with async_session() as db:
        stmt = select(Supplier).where(
            Supplier.is_active == True,
            Supplier.adapter_class != None,
        )
        result = await db.execute(stmt)
        suppliers = result.scalars().all()

    log.info("Inventory sync: found %d active suppliers", len(suppliers))
    for s in suppliers:
        try:
            job_id = await run_import(supplier_id=s.id, mode=DiscoveryMode.INVENTORY_ONLY)
            log.info("Inventory sync job %s started for %s", job_id, s.name)
        except Exception as e:
            log.error("Inventory sync failed for %s: %s", s.name, e)


async def start_inventory_scheduler(interval_minutes: int = INVENTORY_SYNC_INTERVAL_MINUTES):
    """Background loop running inventory-only syncs every N minutes.

    Sleeps first (same pattern as start_scheduler) so a restart doesn't
    immediately hammer every supplier's inventory endpoint.
    Disabled by DISABLE_SCHEDULER=true (same flag as the main scheduler).
    Override interval with INVENTORY_SYNC_INTERVAL_MINUTES env var (default 15).
    """
    if os.getenv("DISABLE_SCHEDULER", "").lower() in ("1", "true", "yes"):
        log.info("Inventory scheduler disabled via DISABLE_SCHEDULER env var.")
        return

    log.info(
        "Inventory scheduler ready — first run in %d minute(s). "
        "Override interval with INVENTORY_SYNC_INTERVAL_MINUTES env var.",
        interval_minutes,
    )
    while True:
        await asyncio.sleep(interval_minutes * 60)
        try:
            log.info("Triggering inventory syncs at %s", datetime.now(timezone.utc))
            await run_all_inventory_syncs()
        except Exception as e:
            log.error("Error in inventory scheduler loop: %s", e)


_SCHEDULER_LOCK_KEY = "scheduler:running"


async def _try_acquire_scheduler_lock(interval_hours: int) -> bool:
    """Acquire a Redis distributed lock for the scheduler run.

    Returns True if this instance should run (lock acquired or Redis
    unavailable — fallback to always-run, which is the pre-Redis behaviour).
    Returns False if another instance already holds the lock.
    """
    from cache import get_redis
    redis = get_redis()
    if redis is None:
        return True  # No Redis — single-instance behaviour, always run

    acquired = await redis.set(
        _SCHEDULER_LOCK_KEY,
        "1",
        nx=True,
        ex=int(interval_hours * 3600 * 0.9),  # 90% of interval so lock expires before next tick
    )
    return bool(acquired)


async def _release_scheduler_lock() -> None:
    """Release the distributed lock after the run completes."""
    from cache import get_redis
    redis = get_redis()
    if redis is not None:
        await redis.delete(_SCHEDULER_LOCK_KEY)


async def start_scheduler(interval_hours: int = SCHEDULER_INTERVAL_HOURS):
    """Background scheduler loop.

    Sleeps FIRST to avoid triggering a bulk sync on every app restart.
    Respects the DISABLE_SCHEDULER env var — set to 'true' if n8n cron
    workflows are managing syncs instead.

    Writes a heartbeat to scheduler_heartbeat after each successful cycle
    so the alerting checker can detect whether the scheduler has stopped.
    When Redis is available, uses a distributed lock so only ONE instance
    runs the scheduled import in a multi-instance (ECS) deployment.
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
            if not await _try_acquire_scheduler_lock(interval_hours):
                log.info("Scheduler: another instance holds the lock — skipping this cycle.")
                continue
            try:
                log.info("Triggering scheduled imports at %s", datetime.now(timezone.utc))
                await run_all_active_imports()
                await _write_heartbeat(interval_hours)
            finally:
                await _release_scheduler_lock()
        except Exception as e:
            log.error("Error in scheduler loop: %s", e)
