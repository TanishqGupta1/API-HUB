# Phase 2 — OPS Inbound Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the OPS *inbound* adapter (reads OnPrintShop products via GraphQL, normalizes into the polymorphic `ProductIngest` shape from Phase 1, persists via `persist_product`) plus the supplier-agnostic adapter registry and import-job orchestrator that drives it. Ship a manual `POST /api/suppliers/{id}/import` endpoint that runs the import in the background and exposes status via the existing `/api/sync-jobs/{id}` polling endpoint.

**Architecture:** A new `modules/import_jobs/` package owns the adapter registry, the `BaseAdapter` interface, and the `run_import` orchestrator. A new `modules/ops_inbound/ops_adapter.py` file holds `OPSAdapter`, which talks to the OnPrintShop GraphQL API for product discovery + hydration and normalizes responses to `ProductIngest` with `product_type="print"` + `print_details` + `product_sizes` + options. Persistence reuses Phase 1's `persist_product` end-to-end. Auth errors abort the entire job (job status `failed`); per-product errors continue the loop and append to `sync_jobs.errors[]` (job status `partial_success`). FastAPI `BackgroundTasks` runs the work; the existing `GET /api/sync-jobs/{id}` returns status. CLAUDE.md splits "n8n owns OPS push" (outbound) from this plan, which is OPS *read* (inbound) only — we do not touch `modules/ops_push/`.

**Tech Stack:** FastAPI + BackgroundTasks, async SQLAlchemy 2.0 + asyncpg, httpx (already present in `backend/scripts/ingest_ops_master_options.py`), Pydantic v2, pytest + pytest-asyncio + `respx` (HTTP mocking — add to requirements). No Alembic — schema upgrades go in `backend/main.py:_SCHEMA_UPGRADES`.

**Spec:** `docs/superpowers/specs/2026-04-29-multi-supplier-product-model-design.md` — implements §6.6 supplier `adapter_class` routing, §7 supplier adapter pipeline (OPS path), §7.1 persistence routing, §7.2 discovery modes, §7.3 error handling, §10 trigger model (manual UI button), and the OPS half of §12 Phase 2 rollout.

**Depends on:** Phase 1 plan `2026-04-29-polymorphic-product-model-foundation.md` must be executed first — this plan calls `persist_product`, `ProductIngest.product_type="print"`, `PrintDetailsIngest`, `ProductSizeIngest`, etc.

**Out of scope (other plans):** SanMar/PromoStandards adapter (Phase 3), pricing API (Phase 4), frontend PDP and the actual UI button (Phase 5 — this plan ships the *backend endpoint* that the button will call), n8n cron scheduling (Phase 6).

---

## File Structure

### Files to create
- `backend/modules/import_jobs/__init__.py` — empty package marker
- `backend/modules/import_jobs/base.py` — `BaseAdapter` abstract class, `ProductRef`, `DiscoveryMode`, error types (`AuthError`, `SupplierError`)
- `backend/modules/import_jobs/registry.py` — `ADAPTERS` dict, `get_adapter(supplier, db)` resolver
- `backend/modules/import_jobs/service.py` — `run_import(supplier_id, mode, limit, explicit_list, db)` orchestrator
- `backend/modules/import_jobs/schemas.py` — `ImportRequest`, `ImportResponse` Pydantic
- `backend/modules/import_jobs/routes.py` — `POST /api/suppliers/{id}/import` endpoint
- `backend/modules/ops_inbound/__init__.py` — empty package marker
- `backend/modules/ops_inbound/ops_client.py` — thin httpx wrapper for OPS GraphQL (auth + query execution)
- `backend/modules/ops_inbound/ops_adapter.py` — `OPSAdapter(BaseAdapter)` with `discover`, `hydrate_product`, `discover_changed`, `_normalize_ops_payload`
- `backend/tests/test_adapter_registry.py` — registry tests
- `backend/tests/test_ops_adapter.py` — OPSAdapter tests (httpx mocked via respx; uses `ops_decals.json` fixture)
- `backend/tests/test_import_jobs_service.py` — orchestrator tests (auth-fatal vs per-product split)
- `backend/tests/test_import_endpoint.py` — endpoint + BackgroundTasks tests

### Files to modify
- `backend/main.py` — register `modules.import_jobs.routes:router`, import `modules.ops_inbound.ops_adapter` so registry self-registers, append OPS-related supplier seed if needed
- `backend/requirements.txt` — add `respx>=0.21.1` for httpx mocking in tests
- `backend/modules/sync_jobs/models.py` — confirm `errors JSONB` column added in Phase 1 Task 15; if missing, this plan re-adds the migration in Task 1

### Files NOT touched
- `backend/modules/catalog/persistence.py` — Phase 1 deliverable, used as-is
- `backend/modules/ops_push/**` — outbound push pipeline, owned by n8n, untouched
- `backend/modules/promostandards/**` — SanMar/PS adapter is Phase 3
- `frontend/**` — frontend PDP + import button is Phase 5
- `backend/n8n_proxy/**` — orchestration scheduling is Phase 6

---

## Task Breakdown

### Task 1: `BaseAdapter` interface, `ProductRef`, error types

**Files:**
- Create: `backend/modules/import_jobs/__init__.py`
- Create: `backend/modules/import_jobs/base.py`
- Test: `backend/tests/test_adapter_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_adapter_registry.py
"""BaseAdapter contract + adapter registry tests."""
from __future__ import annotations

import pytest

from modules.import_jobs.base import (
    AuthError,
    BaseAdapter,
    DiscoveryMode,
    ProductRef,
    SupplierError,
)


def test_product_ref_carries_supplier_sku_and_optional_part_id():
    ref = ProductRef(supplier_sku="DECAL-131", part_id=None)
    assert ref.supplier_sku == "DECAL-131"
    assert ref.part_id is None
    ref2 = ProductRef(supplier_sku="PC61", part_id="1878771")
    assert ref2.part_id == "1878771"


def test_discovery_mode_enum_values():
    assert DiscoveryMode.EXPLICIT_LIST.value == "explicit_list"
    assert DiscoveryMode.FIRST_N.value == "first_n"
    assert DiscoveryMode.FULL.value == "full"
    assert DiscoveryMode.DELTA.value == "delta"


def test_base_adapter_is_abstract():
    with pytest.raises(TypeError):
        BaseAdapter(supplier=None, db=None)   # cannot instantiate ABC


def test_error_types_inherit_correctly():
    assert issubclass(AuthError, Exception)
    assert issubclass(SupplierError, Exception)
    a = AuthError("bad creds", code="401")
    assert a.code == "401"
    s = SupplierError("not found", code="404")
    assert s.code == "404"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_adapter_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.import_jobs'`.

- [ ] **Step 3: Create the package + base module**

Create `backend/modules/import_jobs/__init__.py` (empty file):

```python
```

Create `backend/modules/import_jobs/base.py`:

```python
"""Adapter interface, shared types, and error hierarchy for supplier imports."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.schemas import ProductIngest
from modules.suppliers.models import Supplier


class DiscoveryMode(StrEnum):
    EXPLICIT_LIST = "explicit_list"
    FIRST_N = "first_n"
    FILTERED_SAMPLE = "filtered_sample"
    FULL = "full"
    DELTA = "delta"
    CLOSEOUTS = "closeouts"


@dataclass(frozen=True)
class ProductRef:
    """Discovery returns these. supplier_sku is mandatory; part_id is PS-only."""
    supplier_sku: str
    part_id: Optional[str] = None


class AdapterError(Exception):
    """Base for all adapter-raised errors."""

    def __init__(self, message: str, *, code: Optional[str] = None) -> None:
        super().__init__(message)
        self.code = code


class AuthError(AdapterError):
    """Authentication / authorization failure. Aborts the entire import job."""


class SupplierError(AdapterError):
    """Per-product error from the supplier. Logged to sync_jobs.errors and skipped."""


class TransientError(AdapterError):
    """Retryable network / 5xx error. Caller decides retry policy."""


class BaseAdapter(ABC):
    """Every supplier adapter implements this contract.

    `product_type` is set by the subclass (apparel | print | template | promo)
    and is used by `persist_product` for detail-row routing.
    """

    product_type: str = "apparel"

    def __init__(self, supplier: Supplier, db: AsyncSession) -> None:
        self.supplier = supplier
        self.db = db

    @abstractmethod
    async def discover(
        self,
        mode: DiscoveryMode,
        *,
        limit: Optional[int] = None,
        explicit_list: Optional[list[str]] = None,
    ) -> list[ProductRef]:
        ...

    @abstractmethod
    async def hydrate_product(self, ref: ProductRef) -> ProductIngest:
        ...

    @abstractmethod
    async def discover_changed(self, since: datetime) -> list[ProductRef]:
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_adapter_registry.py -v`
Expected: PASS — 4 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/import_jobs/__init__.py backend/modules/import_jobs/base.py backend/tests/test_adapter_registry.py
git commit -m "feat(import_jobs): BaseAdapter ABC + ProductRef + error hierarchy"
```

---

### Task 2: Adapter registry

**Files:**
- Create: `backend/modules/import_jobs/registry.py`
- Test: `backend/tests/test_adapter_registry.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_adapter_registry.py`:

```python
@pytest.mark.asyncio
async def test_registry_resolves_supplier_to_adapter_class(seed_supplier, db):
    from modules.import_jobs.base import BaseAdapter
    from modules.import_jobs.registry import (
        ADAPTERS,
        AdapterNotRegisteredError,
        get_adapter,
        register_adapter,
    )

    class FakeAdapter(BaseAdapter):
        product_type = "print"

        async def discover(self, mode, *, limit=None, explicit_list=None):
            return []

        async def hydrate_product(self, ref):
            raise NotImplementedError

        async def discover_changed(self, since):
            return []

    register_adapter("FakeAdapter", FakeAdapter)
    seed_supplier.adapter_class = "FakeAdapter"

    adapter = get_adapter(seed_supplier, db)
    assert isinstance(adapter, FakeAdapter)
    assert adapter.supplier is seed_supplier

    seed_supplier.adapter_class = "DoesNotExist"
    with pytest.raises(AdapterNotRegisteredError):
        get_adapter(seed_supplier, db)


