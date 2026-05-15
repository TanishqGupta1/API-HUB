"""Idempotency ledger — proceed / return_existing / conflict. See spec Rev 1."""
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
    """action in {proceed, return_existing, conflict}."""

    action: str
    existing_push_log_id: Optional[UUID] = None


async def check_idempotency(
    *,
    db: AsyncSession,
    key_id: str,
    idempotency_key: str,
    payload_hash: str,
) -> IdempotencyDecision:
    """Lookup (key_id, idempotency_key) on product_push_log; classify hash match."""
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
