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
from database import async_session
from modules.suppliers.models import Supplier
from modules.import_jobs.service import run_import
from modules.import_jobs.base import DiscoveryMode

log = logging.getLogger("import_scheduler")


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

    # SET NX EX: only set if key doesn't exist, expire after the run window.
    # This means at most one instance runs per interval_hours window.
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


async def start_scheduler(interval_hours: int = 24):
    """Background scheduler loop.

    Sleeps FIRST to avoid triggering a bulk sync on every app restart.
    Respects the DISABLE_SCHEDULER env var — set to 'true' if n8n cron
    workflows are managing syncs instead.

    When Redis is available, uses a distributed lock so only ONE instance
    runs the scheduled import in a multi-instance (ECS) deployment.
    """
    if os.getenv("DISABLE_SCHEDULER", "").lower() in ("1", "true", "yes"):
        log.info("Import scheduler disabled via DISABLE_SCHEDULER env var (n8n handles cron).")
        return

    log.info(
        "Import scheduler ready — first run in %d hours (sleeping to avoid restart storms).",
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
            finally:
                await _release_scheduler_lock()
        except Exception as e:
            log.error("Error in scheduler loop: %s", e)
