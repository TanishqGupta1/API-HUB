"""Idempotency ledger for the Integration Gateway.

Resolves three branches when a push request arrives with `Idempotency-Key`:

  proceed         — first time we've seen this (key_id, idempotency_key);
                    the caller goes on to insert a new push_log row.
  return_existing — same key + same canonical payload_hash → safe retry.
                    The caller returns the existing push_log_id's state.
  conflict        — same key + DIFFERENT payload_hash → 409 IDEMPOTENCY_CONFLICT.
                    The orchestrator is reusing a key incorrectly.

The (key_id, idempotency_key) pair lives directly on `product_push_log`
(columns added in M0). No separate ledger table.

Hash algorithm: reuses `compute_payload_hash` from
`modules.ops_push.payload_builder` — RFC 8785 JCS rules per spec Rev 1
§"Idempotency semantics (locked)". Single source of truth across the
codebase prevents the same payload getting two different hashes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.ops_push.payload_builder import compute_payload_hash  # re-exported
from modules.push_log.models import ProductPushLog

__all__ = [
    "IdempotencyDecision",
    "check_idempotency",
    "compute_payload_hash",
]


@dataclass(frozen=True)
class IdempotencyDecision:
    """What the gateway should do with a push request.

    `action` ∈ {"proceed", "return_existing", "conflict"}.
    `existing_push_log_id` is populated for the latter two so the caller
    can either echo back the existing state (return_existing) or include
    it in the 409 error body for ops visibility (conflict).
    """

    action: str
    existing_push_log_id: Optional[UUID] = None


async def check_idempotency(
    *,
    db: AsyncSession,
    key_id: str,
    idempotency_key: str,
    payload_hash: str,
) -> IdempotencyDecision:
    """Look up the most recent push_log row for `(key_id, idempotency_key)`.

    No row found      → IdempotencyDecision(action="proceed")
    Found, hash match → IdempotencyDecision(action="return_existing", id=row.id)
    Found, hash diff  → IdempotencyDecision(action="conflict",        id=row.id)

    Note: the M0 migration enforces a unique index on
    (key_id, idempotency_key) WHERE both are non-null, so there should
    only ever be one row. We `LIMIT 1` defensively in case a future
    migration relaxes that constraint.
    """
    stmt = (
        select(ProductPushLog)
        .where(
            ProductPushLog.key_id == key_id,
            ProductPushLog.idempotency_key == idempotency_key,
        )
        .order_by(ProductPushLog.pushed_at.desc())
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()

    if row is None:
        return IdempotencyDecision(action="proceed")
    if row.payload_hash == payload_hash:
        return IdempotencyDecision(
            action="return_existing", existing_push_log_id=row.id
        )
    return IdempotencyDecision(action="conflict", existing_push_log_id=row.id)
