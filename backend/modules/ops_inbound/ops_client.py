"""Thin httpx wrapper around the OnPrintShop GraphQL endpoint.

Knows how to POST a query and unwrap data/errors. Includes the 6 push-path
mutations and an optional OAuth2 client_credentials refresh-on-401 path.
Domain logic stays in OPSAdapter / payload_builder.
"""
from __future__ import annotations

from typing import Any, Optional

import httpx

from modules.import_jobs.base import AuthError, SupplierError, TransientError


# ---------------------------------------------------------------------------
# Mutation GraphQL strings — canonical shapes from
# n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts (Task 4 source of truth)
# ---------------------------------------------------------------------------

MUTATION_SET_PRODUCT_CATEGORY = (
    "mutation setProductCategory ($input: ProductCategoryInput!) "
    "{ setProductCategory (input: $input) { result message category_id } }"
)

MUTATION_SET_PRODUCT = (
    "mutation setProduct ($input: ProductInput!) "
    "{ setProduct (input: $input) { result message products_id } }"
)

MUTATION_SET_PRODUCT_SIZE = (
    "mutation setProductSize ($input: ProductSizeInput!) "
    "{ setProductSize (input: $input) { result message product_size_id } }"
)

MUTATION_SET_PRODUCT_PRICE = (
    "mutation setProductPrice ($input: ProductPriceInput!) "
    "{ setProductPrice (input: $input) { result message product_price_id } }"
)

MUTATION_SET_ASSIGN_OPTIONS = (
    "mutation setAssignOptions ($input: AssignOptionsInput!) "
    "{ setAssignOptions (input: $input) { result message product_option_id } }"
)

MUTATION_SET_PRODUCT_DESIGN = (
    "mutation setProductDesign "
    "($order_product_id: Int, $ziflow_link: String, $ziflow_preflight_link: String) "
    "{ setProductDesign ("
    "order_product_id: $order_product_id, "
    "ziflow_link: $ziflow_link, "
    "ziflow_preflight_link: $ziflow_preflight_link"
    ") { result message } }"
)


class OPSClient:
    def __init__(
        self,
        *,
        base_url: str,
        auth_token: str,
        timeout: float = 30.0,
        http_client: Optional[httpx.AsyncClient] = None,
        token_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url required")
        if not auth_token:
            raise ValueError("auth_token required")
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout
        self._http_client = http_client  # injected for tests; None = create per-call

        # Optional OAuth2 client_credentials refresh config. All three required
        # together to enable refresh-on-401; any missing => no refresh attempted.
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret

    # -------------------------------------------------------------------
    # Core transport
    # -------------------------------------------------------------------

    async def query(
        self,
        query: str,
        *,
        variables: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        try:
            return await self._post_query(query, variables=variables)
        except AuthError:
            if not self._refresh_enabled():
                raise
            await self._refresh_token()
            return await self._post_query(query, variables=variables)

    async def _post_query(
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

    # -------------------------------------------------------------------
    # OAuth2 client_credentials refresh
    # -------------------------------------------------------------------

    def _refresh_enabled(self) -> bool:
        return bool(self.token_url and self.client_id and self.client_secret)

    async def _refresh_token(self) -> None:
        body = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        if self._http_client is not None:
            resp = await self._http_client.post(self.token_url, data=body)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                try:
                    resp = await http.post(self.token_url, data=body)
                except httpx.TimeoutException as e:
                    raise TransientError(f"OPS token endpoint timeout: {e}") from e
                except httpx.NetworkError as e:
                    raise TransientError(f"OPS token endpoint network error: {e}") from e

        if resp.status_code >= 400:
            raise AuthError(
                f"OPS token refresh failed: {resp.status_code} {resp.text[:200]}",
                code=str(resp.status_code),
            )

        data = resp.json()
        new_token = data.get("access_token")
        if not new_token:
            raise AuthError("OPS token refresh response missing access_token")
        self.auth_token = new_token

    # -------------------------------------------------------------------
    # Mutation wrappers (Task 4)
    # Each wraps query() and unwraps the response key. Raises SupplierError
    # if OPS returns a GraphQL error or the response key is missing.
    # -------------------------------------------------------------------

    async def set_product_category(self, input: dict[str, Any]) -> dict[str, Any]:
        data = await self.query(MUTATION_SET_PRODUCT_CATEGORY, variables={"input": input})
        return self._unwrap(data, "setProductCategory")

    async def set_product(self, input: dict[str, Any]) -> dict[str, Any]:
        data = await self.query(MUTATION_SET_PRODUCT, variables={"input": input})
        return self._unwrap(data, "setProduct")

    async def set_product_size(self, input: dict[str, Any]) -> dict[str, Any]:
        data = await self.query(MUTATION_SET_PRODUCT_SIZE, variables={"input": input})
        return self._unwrap(data, "setProductSize")

    async def set_product_price(self, input: dict[str, Any]) -> dict[str, Any]:
        data = await self.query(MUTATION_SET_PRODUCT_PRICE, variables={"input": input})
        return self._unwrap(data, "setProductPrice")

    async def set_assign_options(self, input: dict[str, Any]) -> dict[str, Any]:
        data = await self.query(MUTATION_SET_ASSIGN_OPTIONS, variables={"input": input})
        return self._unwrap(data, "setAssignOptions")

    async def set_product_design(self, input: dict[str, Any]) -> dict[str, Any]:
        # setProductDesign uses inline scalar args, not an Input wrapper —
        # canonical shape in n8n node line 6632.
        data = await self.query(MUTATION_SET_PRODUCT_DESIGN, variables=input)
        return self._unwrap(data, "setProductDesign")

    @staticmethod
    def _unwrap(data: dict[str, Any], key: str) -> dict[str, Any]:
        node = data.get(key)
        if node is None:
            raise SupplierError(f"OPS response missing '{key}' field")
        return node
