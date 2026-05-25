"""Bounded async task runner for OPS push jobs.

Wraps ``execute_push`` with:
- A semaphore that caps concurrent executions (default 4, override via
  ``OPS_PUSH_CONCURRENCY`` env var) so a burst of push requests doesn't
  exhaust the DB connection pool.
- Unhandled-exception capture: if ``execute_push`` raises unexpectedly the
  push_log is moved to ``failed`` with the error stored rather than silently
  disappearing.
- Structured logging per execution so failures are traceable.

Usage (in routes — replaces ``background_tasks.add_task(execute_push, id)``):
    background_tasks.add_task(run_push_task, push_log_id)
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid as uuid_mod
from datetime import datetime, timezone

from database import async_session
from modules.push_log.models import ProductPushLog

log = logging.getLogger(__name__)

_MAX_CONCURRENT = int(os.getenv("OPS_PUSH_CONCURRENCY", "4"))
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """Lazily create the semaphore inside the running event loop."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
    return _semaphore


async def run_push_task(push_log_id: uuid_mod.UUID) -> None:
    """Bounded, fault-tolerant wrapper around execute_push.

    Always completes without raising — unhandled exceptions are caught and
    written back to the push_log row as ``failed`` status.
    """
    from .gateway import execute_push  # local import to avoid circular deps

    sem = _get_semaphore()
    log.info("push_task queued  push_log=%s  (semaphore slots=%s/%s)",
             push_log_id, _MAX_CONCURRENT - sem._value, _MAX_CONCURRENT)

    async with sem:
        log.info("push_task started push_log=%s", push_log_id)
        try:
            await execute_push(push_log_id)
            log.info("push_task done    push_log=%s", push_log_id)
        except Exception as exc:  # noqa: BLE001
            log.exception("push_task UNHANDLED EXCEPTION for push_log=%s: %s", push_log_id, exc)
            # Last-resort: mark the push_log as failed so it doesn't stay stuck
            # in 'processing' forever.
            try:
                async with async_session() as db:
                    push_log = await db.get(ProductPushLog, push_log_id)
                    if push_log and push_log.status not in (
                        "pushed", "failed", "partial_failure", "dry_run_pushed"
                    ):
                        push_log.status = "failed"
                        push_log.error = f"Unhandled exception: {exc}"
                        push_log.pushed_at = datetime.now(timezone.utc)
                        await db.commit()
            except Exception as db_exc:  # noqa: BLE001
                log.error(
                    "push_task: could not mark push_log=%s as failed: %s",
                    push_log_id, db_exc,
                )
