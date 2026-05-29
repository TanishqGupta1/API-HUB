"""In-memory OPS double for dry-run + tests. Returns synthetic IDs."""
from __future__ import annotations

import re
from typing import Any

from .client import OpsResult


_MUTATION_NAME_RE = re.compile(r"mutation\s+(\w+)")


class FakeOpsClient:
    """Drop-in stand-in for OpsGraphQLClient.

    Same `execute(query, *, variables)` signature so the push orchestrator
    can inject either real or fake by runtime config. Allocates monotonic
    synthetic IDs starting at 1000 and records every call on `self.calls`
    so tests can assert the exact mutation sequence.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._next_id = 1000

    def _allocate_id(self) -> int:
        i = self._next_id
        self._next_id += 1
        return i

    async def execute(
        self, query: str, *, variables: dict[str, Any]
    ) -> OpsResult:
        match = _MUTATION_NAME_RE.search(query)
        name = match.group(1) if match else "Unknown"
        self.calls.append({"mutation_name": name, "variables": variables})

        if name == "SetProductCategory":
            return OpsResult(
                ok=True,
                data={"setProductCategory": {"category_id": self._allocate_id()}},
            )
        if name == "SetProduct":
            return OpsResult(
                ok=True,
                data={"setProduct": {"products_id": self._allocate_id()}},
            )
        if name == "SetProductSize":
            return OpsResult(
                ok=True,
                data={"setProductSize": {"size_id": self._allocate_id()}},
            )
        if name == "SetProductPrice":
            return OpsResult(
                ok=True,
                data={"setProductPrice": {"product_price_id": self._allocate_id()}},
            )
        if name == "SetAdditionalOption":
            return OpsResult(
                ok=True,
                data={"setAdditionalOption": {"prod_add_opt_id": self._allocate_id()}},
            )
        if name == "SetAdditionalOptionAttributes":
            return OpsResult(
                ok=True,
                data={"setAdditionalOptionAttributes": {"attribute_id": self._allocate_id()}},
            )
        if name == "SetProductsAttributePrice":
            return OpsResult(
                ok=True,
                data={"setProductsAttributePrice": {"ok": True}},
            )
        return OpsResult(
            ok=False,
            ops_error_code="UNKNOWN_MUTATION",
            ops_error_message=name,
        )
