"""Redis connection pool — optional backplane.

If REDIS_URL is unset or Redis is unreachable, every caller falls back
to its in-process equivalent automatically.  Local dev works without
Redis; production gets cross-instance rate-limiting, shared token cache,
and a distributed scheduler lock as soon as REDIS_URL is set.

Usage:
    from cache import get_redis          # returns client or None
    from cache import init_redis         # call once in lifespan startup
    from cache import close_redis        # call once in lifespan shutdown
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import redis.asyncio as aioredis

log = logging.getLogger("cache")

# Module-level singleton — populated by init_redis(), cleared by close_redis().
_redis: Optional["aioredis.Redis"] = None


async def init_redis() -> None:
    """Connect to Redis.  Called from the FastAPI lifespan handler on startup.

    Silently disables Redis features when REDIS_URL is absent or the server
    is unreachable so the app boots normally in environments without Redis.
    """
    global _redis

    url = os.getenv("REDIS_URL", "")
    if not url:
        log.info(
            "REDIS_URL not set — Redis disabled; in-process fallbacks active "
            "(rate limiter, token cache, scheduler lock)"
        )
        return

    try:
        import redis.asyncio as aioredis  # noqa: PLC0415 — lazy import keeps dep optional
    except ImportError:
        log.warning(
            "redis package not installed — Redis disabled. "
            "Add redis[asyncio]>=5.0.0 to requirements.txt to enable."
        )
        return

    try:
        client: aioredis.Redis = aioredis.from_url(
            url,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
        await client.ping()
        _redis = client
        # Only log the host:port, never the password.
        safe = url.rsplit("@", 1)[-1] if "@" in url else url
        log.info("Redis connected: %s", safe)
    except Exception as exc:
        log.warning(
            "Redis unavailable (%s: %s) — in-process fallbacks active",
            type(exc).__name__,
            exc,
        )
        _redis = None


async def close_redis() -> None:
    """Disconnect Redis.  Called from the FastAPI lifespan handler on shutdown."""
    global _redis
    if _redis is not None:
        try:
            await _redis.aclose()
        except Exception:
            pass
        _redis = None
        log.info("Redis disconnected")


def get_redis() -> "Optional[aioredis.Redis]":
    """Return the active Redis client, or None when Redis is unavailable."""
    return _redis
