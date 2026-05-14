"""Thin httpx wrapper around the OnPrintShop GraphQL endpoint.

Only knows how to POST a query and unwrap data/errors. No domain logic —
that belongs in OPSAdapter.
"""
from __future__ import annotations

from typing import Any, Optional

import httpx

from modules.import_jobs.base import AuthError, SupplierError, TransientError


class OPSClient:
    def __init__(
        self,
        *,
        base_url: str,
        auth_token: str,
        timeout: float = 30.0,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url required")
        if not auth_token:
            raise ValueError("auth_token required")
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout
        self._http_client = http_client  # injected for tests; None = create per-call

    async def query(
        self,
        query: str,
        *,
        variables: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        body = {"query": query, "variables": variables or {}}
        headers = {
            "authorization": f"Bearer {self.auth_token}",
            "content-type": "application/json",
        }

        if self._http_client is not None:
            # Injected client (tests)
            resp = await self._http_client.post(
                f"{self.base_url}/graphql",
                json=body,
                headers=headers,
            )
        else:
            # Production: create per-call client with base_url set
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=headers,
            ) as http:
                try:
                    resp = await http.post("/graphql", json=body)
                except httpx.TimeoutException as e:
                    raise TransientError(f"OPS timeout: {e}") from e
                except httpx.NetworkError as e:
                    raise TransientError(f"OPS network error: {e}") from e

        if resp.status_code in (401, 403):
            raise AuthError(
                f"OPS auth failed: {resp.status_code}", code=str(resp.status_code)
            )
        if resp.status_code >= 500:
            raise TransientError(
                f"OPS 5xx: {resp.status_code} {resp.text[:200]}",
                code=str(resp.status_code),
            )
        if resp.status_code >= 400:
            raise SupplierError(
                f"OPS {resp.status_code}: {resp.text[:200]}",
                code=str(resp.status_code),
            )

        payload = resp.json()
        if payload.get("errors"):
            err = payload["errors"][0]
            code = (err.get("extensions") or {}).get("code")
            raise SupplierError(err.get("message", "GraphQL error"), code=code)
        return payload.get("data", {})
