"""arq worker — durable OPS push execution.

Replaces the in-process ``BackgroundTasks.add_task(run_push_task, ...)``
path. When an arq worker process is running, push jobs survive an API
restart: the job sits in Redis, the worker picks it up, and ``push_log``
moves to a terminal state regardless of whether the original API pod is
still alive.

Run locally with:
    cd backend && source .venv/bin/activate
    arq worker.WorkerSettings

Or via docker-compose:
    docker compose up worker

Design notes:
- One job function (``run_push_job``) wraps the existing ``execute_push``
  so we don't duplicate orchestration logic. The bounded semaphore in
  ``ops_push.task_runner`` is no longer required (arq's
  ``max_jobs`` setting handles concurrency), but ``run_push_task`` is
  preserved as a synchronous-friendly fallback for in-process callers.
- Retries: ``max_tries=3`` with arq's default exponential backoff
  (``1s, 5s, 25s``). When the retry budget exhausts, the job pushes
  a structured failure entry onto the ``arq:dead_letter:run_push_job``
  Redis list (capped at 1000 entries) AND finalizes ``push_log`` as
  ``failed`` so the row doesn't stay in ``processing`` forever.
- The Redis connection settings are derived from ``REDIS_URL`` (matches
  the existing ``cache.py`` backplane) so we don't fragment config.
"""
from __future__ import annotations

import json
import logging
import os
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

from arq.connections import RedisSettings


log = logging.getLogger(__name__)


DEAD_LETTER_KEY = "arq:dead_letter:run_push_job"
DEAD_LETTER_MAX_ENTRIES = 1000


# ── Job function ─────────────────────────────────────────────────────────────

async def run_push_job(ctx: dict[str, Any], push_log_id: str) -> None:
    """arq job: execute one OPS push to completion.

    ``ctx`` is arq's per-job context dict; carries ``job_try`` (1-based
    attempt counter) and ``redis`` (the worker's connection pool).
    ``push_log_id`` is serialized to str because arq's default Redis
    encoder doesn't know UUID. ``execute_push`` accepts either form.

    Retry contract:
    - On any exception while retry budget remains, re-raise so arq
      reschedules with exponential backoff.
    - On the final attempt's failure, write a DLQ entry + finalize the
      push_log row, then swallow so arq logs the job as failed without
      another retry chain.
    """
    # Local import: avoids a heavy module graph at worker boot when the
    # worker file is loaded for its WorkerSettings alone (e.g. tests).
    from modules.ops_push.gateway import execute_push

    job_try = ctx.get("job_try", 1)
    max_tries = ctx.get("max_tries") or WorkerSettings.max_tries

    log.info(
        "arq.run_push_job start push_log=%s try=%s/%s",
        push_log_id, job_try, max_tries,
    )
    try:
        await execute_push(uuid_mod.UUID(push_log_id))
        log.info("arq.run_push_job done push_log=%s", push_log_id)
    except Exception as exc:  # noqa: BLE001
        if job_try < max_tries:
            log.warning(
                "arq.run_push_job try=%s/%s failed for push_log=%s — will retry: %s",
                job_try, max_tries, push_log_id, exc,
            )
            raise
        # Final attempt failed — bag it for ops + finalize the DB row.
        log.error(
            "arq.run_push_job EXHAUSTED retries (try=%s/%s) push_log=%s: %s",
            job_try, max_tries, push_log_id, exc,
        )
        await _write_dead_letter(ctx.get("redis"), push_log_id, exc, job_try)
        await _finalize_push_log_failed(push_log_id, exc, job_try)
        # Swallow: we've handled the terminal state ourselves.


async def _write_dead_letter(
    redis: Any | None, push_log_id: str, exc: BaseException, tries: int
) -> None:
    """Push a structured failure entry onto the DLQ Redis list, capped at
    DEAD_LETTER_MAX_ENTRIES so it can't grow unbounded.

    ``redis`` is arq's connection (``ArqRedis`` extends redis.asyncio).
    A missing connection is logged and skipped — DLQ is best-effort
    observability, not the source of truth.
    """
    if redis is None:
        log.warning("DLQ write skipped: no redis connection on ctx")
        return
    entry = json.dumps({
        "push_log_id": push_log_id,
        "error": str(exc),
        "exc_type": type(exc).__name__,
        "tries": tries,
        "failed_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        await redis.lpush(DEAD_LETTER_KEY, entry)
        await redis.ltrim(DEAD_LETTER_KEY, 0, DEAD_LETTER_MAX_ENTRIES - 1)
    except Exception as redis_exc:  # noqa: BLE001
        log.error("DLQ write failed for push_log=%s: %s", push_log_id, redis_exc)


async def _finalize_push_log_failed(
    push_log_id: str, exc: BaseException, tries: int
) -> None:
    """Mark the push_log row as failed so it doesn't linger in
    'processing'. Mirrors the last-resort path in task_runner.py so
    behaviour matches between durable and in-process modes."""
    try:
        from database import async_session  # noqa: PLC0415 — keep module-load light
        from modules.push_log.models import ProductPushLog  # noqa: PLC0415
    except Exception:
        log.exception("DLQ finalize: imports failed (worker misconfigured?)")
        return

    try:
        async with async_session() as db:
            row = await db.get(ProductPushLog, uuid_mod.UUID(push_log_id))
            if row is None:
                log.warning("DLQ finalize: push_log %s not found", push_log_id)
                return
            if row.status in ("pushed", "failed", "partial_failure", "dry_run_pushed"):
                # Already terminal — nothing to do, but log so we can see
                # if execute_push wrote the row before re-raising.
                log.info(
                    "DLQ finalize: push_log %s already terminal (%s)",
                    push_log_id, row.status,
                )
                return
            row.status = "failed"
            row.error = f"Exhausted {tries} retries: {type(exc).__name__}: {exc}"
            row.pushed_at = datetime.now(timezone.utc)
            await db.commit()
    except Exception:  # noqa: BLE001
        log.exception("DLQ finalize: DB write failed for push_log=%s", push_log_id)


# ── WorkerSettings ───────────────────────────────────────────────────────────

def _redis_settings() -> RedisSettings:
    """Parse REDIS_URL into arq's settings object.

    Falls back to localhost:6379/0 if unset so local dev works without
    extra config; production must set REDIS_URL explicitly (lifespan
    already requires it via _PROD_REQUIRED_ENV_VARS).
    """
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    # arq ships a from_dsn helper that handles auth + db index.
    return RedisSettings.from_dsn(url)


class WorkerSettings:
    """arq WorkerSettings — point `arq` CLI at this class."""

    functions = [run_push_job]
    redis_settings = _redis_settings()

    # Concurrency: keep parity with the previous semaphore default.
    max_jobs = int(os.getenv("OPS_PUSH_CONCURRENCY", "4"))

    # Retry: 3 attempts with arq's built-in exponential backoff.
    # A truly-failed job lands in the configured dead-letter list (added
    # by P2.1.4) rather than disappearing silently.
    max_tries = 3
    job_timeout = int(os.getenv("OPS_PUSH_JOB_TIMEOUT_SECS", "300"))  # 5 min default
