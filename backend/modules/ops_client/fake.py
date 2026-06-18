"""Canonical in-memory OPS double — used for dry-run AND tests.

Single source of truth: gateway.py imports this instead of defining its own.
Supports two calling conventions:
  • execute(query, *, variables) — used by tests and OpsGraphQLClient-compatible paths
  • per-mutation methods (set_product, set_product_size, …) — used by the gateway
    dispatch loop via _mutation_to_method()
"""
from __future__ import annotations

import re
from typing import Any, Optional

from .client import OpsResult


_OPERATION_NAME_RE = re.compile(r"(?:mutation|query)\s+(\w+)")


class FakeOpsClient:
    """Drop-in stand-in for OpsGraphQLClient + gateway dry-run client.

    • Allocates monotonic synthetic IDs starting at 1000.
    • Records every call on ``self.calls`` for test assertions.
    • ``existing_products_by_sku``: pre-seed the simulated OPS catalog (sku ->
      products_id) so the `products` dedup query returns a match (AI-1 path).
    • ``is_dry_run = True``: sentinel read by _resolve_stock_id_for_size to
      return a synthetic stock_id instead of querying OPS.
    """

    is_dry_run: bool = True

    def __init__(
        self,
        existing_products_by_sku: Optional[dict[str, int]] = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._next_id = 1000
        self.existing_products_by_sku: dict[str, int] = dict(existing_products_by_sku or {})

    def _allocate_id(self) -> int:
        i = self._next_id
        self._next_id += 1
        return i

    async def aclose(self) -> None:
        pass

    # ── execute() — OpsGraphQLClient-compatible path ─────────────────────────

    async def execute(
        self, query: str, *, variables: dict[str, Any]
    ) -> OpsResult:
        match = _OPERATION_NAME_RE.search(query)
        name = match.group(1) if match else "Unknown"
        self.calls.append({"mutation_name": name, "variables": variables})

        if name == "SetProductCategory":
            return OpsResult(ok=True, data={"setProductCategory": {"id": self._allocate_id()}})
        if name == "SetProduct":
            return OpsResult(ok=True, data={"setProduct": {"id": self._allocate_id()}})
        if name == "SetProductSize":
            return OpsResult(ok=True, data={"setProductSize": {"id": self._allocate_id()}})
        if name == "SetProductPrice":
            return OpsResult(ok=True, data={"setProductPrice": {"id": self._allocate_id()}})
        if name == "SetAssignOptions":
            return OpsResult(ok=True, data={"setAssignOptions": {"id": self._allocate_id()}})
        if name == "SetAdditionalOption":
            return OpsResult(ok=True, data={"setAdditionalOption": {"id": self._allocate_id()}})
        if name == "SetAdditionalOptionAttributes":
            return OpsResult(ok=True, data={"setAdditionalOptionAttributes": {"id": self._allocate_id()}})
        if name == "SetProductsAttributePrice":
            return OpsResult(ok=True, data={"setProductsAttributePrice": {"ok": True}})
        if name == "SetProductSku":
            return OpsResult(ok=True, data={"setProductSku": {"id": self._allocate_id(), "result": True}})
        if name == "SetProductsImageGallery":
            return OpsResult(ok=True, data={"setProductsImageGallery": {"result": True, "message": "dry-run"}})
        if name == "UpdateProductStock":
            return OpsResult(ok=True, data={"updateProductStock": {"id": self._allocate_id(), "result": True}})
        if name == "getProductSkuMatrix":
            # Dry-run: report no configured matrix. The gateway treats the
            # Fake (is_dry_run) as "skip matrix validation" anyway, so the
            # exact rows don't matter — just return the well-formed shape.
            return OpsResult(ok=True, data={"getProductSkuMatrix": {"matrix": [], "totalRecords": 0}})
        if name == "products":
            # Dedup path (AI-1): find_product_id_by_main_sku pages this query
            # and matches main_sku client-side. Surface the seeded catalog as
            # products rows so the dedup helper resolves a programmed match.
            rows = [
                {"product_id": pid, "main_sku": sku}
                for sku, pid in self.existing_products_by_sku.items()
            ]
            return OpsResult(ok=True, data={"products": {
                "products": rows,
                "totalProducts": len(rows),
                "currentCount": len(rows),
            }})
        return OpsResult(
            ok=False,
            ops_error_code="UNKNOWN_OPERATION",
            ops_error_message=name,
        )

    # ── Per-mutation methods — gateway dispatch path ──────────────────────────
    # Gateway calls getattr(client, _mutation_to_method(mutation))(variables).
    # All array-input mutations return {"id": x}; _normalize_mutation_response
    # in execute_push aliases that to the named field (products_id, size_id, …).

    async def set_product_category(self, variables: dict) -> dict:
        return {"id": self._allocate_id()}

    async def set_product(self, variables: dict) -> dict:
        return {"id": self._allocate_id()}

    async def set_product_size(self, variables: dict) -> dict:
        return {"id": self._allocate_id()}

    async def set_product_price(self, variables: dict) -> dict:
        return {"id": self._allocate_id()}

    async def set_assign_options(self, variables: dict) -> dict:
        return {"id": self._allocate_id()}

    async def set_additional_option(self, variables: dict) -> dict:
        return {"id": self._allocate_id()}

    async def set_additional_option_attributes(self, variables: dict) -> dict:
        return {"id": self._allocate_id()}

    async def set_products_attribute_price(self, variables: dict) -> dict:
        return {"id": self._allocate_id()}

    async def set_product_sku(self, variables: dict) -> dict:
        return {"id": self._allocate_id()}

    async def set_products_image_gallery(self, variables: dict) -> dict:
        return {"result": True, "message": "dry-run image gallery ok"}

    async def update_product_stock(self, variables: dict) -> dict:
        return {"id": self._allocate_id()}
