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
  (``1s, 5s, 25s``). The last-resort error catcher in ``run_push_task``
  is still useful — it ensures ``push_log.status='failed'`` is written
  even if a retry chain truly exhausts.
- The Redis connection settings are derived from ``REDIS_URL`` (matches
  the existing ``cache.py`` backplane) so we don't fragment config.
"""
from __future__ import annotations

import logging
import os
import uuid as uuid_mod
from typing import Any

from arq.connections import RedisSettings


log = logging.getLogger(__name__)


# ── Job function ─────────────────────────────────────────────────────────────

async def run_push_job(ctx: dict[str, Any], push_log_id: str) -> None:
    """arq job: execute one OPS push to completion.

    ``ctx`` is arq's per-job context dict; we don't need anything from
    it today, but the signature must accept it. ``push_log_id`` is
    serialized to str because arq's default Redis encoder doesn't know
    UUID. ``execute_push`` accepts either form.
    """
    # Local import: avoids a heavy module graph at worker boot when the
    # worker file is loaded for its WorkerSettings alone (e.g. tests).
    from modules.ops_push.gateway import execute_push

    log.info("arq.run_push_job start push_log=%s try=%s", push_log_id, ctx.get("job_try"))
    await execute_push(uuid_mod.UUID(push_log_id))
    log.info("arq.run_push_job done  push_log=%s", push_log_id)


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
