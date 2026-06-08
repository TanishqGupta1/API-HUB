"""In-memory OPS double for dry-run + tests. Returns synthetic IDs."""
from __future__ import annotations

import re
from typing import Any, Optional

from .client import OpsResult


_OPERATION_NAME_RE = re.compile(r"(?:mutation|query)\s+(\w+)")


class FakeOpsClient:
    """Drop-in stand-in for OpsGraphQLClient.

    Same `execute(query, *, variables)` signature so the push orchestrator
    can inject either real or fake by runtime config. Allocates monotonic
    synthetic IDs starting at 1000 and records every call on `self.calls`
    so tests can assert the exact mutation sequence.

    ``existing_products_by_sku``: optional dict {sku: products_id} that
    pre-seeds the simulated OPS catalog. ``GetProductBySku`` queries
    return the matching products_id when present, otherwise an empty
    result (treated by callers as 'not found'). Lets tests exercise the
    dedup path without spinning up real OPS.
    """

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

    async def execute(
        self, query: str, *, variables: dict[str, Any]
    ) -> OpsResult:
        match = _OPERATION_NAME_RE.search(query)
        name = match.group(1) if match else "Unknown"
        self.calls.append({"mutation_name": name, "variables": variables})

        if name == "SetProductCategory":
            return OpsResult(
                ok=True,
                data={"setProductCategory": {"id": self._allocate_id()}},
            )
        if name == "SetProduct":
            return OpsResult(
                ok=True,
                data={"setProduct": {"id": self._allocate_id()}},
            )
        if name == "SetProductSize":
            return OpsResult(
                ok=True,
                data={"setProductSize": {"id": self._allocate_id()}},
            )
        if name == "SetProductPrice":
            return OpsResult(
                ok=True,
                data={"setProductPrice": {"id": self._allocate_id()}},
            )
        if name == "SetAdditionalOption":
            return OpsResult(
                ok=True,
                data={"setAdditionalOption": {"id": self._allocate_id()}},
            )
        if name == "SetAdditionalOptionAttributes":
            return OpsResult(
                ok=True,
                data={"setAdditionalOptionAttributes": {"id": self._allocate_id()}},
            )
        if name == "SetProductsAttributePrice":
            return OpsResult(
                ok=True,
                data={"setProductsAttributePrice": {"ok": True}},
            )
        if name == "GetProductBySku":
            sku = (variables or {}).get("products_sku")
            existing = self.existing_products_by_sku.get(sku)
            if existing is None:
                # Not found — return ok=True with an empty object so callers
                # treat "no products_id" as a successful "not found" lookup.
                return OpsResult(ok=True, data={"getProductBySku": {}})
            return OpsResult(
                ok=True,
                data={"getProductBySku": {
                    "products_id": existing,
                    "products_sku": sku,
                }},
            )
        return OpsResult(
            ok=False,
            ops_error_code="UNKNOWN_OPERATION",
            ops_error_message=name,
        )