@pytest.mark.asyncio
async def test_registry_rejects_supplier_with_no_adapter_class(seed_supplier, db):
    from modules.import_jobs.registry import (
        AdapterNotConfiguredError,
        get_adapter,
    )
    seed_supplier.adapter_class = None
    with pytest.raises(AdapterNotConfiguredError):
        get_adapter(seed_supplier, db)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_adapter_registry.py::test_registry_resolves_supplier_to_adapter_class tests/test_adapter_registry.py::test_registry_rejects_supplier_with_no_adapter_class -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.import_jobs.registry'`.

- [ ] **Step 3: Create the registry module**

Create `backend/modules/import_jobs/registry.py`:

```python
"""Maps Supplier.adapter_class string -> BaseAdapter subclass.

Adapter modules self-register at import time. main.py imports each adapter
module so the registry is populated by the time routes mount.
"""
from __future__ import annotations

from typing import Type

from sqlalchemy.ext.asyncio import AsyncSession

from modules.suppliers.models import Supplier

from .base import BaseAdapter


class AdapterNotConfiguredError(Exception):
    """supplier.adapter_class is NULL — operator must set one before importing."""


class AdapterNotRegisteredError(Exception):
    """supplier.adapter_class points at a name nobody has registered."""


ADAPTERS: dict[str, Type[BaseAdapter]] = {}


def register_adapter(name: str, cls: Type[BaseAdapter]) -> None:
    if not issubclass(cls, BaseAdapter):
        raise TypeError(f"{cls!r} is not a BaseAdapter subclass")
    ADAPTERS[name] = cls


def get_adapter(supplier: Supplier, db: AsyncSession) -> BaseAdapter:
    if not supplier.adapter_class:
        raise AdapterNotConfiguredError(
            f"Supplier {supplier.id} ({supplier.name}) has no adapter_class set"
        )
    cls = ADAPTERS.get(supplier.adapter_class)
    if cls is None:
        raise AdapterNotRegisteredError(
            f"adapter_class {supplier.adapter_class!r} not registered. "
            f"Known: {sorted(ADAPTERS)}"
        )
    return cls(supplier=supplier, db=db)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_adapter_registry.py -v`
Expected: 6 PASS (4 from Task 1 + 2 here).

- [ ] **Step 5: Commit**

```bash
git add backend/modules/import_jobs/registry.py backend/tests/test_adapter_registry.py
git commit -m "feat(import_jobs): adapter registry resolves supplier.adapter_class"
```

---

### Task 3: `OPSClient` thin httpx wrapper

**Files:**
- Create: `backend/modules/ops_inbound/__init__.py`
- Create: `backend/modules/ops_inbound/ops_client.py`
- Test: `backend/tests/test_ops_adapter.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add `respx` to requirements**

Edit `backend/requirements.txt`, append on its own line:

```
respx>=0.21.1
```

Run: `cd backend && pip install respx>=0.21.1`

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_ops_adapter.py
"""OPSAdapter + OPSClient unit tests. All HTTP mocked via respx — no live OPS hits."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from modules.ops_inbound.ops_client import OPSClient


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_ops_client_executes_graphql_query():
    """OPSClient.query() POSTs JSON to the configured base_url with auth header."""
    base_url = "https://vg.onprintshop.test"
    auth_token = "tok-abc"
    client = OPSClient(base_url=base_url, auth_token=auth_token)

    payload = {"data": {"products": [{"product_id": 1, "product_name": "Test"}]}}
    with respx.mock(base_url=base_url) as router:
        route = router.post("/graphql").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = await client.query("query { products { product_id product_name } }")
        assert route.called
        sent = route.calls[0].request
        body = json.loads(sent.content)
        assert body["query"].startswith("query")
        assert sent.headers["authorization"] == "Bearer tok-abc"
        assert result == {"products": [{"product_id": 1, "product_name": "Test"}]}


@pytest.mark.asyncio
async def test_ops_client_raises_auth_error_on_401():
    from modules.import_jobs.base import AuthError
    client = OPSClient(base_url="https://vg.onprintshop.test", auth_token="bad")
    with respx.mock(base_url="https://vg.onprintshop.test") as router:
        router.post("/graphql").mock(return_value=httpx.Response(401, text="bad"))
        with pytest.raises(AuthError):
            await client.query("query {}")


@pytest.mark.asyncio
async def test_ops_client_raises_supplier_error_on_graphql_errors():
    from modules.import_jobs.base import SupplierError
    client = OPSClient(base_url="https://vg.onprintshop.test", auth_token="t")
    with respx.mock(base_url="https://vg.onprintshop.test") as router:
        router.post("/graphql").mock(
            return_value=httpx.Response(200, json={
                "errors": [{"message": "Product not found", "extensions": {"code": "NOT_FOUND"}}],
            })
        )
        with pytest.raises(SupplierError) as exc_info:
            await client.query("query {}")
        assert "Product not found" in str(exc_info.value)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && pytest tests/test_ops_adapter.py::test_ops_client_executes_graphql_query -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.ops_inbound'`.

- [ ] **Step 4: Create the package + client**

Create `backend/modules/ops_inbound/__init__.py` (empty file):

```python
```

Create `backend/modules/ops_inbound/ops_client.py`:

```python
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
    ) -> None:
        if not base_url:
            raise ValueError("base_url required")
        if not auth_token:
            raise ValueError("auth_token required")
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout

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
        async with httpx.AsyncClient(
            base_url=self.base_url, timeout=self.timeout, headers=headers
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_ops_adapter.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/modules/ops_inbound/__init__.py backend/modules/ops_inbound/ops_client.py backend/tests/test_ops_adapter.py
git commit -m "feat(ops_inbound): OPSClient httpx wrapper with auth/error mapping"
```

---

### Task 4: `OPSAdapter.discover()` with mode dispatch

**Files:**
- Create: `backend/modules/ops_inbound/ops_adapter.py`
- Test: `backend/tests/test_ops_adapter.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_ops_adapter.py`:

