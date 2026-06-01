"""Alerting background checker.

Runs every CHECK_INTERVAL_SECONDS inside the FastAPI process.
Detects three real gaps and writes Notification rows:

  1. product_push_log rows where status = 'failed' and alerted = false
  2. sync_jobs rows where status = 'failed' and alerted = false
  3. scheduler_heartbeat is stale (scheduler not running)

The `alerted` flag on push_log and sync_jobs acts as an idempotency key
so the same failure never produces more than one notification even if the
checker runs multiple times before the admin dismisses it.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
import re

from sqlalchemy import select

from database import async_session
from modules.alerting.models import Notification, SchedulerHeartbeat
from modules.alerting.service import create_notification
from modules.push_log.models import ProductPushLog
from modules.sync_jobs.models import SyncJob

log = logging.getLogger("alerting.checker")

CHECK_INTERVAL_SECONDS = int(os.getenv("ALERT_CHECK_INTERVAL_SECONDS", "300"))  # 5 min

# Cap how many failed rows a single tick will turn into notifications. A large
# backlog (e.g. a supplier outage producing thousands of failures) would
# otherwise create thousands of notifications in one transaction. Oldest rows
# are handled first; the rest stay alerted=False and get picked up next tick.
MAX_ALERTS_PER_TICK = 100

_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
_TOKEN_PATTERN = re.compile(r"(token|key|secret|password|auth|bearer)[=:\s]+\S+", re.IGNORECASE)


def _sanitize_error(raw: str | None, max_len: int = 200) -> str:
    """Strip URLs and credential-like strings from error messages before
    embedding them in broadly-visible notification bodies."""
    if not raw:
        return "No error detail recorded"
    cleaned = _URL_PATTERN.sub("[url redacted]", raw)
    cleaned = _TOKEN_PATTERN.sub(r"\1=[redacted]", cleaned)
    return cleaned[:max_len]


# ---------------------------------------------------------------------------
# Gap 1 — push_log failures
# ---------------------------------------------------------------------------

async def _check_push_failures() -> None:
    async with async_session() as db:
        rows = (
            await db.execute(
                select(ProductPushLog)
                .where(
                    ProductPushLog.status == "failed",
                    ProductPushLog.alerted == False,  # noqa: E712
                )
                .order_by(ProductPushLog.pushed_at.asc())
                .limit(MAX_ALERTS_PER_TICK)
            )
        ).scalars().all()

        if not rows:
            return

        for entry in rows:
            sku = entry.supplier_sku or "unknown SKU"
            # Show only the last 8 chars of the UUID — enough to correlate
            # in logs without leaking the full customer identifier.
            cid = str(entry.customer_id)
            customer = f"…{cid[-8:]}" if entry.customer_id else "unknown"
            error_detail = _sanitize_error(entry.error)
            pushed_at = (
                entry.pushed_at.strftime("%Y-%m-%d %H:%M UTC")
                if entry.pushed_at
                else "unknown time"
            )

            await create_notification(
                db,
                type="push_failed",
                severity="error",
                title=f"Push failed — {sku}",
                body=(
                    f"Customer: {customer}\n"
                    f"Error: {error_detail}\n"
                    f"Time: {pushed_at}"
                ),
                link=f"/push-log/{entry.id}",
            )
            entry.alerted = True

        await db.commit()
        log.info("Push failure check: created %d notification(s)", len(rows))


# ---------------------------------------------------------------------------
# Gap 2 — sync_job failures
# ---------------------------------------------------------------------------

async def _check_sync_failures() -> None:
    async with async_session() as db:
        rows = (
            await db.execute(
                select(SyncJob)
                .where(
                    SyncJob.status == "failed",
                    SyncJob.alerted == False,  # noqa: E712
                )
                .order_by(SyncJob.started_at.asc())
                .limit(MAX_ALERTS_PER_TICK)
            )
        ).scalars().all()

        if not rows:
            return

        for job in rows:
            error_detail = _sanitize_error(job.error_log)
            started = (
                job.started_at.strftime("%Y-%m-%d %H:%M UTC")
                if job.started_at
                else "unknown time"
            )

            await create_notification(
                db,
                type="sync_failed",
                severity="error",
                title=f"Sync failed — {job.supplier_name} ({job.job_type})",
                body=(
                    f"Records processed: {job.records_processed}\n"
                    f"Failed: {job.failed_count}\n"
                    f"Error: {error_detail}\n"
                    f"Started: {started}"
                ),
                link="/sync",
            )
            job.alerted = True

        await db.commit()
        log.info("Sync failure check: created %d notification(s)", len(rows))


# ---------------------------------------------------------------------------
# Gap 3 — scheduler heartbeat staleness
# ---------------------------------------------------------------------------

async def _check_scheduler_heartbeat() -> None:
    async with async_session() as db:
        hb = await db.get(SchedulerHeartbeat, 1)

        if hb is None or hb.last_ran_at is None:
            # Scheduler has never run — don't alert yet (could be first boot)
            return

        # Use the persisted interval from the DB row, not the env var, so the
        # threshold stays consistent even after the env var is changed.
        interval_hours = hb.interval_hours
        stale_threshold = timedelta(hours=interval_hours * 2.5)

        age = datetime.now(timezone.utc) - hb.last_ran_at
        if age <= stale_threshold:
            return  # all good

        # Only create a new notification if there is no existing unread
        # scheduler_down alert — prevents flooding the bell with duplicates.
        existing = (
            await db.execute(
                select(Notification).where(
                    Notification.type == "scheduler_down",
                    Notification.is_read == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()

        if existing:
            return

        hours_ago = age.total_seconds() / 3600
        await create_notification(
            db,
            type="scheduler_down",
            severity="warning",
            title="Scheduler may be down",
            body=(
                f"Last successful run was {hours_ago:.1f} hour(s) ago.\n"
                f"Expected every {interval_hours} hour(s).\n"
                f"If DISABLE_SCHEDULER=true this alert can be ignored."
            ),
            link="/monitoring",
        )
        await db.commit()
        log.warning("Scheduler heartbeat stale (%.1f hours ago) — notification created", hours_ago)


# ---------------------------------------------------------------------------
# Startup check — run once immediately when the app boots
# ---------------------------------------------------------------------------

async def run_startup_check() -> None:
    """Called once from main.py lifespan after DB is ready.

    Catches cases where the scheduler was down during a previous restart
    and the stale heartbeat wouldn't be caught until the first 5-min tick.
    """
    try:
        await _check_push_failures()
        await _check_sync_failures()
        await _check_scheduler_heartbeat()
        log.info("Startup alerting check complete")
    except Exception as exc:
        log.error("Startup alerting check failed: %s", exc)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def run_checker() -> None:
    """Infinite loop — sleeps first, then checks every CHECK_INTERVAL_SECONDS."""
    log.info(
        "Alerting checker started — polling every %ds", CHECK_INTERVAL_SECONDS
    )
    while True:
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        try:
            await _check_push_failures()
            await _check_sync_failures()
            await _check_scheduler_heartbeat()
        except Exception as exc:
            log.error("Alerting checker error: %s", exc)
