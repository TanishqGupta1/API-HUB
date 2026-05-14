"""OPS GraphQL transport — OAuth-aware client with typed results.

This module provides the foundational transport layer for talking directly
to an OnPrintShop storefront's GraphQL API. It handles:

1. OAuth2 client-credentials flow (get access token from token_url)
2. In-memory token caching (don't re-login every request)
3. Typed OpsResult on every call (never raises on GraphQL errors)

Usage:
    auth = OpsAuth(
        base_url="https://customer-store.onprintshop.com",
        token_url="https://customer-store.onprintshop.com/oauth/token",
        client_id="...",
        client_secret="...",
    )
    client = OpsGraphQLClient(auth=auth)
    result = await client.execute(
        "mutation SetProduct($input: setProduct_input!) { setProduct(input: $input) { products_id } }",
        variables={"input": {"category_id": 42, "products_title": "My Product"}},
    )
    if result.ok:
        print(result.data)  # {"setProduct": {"products_id": 12345}}
    else:
        print(result.ops_error_message)  # "invalid category_id"
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger("ops_client")


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OpsAuth:
    """Immutable container for OPS OAuth2 credentials.

    Frozen so credentials can't be accidentally overwritten after construction.
    Values come from the customer's encrypted `ops_auth_config` column in the DB.
    """

    base_url: str  # e.g. "https://customer-store.onprintshop.com"
    token_url: str  # e.g. "https://customer-store.onprintshop.com/oauth/token"
    client_id: str
    client_secret: str


@dataclass(frozen=True)
class OpsResult:
    """Immutable container for every OPS GraphQL response.

    The client NEVER raises exceptions on GraphQL errors. Instead it returns
    an OpsResult with ok=False and the error details populated. This lets
    the push orchestrator (push.py) inspect each step's result and decide
    whether to halt or continue — without messy try/except blocks.
    """

    ok: bool
    data: dict[str, Any] | None = None
    ops_error_code: str | None = None
    ops_error_message: str | None = None
    raw: dict[str, Any] | None = None


# ── Client ───────────────────────────────────────────────────────────────────


class OpsGraphQLClient:
    """OAuth-aware GraphQL client for OnPrintShop.

    Caches access token in-memory per instance until expiry. Each push
    request constructs a fresh client (creds resolved from EncryptedJSON
    on customer row), so token cache is per-push, not global.

    Token refresh happens automatically — if the token is within 30 seconds
    of expiry, a new one is fetched before the GraphQL call.
    """

    GRAPHQL_PATH = "/graphql"

    def __init__(self, auth: OpsAuth, *, timeout_seconds: float = 30.0) -> None:
        self.auth = auth
        self._timeout = timeout_seconds
        # In-memory token cache
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    async def _get_token(self) -> str:
        """Get a valid access token, fetching a new one if expired.

        Uses OAuth2 client-credentials flow:
        POST to token_url with client_id + client_secret → get access_token.
        Token is cached until 30 seconds before its expiry time.
        """
        now = time.time()

        # If we have a token and it's not about to expire, reuse it
        if self._token and now < self._token_expires_at - 30:
            return self._token

        # Otherwise, request a new token
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

        # Cache the token with its expiry time
        self._token = body["access_token"]
        ttl = int(body.get("expires_in", 3600))  # default 1 hour if not specified
        self._token_expires_at = now + ttl
        log.debug("OPS token cached, expires in %d seconds", ttl)
        return self._token

    async def execute(self, query: str, *, variables: dict[str, Any]) -> OpsResult:
        """Send a GraphQL query/mutation to OPS. Returns OpsResult (never raises).

        Steps:
        1. Get a valid token (auto-refreshes if expired)
        2. POST to {base_url}/graphql with the query + variables
        3. Parse the response into OpsResult
        4. If OPS returned errors, extract the first error's code + message
        """
        # Step 1: Get token
        token = await self._get_token()

        # Step 2: Build the URL and send the request
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

        # Step 3: Parse the response
        try:
            body = resp.json()
        except ValueError:
            # OPS returned non-JSON (rare, but handle gracefully)
            return OpsResult(
                ok=False,
                ops_error_code="NON_JSON_RESPONSE",
                ops_error_message=resp.text[:300],
                raw=None,
            )

        # Step 4: Check for errors
        if resp.status_code >= 400 or body.get("errors"):
            errors = body.get("errors") or [{"message": f"HTTP {resp.status_code}"}]
            first = errors[0]
            return OpsResult(
                ok=False,
                ops_error_code=first.get("extensions", {}).get("code", "GRAPHQL_ERROR"),
                ops_error_message=first.get("message", "")[:300],
                raw=body,
            )

        # Success!
        return OpsResult(ok=True, data=body.get("data"), raw=body)
