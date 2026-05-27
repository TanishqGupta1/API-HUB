"""X-Orchestrator-Key authentication dependency for the Integration Gateway."""
import asyncio
import hashlib
import time
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session, get_db
from .models import IntegrationKey

# ── In-process rate limiter (token bucket, per key id) ───────────────────────
# Keyed by IntegrationKey.id (UUID str) → (tokens_remaining, window_start_ts)
# Bounded to _RATE_BUCKETS_MAX entries to prevent memory leak per integration key.
_RATE_BUCKETS: dict[str, tuple[int, float]] = {}
_RATE_BUCKETS_MAX = 10_000
_rate_lock = asyncio.Lock()


async def _check_rate_limit(key: IntegrationKey) -> None:
    """Raise 429 if the key has exceeded its rate_limit_per_minute.

    Uses an asyncio.Lock so concurrent coroutines don't race the dict write.
    """
    limit = key.rate_limit_per_minute
    if not limit or limit <= 0:
        return
    key_str = str(key.id)
    now = time.monotonic()
    async with _rate_lock:
        tokens, window_start = _RATE_BUCKETS.get(key_str, (limit, now))
        if now - window_start >= 60:
            # New window — reset bucket
            tokens = limit
            window_start = now
        if tokens <= 0:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "RATE_LIMITED", "message": "Request rate limit exceeded"},
            )
        _RATE_BUCKETS[key_str] = (tokens - 1, window_start)
        # Evict oldest entries when the dict grows too large
        if len(_RATE_BUCKETS) > _RATE_BUCKETS_MAX:
            oldest = min(_RATE_BUCKETS, key=lambda k: _RATE_BUCKETS[k][1])
            del _RATE_BUCKETS[oldest]


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def get_orchestrator_key(
    x_orchestrator_key: Annotated[Optional[str], Header(alias="X-Orchestrator-Key")] = None,
    db: AsyncSession = Depends(get_db),
) -> IntegrationKey:
    if not x_orchestrator_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={
            "code": "BAD_SIGNATURE", "message": "X-Orchestrator-Key header required"
        })

    key_hash = _hash_key(x_orchestrator_key)
    # Filter out synthetic admin-proxy keys at SQL level — they MUST NOT
    # be reachable via the X-Orchestrator-Key header path. The admin-proxy
    # route loads them by primary key separately.
    result = await db.execute(
        select(IntegrationKey).where(
            IntegrationKey.key_hash == key_hash,
            IntegrationKey.is_synthetic == False,  # noqa: E712 — SQL boolean
        )
    )
    key = result.scalar_one_or_none()

    if not key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={
            "code": "BAD_SIGNATURE", "message": "Invalid API key"
        })
    if key.revoked_at is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={
            "code": "KEY_REVOKED", "message": "This API key has been revoked"
        })
    if not key.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={
            "code": "KEY_REVOKED", "message": "This API key is inactive"
        })

    # Enforce per-minute rate limit
    _check_rate_limit(key)

    # Fire-and-forget last_used_at update — doesn't block the request
    # NOTE: we do NOT pass `db` here — the request-scoped session will be
    # closed by the time the task runs.  _update_last_used opens its own
    # session via async_session().
    asyncio.create_task(_update_last_used(key.id))

    return key


async def _update_last_used(key_id) -> None:
    """Update last_used_at on the integration key (background, best-effort).

    Opens its own session so it is not affected by the request session's
    lifetime (the request-scoped session is closed before this task runs).
    """
    from datetime import datetime, timezone
    try:
        async with async_session() as db:
            await db.execute(
                update(IntegrationKey)
                .where(IntegrationKey.id == key_id)
                .values(last_used_at=datetime.now(timezone.utc))
            )
            await db.commit()
    except Exception:
        pass  # Non-critical — never fail a request over this


def check_key_scope(
    key: IntegrationKey,
    customer_id: str,
    supplier_slug: str,
) -> None:
    if key.allowed_customer_ids and customer_id not in key.allowed_customer_ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={
            "code": "KEY_NOT_ALLOWED",
            "message": f"Key not authorized for customer {customer_id}"
        })
    if key.allowed_supplier_slugs and supplier_slug not in key.allowed_supplier_slugs:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={
            "code": "KEY_NOT_ALLOWED",
            "message": f"Key not authorized for supplier {supplier_slug}"
        })


OrchestratorKey = Annotated[IntegrationKey, Depends(get_orchestrator_key)]
