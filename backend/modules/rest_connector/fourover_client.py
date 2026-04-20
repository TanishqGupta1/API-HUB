"""4Over REST + HMAC-SHA256 API client.

4Over is NOT PromoStandards-compliant. Its REST API requires every request to be
signed with HMAC-SHA256 using a private key the supplier provides at onboarding.

Signature contract:
    Authorization: hmac <api_key>:<signature>
    X-Timestamp:   <ISO-8601 UTC timestamp, second precision, "Z" suffix>

Where:
    signature = HMAC-SHA256(private_key, method + path + timestamp).hexdigest()

Example signed GET to /printproducts/categories at 2026-04-20T12:00:00Z:
    payload   = b"GET/printproducts/categories2026-04-20T12:00:00Z"
    signature = hmac_sha256(private_key, payload)
    header    = f"hmac {api_key}:{signature}"

Credentials come from `supplier.auth_config` (encrypted JSONB column) — never
hardcoded. The supplier row lives in the `suppliers` table and stores:
    {"api_key": "...", "private_key": "..."}

API environments:
    - Production: https://api.4over.com
    - Sandbox:    https://sandbox-api.4over.com
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any

import httpx


# Per-request timeout. 4Over product catalog calls can be slow (~5–10s), so
# we give a comfortable margin without hanging on bad networks.
_DEFAULT_TIMEOUT = 30.0


class FourOverClient:
    """HMAC-signed REST client for the 4Over print-products API.

    One instance per supplier sync. Stateless between calls — safe to create
    per-request. Pass an optional `http_client` for testing with
    `httpx.MockTransport`.

    Usage:
        client = FourOverClient(
            base_url="https://sandbox-api.4over.com",
            auth_config={"api_key": "abc", "private_key": "shh"},
        )
        categories = await client.get_categories()
    """

    def __init__(self, base_url: str, auth_config: dict[str, str]):
        if not base_url:
            raise ValueError("base_url is required")
        if not isinstance(auth_config, dict):
            raise ValueError("auth_config must be a dict")
        if "api_key" not in auth_config or not auth_config["api_key"]:
            raise ValueError("auth_config.api_key is required")
        if "private_key" not in auth_config or not auth_config["private_key"]:
            raise ValueError("auth_config.private_key is required")

        self.base_url = base_url.rstrip("/")
        self.api_key = auth_config["api_key"]
        # Encode the private key once — HMAC requires bytes, and we use the
        # same key for every call during this client's lifetime.
        self._private_key_bytes = auth_config["private_key"].encode("utf-8")

    # ------------------------------------------------------------------ #
    # Signing
    # ------------------------------------------------------------------ #

    @staticmethod
    def _utc_timestamp() -> str:
        """Return the current UTC time in ISO-8601 with 'Z' suffix.

        4Over's signature contract uses second precision. Millisecond or
        microsecond values break signature validation on their end.
        """
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _sign(
        self,
        method: str,
        path: str,
        timestamp: str | None = None,
    ) -> dict[str, str]:
        """Build the Authorization + X-Timestamp headers for one request.

        Args:
            method: HTTP verb in uppercase — "GET", "POST", etc.
            path: Request path including leading slash
                (e.g. "/printproducts/categories").
            timestamp: Optional pre-generated timestamp. Pass a fixed value
                in tests so the signature is deterministic. Defaults to
                the current UTC time.

        Returns:
            Header dict ready to merge into an httpx request.
        """
        ts = timestamp or self._utc_timestamp()
        payload = f"{method}{path}{ts}".encode("utf-8")
        signature = hmac.new(self._private_key_bytes, payload, hashlib.sha256).hexdigest()
        return {
            "Authorization": f"hmac {self.api_key}:{signature}",
            "X-Timestamp": ts,
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------ #
    # Transport
    # ------------------------------------------------------------------ #

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> Any:
        """Sign and send a single request. Returns parsed JSON.

        If `http_client` is None, a one-shot AsyncClient is created and
        closed around the request. Pass an existing client to reuse
        connection pools across many calls, or to inject a MockTransport
        in tests.
        """
        headers = self._sign(method, path)
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        url = f"{self.base_url}{path}"
        owns_client = http_client is None
        client = http_client or httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        try:
            resp = await client.request(method, url, headers=headers, json=json_body)
            resp.raise_for_status()
            return resp.json()
        finally:
            if owns_client:
                await client.aclose()

    # ------------------------------------------------------------------ #
    # Public API surface — matches Task 14 spec
    # ------------------------------------------------------------------ #

    async def get_categories(
        self,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> list[dict]:
        """Fetch 4Over's print-product category tree."""
        return await self._request(
            "GET", "/printproducts/categories", http_client=http_client
        )

    async def get_products(
        self,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> list[dict]:
        """Fetch the full product catalog."""
        return await self._request(
            "GET", "/printproducts/products", http_client=http_client
        )

    async def get_product_options(
        self,
        product_uuid: str,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> dict:
        """Fetch option groups (paper, coating, folds, ...) for one product."""
        if not product_uuid:
            raise ValueError("product_uuid is required")
        return await self._request(
            "GET",
            f"/printproducts/products/{product_uuid}/optiongroups",
            http_client=http_client,
        )

    async def get_quote(
        self,
        product_uuid: str,
        options: dict,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> dict:
        """Fetch a live quote for a product configuration."""
        if not product_uuid:
            raise ValueError("product_uuid is required")
        if not isinstance(options, dict):
            raise ValueError("options must be a dict")
        return await self._request(
            "POST",
            "/printproducts/productquote",
            json_body={"product_uuid": product_uuid, "options": options},
            http_client=http_client,
        )
