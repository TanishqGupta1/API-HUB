from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger("ops_client")


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

    async def _get_token(self) -> str:
        async with self._token_lock:
            now = time.time()
            if self._token and now < self._token_expires_at - 30:
                return self._token

            log.debug("Requesting new OPS access token from %s", self.auth.token_url)
            async with httpx.AsyncClient(timeout=self._timeout) as hc:
                resp = await hc.post(
                    self.auth.token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.auth.client_id,
                        "client_secret": self.auth.client_secret,
                    },
                )
                resp.raise_for_status()
                body = resp.json()

            self._token = body["access_token"]
            ttl = int(body.get("expires_in", 3600))
            self._token_expires_at = now + ttl
            return self._token

    def _invalidate_token(self) -> None:
        self._token = None
        self._token_expires_at = 0.0

    async def execute(self, query: str, *, variables: dict[str, Any]) -> OpsResult:
        """POST a GraphQL mutation/query. Returns OpsResult (never raises)."""
        return await self._execute_once(query, variables=variables, allow_retry=True)

    async def _execute_once(
        self, query: str, *, variables: dict[str, Any], allow_retry: bool
    ) -> OpsResult:
        token = await self._get_token()
        url = f"{self.auth.base_url.rstrip('/')}{self.GRAPHQL_PATH}"

        async with httpx.AsyncClient(timeout=self._timeout) as hc:
            resp = await hc.post(
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