```python
@pytest.mark.asyncio
async def test_ops_adapter_discover_explicit_list_skips_graphql(seed_supplier, db):
    """EXPLICIT_LIST mode returns refs without calling OPS at all."""
    from modules.import_jobs.base import DiscoveryMode
    from modules.ops_inbound.ops_adapter import OPSAdapter

    seed_supplier.auth_config = {"auth_token": "tok"}
    seed_supplier.base_url = "https://vg.onprintshop.test"

    adapter = OPSAdapter(supplier=seed_supplier, db=db)
    refs = await adapter.discover(
        DiscoveryMode.EXPLICIT_LIST,
        explicit_list=["131", "262"],
    )
    assert [r.supplier_sku for r in refs] == ["131", "262"]
    assert all(r.part_id is None for r in refs)


@pytest.mark.asyncio
async def test_ops_adapter_discover_first_n_calls_list_products(seed_supplier, db):
    from modules.import_jobs.base import DiscoveryMode
    from modules.ops_inbound.ops_adapter import OPSAdapter

    seed_supplier.auth_config = {"auth_token": "tok"}
    seed_supplier.base_url = "https://vg.onprintshop.test"

    payload = {
        "data": {
            "listProducts": [
                {"product_id": 131},
                {"product_id": 262},
                {"product_id": 444},
            ]
        }
    }
    with respx.mock(base_url="https://vg.onprintshop.test") as router:
        router.post("/graphql").mock(return_value=httpx.Response(200, json=payload))
        adapter = OPSAdapter(supplier=seed_supplier, db=db)
        refs = await adapter.discover(DiscoveryMode.FIRST_N, limit=2)
        assert [r.supplier_sku for r in refs] == ["131", "262"]


@pytest.mark.asyncio
async def test_ops_adapter_discover_full_returns_all(seed_supplier, db):
    from modules.import_jobs.base import DiscoveryMode
    from modules.ops_inbound.ops_adapter import OPSAdapter

    seed_supplier.auth_config = {"auth_token": "tok"}
    seed_supplier.base_url = "https://vg.onprintshop.test"

    payload = {
        "data": {
            "listProducts": [
                {"product_id": 1}, {"product_id": 2}, {"product_id": 3},
            ]
        }
    }
    with respx.mock(base_url="https://vg.onprintshop.test") as router:
        router.post("/graphql").mock(return_value=httpx.Response(200, json=payload))
        adapter = OPSAdapter(supplier=seed_supplier, db=db)
        refs = await adapter.discover(DiscoveryMode.FULL)
        assert len(refs) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_ops_adapter.py::test_ops_adapter_discover_explicit_list_skips_graphql tests/test_ops_adapter.py::test_ops_adapter_discover_first_n_calls_list_products tests/test_ops_adapter.py::test_ops_adapter_discover_full_returns_all -v`
Expected: 3 FAIL — `ModuleNotFoundError: No module named 'modules.ops_inbound.ops_adapter'`.

- [ ] **Step 3: Create the adapter skeleton + discover()**

Create `backend/modules/ops_inbound/ops_adapter.py`:

```python
"""OnPrintShop inbound adapter.

Reads products from OPS GraphQL, normalizes to ProductIngest with
product_type='print', and feeds Phase 1's persist_product. Outbound push
to OPS lives in modules/ops_push and stays untouched here.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from modules.catalog.schemas import (
    ImageIngest,
    OptionAttributeIngest,
    OptionIngest,
    PrintDetailsIngest,
    ProductIngest,
    ProductSizeIngest,
)
from modules.import_jobs.base import (
    AuthError,
    BaseAdapter,
    DiscoveryMode,
    ProductRef,
    SupplierError,
)
from modules.import_jobs.registry import register_adapter

from .ops_client import OPSClient


_LIST_PRODUCTS_QUERY = """
query ListProducts {
  listProducts {
    product_id
  }
}
""".strip()


class OPSAdapter(BaseAdapter):
    product_type = "print"

    def __init__(self, supplier, db) -> None:
        super().__init__(supplier=supplier, db=db)
        if not supplier.base_url:
            raise AuthError("OPS supplier missing base_url")
        token = (supplier.auth_config or {}).get("auth_token")
        if not token:
            raise AuthError("OPS supplier missing auth_token in auth_config")
        self.client = OPSClient(base_url=supplier.base_url, auth_token=token)

    async def discover(
        self,
        mode: DiscoveryMode,
        *,
        limit: Optional[int] = None,
        explicit_list: Optional[list[str]] = None,
    ) -> list[ProductRef]:
        if mode == DiscoveryMode.EXPLICIT_LIST:
            if not explicit_list:
                raise ValueError("EXPLICIT_LIST mode requires explicit_list")
            return [ProductRef(supplier_sku=str(s)) for s in explicit_list]

        if mode in (DiscoveryMode.FIRST_N, DiscoveryMode.FULL):
            data = await self.client.query(_LIST_PRODUCTS_QUERY)
            rows = data.get("listProducts", [])
            refs = [ProductRef(supplier_sku=str(r["product_id"])) for r in rows]
            if mode == DiscoveryMode.FIRST_N and limit is not None:
                refs = refs[:limit]
            return refs

        if mode == DiscoveryMode.DELTA:
            raise NotImplementedError("DELTA discovery comes in Task 8")

        raise ValueError(f"Unsupported discovery mode for OPS: {mode}")

    async def hydrate_product(self, ref: ProductRef) -> ProductIngest:
        raise NotImplementedError("hydrate_product comes in Tasks 5-7")

    async def discover_changed(self, since: datetime) -> list[ProductRef]:
        raise NotImplementedError("discover_changed comes in Task 8")


register_adapter("OPSAdapter", OPSAdapter)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_ops_adapter.py -v`
Expected: all OPS adapter tests so far PASS (3 client + 3 discover = 6).

- [ ] **Step 5: Commit**

```bash
git add backend/modules/ops_inbound/ops_adapter.py backend/tests/test_ops_adapter.py
git commit -m "feat(ops_inbound): OPSAdapter.discover with explicit_list/first_n/full modes"
```

---

### Task 5: `OPSAdapter.hydrate_product()` GraphQL fetch

**Files:**
- Modify: `backend/modules/ops_inbound/ops_adapter.py`
- Test: `backend/tests/test_ops_adapter.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_ops_adapter.py`:

```python
@pytest.mark.asyncio
async def test_ops_adapter_hydrate_product_fetches_full_record(seed_supplier, db):
    from modules.import_jobs.base import ProductRef
    from modules.ops_inbound.ops_adapter import OPSAdapter

    seed_supplier.auth_config = {"auth_token": "tok"}
    seed_supplier.base_url = "https://vg.onprintshop.test"

    raw = json.loads((FIXTURES_DIR / "ops_decals.json").read_text())
    decal = raw[0]   # "Decals - General Performance" product_id=131
    response = {"data": {"getProduct": decal}}

    with respx.mock(base_url="https://vg.onprintshop.test") as router:
        router.post("/graphql").mock(
            return_value=httpx.Response(200, json=response)
        )
        adapter = OPSAdapter(supplier=seed_supplier, db=db)
        ingest = await adapter.hydrate_product(ProductRef(supplier_sku="131"))

    # Top-level product fields
    assert ingest.supplier_sku == "131"
    assert ingest.product_type == "print"
    assert ingest.pricing_method == "formula"
    assert ingest.product_name == "Decals - General Performance"
    assert ingest.ops_product_id == "131"

    # print_details routed correctly
    assert ingest.print_details is not None
    assert ingest.print_details.ops_product_id_int == 131
    assert ingest.print_details.default_category_id == 22
    assert ingest.print_details.external_catalogue == 1

    # sizes
    assert len(ingest.sizes) == len(decal.get("product_size", []))
    assert ingest.sizes[0].size_title == "Custom Size"

    # options: at least 30 in the Decals fixture
    assert len(ingest.options) >= 30
    lam = next(o for o in ingest.options if o.option_key == "lamMaterial")
    assert lam.master_option_id == 59
    assert isinstance(lam.attributes, list)
    assert len(lam.attributes) == 3
    assert all(a.multiplier is not None for a in lam.attributes)

    # images: large + small image present
    urls = [img.url for img in ingest.images]
    assert decal["large_image"] in urls

    # raw_payload preserved
    assert ingest.raw_payload == decal
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_ops_adapter.py::test_ops_adapter_hydrate_product_fetches_full_record -v`
Expected: FAIL — `NotImplementedError`.

- [ ] **Step 3: Implement hydrate + the normalizer**

Edit `backend/modules/ops_inbound/ops_adapter.py`. Add the GraphQL query string above the class:

```python
_GET_PRODUCT_QUERY = """
query GetProduct($id: Int!) {
  getProduct(product_id: $id) {
    product_id
    product_name
    main_sku
    status
    default_category_id
    small_image
    large_image
    externalCatalogue
    description
    brand
    product_size {
      size_id
      size_title
      size_width
      size_height
    }
    product_additional_options {
      master_option_id
      option_key
      title
      options_type
      required
      attributes {
        attribute_id
        master_attribute_id
        attribute_key
        sort_order
        status
        setup_cost
        multiplier
      }
    }
  }
}
""".strip()
```

Replace the `hydrate_product` stub with:

