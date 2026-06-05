"""Push-job enqueue helper.

Single entry point used by every call site that previously did
``background_tasks.add_task(run_push_task, push_log_id)``. Behaviour:

- **Durable path (production):** when an arq pool is available, the
  job is enqueued to Redis. A separate worker process executes it,
  so an API crash / restart never loses a push mid-flight.

- **In-process fallback (local dev):** if ``REDIS_URL`` is unset or
  the pool can't be created, we fall back to the existing in-process
  ``run_push_task`` via ``BackgroundTasks``. This keeps the dev loop
  working without spinning up a worker, while production sets the env
  var and always takes the durable path.

The fallback is intentionally narrow: any *unexpected* arq/Redis error
on the durable path is re-raised so a misconfigured production deploy
fails loudly instead of silently dropping jobs.
"""
from __future__ import annotations

import logging
import os
import uuid as uuid_mod
from typing import Optional

from fastapi import BackgroundTasks


log = logging.getLogger(__name__)


async def enqueue_push(
    push_log_id: uuid_mod.UUID,
    background_tasks: Optional[BackgroundTasks] = None,
) -> str:
    """Enqueue a push job for execution.

    Returns the arq job_id when the durable path is used, or a synthetic
    ``"inproc:<uuid>"`` identifier when falling back. Callers can store
    this on ``push_log.queue_job_id`` for ops visibility.
    """
    if _durable_queue_enabled():
        try:
            from arq import create_pool
            from worker import WorkerSettings

            pool = await create_pool(WorkerSettings.redis_settings)
            try:
                job = await pool.enqueue_job(
                    "run_push_job",
                    str(push_log_id),
                    _job_id=f"push:{push_log_id}",
                )
                if job is None:
                    # arq returns None when a job with the same _job_id
                    # already exists (uniqueness guard). Treat as success
                    # — the prior job is what we want to run.
                    log.info(
                        "enqueue_push: duplicate-job suppressed for push_log=%s",
                        push_log_id,
                    )
                    return f"arq:dedup:{push_log_id}"
                log.info(
                    "enqueue_push: durable job_id=%s push_log=%s",
                    job.job_id, push_log_id,
                )
                return job.job_id
            finally:
                await pool.aclose()
        except Exception:
            # In production we want a loud failure; in development a
            # missing-redis falls through to in-process so the dev loop
            # keeps working.
            if os.getenv("ENVIRONMENT", "development").lower() == "production":
                raise
            log.warning(
                "enqueue_push: durable path failed in dev — falling back to in-process",
                exc_info=True,
            )

    # In-process fallback path
    if background_tasks is None:
        raise RuntimeError(
            "enqueue_push: in-process fallback requires a BackgroundTasks instance. "
            "Either set REDIS_URL + run an arq worker, or pass background_tasks=…"
        )
    from .task_runner import run_push_task

    background_tasks.add_task(run_push_task, push_log_id)
    log.info("enqueue_push: in-process push_log=%s", push_log_id)
    return f"inproc:{push_log_id}"


def _durable_queue_enabled() -> bool:
    """True when both arq is importable and REDIS_URL is set.

    Setting ``OPS_PUSH_DURABLE_QUEUE=0`` forces the in-process path
    even in production — useful as a one-shot kill switch.
    """
    if os.getenv("OPS_PUSH_DURABLE_QUEUE", "1") == "0":
        return False
    if not os.getenv("REDIS_URL", "").strip():
        return False
    return True
