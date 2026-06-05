"""Smoke-test DLQ behaviour for run_push_job.

Calls run_push_job directly with a forged ctx where job_try == max_tries
(simulating the final retry attempt). Patches execute_push to raise.
Asserts the DLQ list grew by 1 and the entry matches.

Run from backend/ with the venv active:
    python scripts/test_dlq_smoke.py
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid as uuid_mod
from unittest.mock import patch

os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from arq import create_pool  # noqa: E402
from worker import (  # noqa: E402
    WorkerSettings,
    run_push_job,
    DEAD_LETTER_KEY,
)


async def main() -> int:
    pool = await create_pool(WorkerSettings.redis_settings)
    fake_push_log_id = str(uuid_mod.uuid4())

    before = await pool.llen(DEAD_LETTER_KEY)
    print(f"DLQ before: {before}")

    async def _always_fail(_id):
        raise RuntimeError(f"smoke: simulated failure for {_id}")

    # Forge a ctx that simulates arq's final retry attempt (job_try == max_tries).
    # The redis connection on ctx is what run_push_job writes the DLQ entry to.
    ctx = {
        "job_try": WorkerSettings.max_tries,
        "max_tries": WorkerSettings.max_tries,
        "redis": pool,
    }

    # Mute the push_log DB finalize — we don't have a real row in this smoke.
    with patch("modules.ops_push.gateway.execute_push", _always_fail), \
         patch("worker._finalize_push_log_failed") as _fin:
        _fin.return_value = None
        # run_push_job should swallow the exception on the final attempt
        # and write to DLQ. If it re-raises, that's a contract bug.
        await run_push_job(ctx, fake_push_log_id)

    after = await pool.llen(DEAD_LETTER_KEY)
    print(f"DLQ after:  {after}")

    if after != before + 1:
        print(f"FAIL — expected DLQ to grow by 1; grew by {after - before}")
        await pool.aclose()
        return 1

    entry = json.loads(await pool.lindex(DEAD_LETTER_KEY, 0))
    print(f"DLQ entry:  {entry}")
    if (
        entry["push_log_id"] == fake_push_log_id
        and entry["tries"] == WorkerSettings.max_tries
        and entry["exc_type"] == "RuntimeError"
        and "simulated failure" in entry["error"]
    ):
        print("OK — DLQ entry matches the simulated final-attempt failure.")
        # Clean up: remove the test entry so we don't pollute the queue.
        await pool.lpop(DEAD_LETTER_KEY)
        await pool.aclose()
        return 0

    print("FAIL — DLQ entry contents don't match.")
    await pool.aclose()
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
