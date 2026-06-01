"""X-Orchestrator-Key authentication dependency for the Integration Gateway."""
import asyncio
import hashlib
import logging
import time
import uuid
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session, get_db
from .models import IntegrationKey

log = logging.getLogger("integrations.auth")

# ── Rate limiter ─────────────────────────────────────────────────────────────
# When Redis is available (REDIS_URL set) → sliding-window via sorted sets,
# shared across all server instances.
# When Redis is unavailable → in-process token-bucket fallback (single instance
# only; breaks under horizontal scale but keeps dev/staging working without Redis).

# In-process fallback state
_RATE_BUCKETS: dict[str, tuple[int, float]] = {}
_RATE_BUCKETS_MAX = 10_000
_rate_lock = asyncio.Lock()

# Strong refs to in-flight fire-and-forget tasks so the event loop doesn't
# GC them mid-run (asyncio holds only weak refs to tasks).
_BACKGROUND_TASKS: set[asyncio.Task] = set()


async def _check_rate_limit_redis(key_str: str, limit: int) -> bool:
    """Sliding-window rate check via Redis sorted sets.

    Returns True if the request is allowed, False if rate-limited.

    Accept-then-record semantics: we trim the window and count FIRST, and
    only record (ZADD) this request when it is under the limit. Rejected
    (429'd) requests are NOT written to the set, so they don't inflate the
    window and starve subsequent requests.

    The sorted-set MEMBER is unique per request (now + uuid) while the SCORE
    stays equal to ``now``. Using the timestamp alone as the member caused
    same-microsecond/concurrent requests to collide on one member, which made
    ZCARD undercount and silently leaked the limit.

    Raises on any Redis error — the caller (_check_rate_limit) catches it and
    fails open to the in-process bucket.
    """
    from cache import get_redis
    redis = get_redis()
    if redis is None:
        return True  # Redis unavailable — defer to in-process fallback

    rkey = f"rl:{key_str}"
    now = time.time()
    window_start = now - 60.0

    # Step 1 — trim expired entries and read the current window count.
    trim_pipe = redis.pipeline()
    trim_pipe.zremrangebyscore(rkey, "-inf", window_start)  # drop old entries
    trim_pipe.zcard(rkey)                                    # count in window
    trim_pipe.expire(rkey, 65)                               # TTL slightly > window
    trim_results = await trim_pipe.execute()
    count: int = trim_results[1]

    # Step 2 — reject without recording when already at/over the limit.
    if count >= limit:
        return False

    # Step 3 — under the limit: record this request with a unique member so
    # concurrent same-instant requests can't collide on a single member.
    member = f"{now:.6f}:{uuid.uuid4().hex}"
    add_pipe = redis.pipeline()
    add_pipe.zadd(rkey, {member: now})
    add_pipe.expire(rkey, 65)
    await add_pipe.execute()
    return True


async def _check_rate_limit(key: IntegrationKey) -> None:
    """Raise 429 if the key has exceeded its rate_limit_per_minute.

    Tries Redis first (cross-instance, accurate under horizontal scale).
    Falls back to the in-process token-bucket when Redis is unavailable.
    """
    limit = key.rate_limit_per_minute
    if not limit or limit <= 0:
        return

    key_str = str(key.id)

    # ── Redis path ────────────────────────────────────────────────────────────
    from cache import get_redis
    if get_redis() is not None:
        try:
            allowed = await _check_rate_limit_redis(key_str, limit)
        except Exception as exc:
            # FAIL-OPEN TO IN-PROCESS LIMITING (not fail-open to no-limit):
            # a Redis flap/timeout must NOT 500 the request, and must NOT
            # silently disable rate limiting. Log and fall through to the
            # in-process token bucket below so the key is still limited
            # (per-instance only, but better than unbounded).
            log.warning(
                "Redis rate-limit check failed (%s: %s) — falling back to "
                "in-process bucket for key %s",
                type(exc).__name__,
                exc,
                key_str,
            )
        else:
            if not allowed:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={"code": "RATE_LIMITED", "message": "Request rate limit exceeded"},
                )
            return

    # ── In-process fallback (single-instance only) ────────────────────────────
    # Reached when Redis is unavailable OR the Redis check raised (fail-open).
    now = time.monotonic()
    async with _rate_lock:
        tokens, window_start = _RATE_BUCKETS.get(key_str, (limit, now))
        if now - window_start >= 60:
            tokens = limit
            window_start = now
        if tokens <= 0:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "RATE_LIMITED", "message": "Request rate limit exceeded"},
            )
        _RATE_BUCKETS[key_str] = (tokens - 1, window_start)
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
    await _check_rate_limit(key)

    # Fire-and-forget last_used_at update — doesn't block the request.
    # Keep a strong ref so the loop doesn't GC the task before it runs.
    task = asyncio.create_task(_update_last_used(key.id))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

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
