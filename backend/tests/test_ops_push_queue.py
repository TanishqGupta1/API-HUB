"""Tests for the durable arq queue + DLQ contract.

Covers:
  - enqueue_push() durable path puts a job on the arq queue (Redis ZSET).
  - enqueue_push() in-process fallback uses BackgroundTasks.
  - enqueue_push() kill-switch (OPS_PUSH_DURABLE_QUEUE=0) forces in-process.
  - run_push_job() retry contract: re-raises while budget remains.
  - run_push_job() exhausted retries: writes DLQ entry + swallows.
  - DLQ list cap (ltrim) keeps the list from growing unbounded.

Uses fakeredis so the suite doesn't depend on a running Redis instance.
"""
from __future__ import annotations

import json
import os
import uuid as uuid_mod
from unittest.mock import AsyncMock, patch

import pytest

# These tests are pure unit tests against the queue/worker helpers.
# No DB tables or real network calls.
pytestmark = [pytest.mark.no_db, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# enqueue_push()
# ---------------------------------------------------------------------------


async def test_inprocess_fallback_uses_background_tasks(monkeypatch):
    """OPS_PUSH_DURABLE_QUEUE=0 forces the in-process path regardless of
    REDIS_URL; BackgroundTasks gets the push task appended."""
    monkeypatch.setenv("OPS_PUSH_DURABLE_QUEUE", "0")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    from fastapi import BackgroundTasks
    from modules.ops_push.queue import enqueue_push

    bt = BackgroundTasks()
    push_id = uuid_mod.uuid4()
    job_id = await enqueue_push(push_id, background_tasks=bt)

    assert job_id == f"inproc:{push_id}"
    assert len(bt.tasks) == 1


async def test_inprocess_fallback_raises_without_background_tasks(monkeypatch):
    """If the durable queue is disabled and no BackgroundTasks is passed,
    enqueue_push raises rather than silently dropping the job."""
    monkeypatch.setenv("OPS_PUSH_DURABLE_QUEUE", "0")
    from modules.ops_push.queue import enqueue_push

    with pytest.raises(RuntimeError, match="in-process fallback"):
        await enqueue_push(uuid_mod.uuid4())


async def test_durable_path_enqueues_to_arq(monkeypatch):
    """OPS_PUSH_DURABLE_QUEUE=1 + REDIS_URL set → enqueue_push goes through
    arq.create_pool().enqueue_job and returns the resulting job_id.
    _job_id must be passed so arq's uniqueness dedup is active (Bug 2 fix)."""
    monkeypatch.setenv("OPS_PUSH_DURABLE_QUEUE", "1")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    from modules.ops_push.queue import enqueue_push

    fake_job = AsyncMock()
    fake_job.job_id = "fake-job-id-abc123"

    fake_pool = AsyncMock()
    fake_pool.enqueue_job = AsyncMock(return_value=fake_job)
    fake_pool.aclose = AsyncMock()

    push_id = uuid_mod.uuid4()
    with patch("arq.create_pool", AsyncMock(return_value=fake_pool)):
        job_id = await enqueue_push(push_id)

    assert job_id == "fake-job-id-abc123"
    fake_pool.aclose.assert_awaited_once()
    # Verify _job_id is passed so arq's dedup guard is active
    call_kwargs = fake_pool.enqueue_job.call_args
    assert call_kwargs.kwargs.get("_job_id") == f"push:{push_id}"


async def test_durable_path_duplicate_job_returns_sentinel(monkeypatch):
    """arq returns None when a job with the same _job_id already exists
    (uniqueness guard). enqueue_push treats that as success — the prior
    job is what we want to run — and returns a 'dedup' sentinel.
    This path is now reachable because _job_id is set (Bug 2 fix)."""
    monkeypatch.setenv("OPS_PUSH_DURABLE_QUEUE", "1")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    from modules.ops_push.queue import enqueue_push

    fake_pool = AsyncMock()
    fake_pool.enqueue_job = AsyncMock(return_value=None)
    fake_pool.aclose = AsyncMock()

    push_id = uuid_mod.uuid4()
    with patch("arq.create_pool", AsyncMock(return_value=fake_pool)):
        job_id = await enqueue_push(push_id)

    assert job_id == f"arq:dedup:{push_id}"
    # Confirm _job_id was passed (this is what makes arq return None on dupe)
    call_kwargs = fake_pool.enqueue_job.call_args
    assert call_kwargs.kwargs.get("_job_id") == f"push:{push_id}"


async def test_durable_path_falls_back_in_dev_on_redis_failure(monkeypatch):
    """When ENVIRONMENT=development, a failing durable-queue path falls
    back to in-process so the dev loop keeps working. In production the
    same failure would raise."""
    monkeypatch.setenv("OPS_PUSH_DURABLE_QUEUE", "1")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("ENVIRONMENT", "development")

    from fastapi import BackgroundTasks
    from modules.ops_push.queue import enqueue_push

    with patch(
        "arq.create_pool",
        AsyncMock(side_effect=ConnectionRefusedError("no redis")),
    ):
        bt = BackgroundTasks()
        push_id = uuid_mod.uuid4()
        job_id = await enqueue_push(push_id, background_tasks=bt)

    assert job_id == f"inproc:{push_id}"
    assert len(bt.tasks) == 1


async def test_durable_path_raises_in_production_on_redis_failure(monkeypatch):
    """Production must surface a misconfigured Redis loudly so the deploy
    fails instead of silently dropping pushes."""
    monkeypatch.setenv("OPS_PUSH_DURABLE_QUEUE", "1")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("ENVIRONMENT", "production")

    from modules.ops_push.queue import enqueue_push

    with patch(
        "arq.create_pool",
        AsyncMock(side_effect=ConnectionRefusedError("no redis")),
    ):
        with pytest.raises(ConnectionRefusedError):
            await enqueue_push(uuid_mod.uuid4())


# ---------------------------------------------------------------------------
# run_push_job retry contract
# ---------------------------------------------------------------------------


async def test_run_push_job_reraises_while_retries_remain():
    """job_try < max_tries → re-raise so arq schedules another attempt."""
    from worker import run_push_job

    ctx = {"job_try": 1, "max_tries": 3, "redis": AsyncMock()}
    push_id = str(uuid_mod.uuid4())

    async def _boom(_):
        raise RuntimeError("transient")

    with patch("modules.ops_push.gateway.execute_push", _boom):
        with pytest.raises(RuntimeError, match="transient"):
            await run_push_job(ctx, push_id)


async def test_run_push_job_swallows_on_final_attempt():
    """job_try == max_tries → write DLQ entry + finalize push_log;
    do NOT re-raise (arq has nothing left to do)."""
    from worker import run_push_job, DEAD_LETTER_KEY

    redis = AsyncMock()
    redis.lpush = AsyncMock()
    redis.ltrim = AsyncMock()

    ctx = {"job_try": 3, "max_tries": 3, "redis": redis}
    push_id = str(uuid_mod.uuid4())

    async def _boom(_):
        raise RuntimeError("permanent")

    with patch("modules.ops_push.gateway.execute_push", _boom), \
         patch("worker._finalize_push_log_failed", AsyncMock()) as fin:
        # Must not raise on the final attempt
        await run_push_job(ctx, push_id)

    fin.assert_awaited_once()
    redis.lpush.assert_awaited_once()
    redis.ltrim.assert_awaited_once()

    # DLQ entry contents
    _, args, _ = (
        redis.lpush.await_args.args[0],
        redis.lpush.await_args.args,
        None,
    )
    key, entry_json = args
    assert key == DEAD_LETTER_KEY
    entry = json.loads(entry_json)
    assert entry["push_log_id"] == push_id
    assert entry["tries"] == 3
    assert entry["exc_type"] == "RuntimeError"
    assert "permanent" in entry["error"]
    assert "failed_at" in entry


async def test_run_push_job_dlq_cap_uses_ltrim():
    """The DLQ list must be ltrim'd to DEAD_LETTER_MAX_ENTRIES - 1
    so it doesn't grow unbounded across many failures."""
    from worker import run_push_job, DEAD_LETTER_MAX_ENTRIES, DEAD_LETTER_KEY

    redis = AsyncMock()
    redis.lpush = AsyncMock()
    redis.ltrim = AsyncMock()

    ctx = {"job_try": 3, "max_tries": 3, "redis": redis}
    with patch("modules.ops_push.gateway.execute_push", AsyncMock(side_effect=RuntimeError("x"))), \
         patch("worker._finalize_push_log_failed", AsyncMock()):
        await run_push_job(ctx, str(uuid_mod.uuid4()))

    redis.ltrim.assert_awaited_once_with(
        DEAD_LETTER_KEY, 0, DEAD_LETTER_MAX_ENTRIES - 1
    )


async def test_run_push_job_handles_missing_redis_on_ctx():
    """If ctx['redis'] is None we log + skip DLQ write but still
    finalize the push_log. The job must not raise."""
    from worker import run_push_job

    ctx = {"job_try": 3, "max_tries": 3, "redis": None}
    with patch("modules.ops_push.gateway.execute_push", AsyncMock(side_effect=RuntimeError("x"))), \
         patch("worker._finalize_push_log_failed", AsyncMock()) as fin:
        await run_push_job(ctx, str(uuid_mod.uuid4()))

    # push_log finalize is still called even without redis on ctx
    fin.assert_awaited_once()


async def test_run_push_job_success_path_is_silent_on_retry_state():
    """A successful execute_push completes without touching DLQ or
    push_log finalize."""
    from worker import run_push_job

    redis = AsyncMock()
    ctx = {"job_try": 1, "max_tries": 3, "redis": redis}

    async def _ok(_):
        return None

    with patch("modules.ops_push.gateway.execute_push", _ok), \
         patch("worker._finalize_push_log_failed", AsyncMock()) as fin, \
         patch("worker._write_dead_letter", AsyncMock()) as dl:
        await run_push_job(ctx, str(uuid_mod.uuid4()))

    fin.assert_not_awaited()
    dl.assert_not_awaited()


# ---------------------------------------------------------------------------
# Bug 1 — execute_push stuck-processing retry contract
# ---------------------------------------------------------------------------


async def test_execute_push_raises_on_stuck_processing_row():
    """Bug 1 fix: when execute_push finds the row in 'processing' (a prior
    attempt crashed), it must RAISE — not silently return — so arq's retry
    and DLQ contract actually engages.

    Without this fix the retry returns None, arq treats that as success,
    no further retries fire, and the row stays in 'processing' forever."""
    import uuid as _uuid
    from unittest.mock import MagicMock, AsyncMock, patch
    from modules.ops_push.gateway import execute_push
    from modules.push_log.models import ProductPushLog

    push_log_id = _uuid.uuid4()

    # Simulate a push_log already in 'processing' (prior attempt crashed).
    fake_row = MagicMock(spec=ProductPushLog)
    fake_row.id = push_log_id
    fake_row.status = "processing"

    # The atomic UPDATE finds no row (status != 'accepted') → returns nothing.
    fake_result = MagicMock()
    fake_result.fetchone.return_value = None

    fake_db = AsyncMock()
    fake_db.get = AsyncMock(return_value=fake_row)
    fake_db.execute = AsyncMock(return_value=fake_result)
    fake_db.commit = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)

    fake_session = MagicMock()
    fake_session.return_value.__aenter__ = AsyncMock(return_value=fake_db)
    fake_session.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("modules.ops_push.gateway.async_session", fake_session):
        with pytest.raises(RuntimeError, match="processing"):
            await execute_push(push_log_id)


