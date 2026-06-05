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

    def __post_init__(self) -> None:
        # Defensive trim: a stray leading/trailing space pasted into a URL via
        # the UI otherwise breaks httpx with "missing protocol". Frozen
        # dataclass → set via object.__setattr__.
        for _f in ("base_url", "token_url", "client_id", "client_secret"):
            _v = getattr(self, _f)
            if isinstance(_v, str):
                object.__setattr__(self, _f, _v.strip())


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

    # OPS serves GraphQL at /api/ (matches the n8n OnPrintShop node). The old
    # /graphql path returns the storefront HTML page, not the API.
    GRAPHQL_PATH = "/api/"

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
                cache_key = _token_cache_key(self.auth)
                cached = await redis.get(cache_key)
                if cached:
                    self._token = cached          # keep local copy for 401-retry
                    # Derive the per-instance expiry from the REAL remaining
                    # Redis TTL — never fabricate a flat 1h. Faking the expiry
                    # meant that after the Redis key expired, the per-instance
                    # fast-path below would keep serving a stale token → 401s.
                    pttl_ms = await redis.pttl(cache_key)
                    if pttl_ms is not None and pttl_ms > 0:
                        # pttl = remaining lifetime in ms. The -30s safety
                        # margin is applied at the fast-path read site below.
                        self._token_expires_at = now + (pttl_ms / 1000.0)
                    else:
                        # No usable TTL (-1 no-expiry, -2 missing, or None):
                        # don't trust a local fast-path — force a re-check on
                        # the next call instead of inventing an expiry.
                        self._token_expires_at = 0.0
                    return cached

            # ── Fall back to per-instance cache ───────────────────────────────
            if self._token and now < self._token_expires_at - 30:
                return self._token

            log.debug("Requesting new OPS access token from %s", self.auth.token_url)
            # OPS token endpoints vary by deployment in how they accept client
            # credentials. Mirror VG's proven n8n OnPrintShop node: try JSON body,
            # then form-urlencoded body, then HTTP Basic auth — first 2xx wins.
            # (see n8n-nodes-onprintshop GenericFunctions.getAccessToken)
            cid, csecret = self.auth.client_id, self.auth.client_secret
            _attempts = (
                ("json", {"json": {"grant_type": "client_credentials",
                                   "client_id": cid, "client_secret": csecret}}),
                ("form", {"data": {"grant_type": "client_credentials",
                                   "client_id": cid, "client_secret": csecret}}),
                ("basic", {"data": {"grant_type": "client_credentials"},
                           "auth": (cid, csecret)}),
            )
            resp = None
            for _label, _kwargs in _attempts:
                resp = await self._http.post(self.auth.token_url, **_kwargs)
                # Only a 2xx is a real success. `< 400` wrongly accepted 3xx
                # redirects (no token body) and fell through to a None token.
                if 200 <= resp.status_code < 300:
                    log.debug("OPS access token obtained via %s auth", _label)
                    break
            if resp is None or not (200 <= resp.status_code < 300):
                # Surface OPS's actual error body — essential for diagnosing 401s.
                raise RuntimeError(
                    f"OPS token endpoint returned "
                    f"{resp.status_code if resp is not None else 'no-response'} at "
                    f"{self.auth.token_url} (tried json/form/basic auth): "
                    f"{resp.text[:400] if resp is not None else ''}"
                )
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

    async def _invalidate_token(self) -> None:
        """Invalidate both the per-instance and Redis-cached token.

        Awaits the Redis DELETE so eviction is DETERMINISTIC before the 401
        retry mints a new token. The previous fire-and-forget create_task()
        could race the retry and let it re-read the revoked token from Redis.
        """
        self._token = None
        self._token_expires_at = 0.0
        try:
            from cache import get_redis
            redis = get_redis()
            if redis is not None:
                await redis.delete(_token_cache_key(self.auth))
        except Exception as exc:
            # Non-fatal: we already cleared the per-instance token, so the
            # retry will mint a fresh one regardless. Log instead of swallowing.
            log.warning(
                "Failed to evict OPS token from Redis (%s: %s)",
                type(exc).__name__,
                exc,
            )

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

        # OPS revoked/expired the token — refresh once and retry.
        # Some OPS deployments return 403 instead of 401 for expired tokens.
        if resp.status_code in (401, 403) and allow_retry:
            log.debug("OPS %s — invalidating cached token and retrying once", resp.status_code)
            await self._invalidate_token()
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