```python
    async def hydrate_product(self, ref: ProductRef) -> ProductIngest:
        product_id_int = int(ref.supplier_sku)
        data = await self.client.query(
            _GET_PRODUCT_QUERY, variables={"id": product_id_int}
        )
        raw = data.get("getProduct")
        if raw is None:
            raise SupplierError(f"OPS product {ref.supplier_sku} not found", code="404")
        return self._normalize_to_ingest(raw)

    def _normalize_to_ingest(self, raw: dict[str, Any]) -> ProductIngest:
        sizes = [
            ProductSizeIngest(
                ops_size_id=s.get("size_id"),
                size_title=s.get("size_title", "Custom Size"),
                size_width=Decimal(str(s.get("size_width", 0) or 0)),
                size_height=Decimal(str(s.get("size_height", 0) or 0)),
            )
            for s in (raw.get("product_size") or [])
        ]

        options: list[OptionIngest] = []
        for opt in raw.get("product_additional_options") or []:
            attrs_src = opt.get("attributes")
            attrs: list[OptionAttributeIngest] = []
            if isinstance(attrs_src, list):
                for a in attrs_src:
                    attrs.append(OptionAttributeIngest(
                        title=a.get("attribute_key", "") or "",
                        sort_order=int(a.get("sort_order", 0) or 0),
                        master_attribute_id=a.get("master_attribute_id"),
                        attribute_key=a.get("attribute_key"),
                        setup_cost=Decimal(str(a.get("setup_cost", 0) or 0)),
                        multiplier=Decimal(str(a.get("multiplier", 0) or 0)),
                    ))
            options.append(OptionIngest(
                option_key=opt["option_key"],
                title=opt.get("title") or opt["option_key"],
                options_type=opt.get("options_type"),
                sort_order=0,
                master_option_id=opt.get("master_option_id"),
                required=bool(opt.get("required") in (True, "1", 1)),
                attributes=attrs,
            ))

        images: list[ImageIngest] = []
        if raw.get("large_image"):
            images.append(ImageIngest(
                url=raw["large_image"], image_type="primary", sort_order=0,
            ))
        if raw.get("small_image"):
            images.append(ImageIngest(
                url=raw["small_image"], image_type="thumbnail", sort_order=1,
            ))

        return ProductIngest(
            supplier_sku=str(raw["product_id"]),
            product_name=raw["product_name"],
            brand=raw.get("brand"),
            description=raw.get("description"),
            product_type="print",
            pricing_method="formula",
            image_url=raw.get("large_image"),
            ops_product_id=str(raw["product_id"]),
            external_catalogue=raw.get("externalCatalogue"),
            print_details=PrintDetailsIngest(
                ops_product_id_int=int(raw["product_id"]),
                default_category_id=raw.get("default_category_id"),
                external_catalogue=raw.get("externalCatalogue"),
            ),
            sizes=sizes,
            options=options,
            images=images,
            raw_payload=raw,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_ops_adapter.py::test_ops_adapter_hydrate_product_fetches_full_record -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/ops_inbound/ops_adapter.py backend/tests/test_ops_adapter.py
git commit -m "feat(ops_inbound): OPSAdapter.hydrate_product + normalize to ProductIngest"
```

---

### Task 6: `OPSAdapter.discover_changed()` for delta sync

**Files:**
- Modify: `backend/modules/ops_inbound/ops_adapter.py`
- Test: `backend/tests/test_ops_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_ops_adapter_discover_changed_filters_by_modified_at(seed_supplier, db):
    from datetime import datetime, timezone
    from modules.ops_inbound.ops_adapter import OPSAdapter

    seed_supplier.auth_config = {"auth_token": "tok"}
    seed_supplier.base_url = "https://vg.onprintshop.test"

    response = {
        "data": {
            "listProductsModifiedSince": [
                {"product_id": 131},
                {"product_id": 262},
            ]
        }
    }
    since = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
    with respx.mock(base_url="https://vg.onprintshop.test") as router:
        route = router.post("/graphql").mock(
            return_value=httpx.Response(200, json=response)
        )
        adapter = OPSAdapter(supplier=seed_supplier, db=db)
        refs = await adapter.discover_changed(since)
        assert route.called
        body = json.loads(route.calls[0].request.content)
        assert body["variables"]["since"] == since.isoformat()
        assert [r.supplier_sku for r in refs] == ["131", "262"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_ops_adapter.py::test_ops_adapter_discover_changed_filters_by_modified_at -v`
Expected: FAIL — `NotImplementedError`.

- [ ] **Step 3: Implement discover_changed**

In `backend/modules/ops_inbound/ops_adapter.py`, add the query above the class:

```python
_LIST_MODIFIED_QUERY = """
query ListModifiedSince($since: String!) {
  listProductsModifiedSince(since: $since) {
    product_id
  }
}
""".strip()
```

Replace the `discover_changed` stub:

```python
    async def discover_changed(self, since: datetime) -> list[ProductRef]:
        data = await self.client.query(
            _LIST_MODIFIED_QUERY, variables={"since": since.isoformat()}
        )
        rows = data.get("listProductsModifiedSince") or []
        return [ProductRef(supplier_sku=str(r["product_id"])) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_ops_adapter.py::test_ops_adapter_discover_changed_filters_by_modified_at -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/ops_inbound/ops_adapter.py backend/tests/test_ops_adapter.py
git commit -m "feat(ops_inbound): OPSAdapter.discover_changed for delta sync"
```

---

### Task 7: `run_import` orchestrator skeleton + auth-fatal handling

**Files:**
- Create: `backend/modules/import_jobs/service.py`
- Test: `backend/tests/test_import_jobs_service.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_import_jobs_service.py
"""Import-job orchestrator tests. Auth = fatal abort. Per-product = log + continue."""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from modules.import_jobs.base import (
    AuthError,
    BaseAdapter,
    DiscoveryMode,
    ProductRef,
    SupplierError,
)
from modules.import_jobs.registry import register_adapter
from modules.import_jobs.service import run_import
from modules.suppliers.models import Supplier
from modules.sync_jobs.models import SyncJob


class _AuthFailAdapter(BaseAdapter):
    product_type = "print"

    async def discover(self, mode, *, limit=None, explicit_list=None):
        raise AuthError("bad creds", code="401")

    async def hydrate_product(self, ref):
        raise NotImplementedError

    async def discover_changed(self, since):
        return []


@pytest.mark.asyncio
async def test_run_import_auth_error_marks_job_failed(seed_supplier: Supplier):
    register_adapter("AuthFailAdapter", _AuthFailAdapter)
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "AuthFailAdapter"
        await s.commit()

    sync_job_id = await run_import(
        supplier_id=seed_supplier.id,
        mode=DiscoveryMode.FULL,
    )

    async with async_session() as s:
        job = await s.get(SyncJob, sync_job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.records_processed == 0
        assert job.errors and any(
            "bad creds" in (e.get("msg") or "") for e in job.errors
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_import_jobs_service.py::test_run_import_auth_error_marks_job_failed -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.import_jobs.service'`.

- [ ] **Step 3: Implement the orchestrator**

Create `backend/modules/import_jobs/service.py`:

```python
"""Drives a supplier import:
   resolve adapter -> discover -> hydrate -> persist -> record sync_jobs.

Auth errors abort and mark the job 'failed'.
Per-product errors continue the loop and are logged to sync_jobs.errors[].
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from modules.catalog.persistence import (
    PersistError,
    persist_product,
)
from modules.suppliers.models import Supplier
from modules.sync_jobs.models import SyncJob

from .base import (
    AdapterError,
    AuthError,
    DiscoveryMode,
    SupplierError,
    TransientError,
)
from .registry import (
    AdapterNotConfiguredError,
    AdapterNotRegisteredError,
    get_adapter,
)


log = logging.getLogger("import_jobs")


async def run_import(
    *,
    supplier_id: uuid.UUID,
    mode: DiscoveryMode,
    limit: Optional[int] = None,
    explicit_list: Optional[list[str]] = None,
) -> uuid.UUID:
    """Run an import end-to-end. Returns the sync_job id.

    Opens its own DB session (so it can be invoked from BackgroundTasks
    without a request-scoped session leaking past response time).
    """
    async with async_session() as db:
        supplier = await db.get(Supplier, supplier_id)
        if supplier is None:
            raise ValueError(f"supplier {supplier_id} not found")

        job = SyncJob(
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            job_type=f"import:{mode.value}",
            status="running",
            started_at=datetime.now(timezone.utc),
            records_processed=0,
            errors=None,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

        errors: list[dict] = []

        try:
            adapter = get_adapter(supplier, db)
        except (AdapterNotConfiguredError, AdapterNotRegisteredError) as e:
            errors.append({"phase": "registry", "msg": str(e)})
            await _finalize_job(db, job, status="failed", errors=errors)
            return job_id

        try:
            refs = await adapter.discover(
                mode, limit=limit, explicit_list=explicit_list,
            )
        except AuthError as e:
            errors.append({"phase": "discover", "code": e.code, "msg": str(e)})
            await _finalize_job(db, job, status="failed", errors=errors)
            return job_id
        except (SupplierError, TransientError, AdapterError) as e:
            errors.append({"phase": "discover", "code": getattr(e, "code", None), "msg": str(e)})
            await _finalize_job(db, job, status="failed", errors=errors)
            return job_id

        success_count = 0
        for ref in refs:
            try:
                ingest = await adapter.hydrate_product(ref)
                await persist_product(ingest, supplier, db)
                await db.commit()
                success_count += 1
            except AuthError as e:
                # Mid-loop auth = still fatal.
                errors.append({"phase": "hydrate", "ref": ref.supplier_sku, "code": e.code, "msg": str(e)})
                await db.rollback()
                await _finalize_job(db, job, status="failed", errors=errors, processed=success_count)
                return job_id
            except (SupplierError, TransientError, PersistError, AdapterError) as e:
                errors.append({
                    "phase": "hydrate",
                    "ref": ref.supplier_sku,
                    "code": getattr(e, "code", None),
                    "msg": str(e),
                })
                await db.rollback()
            except Exception as e:                              # noqa: BLE001
                # Unexpected — log + continue but track in errors[].
                log.exception("unexpected per-product error: %s", e)
                errors.append({"phase": "hydrate", "ref": ref.supplier_sku, "msg": str(e)})
                await db.rollback()

        status = (
            "success" if not errors
            else "failed" if success_count == 0
            else "partial_success"
        )
        await _finalize_job(
            db, job, status=status, errors=errors or None, processed=success_count,
        )
        return job_id


async def _finalize_job(
    db: AsyncSession,
    job: SyncJob,
    *,
    status: str,
    errors: Optional[list[dict]] = None,
    processed: int = 0,
) -> None:
    job.status = status
    job.errors = errors
    job.records_processed = processed
    job.finished_at = datetime.now(timezone.utc)
    await db.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_import_jobs_service.py::test_run_import_auth_error_marks_job_failed -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/import_jobs/service.py backend/tests/test_import_jobs_service.py
git commit -m "feat(import_jobs): run_import orchestrator with auth-fatal handling"
```