async def test_execute_push_returns_silently_for_terminal_states():
    """Bug 1 fix: when execute_push finds the row already in a terminal state
    (pushed / failed / partial_failure / dry_run_pushed) it must return
    silently — the job already completed on a prior attempt."""
    import uuid as _uuid
    from unittest.mock import MagicMock, AsyncMock, patch
    from modules.ops_push.gateway import execute_push
    from modules.push_log.models import ProductPushLog

    for terminal_status in ("pushed", "failed", "partial_failure", "dry_run_pushed"):
        push_log_id = _uuid.uuid4()

        fake_row = MagicMock(spec=ProductPushLog)
        fake_row.id = push_log_id
        fake_row.status = terminal_status

        fake_result = MagicMock()
        fake_result.fetchone.return_value = None

        fake_db = AsyncMock()
        fake_db.get = AsyncMock(return_value=fake_row)
        fake_db.execute = AsyncMock(return_value=fake_result)
        fake_db.commit = AsyncMock()

        fake_session = MagicMock()
        fake_session.return_value.__aenter__ = AsyncMock(return_value=fake_db)
        fake_session.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("modules.ops_push.gateway.async_session", fake_session):
            # Must not raise — just return silently
            result = await execute_push(push_log_id)
            assert result is None, f"Expected None for terminal status '{terminal_status}'"
