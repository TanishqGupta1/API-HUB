"""HTTP client for pushing the Connect catalog into GraphX-Manage.

Mirrors `modules/ops_client/client.OpsGraphQLClient`: a thin httpx-based client that
NEVER raises on a transport/HTTP error — it returns a `ManageResult(ok=False, ...)` so a
flaky Manage endpoint can never sink a push loop (same contract as `OpsResult`).

Unlike OPS (per-customer OAuth2 client-credentials), Manage is a single app-level target
configured via env (plan OD3): `MANAGE_INGEST_URL` + `MANAGE_INGEST_TOKEN` (a bearer token
minted by Manage's `create-connect-integration-principal.ts`, holding `integration:connect:sync`).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger("manage_client")

# Manage registers the Connect catalog ingest here (apps/api/src/server.ts).
INGEST_PATH = "/integration/connect/ingest/products"


@dataclass(frozen=True)
class ManageResult:
    """Never raises on HTTP/transport errors — ok=False carries the detail instead."""
    ok: bool
    status: int | None = None
    data: dict[str, Any] | None = None
    error: str | None = None


class ManageClient:
    """Bearer-authed HTTP client for the Manage Connect-ingest endpoint."""

    def __init__(self, base_url: str, token: str, *, timeout_seconds: float = 30.0) -> None:
        # Trim stray whitespace (a pasted URL/token otherwise breaks httpx / the header).
        self.base_url = (base_url or "").strip().rstrip("/")
        self._token = (token or "").strip()
        self._timeout = timeout_seconds
        self._http = httpx.AsyncClient(timeout=self._timeout)

    @classmethod
    def from_env(cls, *, timeout_seconds: float = 30.0) -> "ManageClient":
        """Build from MANAGE_INGEST_URL + MANAGE_INGEST_TOKEN (read at call time so
        load_dotenv() has already run)."""
        return cls(
            base_url=os.getenv("MANAGE_INGEST_URL", ""),
            token=os.getenv("MANAGE_INGEST_TOKEN", ""),
            timeout_seconds=timeout_seconds,
        )

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self._token)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "ManageClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def push_products(self, payload: dict[str, Any]) -> ManageResult:
        """POST a ConnectProductPush batch to Manage. payload = {"products": [...]}.

        Returns ManageResult; never raises. A non-2xx is ok=False with the status + body.
        """
        if not self.configured:
            return ManageResult(ok=False, error="MANAGE_INGEST_URL / MANAGE_INGEST_TOKEN not set")
        url = f"{self.base_url}{INGEST_PATH}"
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        try:
            resp = await self._http.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            log.warning("manage push transport error: %s", exc)
            return ManageResult(ok=False, error=f"transport error: {exc}")
        body: dict[str, Any] | None
        try:
            parsed = resp.json()
            body = parsed if isinstance(parsed, dict) else {"value": parsed}
        except ValueError:
            body = {"raw": resp.text[:500]}
        if resp.is_success:
            return ManageResult(ok=True, status=resp.status_code, data=body)
        return ManageResult(
            ok=False,
            status=resp.status_code,
            data=body,
            error=(body or {}).get("error") or f"HTTP {resp.status_code}",
        )