---

### Task 8: Per-product error path + partial_success

**Files:**
- Test: `backend/tests/test_import_jobs_service.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_import_jobs_service.py`:

```python
class _MixedAdapter(BaseAdapter):
    product_type = "print"

    async def discover(self, mode, *, limit=None, explicit_list=None):
        return [
            ProductRef(supplier_sku="OK-1"),
            ProductRef(supplier_sku="BAD-1"),
            ProductRef(supplier_sku="OK-2"),
        ]

    async def hydrate_product(self, ref):
        from modules.catalog.schemas import (
            PrintDetailsIngest, ProductIngest,
        )
        if ref.supplier_sku == "BAD-1":
            raise SupplierError("not found", code="404")
        return ProductIngest(
            supplier_sku=ref.supplier_sku,
            product_name=f"product {ref.supplier_sku}",
            product_type="print",
            pricing_method="formula",
            print_details=PrintDetailsIngest(),
        )

    async def discover_changed(self, since):
        return []


@pytest.mark.asyncio
async def test_run_import_continues_after_per_product_error(seed_supplier: Supplier):
    register_adapter("MixedAdapter", _MixedAdapter)
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "MixedAdapter"
        await s.commit()

    sync_job_id = await run_import(
        supplier_id=seed_supplier.id, mode=DiscoveryMode.FULL,
    )

    async with async_session() as s:
        job = await s.get(SyncJob, sync_job_id)
        assert job.status == "partial_success"
        assert job.records_processed == 2
        assert job.errors is not None and len(job.errors) == 1
        assert job.errors[0]["ref"] == "BAD-1"


@pytest.mark.asyncio
async def test_run_import_success_when_no_errors(seed_supplier: Supplier):
    class _OkAdapter(BaseAdapter):
        product_type = "print"

        async def discover(self, mode, *, limit=None, explicit_list=None):
            return [ProductRef(supplier_sku="OK-1")]

        async def hydrate_product(self, ref):
            from modules.catalog.schemas import (
                PrintDetailsIngest, ProductIngest,
            )
            return ProductIngest(
                supplier_sku=ref.supplier_sku,
                product_name="ok",
                product_type="print",
                pricing_method="formula",
                print_details=PrintDetailsIngest(),
            )

        async def discover_changed(self, since):
            return []

    register_adapter("OkAdapter", _OkAdapter)
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "OkAdapter"
        await s.commit()

    sync_job_id = await run_import(
        supplier_id=seed_supplier.id, mode=DiscoveryMode.FULL,
    )

    async with async_session() as s:
        job = await s.get(SyncJob, sync_job_id)
        assert job.status == "success"
        assert job.records_processed == 1
        assert job.errors is None
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_import_jobs_service.py -v`
Expected: 3 PASS (auth-fail from Task 7 + these 2). The orchestrator already implements the partial_success path; these tests just confirm it.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_import_jobs_service.py
git commit -m "test(import_jobs): per-product error logged + partial_success accounting"
```

---

### Task 9: `ImportRequest`/`ImportResponse` schemas

**Files:**
- Create: `backend/modules/import_jobs/schemas.py`
- Test: `backend/tests/test_import_endpoint.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_import_endpoint.py
"""POST /api/suppliers/{id}/import endpoint tests."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_import_request_validates_mode_and_limit():
    from pydantic import ValidationError
    from modules.import_jobs.schemas import ImportRequest

    ok = ImportRequest(mode="full", limit=10)
    assert ok.mode == "full"
    assert ok.limit == 10

    explicit = ImportRequest(mode="explicit_list", explicit_list=["131", "262"])
    assert explicit.explicit_list == ["131", "262"]

    with pytest.raises(ValidationError):
        ImportRequest(mode="not_a_mode")

    with pytest.raises(ValidationError):
        # explicit_list mode requires list
        ImportRequest(mode="explicit_list")

    with pytest.raises(ValidationError):
        # negative limit
        ImportRequest(mode="first_n", limit=-1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_import_endpoint.py::test_import_request_validates_mode_and_limit -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.import_jobs.schemas'`.

- [ ] **Step 3: Create the schemas**

Create `backend/modules/import_jobs/schemas.py`:

```python
"""Pydantic models for the manual import endpoint."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .base import DiscoveryMode


class ImportRequest(BaseModel):
    mode: DiscoveryMode = DiscoveryMode.FIRST_N
    limit: Optional[int] = Field(default=20, ge=1, le=10000)
    explicit_list: Optional[list[str]] = None

    @model_validator(mode="after")
    def _check_mode(self) -> "ImportRequest":
        if self.mode == DiscoveryMode.EXPLICIT_LIST and not self.explicit_list:
            raise ValueError("mode=explicit_list requires explicit_list")
        return self


class ImportResponse(BaseModel):
    sync_job_id: UUID
    supplier_id: UUID
    mode: DiscoveryMode
    accepted_at: str   # ISO 8601 timestamp
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_import_endpoint.py::test_import_request_validates_mode_and_limit -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/import_jobs/schemas.py backend/tests/test_import_endpoint.py
git commit -m "feat(import_jobs): ImportRequest/ImportResponse schemas"
```

---

### Task 10: `POST /api/suppliers/{id}/import` endpoint with BackgroundTasks

**Files:**
- Create: `backend/modules/import_jobs/routes.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_import_endpoint.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_import_endpoint.py`:

```python
import json
from pathlib import Path

import httpx
import respx
from sqlalchemy import select

from database import async_session
from modules.import_jobs.base import BaseAdapter, ProductRef
from modules.import_jobs.registry import register_adapter
from modules.suppliers.models import Supplier
from modules.sync_jobs.models import SyncJob


