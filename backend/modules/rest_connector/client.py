"""REST protocol adapter — S&S Activewear and other JSON-over-HTTP suppliers.

Mirrors the role of PromoStandardsClient but for REST APIs. Base URL and
credentials come from the Supplier row (supplier.base_url, supplier.auth_config);
nothing is hardcoded, so adding another REST supplier is a config change.

S&S uses HTTP Basic Auth with (account_number, api_key) pulled from
supplier.auth_config. Sinchana's normalizer (Task 8a, `ss_normalizer.py`)
maps the raw JSON into PSProductData so the canonical `upsert_products()`
storage path works unchanged.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Final

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT: Final[float] = 60.0
DEFAULT_MAX_RETRIES: Final[int] = 3
RETRY_BACKOFF_BASE: Final[float] = 1.5


class RESTConnectorError(Exception):
    """Base exception for REST connector failures."""


class RESTConnectorAuthError(RESTConnectorError):
    """auth_config is missing a required key."""


class RESTConnectorHTTPError(RESTConnectorError):
    """Upstream API returned a non-2xx response after all retries."""

    def __init__(self, status_code: int, url: str, body: str):
        self.status_code = status_code
        self.url = url
        self.body = body
        super().__init__(f"{url} returned {status_code}: {body[:200]}")


def _is_retryable_status(code: int) -> bool:
    return code == 429 or 500 <= code < 600


class RESTConnectorClient:
    """Supplier-agnostic REST client for JSON-over-HTTP catalog APIs."""

    def __init__(
        self,
        base_url: str,
        auth_config: dict,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not base_url:
            raise ValueError("base_url is required")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        # Injectable transport lets tests feed canned responses without a real socket.
        self._transport = transport

        try:
            self.auth = (auth_config["account_number"], auth_config["api_key"])
        except KeyError as missing:
            raise RESTConnectorAuthError(
                f"auth_config missing required key {missing}; "
                "expected 'account_number' and 'api_key'"
            ) from None

    async def _get(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        last_exc: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(
                    auth=self.auth,
                    timeout=self.timeout,
                    transport=self._transport,
                ) as client:
                    resp = await client.get(url)

                if resp.status_code < 400:
                    return resp.json()

                err = RESTConnectorHTTPError(resp.status_code, url, resp.text)
                if not _is_retryable_status(resp.status_code):
                    raise err
                last_exc = err
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc

            if attempt + 1 >= self.max_retries:
                break
            sleep_for = RETRY_BACKOFF_BASE ** attempt
            logger.warning(
                "rest_connector retry %d/%d for %s after %s (sleep %.1fs)",
                attempt + 1, self.max_retries, url, last_exc, sleep_for,
            )
            await asyncio.sleep(sleep_for)

        assert last_exc is not None
        raise last_exc

    async def get_products(self) -> list[dict[str, Any]]:
        """S&S: GET /Products/ → JSON array of products."""
        return await self._get("/Products/")

    async def get_styles(self) -> list[dict[str, Any]]:
        """S&S: GET /Styles/ → styles with color/size variants."""
        return await self._get("/Styles/")

    async def get_categories(self) -> list[dict[str, Any]]:
        """S&S: GET /Categories/ → category hierarchy."""
        return await self._get("/Categories/")
