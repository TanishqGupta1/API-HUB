from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger("ops_client")


def _token_cache_key(auth: "OpsAuth") -> str:
    """Stable Redis key for a given OPS credential pair.

    Derived from client_id + token_url so different storefronts
    get independent cache slots.
    """
    raw = f"{auth.client_id}:{auth.token_url}"
    return f"ops_token:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


@dataclass(frozen=True)
class OpsAuth:
    # Values from customer's encrypted ops_auth_config column
    base_url: str
    token_url: str
    client_id: str
    client_secret: str


@dataclass(frozen=True)
class OpsResult:
    # Never raises on GraphQL errors — ok=False carries the detail instead
    ok: bool
    data: dict[str, Any] | None = None
    ops_error_code: str | None = None
    ops_error_message: str | None = None
    raw: dict[str, Any] | None = None


class OpsGraphQLClient:
    """OAuth-aware GraphQL client for OnPrintShop. Token cached per instance."""

    GRAPHQL_PATH = "/graphql"

    def __init__(self, auth: OpsAuth, *, timeout_seconds: float = 30.0) -> None:
        self.auth = auth
        self._timeout = timeout_seconds
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = asyncio.Lock()
        self._http = httpx.AsyncClient(timeout=self._timeout)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "OpsGraphQLClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def _get_token(self) -> str:
        async with self._token_lock:
            now = time.time()

            # ── Try Redis cache first ─────────────────────────────────────────
            from cache import get_redis
            redis = get_redis()
            if redis is not None:
                cached = await redis.get(_token_cache_key(self.auth))
                if cached:
                    self._token = cached          # keep local copy for 401-retry
                    self._token_expires_at = now + 3600  # approximate; Redis TTL is authoritative
                    return cached

            # ── Fall back to per-instance cache ───────────────────────────────
            if self._token and now < self._token_expires_at - 30:
                return self._token

            log.debug("Requesting new OPS access token from %s", self.auth.token_url)
            resp = await self._http.post(
                self.auth.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.auth.client_id,
                    "client_secret": self.auth.client_secret,
                },
            )
            resp.raise_for_status()
            body = resp.json()

            token = body.get("access_token")
            if not token:
                raise RuntimeError(
                    f"OPS token endpoint returned no access_token: {str(body)[:200]}"
                )
            ttl = int(body.get("expires_in", 3600))

            # Store in Redis (expire 60s early to avoid using a near-expired token)
            if redis is not None:
                await redis.set(_token_cache_key(self.auth), token, ex=max(ttl - 60, 60))

            self._token = token
            self._token_expires_at = now + ttl
            return self._token

    def _invalidate_token(self) -> None:
        """Invalidate both the per-instance and Redis-cached token."""
        self._token = None
        self._token_expires_at = 0.0
        # Best-effort Redis eviction so the next request doesn't reuse a
        # revoked token. Fire-and-forget — don't block the caller.
        try:
            from cache import get_redis
            import asyncio
            redis = get_redis()
            if redis is not None:
                task = asyncio.create_task(redis.delete(_token_cache_key(self.auth)))
                task.add_done_callback(lambda _: None)  # silence "task never awaited"
        except Exception:
            pass

    async def execute(self, query: str, *, variables: dict[str, Any]) -> OpsResult:
        """POST a GraphQL mutation/query. Returns OpsResult (never raises)."""
        return await self._execute_once(query, variables=variables, allow_retry=True)

    async def _execute_once(
        self, query: str, *, variables: dict[str, Any], allow_retry: bool
    ) -> OpsResult:
        token = await self._get_token()
        url = f"{self.auth.base_url.rstrip('/')}{self.GRAPHQL_PATH}"

        resp = await self._http.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"query": query, "variables": variables},
        )

        # OPS revoked the token early — refresh once and retry
        if resp.status_code == 401 and allow_retry:
            log.debug("OPS 401 — invalidating cached token and retrying once")
            self._invalidate_token()
            return await self._execute_once(query, variables=variables, allow_retry=False)

        try:
            body = resp.json()
        except ValueError:
            return OpsResult(
                ok=False,
                ops_error_code="NON_JSON_RESPONSE",
                ops_error_message=resp.text[:300],
            )

        if resp.status_code >= 400 or body.get("errors"):
            errors = body.get("errors") or [{"message": f"HTTP {resp.status_code}"}]
            first = errors[0]
            return OpsResult(
                ok=False,
                ops_error_code=first.get("extensions", {}).get("code", "GRAPHQL_ERROR"),
                ops_error_message=first.get("message", "")[:300],
                raw=body,
            )

        return OpsResult(ok=True, data=body.get("data"), raw=body)