@pytest.mark.asyncio
async def test_import_endpoint_returns_202_and_records_job(client, seed_supplier):
    class _StaticAdapter(BaseAdapter):
        product_type = "print"

        async def discover(self, mode, *, limit=None, explicit_list=None):
            return [ProductRef(supplier_sku="STATIC-1")]

        async def hydrate_product(self, ref):
            from modules.catalog.schemas import PrintDetailsIngest, ProductIngest
            return ProductIngest(
                supplier_sku=ref.supplier_sku,
                product_name="static",
                product_type="print",
                pricing_method="formula",
                print_details=PrintDetailsIngest(),
            )

        async def discover_changed(self, since):
            return []

    register_adapter("StaticAdapter", _StaticAdapter)

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "StaticAdapter"
        await s.commit()

    resp = await client.post(
        f"/api/suppliers/{seed_supplier.id}/import",
        json={"mode": "first_n", "limit": 5},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert "sync_job_id" in body
    assert body["supplier_id"] == str(seed_supplier.id)
    assert body["mode"] == "first_n"

    # BackgroundTasks runs after the response. Poll for completion.
    sync_job_id = body["sync_job_id"]
    async with async_session() as s:
        # The bg task may still be running; httpx ASGITransport does drain
        # background tasks before returning, but assert defensively.
        job = await s.get(SyncJob, sync_job_id)
        assert job is not None
        assert job.status in ("running", "success", "partial_success", "failed")


@pytest.mark.asyncio
async def test_import_endpoint_rejects_unknown_supplier(client):
    import uuid
    fake_id = uuid.uuid4()
    resp = await client.post(f"/api/suppliers/{fake_id}/import", json={"mode": "full"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_import_endpoint_rejects_supplier_without_adapter(client, seed_supplier):
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = None
        await s.commit()

    resp = await client.post(
        f"/api/suppliers/{seed_supplier.id}/import", json={"mode": "full"}
    )
    assert resp.status_code == 409
    assert "adapter_class" in resp.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_import_endpoint.py -v`
Expected: 3 FAIL — endpoint not registered.

- [ ] **Step 3: Create the routes**

Create `backend/modules/import_jobs/routes.py`:

```python
"""Manual import endpoint. Returns 202 + sync_job_id; work runs in background."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.suppliers.models import Supplier

from .schemas import ImportRequest, ImportResponse
from .service import run_import


router = APIRouter(prefix="/api/suppliers", tags=["import_jobs"])


@router.post("/{supplier_id}/import", response_model=ImportResponse, status_code=202)
async def trigger_import(
    supplier_id: uuid.UUID,
    body: ImportRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ImportResponse:
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(404, f"supplier {supplier_id} not found")
    if not supplier.adapter_class:
        raise HTTPException(
            409,
            f"supplier {supplier.name!r} has no adapter_class set; "
            f"configure one before importing",
        )

    # Pre-create the sync_job synchronously so the caller can poll it.
    # The orchestrator will load it again and update status from there.
    job_id = uuid.uuid4()

    background.add_task(
        run_import,
        supplier_id=supplier_id,
        mode=body.mode,
        limit=body.limit,
        explicit_list=body.explicit_list,
    )
    return ImportResponse(
        sync_job_id=job_id,                   # placeholder; orchestrator creates real one
        supplier_id=supplier_id,
        mode=body.mode,
        accepted_at=datetime.now(timezone.utc).isoformat(),
    )
```

NOTE: `sync_job_id` returned here is a placeholder UUID — the orchestrator creates the real `SyncJob` row inside `run_import`. Task 11 fixes this by returning the real id (we run the discover phase synchronously enough to mint a real job row, then dispatch hydration to background).

- [ ] **Step 4: Wire the router into main.py**

Edit `backend/main.py`:

a) In the model/route imports block, add after the existing module imports:

```python
import modules.ops_inbound.ops_adapter  # noqa: F401  registers OPSAdapter
from modules.import_jobs.routes import router as import_jobs_router
```

b) Where other routers are mounted (`app.include_router(...)`), add:

```python
app.include_router(import_jobs_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_import_endpoint.py -v`
Expected: PASS for the 404 + 409 cases. The 202 case may still fail because `sync_job_id` is fake — that is wired up in Task 11. Skip the assertion on `body == real job id` for now; the test only asserts the field is present.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/import_jobs/routes.py backend/main.py backend/tests/test_import_endpoint.py
git commit -m "feat(import_jobs): POST /api/suppliers/{id}/import endpoint"
```

---

### Task 11: Return the real `sync_job_id` to the caller

**Files:**
- Modify: `backend/modules/import_jobs/service.py`
- Modify: `backend/modules/import_jobs/routes.py`
- Test: `backend/tests/test_import_endpoint.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_import_endpoint.py`:

```python
@pytest.mark.asyncio
async def test_import_endpoint_returns_real_sync_job_id_that_appears_in_db(
    client, seed_supplier,
):
    class _NoopAdapter(BaseAdapter):
        product_type = "print"

        async def discover(self, mode, *, limit=None, explicit_list=None):
            return []   # discover returns empty -> success

        async def hydrate_product(self, ref):
            from modules.catalog.schemas import PrintDetailsIngest, ProductIngest
            return ProductIngest(
                supplier_sku=ref.supplier_sku,
                product_name="x",
                product_type="print",
                pricing_method="formula",
                print_details=PrintDetailsIngest(),
            )

        async def discover_changed(self, since):
            return []

    register_adapter("NoopAdapter", _NoopAdapter)
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "NoopAdapter"
        await s.commit()

    resp = await client.post(
        f"/api/suppliers/{seed_supplier.id}/import",
        json={"mode": "full"},
    )
    assert resp.status_code == 202
    job_id = resp.json()["sync_job_id"]

    async with async_session() as s:
        job = await s.get(SyncJob, job_id)
        assert job is not None
        # Either the bg task already ran (status success) or it is still running.
        assert job.status in ("running", "success")
        assert str(job.supplier_id) == str(seed_supplier.id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_import_endpoint.py::test_import_endpoint_returns_real_sync_job_id_that_appears_in_db -v`
Expected: FAIL — fake UUID does not resolve to a SyncJob row.

- [ ] **Step 3: Split job-creation from job-execution**

Edit `backend/modules/import_jobs/service.py`. Add a helper that creates the `SyncJob` row up front and a separate function that runs the import against an existing job id:

```python
async def create_pending_import_job(
    *,
    supplier_id: uuid.UUID,
    mode: DiscoveryMode,
) -> uuid.UUID:
    """Create a queued sync_job synchronously so the caller can poll it."""
    async with async_session() as db:
        supplier = await db.get(Supplier, supplier_id)
        if supplier is None:
            raise ValueError(f"supplier {supplier_id} not found")
        job = SyncJob(
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            job_type=f"import:{mode.value}",
            status="queued",
            started_at=datetime.now(timezone.utc),
            records_processed=0,
            errors=None,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job.id


async def run_existing_import_job(
    *,
    job_id: uuid.UUID,
    supplier_id: uuid.UUID,
    mode: DiscoveryMode,
    limit: Optional[int] = None,
    explicit_list: Optional[list[str]] = None,
) -> None:
    """Execute the work of an already-created sync_job."""
    async with async_session() as db:
        supplier = await db.get(Supplier, supplier_id)
        job = await db.get(SyncJob, job_id)
        if supplier is None or job is None:
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await db.commit()

        errors: list[dict] = []
        try:
            adapter = get_adapter(supplier, db)
        except (AdapterNotConfiguredError, AdapterNotRegisteredError) as e:
            errors.append({"phase": "registry", "msg": str(e)})
            await _finalize_job(db, job, status="failed", errors=errors)
            return

        try:
            refs = await adapter.discover(
                mode, limit=limit, explicit_list=explicit_list,
            )
        except AuthError as e:
            errors.append({"phase": "discover", "code": e.code, "msg": str(e)})
            await _finalize_job(db, job, status="failed", errors=errors)
            return
        except (SupplierError, TransientError, AdapterError) as e:
            errors.append({"phase": "discover", "code": getattr(e, "code", None), "msg": str(e)})
            await _finalize_job(db, job, status="failed", errors=errors)
            return

        success_count = 0
        for ref in refs:
            try:
                ingest = await adapter.hydrate_product(ref)
                await persist_product(ingest, supplier, db)
                await db.commit()
                success_count += 1
            except AuthError as e:
                errors.append({"phase": "hydrate", "ref": ref.supplier_sku, "code": e.code, "msg": str(e)})
                await db.rollback()
                await _finalize_job(db, job, status="failed", errors=errors, processed=success_count)
                return
            except (SupplierError, TransientError, PersistError, AdapterError) as e:
                errors.append({
                    "phase": "hydrate", "ref": ref.supplier_sku,
                    "code": getattr(e, "code", None), "msg": str(e),
                })
                await db.rollback()
            except Exception as e:                              # noqa: BLE001
                log.exception("unexpected per-product error: %s", e)
                errors.append({"phase": "hydrate", "ref": ref.supplier_sku, "msg": str(e)})
                await db.rollback()

        status = (
            "success" if not errors
            else "failed" if success_count == 0
            else "partial_success"
        )
        await _finalize_job(
            db, job, status=status, errors=errors or None, processed=success_count,
        )
```

Update the original `run_import` to use the split (so its tests still pass):

```python
async def run_import(
    *,
    supplier_id: uuid.UUID,
    mode: DiscoveryMode,
    limit: Optional[int] = None,
    explicit_list: Optional[list[str]] = None,
) -> uuid.UUID:
    job_id = await create_pending_import_job(supplier_id=supplier_id, mode=mode)
    await run_existing_import_job(
        job_id=job_id,
        supplier_id=supplier_id,
        mode=mode,
        limit=limit,
        explicit_list=explicit_list,
    )
    return job_id
```

- [ ] **Step 4: Update the route to mint the real id, dispatch only the runner**

Edit `backend/modules/import_jobs/routes.py`. Replace `trigger_import`:

```python
from .service import create_pending_import_job, run_existing_import_job


@router.post("/{supplier_id}/import", response_model=ImportResponse, status_code=202)
async def trigger_import(
    supplier_id: uuid.UUID,
    body: ImportRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ImportResponse:
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(404, f"supplier {supplier_id} not found")
    if not supplier.adapter_class:
        raise HTTPException(
            409,
            f"supplier {supplier.name!r} has no adapter_class set; "
            f"configure one before importing",
        )

    job_id = await create_pending_import_job(supplier_id=supplier_id, mode=body.mode)

    background.add_task(
        run_existing_import_job,
        job_id=job_id,
        supplier_id=supplier_id,
        mode=body.mode,
        limit=body.limit,
        explicit_list=body.explicit_list,
    )

    return ImportResponse(
        sync_job_id=job_id,
        supplier_id=supplier_id,
        mode=body.mode,
        accepted_at=datetime.now(timezone.utc).isoformat(),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_import_endpoint.py tests/test_import_jobs_service.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/import_jobs/service.py backend/modules/import_jobs/routes.py backend/tests/test_import_endpoint.py
git commit -m "feat(import_jobs): mint real sync_job_id sync, run hydrate in background"
```

---

### Task 12: Concurrency guard — reject second import for same supplier+mode

**Files:**
- Modify: `backend/modules/import_jobs/routes.py`
- Test: `backend/tests/test_import_endpoint.py`

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_import_endpoint_rejects_when_running_job_exists_same_mode(
    client, seed_supplier,
):
    """409 if a 'running' or 'queued' job already exists for this supplier+mode."""
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "NoopAdapter"
        await s.commit()

        running = SyncJob(
            supplier_id=seed_supplier.id,
            supplier_name=seed_supplier.name,
            job_type="import:full",
            status="running",
            started_at=datetime.now(timezone.utc) if False else None,
            records_processed=0,
        )
        # status='running' has a not-null started_at constraint? If yes:
        from datetime import datetime, timezone
        running.started_at = datetime.now(timezone.utc)
        s.add(running)
        await s.commit()

    resp = await client.post(
        f"/api/suppliers/{seed_supplier.id}/import",
        json={"mode": "full"},
    )
    assert resp.status_code == 409
    assert "already running" in resp.text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_import_endpoint.py::test_import_endpoint_rejects_when_running_job_exists_same_mode -v`
Expected: FAIL — endpoint accepts the second request with 202.

- [ ] **Step 3: Add the concurrency check**

Edit `backend/modules/import_jobs/routes.py`. Inside `trigger_import`, after the `409 adapter_class` check, add:

```python
    from sqlalchemy import select
    from modules.sync_jobs.models import SyncJob

    in_flight = (await db.execute(
        select(SyncJob.id).where(
            SyncJob.supplier_id == supplier_id,
            SyncJob.job_type == f"import:{body.mode.value}",
            SyncJob.status.in_(("queued", "running")),
        ).limit(1)
    )).scalar_one_or_none()
    if in_flight is not None:
        raise HTTPException(
            409,
            f"import already running for supplier {supplier.name!r} mode {body.mode.value!r} (job {in_flight})",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_import_endpoint.py::test_import_endpoint_rejects_when_running_job_exists_same_mode -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/import_jobs/routes.py backend/tests/test_import_endpoint.py
git commit -m "feat(import_jobs): 409 when same-mode import already running for supplier"
```

---

### Task 13: End-to-end test — full OPS Decals import via mocked GraphQL

**Files:**
- Test: `backend/tests/test_import_endpoint.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_import_endpoint.py`:

```python
@pytest.mark.asyncio
async def test_e2e_ops_import_persists_decals_via_endpoint(client, seed_supplier):
    """Hits POST /api/suppliers/{id}/import, drives OPSAdapter against mocked
    GraphQL serving the on-disk Decals fixture, then asserts persisted shape."""
    from modules.catalog.models import (
        PrintDetails,
        Product,
        ProductOption,
        ProductSize,
    )

    base_url = "https://vg.onprintshop.test"
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "OPSAdapter"
        loaded.base_url = base_url
        loaded.auth_config = {"auth_token": "tok-e2e"}
        await s.commit()

    fixtures_dir = Path(__file__).parent / "fixtures"
    raw_list = json.loads((fixtures_dir / "ops_decals.json").read_text())

    list_response = {
        "data": {
            "listProducts": [
                {"product_id": p["product_id"]} for p in raw_list
            ]
        }
    }

    def get_product_response(product_id: int) -> dict:
        match = next(p for p in raw_list if p["product_id"] == product_id)
        return {"data": {"getProduct": match}}

    with respx.mock(base_url=base_url) as router:
        def _route(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            q = payload["query"]
            if q.startswith("query ListProducts"):
                return httpx.Response(200, json=list_response)
            if q.startswith("query GetProduct"):
                pid = int(payload["variables"]["id"])
                return httpx.Response(200, json=get_product_response(pid))
            return httpx.Response(400, json={"errors": [{"message": "unknown"}]})

        router.post("/graphql").mock(side_effect=_route)

        resp = await client.post(
            f"/api/suppliers/{seed_supplier.id}/import",
            json={"mode": "first_n", "limit": len(raw_list)},
        )

    assert resp.status_code == 202, resp.text
    job_id = resp.json()["sync_job_id"]

    # Poll job to terminal state. ASGITransport drains BackgroundTasks before
    # returning, but be defensive in case it doesn't.
    import asyncio
    for _ in range(20):
        async with async_session() as s:
            job = await s.get(SyncJob, job_id)
            if job and job.status in ("success", "partial_success", "failed"):
                break
        await asyncio.sleep(0.2)

    async with async_session() as s:
        job = await s.get(SyncJob, job_id)
        assert job.status == "success", f"errors: {job.errors}"
        assert job.records_processed == len(raw_list)

        products = (await s.execute(
            select(Product).where(Product.supplier_id == seed_supplier.id)
        )).scalars().all()
        assert len(products) == len(raw_list)
        for p in products:
            assert p.product_type == "print"
            assert p.pricing_method == "formula"

            details = await s.get(PrintDetails, p.id)
            assert details is not None
            assert details.ops_product_id_int == int(p.supplier_sku)

            sizes = (await s.execute(
                select(ProductSize).where(ProductSize.product_id == p.id)
            )).scalars().all()
            assert len(sizes) >= 1

            options = (await s.execute(
                select(ProductOption).where(ProductOption.product_id == p.id)
            )).scalars().all()
            assert len(options) >= 30
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd backend && pytest tests/test_import_endpoint.py::test_e2e_ops_import_persists_decals_via_endpoint -v`
Expected: PASS — every other piece is in place.

If it fails because `BackgroundTasks` isn't drained inline by `ASGITransport`, the polling loop should pick up the terminal status; if it still fails, drop the loop count to 1 and call `await asyncio.sleep(2.0)` once before the assertion.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_import_endpoint.py
git commit -m "test(import_jobs): E2E OPS Decals import via mocked GraphQL + endpoint"
```

---

### Task 14: Set `last_full_sync` / `last_delta_sync` on success

**Files:**
- Modify: `backend/modules/import_jobs/service.py`
- Test: `backend/tests/test_import_jobs_service.py`

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_run_import_full_sets_last_full_sync(seed_supplier: Supplier):
    register_adapter("NoopAdapter2", _NoopAdapter2 := type("_NoopAdapter2", (BaseAdapter,), {
        "product_type": "print",
        "discover": lambda self, mode, *, limit=None, explicit_list=None: __import__("asyncio").sleep(0, result=[]),
        "hydrate_product": lambda self, ref: (_ for _ in ()).throw(NotImplementedError),
        "discover_changed": lambda self, since: __import__("asyncio").sleep(0, result=[]),
    }))
    # Easier: use the inline class style instead
```

That metaprogramming trick is fragile; rewrite:

```python
class _EmptyDiscoverAdapter(BaseAdapter):
    product_type = "print"

    async def discover(self, mode, *, limit=None, explicit_list=None):
        return []

    async def hydrate_product(self, ref):
        raise NotImplementedError

    async def discover_changed(self, since):
        return []


@pytest.mark.asyncio
async def test_run_import_full_sets_last_full_sync_on_supplier(seed_supplier: Supplier):
    register_adapter("EmptyDiscoverAdapter", _EmptyDiscoverAdapter)
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "EmptyDiscoverAdapter"
        loaded.last_full_sync = None
        await s.commit()

    job_id = await run_import(
        supplier_id=seed_supplier.id, mode=DiscoveryMode.FULL,
    )

    async with async_session() as s:
        sup = await s.get(Supplier, seed_supplier.id)
        assert sup.last_full_sync is not None
        assert sup.last_delta_sync is None


@pytest.mark.asyncio
async def test_run_import_delta_sets_last_delta_sync(seed_supplier: Supplier):
    register_adapter("EmptyDiscoverAdapter", _EmptyDiscoverAdapter)
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "EmptyDiscoverAdapter"
        loaded.last_delta_sync = None
        await s.commit()

    job_id = await run_import(
        supplier_id=seed_supplier.id, mode=DiscoveryMode.DELTA,
    )
    async with async_session() as s:
        sup = await s.get(Supplier, seed_supplier.id)
        assert sup.last_delta_sync is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_import_jobs_service.py::test_run_import_full_sets_last_full_sync_on_supplier tests/test_import_jobs_service.py::test_run_import_delta_sets_last_delta_sync -v`
Expected: FAIL — service does not stamp those columns.

- [ ] **Step 3: Stamp the timestamps in `_finalize_job`**

Edit `backend/modules/import_jobs/service.py`. Update `_finalize_job` to take the supplier + mode and stamp accordingly:

```python
async def _finalize_job(
    db: AsyncSession,
    job: SyncJob,
    *,
    status: str,
    errors: Optional[list[dict]] = None,
    processed: int = 0,
    supplier: Optional[Supplier] = None,
    mode: Optional[DiscoveryMode] = None,
) -> None:
    job.status = status
    job.errors = errors
    job.records_processed = processed
    job.finished_at = datetime.now(timezone.utc)

    if status in ("success", "partial_success") and supplier is not None and mode is not None:
        now = datetime.now(timezone.utc)
        if mode == DiscoveryMode.FULL:
            supplier.last_full_sync = now
        elif mode == DiscoveryMode.DELTA:
            supplier.last_delta_sync = now

    await db.commit()
```

Update every `_finalize_job` call site in `service.py` (both `run_existing_import_job` paths and the legacy `run_import` flow if still present) to pass `supplier=supplier, mode=mode`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_import_jobs_service.py -v`
Expected: all PASS (Tasks 7-8 + these 2).

- [ ] **Step 5: Commit**

```bash
git add backend/modules/import_jobs/service.py backend/tests/test_import_jobs_service.py
git commit -m "feat(import_jobs): stamp last_full_sync / last_delta_sync on success"
```

---

### Task 15: Final regression sweep + ops-adapter runbook

**Files:**
- Create: `backend/docs/ops_inbound_adapter_runbook.md`
- Test: full backend suite

- [ ] **Step 1: Run the full backend test suite**

Run: `cd backend && pytest tests/ -v`
Expected: all PASS. Fix any unrelated breakage in a separate commit (do not bury it inside the Phase 2 series).

- [ ] **Step 2: Write the runbook**

Create `backend/docs/ops_inbound_adapter_runbook.md`:

```markdown
# OPS Inbound Adapter — Operations Runbook

## What this gives you
- `OPSAdapter` reads OnPrintShop products via GraphQL (`listProducts`,
  `getProduct`, `listProductsModifiedSince`) and feeds them through the
  polymorphic `persist_product` from Phase 1.
- `POST /api/suppliers/{id}/import` queues an import job, returns a real
  `sync_job_id` immediately, and runs hydration in a FastAPI BackgroundTask.
- `GET /api/sync-jobs/{id}` (already shipped) lets the caller poll status.

## Configuring an OPS supplier
```sql
update suppliers
   set adapter_class = 'OPSAdapter',
       base_url      = 'https://<storefront>.onprintshop.com',
       auth_config   = jsonb_build_object('auth_token', '<bearer-token>')
 where id = '<supplier-uuid>';
```

## Triggering an import
```bash
curl -X POST http://localhost:8000/api/suppliers/$ID/import \
     -H 'content-type: application/json' \
     -d '{"mode": "first_n", "limit": 20}'
```

Modes:
- `explicit_list` — `{"mode": "explicit_list", "explicit_list": ["131", "262"]}`
- `first_n`       — `{"mode": "first_n", "limit": 20}`
- `full`          — `{"mode": "full"}`
- `delta`         — `{"mode": "delta"}` (uses `listProductsModifiedSince`)

## Status semantics
| Status | Meaning |
|--------|---------|
| `queued` | Endpoint accepted, BG task not started yet. |
| `running` | BG task in flight. |
| `success` | All products hydrated + persisted. `last_full_sync` / `last_delta_sync` updated. |
| `partial_success` | At least one product persisted; per-product errors in `sync_jobs.errors[]`. |
| `failed` | Auth error or zero products persisted. See `sync_jobs.errors[]`. |

## Concurrency
A second `POST /api/suppliers/{id}/import` for the same `(supplier, mode)` while
the previous job is `queued` or `running` returns `409`.

## Rollback
- Code rollback only: revert this branch + restart. New tables/columns from
  Phase 1 stay in place (idempotent).
- The new `import_jobs` package and `ops_inbound` package are unused after
  rollback but harmless. Drop them only if you're sure no scheduled task or
  in-flight job references them.
```

- [ ] **Step 3: Commit**

```bash
git add backend/docs/ops_inbound_adapter_runbook.md
git commit -m "docs(ops_inbound): runbook for triggering + monitoring OPS imports"
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Implemented in |
|--------------|----------------|
| §6.6 `suppliers.adapter_class` resolves an adapter | Tasks 2, 10 (uses Phase 1 column) |
| §7 `BaseAdapter` interface (discover / hydrate / discover_changed) | Task 1 |
| §7 `PromoStandardsAdapter` / peer registration model | Task 2 (registry) |
| §7 `OPSAdapter` discover / hydrate / discover_changed | Tasks 4, 5, 6 |
| §7.1 persistence routing — `OPSAdapter` writes `print_details` | Task 5 (routes through Phase 1's `persist_product` with `product_type='print'`) |
| §7.2 discovery modes (explicit_list / first_n / full / delta) | Tasks 4, 6, 9 |
| §7.3 error handling (auth = fatal abort, per-product = log + continue) | Tasks 7, 8, 11 |
| §10 trigger model (manual UI button → BackgroundTasks) | Tasks 9, 10, 11 |
| §10 concurrency guard (409 on duplicate in-flight) | Task 12 |
| §11.2 OPS Decals fixture-driven adapter test | Tasks 5, 13 |
| §12 Phase 2 manual import button (backend half) | Tasks 9, 10, 11 |
| `last_full_sync` / `last_delta_sync` stamping | Task 14 |

Out of scope (explicitly deferred to other phase plans): SanMar/PS adapter, pricing API, frontend PDP, n8n cron.

**2. Placeholder scan:**
No "TBD" / "TODO" / "implement later". The Task 10 commentary about a placeholder UUID is resolved by Task 11 in the same plan; no on-disk placeholder ships in the final state.

**3. Type consistency:**
- `BaseAdapter.discover` signature `(mode, *, limit, explicit_list)` matches between `base.py` (Task 1), `OPSAdapter` (Task 4), test adapters (Tasks 7, 8, 11), and `run_import` callers (Tasks 7, 11).
- `ProductRef(supplier_sku, part_id)` used identically across discover (Tasks 4, 6) and orchestrator (Tasks 7, 11).
- `register_adapter` / `get_adapter` / `AdapterNotConfiguredError` / `AdapterNotRegisteredError` defined in Task 2, consumed in Tasks 7, 10, 11.
- `create_pending_import_job` / `run_existing_import_job` defined in Task 11, consumed in Tasks 11 (route), 12 (route), 14 (orchestrator).
- `OPSAdapter` self-registers via `register_adapter("OPSAdapter", OPSAdapter)` at module import time (Task 4); `main.py` imports `modules.ops_inbound.ops_adapter` (Task 10) so the registry is populated before routes mount.

---

## Spec Gaps Noticed

1. **GraphQL query names assumed.** Spec doesn't pin OPS query field names. This plan assumes `listProducts`, `getProduct`, `listProductsModifiedSince`. Verify against the actual OnPrintShop schema before merging — adjust `_LIST_PRODUCTS_QUERY` / `_GET_PRODUCT_QUERY` / `_LIST_MODIFIED_QUERY` if they differ. Recorded fixtures match the schema we assume.
2. **OPS auth token shape.** Spec doesn't specify whether OPS uses Bearer JWT or another header. This plan assumes `Authorization: Bearer <token>` and reads it from `supplier.auth_config["auth_token"]`. `EncryptedJSON` (per CLAUDE.md) handles the at-rest encryption.
3. **Job lifecycle "queued" status.** The spec only mentions `success | partial_success | failed`. This plan adds an intermediate `queued` state (set synchronously by the endpoint, before BG task starts) so callers polling `/api/sync-jobs/{id}` see something deterministic. Update spec §7.3 if you want this codified.
4. **Concurrency key.** Spec says "single BackgroundTask per `(supplier_id, mode)`". Implemented as DB-row check (`SELECT … WHERE status IN ('queued','running')`). Race window between the SELECT and INSERT exists in theory; in practice BackgroundTasks run sequentially per worker. Out of scope to add advisory locks here.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-29-phase2-ops-adapter.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration via `superpowers:subagent-driven-development`.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
