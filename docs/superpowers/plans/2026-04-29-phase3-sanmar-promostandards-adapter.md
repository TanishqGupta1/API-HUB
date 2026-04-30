# Phase 3: SanMar / PromoStandards Adapter Implementation Plan

> **STATUS (2026-04-30): ⏸ NOT STARTED — needs plan revision before execution.**
>
> **Blockers:** SanMar API credentials still pending from Christian (per V1 plan note). Without creds, only fixture-driven tests are possible. Live SOAP integration deferred until creds arrive.
>
> **Plan revisions needed before execution:**
> 1. **`BaseAdapter` already exists** — Phase 2 shipped it at `backend/modules/import_jobs/base.py`. This plan said "create `BaseAdapter` ABC unless Phase 2 already shipped it" — Phase 2 shipped, so SanMarAdapter just subclasses the existing ABC. Remove duplicate-creation tasks from this plan.
> 2. **Adapter registry already exists** — `register_adapter` decorator at `backend/modules/import_jobs/registry.py`. Use it.
> 3. **Import endpoint already exists** — `POST /api/suppliers/{id}/import` at `backend/modules/import_jobs/routes.py`. Reuse, don't recreate.
> 4. **Match Phase 2 patterns:** OPSAdapter uses thin client (`OPSClient` httpx wrapper) + adapter (normalize to `ProductIngest`) split. Mirror this with `SanMarSOAPClient` (zeep wrapper) + `SanMarAdapter` (normalize).
> 5. **Smoke script `backend/scripts/sanmar_smoke.py`** referenced in plan — verify it exists; if not, drop the reference.
>
> **Estimated effort after revisions:** Reduces from ~12 tasks to ~6-8 tasks (no framework setup, just the SanMar-specific adapter + fixtures + tests).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `PromoStandardsAdapter` base class plus `SanMarAdapter` subclass on top of the polymorphic foundation (Phase 1) so SanMar and any future PromoStandards apparel supplier can be ingested via the same registry: discover → hydrate (`GetProduct` + `GetMediaContent` + `GetPricing`) → normalize to `ProductIngest` → `persist_product`. Ship configurable test mode (15-20 products) end-to-end with recorded SOAP fixtures (no live SanMar calls in tests).

**Architecture:** A new `BaseAdapter` ABC (created here unless Phase 2 already shipped it) defines `discover` / `hydrate_product` / `discover_changed` / `discover_closeouts`. `PromoStandardsAdapter` is the concrete generic PS implementation, wrapping the existing `PromoStandardsClient` for SOAP calls. `SanMarAdapter` is a subclass that overrides WSDL endpoint resolution (SanMar's WSDL URLs are deterministic per service), encodes SanMar's `id` / `password` auth shape, plumbs an FTP-bulk discovery flag (impl deferred), and adds a runtime `live_inventory` helper that hits PS Inventory v2 without writing rows. A registry resolves the adapter class by `Supplier.adapter_class` and exposes a single `POST /api/suppliers/{id}/import` endpoint that runs the import as a `BackgroundTask`. Tests drive everything off recorded XML fixtures synthesized from the SanMar Web Services Integration Guide v24.3 examples — never from live SanMar endpoints.

**Tech Stack:** FastAPI, async SQLAlchemy 2.0 + asyncpg, PostgreSQL, Pydantic v2, zeep for SOAP, lxml for fixture parsing, pytest + pytest-asyncio, respx (or unittest.mock) for SOAP transport mocking.

**Spec:** `docs/superpowers/specs/2026-04-29-multi-supplier-product-model-design.md` (use §6.7 PS field mapping, §7 adapter pipeline, §12 Phase 3 rollout).

**Depends on:** Phase 1 (`docs/superpowers/plans/2026-04-29-polymorphic-product-model-foundation.md`) — `persist_product`, `apparel_details`, `variant_prices`, polymorphic `ProductIngest` schema, `Supplier.adapter_class` column.

**Out of scope (follow-up plans):**
- OPS adapter (Phase 2) — peer adapter, separate plan
- Pricing API `/api/pricing/quote` (Phase 4)
- Frontend PDP (Phase 5)
- n8n scheduling + production cron (Phase 6)
- Live SanMar SOAP integration tests (creds-blocked; smoke test in `backend/scripts/sanmar_smoke.py` already covers manual verification)
- FTP-bulk discovery implementation (`sanmar_epdd.csv`, `sanmar_dip.txt`) — config flag added, parser deferred

---

## File Structure

### Files to create
- `backend/modules/import_jobs/__init__.py` — empty package marker
- `backend/modules/import_jobs/base.py` — `BaseAdapter` ABC + `ProductRef` + `DiscoveryMode` enum + adapter exceptions
- `backend/modules/import_jobs/registry.py` — adapter registry + `get_adapter` factory
- `backend/modules/import_jobs/service.py` — `run_import` orchestrator
- `backend/modules/import_jobs/routes.py` — `POST /api/suppliers/{id}/import` + `GET /api/sync_jobs/{id}`
- `backend/modules/promostandards/adapter.py` — `PromoStandardsAdapter` base
- `backend/modules/promostandards/sanmar_adapter.py` — `SanMarAdapter` subclass
- `backend/modules/promostandards/ps_normalizer_v2.py` — PS XML → `ProductIngest` (replaces inline DB-write `normalizer.py`)
- `backend/tests/test_promostandards_adapter.py` — tests for the base adapter (auth, discovery, hydration, error mapping)
- `backend/tests/test_sanmar_adapter.py` — SanMar overrides (WSDL resolution, auth shape, live_inventory helper)
- `backend/tests/test_import_service.py` — end-to-end run_import with recorded fixtures (apparel persistence path)
- `backend/tests/test_import_routes.py` — POST /api/suppliers/{id}/import smoke
- `backend/tests/fixtures/sanmar_get_product_pc61.xml`
- `backend/tests/fixtures/sanmar_get_product_mm1000.xml`
- `backend/tests/fixtures/sanmar_get_media_pc61.xml`
- `backend/tests/fixtures/sanmar_get_pricing_pc61.xml`
- `backend/tests/fixtures/sanmar_get_product_sellable.xml`
- `backend/tests/fixtures/sanmar_get_product_date_modified.xml`
- `backend/tests/fixtures/sanmar_get_product_closeout.xml`
- `backend/tests/fixtures/sanmar_get_inventory_pc61.xml`
- `backend/tests/fixtures/sanmar_auth_failure.xml`
- `backend/tests/fixtures/sanmar_product_not_found.xml`

### Files to modify
- `backend/modules/suppliers/models.py` — add `protocol_config: JSONB` (carries `discovery_mode`, `max_products`, `explicit_list`, `wsdl_overrides`, `enable_ftp_bulk` flag)
- `backend/main.py` — register `import_jobs.routes.router`; append `_SCHEMA_UPGRADES` for `protocol_config`
- `backend/modules/promostandards/__init__.py` — export the new adapter classes
- `backend/modules/sync_jobs/models.py` — `errors: JSONB` + `discovery_mode: VARCHAR(32)` columns (errors may already be added by Phase 1; add `discovery_mode` here)

### Files NOT touched
- `backend/modules/promostandards/client.py` — used as-is by the new adapter (zeep wrapper stays)
- `backend/modules/promostandards/resolver.py` — used as-is for non-SanMar PS suppliers that resolve WSDL via the PS directory
- `backend/modules/promostandards/normalizer.py` — left for now; PS routes still use it for the legacy `/api/sync` flow. Deprecation marker added but no removal in this plan.
- `backend/modules/promostandards/routes.py` — old `/api/sync/...` endpoints stay; the new `/api/suppliers/{id}/import` lives alongside them
- `backend/modules/catalog/persistence.py` — Phase 1 already shipped this
- Frontend / n8n — none

---

## Task Breakdown

### Task 1: Add `protocol_config` to `Supplier` + schema upgrade

**Files:**
- Modify: `backend/modules/suppliers/models.py` (after `auth_config`)
- Modify: `backend/main.py` (`_SCHEMA_UPGRADES`)
- Test: `backend/tests/test_promostandards_adapter.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_promostandards_adapter.py` with the first test:

```python
"""PromoStandardsAdapter + SanMarAdapter tests.

All tests run against recorded XML fixtures — no live SOAP calls.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from modules.suppliers.models import Supplier


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_supplier_has_protocol_config(db: AsyncSession, seed_supplier: Supplier):
    """Supplier carries a JSONB protocol_config column for adapter settings."""
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.protocol_config = {
            "discovery_mode": "explicit_list",
            "explicit_list": ["PC61", "MM1000"],
            "max_products": 20,
        }
        await s.commit()
        await s.refresh(loaded)
        assert loaded.protocol_config["discovery_mode"] == "explicit_list"
        assert loaded.protocol_config["max_products"] == 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_promostandards_adapter.py::test_supplier_has_protocol_config -v`
Expected: FAIL — column missing or attribute error.

- [ ] **Step 3: Add the column**

In `backend/modules/suppliers/models.py`, in `class Supplier(Base)`, add after `auth_config`:

```python
protocol_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=None)
```

`JSONB` is already imported.

- [ ] **Step 4: Append schema upgrade**

In `backend/main.py`, append to `_SCHEMA_UPGRADES`:

```python
"ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS protocol_config JSONB",
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_promostandards_adapter.py::test_supplier_has_protocol_config -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/suppliers/models.py backend/main.py backend/tests/test_promostandards_adapter.py
git commit -m "feat(suppliers): add protocol_config JSONB for adapter settings"
```

---

### Task 2: Define `BaseAdapter` ABC + `ProductRef` + `DiscoveryMode`

**Files:**
- Create: `backend/modules/import_jobs/__init__.py`
- Create: `backend/modules/import_jobs/base.py`
- Test: `backend/tests/test_promostandards_adapter.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_promostandards_adapter.py`:

```python
def test_base_adapter_contract():
    """BaseAdapter declares discover, hydrate_product, discover_changed,
    discover_closeouts — ABC enforces overriding."""
    from modules.import_jobs.base import (
        BaseAdapter,
        DiscoveryMode,
        ProductRef,
    )

    # Cannot instantiate the abstract class.
    with pytest.raises(TypeError):
        BaseAdapter(supplier=None, db=None)

    # Discovery modes are stable strings.
    assert DiscoveryMode.EXPLICIT_LIST.value == "explicit_list"
    assert DiscoveryMode.FIRST_N.value == "first_n"
    assert DiscoveryMode.FILTERED_SAMPLE.value == "filtered_sample"
    assert DiscoveryMode.FULL_SELLABLE.value == "full_sellable"
    assert DiscoveryMode.DELTA.value == "delta"
    assert DiscoveryMode.CLOSEOUTS.value == "closeouts"

    # ProductRef is a frozen dataclass / NamedTuple-like with product_id + part_id.
    ref = ProductRef(product_id="PC61", part_id=None)
    assert ref.product_id == "PC61"
    assert ref.part_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_promostandards_adapter.py::test_base_adapter_contract -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Create the package**

Create `backend/modules/import_jobs/__init__.py` (empty):

```python
"""Supplier-agnostic import job orchestration."""
```

Create `backend/modules/import_jobs/base.py`:

```python
"""Adapter abstract base + shared types.

Every supplier protocol (PromoStandards SOAP, OPS GraphQL, 4Over REST/HMAC)
implements this interface. The orchestrator in service.py never branches on
supplier identity — it only calls these methods.
"""
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
    FULL_SELLABLE = "full_sellable"
    DELTA = "delta"
    CLOSEOUTS = "closeouts"


@dataclass(frozen=True)
class ProductRef:
    """Lightweight identifier for a discoverable product.

    For PS apparel, ``product_id`` is the style number (e.g. "PC61") and
    ``part_id`` is the optional unique-key. For OPS print, ``product_id`` is
    the OPS numeric id stringified.
    """
    product_id: str
    part_id: Optional[str] = None


class AdapterError(Exception):
    """Base for adapter-raised errors."""


class AuthError(AdapterError):
    """Credentials rejected by supplier. Caller aborts the whole job."""


class SupplierError(AdapterError):
    """Per-product error from supplier (not-found, bad data, etc.). Caller logs and continues."""

    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class TransientError(AdapterError):
    """Transient failure (5xx, timeout). Caller retries with backoff."""


class BaseAdapter(ABC):
    """Abstract supplier adapter.

    Subclasses MUST implement ``discover`` and ``hydrate_product``.
    ``discover_changed`` / ``discover_closeouts`` are optional — default
    raises ``NotImplementedError``.
    """

    product_type: str  # subclass sets "apparel" | "print"

    def __init__(self, supplier: Supplier, db: AsyncSession):
        self.supplier = supplier
        self.db = db

    @abstractmethod
    async def discover(
        self, mode: DiscoveryMode, limit: Optional[int]
    ) -> list[ProductRef]:
        """Return product refs to hydrate next."""

    @abstractmethod
    async def hydrate_product(self, ref: ProductRef) -> ProductIngest:
        """Fetch full product detail + media + pricing for one ref."""

    async def discover_changed(self, since: datetime) -> list[ProductRef]:
        raise NotImplementedError

    async def discover_closeouts(self) -> list[ProductRef]:
        raise NotImplementedError
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_promostandards_adapter.py::test_base_adapter_contract -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/import_jobs/__init__.py backend/modules/import_jobs/base.py backend/tests/test_promostandards_adapter.py
git commit -m "feat(import_jobs): BaseAdapter ABC + DiscoveryMode + ProductRef"
```

---

### Task 3: Adapter registry + `get_adapter`

**Files:**
- Create: `backend/modules/import_jobs/registry.py`
- Test: `backend/tests/test_promostandards_adapter.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_promostandards_adapter.py`:

```python
@pytest.mark.asyncio
async def test_registry_resolves_adapter_class(seed_supplier: Supplier):
    """get_adapter looks up the class by Supplier.adapter_class."""
    from modules.import_jobs.registry import get_adapter, register_adapter
    from modules.import_jobs.base import BaseAdapter, DiscoveryMode, ProductRef

    class StubAdapter(BaseAdapter):
        product_type = "apparel"

        async def discover(self, mode, limit):
            return [ProductRef(product_id="STUB-1")]

        async def hydrate_product(self, ref):
            raise NotImplementedError

    register_adapter("StubAdapter", StubAdapter)

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "StubAdapter"
        await s.commit()
        adapter = get_adapter(loaded, s)
        assert isinstance(adapter, StubAdapter)
        refs = await adapter.discover(DiscoveryMode.EXPLICIT_LIST, 1)
        assert refs[0].product_id == "STUB-1"


def test_registry_unknown_class_raises():
    from modules.import_jobs.registry import get_adapter, UnknownAdapterError

    class FakeSupplier:
        adapter_class = "NotARealAdapter"
        name = "fake"

    with pytest.raises(UnknownAdapterError):
        get_adapter(FakeSupplier(), None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_promostandards_adapter.py::test_registry_resolves_adapter_class tests/test_promostandards_adapter.py::test_registry_unknown_class_raises -v`
Expected: 2 FAILS — `ImportError`.

- [ ] **Step 3: Create the registry**

Create `backend/modules/import_jobs/registry.py`:

```python
"""Adapter registry. Maps Supplier.adapter_class string → BaseAdapter subclass."""
from __future__ import annotations

from typing import Type

from sqlalchemy.ext.asyncio import AsyncSession

from modules.suppliers.models import Supplier

from .base import AdapterError, BaseAdapter


class UnknownAdapterError(AdapterError):
    """Supplier.adapter_class names a class that is not registered."""


_REGISTRY: dict[str, Type[BaseAdapter]] = {}


def register_adapter(name: str, cls: Type[BaseAdapter]) -> None:
    _REGISTRY[name] = cls


def get_adapter(supplier: Supplier, db: AsyncSession) -> BaseAdapter:
    name = getattr(supplier, "adapter_class", None)
    if not name:
        raise UnknownAdapterError(
            f"Supplier {supplier.name!r} has no adapter_class set"
        )
    cls = _REGISTRY.get(name)
    if cls is None:
        raise UnknownAdapterError(
            f"adapter_class {name!r} is not registered (known: {sorted(_REGISTRY)})"
        )
    return cls(supplier=supplier, db=db)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_promostandards_adapter.py::test_registry_resolves_adapter_class tests/test_promostandards_adapter.py::test_registry_unknown_class_raises -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/import_jobs/registry.py backend/tests/test_promostandards_adapter.py
git commit -m "feat(import_jobs): adapter registry with name → class lookup"
```

---

### Task 4: Author SOAP fixture files

**Files:**
- Create: `backend/tests/fixtures/sanmar_get_product_pc61.xml`
- Create: `backend/tests/fixtures/sanmar_get_product_mm1000.xml`
- Create: `backend/tests/fixtures/sanmar_get_media_pc61.xml`
- Create: `backend/tests/fixtures/sanmar_get_pricing_pc61.xml`
- Create: `backend/tests/fixtures/sanmar_get_product_sellable.xml`
- Create: `backend/tests/fixtures/sanmar_get_product_date_modified.xml`
- Create: `backend/tests/fixtures/sanmar_get_product_closeout.xml`
- Create: `backend/tests/fixtures/sanmar_get_inventory_pc61.xml`
- Create: `backend/tests/fixtures/sanmar_auth_failure.xml`
- Create: `backend/tests/fixtures/sanmar_product_not_found.xml`

- [ ] **Step 1: Verify fixtures dir exists**

Run:

```bash
mkdir -p /Users/tanishq/Documents/project-files/api-hub/api-hub/backend/tests/fixtures
ls /Users/tanishq/Documents/project-files/api-hub/api-hub/backend/tests/fixtures
```

- [ ] **Step 2: Write `sanmar_get_product_pc61.xml`**

Synthesized from PDF v24.3 §"PromoStandards GetProduct V2.0.0 Service XML Response" (with productId changed to PC61 for distinct identity). Two parts (Black/S, Black/L) with one MSRP price tier each.

Path: `backend/tests/fixtures/sanmar_get_product_pc61.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
  <S:Body>
    <ns2:GetProductResponse xmlns:ns2="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/" xmlns="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/">
      <ns2:Product>
        <productId>PC61</productId>
        <productName>Port &amp; Company Essential Tee PC61</productName>
        <description>Classic essential tee</description>
        <description>5.4-ounce, 100% cotton</description>
        <description>Tagless label</description>
        <ns2:ProductKeywordArray>
          <ProductKeyword><keyword>Tee</keyword></ProductKeyword>
          <ProductKeyword><keyword>Essential</keyword></ProductKeyword>
        </ns2:ProductKeywordArray>
        <productBrand>Port &amp; Company</productBrand>
        <ns2:export>false</ns2:export>
        <ns2:ProductCategoryArray>
          <ProductCategory>
            <category>T-Shirts</category>
            <subCategory>Cotton</subCategory>
          </ProductCategory>
        </ns2:ProductCategoryArray>
        <primaryImageUrl>https://cdnm.sanmar.com/catalog/images/PC61.jpg</primaryImageUrl>
        <ns2:ProductPriceGroupArray>
          <ProductPriceGroup>
            <ProductPriceArray>
              <ProductPrice>
                <quantityMin>1</quantityMin>
                <quantityMax>2147483647</quantityMax>
                <price>4.98</price>
              </ProductPrice>
            </ProductPriceArray>
            <groupName>MSRP</groupName>
            <currency>USD</currency>
          </ProductPriceGroup>
        </ns2:ProductPriceGroupArray>
        <ns2:ProductPartArray>
          <ns2:ProductPart>
            <partId>PC61-BLK-S</partId>
            <ns2:primaryColor>
              <Color>
                <standardColorName>Jet Black</standardColorName>
                <colorName>Jet Black</colorName>
              </Color>
            </ns2:primaryColor>
            <ns2:ColorArray>
              <Color>
                <standardColorName>Jet Black</standardColorName>
                <approximatePms>BLACK C</approximatePms>
                <colorName>Jet Black</colorName>
              </Color>
            </ns2:ColorArray>
            <ApparelSize>
              <apparelStyle>Mens</apparelStyle>
              <labelSize>S</labelSize>
            </ApparelSize>
            <Dimension>
              <weightUom>OZ</weightUom>
              <weight>5.40</weight>
            </Dimension>
            <gtin>00191265111111</gtin>
            <isCloseout>false</isCloseout>
            <isCaution>false</isCaution>
            <isOnDemand>false</isOnDemand>
            <isHazmat>false</isHazmat>
          </ns2:ProductPart>
          <ns2:ProductPart>
            <partId>PC61-BLK-L</partId>
            <ns2:primaryColor>
              <Color>
                <standardColorName>Jet Black</standardColorName>
                <colorName>Jet Black</colorName>
              </Color>
            </ns2:primaryColor>
            <ns2:ColorArray>
              <Color>
                <standardColorName>Jet Black</standardColorName>
                <approximatePms>BLACK C</approximatePms>
                <colorName>Jet Black</colorName>
              </Color>
            </ns2:ColorArray>
            <ApparelSize>
              <apparelStyle>Mens</apparelStyle>
              <labelSize>L</labelSize>
            </ApparelSize>
            <Dimension>
              <weightUom>OZ</weightUom>
              <weight>5.80</weight>
            </Dimension>
            <gtin>00191265222222</gtin>
            <isCloseout>false</isCloseout>
            <isCaution>false</isCaution>
            <isOnDemand>false</isOnDemand>
            <isHazmat>false</isHazmat>
          </ns2:ProductPart>
        </ns2:ProductPartArray>
        <ns2:lastChangeDate>2024-08-01T12:00:00.000</ns2:lastChangeDate>
        <ns2:creationDate>2010-01-01T08:00:00.000</ns2:creationDate>
        <isCaution>false</isCaution>
        <isCloseout>false</isCloseout>
        <FobPointArray>
          <FobPoint>
            <fobId>6</fobId>
            <fobCity>Jacksonville</fobCity>
            <fobState>FL</fobState>
            <fobPostalCode>32219</fobPostalCode>
            <fobCountry>USA</fobCountry>
          </FobPoint>
        </FobPointArray>
      </ns2:Product>
    </ns2:GetProductResponse>
  </S:Body>
</S:Envelope>
```

- [ ] **Step 3: Write `sanmar_get_product_mm1000.xml`**

Path: `backend/tests/fixtures/sanmar_get_product_mm1000.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
  <S:Body>
    <ns2:GetProductResponse xmlns:ns2="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/" xmlns="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/">
      <ns2:Product>
        <productId>MM1000</productId>
        <productName>MERCER+METTLE Stretch Heavyweight Pique Polo MM1000</productName>
        <description>Crafted in a heavier knit, this refined polo is just as comfortable as the classics from which it was inspired.</description>
        <description>8.1-ounce, 58/39/3 cotton/poly/spandex diamond pique</description>
        <description>Moisture-wicking</description>
        <productBrand>Mercer+Mettle</productBrand>
        <ns2:export>false</ns2:export>
        <ns2:ProductCategoryArray>
          <ProductCategory>
            <category>Polos/Knits</category>
            <subCategory>Cotton, Easy Care</subCategory>
          </ProductCategory>
        </ns2:ProductCategoryArray>
        <primaryImageUrl>https://cdnm.sanmar.com/catalog/images/MM1000.jpg</primaryImageUrl>
        <ns2:ProductPriceGroupArray>
          <ProductPriceGroup>
            <ProductPriceArray>
              <ProductPrice>
                <quantityMin>1</quantityMin>
                <quantityMax>2147483647</quantityMax>
                <price>24.98</price>
              </ProductPrice>
            </ProductPriceArray>
            <groupName>MSRP</groupName>
            <currency>USD</currency>
          </ProductPriceGroup>
        </ns2:ProductPriceGroupArray>
        <ns2:ProductPartArray>
          <ns2:ProductPart>
            <partId>1878771</partId>
            <ns2:primaryColor>
              <Color>
                <standardColorName>Deep Black</standardColorName>
                <colorName>DeepBlack</colorName>
              </Color>
            </ns2:primaryColor>
            <ns2:ColorArray>
              <Color>
                <standardColorName>Deep Black</standardColorName>
                <approximatePms>BLACK C</approximatePms>
                <colorName>DeepBlack</colorName>
              </Color>
            </ns2:ColorArray>
            <ApparelSize>
              <apparelStyle>Mens</apparelStyle>
              <labelSize>S</labelSize>
            </ApparelSize>
            <Dimension>
              <weightUom>OZ</weightUom>
              <weight>8.10</weight>
            </Dimension>
            <gtin>00191265938235</gtin>
            <isCloseout>false</isCloseout>
            <isCaution>false</isCaution>
            <isOnDemand>false</isOnDemand>
            <isHazmat>false</isHazmat>
          </ns2:ProductPart>
        </ns2:ProductPartArray>
        <ns2:lastChangeDate>2023-04-20T16:35:43.653</ns2:lastChangeDate>
        <ns2:creationDate>2021-09-01T08:05:34.297</ns2:creationDate>
        <isCaution>false</isCaution>
        <isCloseout>false</isCloseout>
        <FobPointArray>
          <FobPoint>
            <fobId>6</fobId>
            <fobCity>Jacksonville</fobCity>
            <fobState>FL</fobState>
            <fobPostalCode>32219</fobPostalCode>
            <fobCountry>USA</fobCountry>
          </FobPoint>
        </FobPointArray>
      </ns2:Product>
    </ns2:GetProductResponse>
  </S:Body>
</S:Envelope>
```

- [ ] **Step 4: Write `sanmar_get_media_pc61.xml`**

Path: `backend/tests/fixtures/sanmar_get_media_pc61.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
  <S:Body>
    <ns2:GetMediaContentResponse xmlns:ns2="http://www.promostandards.org/WSDL/MediaService/1.0.0/" xmlns="http://www.promostandards.org/WSDL/MediaService/1.0.0/SharedObjects/">
      <ns2:MediaContentArray>
        <ns2:MediaContent>
          <productId>PC61</productId>
          <partId>PC61-BLK-S</partId>
          <ns2:url>https://cdnm.sanmar.com/imglib/mresjpg/PC61_Black_front.jpg</ns2:url>
          <mediaType>Image</mediaType>
          <ns2:ClassTypeArray>
            <ns2:ClassType>
              <ns2:classTypeId>1007</ns2:classTypeId>
              <ns2:classTypeName>Front</ns2:classTypeName>
            </ns2:ClassType>
          </ns2:ClassTypeArray>
          <ns2:color>Jet Black</ns2:color>
          <ns2:singlePart>true</ns2:singlePart>
        </ns2:MediaContent>
        <ns2:MediaContent>
          <productId>PC61</productId>
          <partId>PC61-BLK-S</partId>
          <ns2:url>https://cdnm.sanmar.com/imglib/mresjpg/PC61_Black_back.jpg</ns2:url>
          <mediaType>Image</mediaType>
          <ns2:ClassTypeArray>
            <ns2:ClassType>
              <ns2:classTypeId>1008</ns2:classTypeId>
              <ns2:classTypeName>Rear</ns2:classTypeName>
            </ns2:ClassType>
          </ns2:ClassTypeArray>
          <ns2:color>Jet Black</ns2:color>
          <ns2:singlePart>true</ns2:singlePart>
        </ns2:MediaContent>
        <ns2:MediaContent>
          <productId>PC61</productId>
          <partId>PC61-BLK-S</partId>
          <ns2:url>https://cdnm.sanmar.com/catalog/images/PC61.jpg</ns2:url>
          <mediaType>Image</mediaType>
          <ns2:ClassTypeArray>
            <ns2:ClassType>
              <ns2:classTypeId>1006</ns2:classTypeId>
              <ns2:classTypeName>Primary</ns2:classTypeName>
            </ns2:ClassType>
          </ns2:ClassTypeArray>
          <ns2:color>Jet Black</ns2:color>
          <ns2:singlePart>true</ns2:singlePart>
        </ns2:MediaContent>
        <ns2:MediaContent>
          <productId>PC61</productId>
          <partId>PC61-BLK-S</partId>
          <ns2:url>https://cdnm.sanmar.com/swatch/gifs/port_black.gif</ns2:url>
          <mediaType>Image</mediaType>
          <ns2:ClassTypeArray>
            <ns2:ClassType>
              <ns2:classTypeId>1004</ns2:classTypeId>
              <ns2:classTypeName>Swatch</ns2:classTypeName>
            </ns2:ClassType>
          </ns2:ClassTypeArray>
          <ns2:color>Jet Black</ns2:color>
          <ns2:singlePart>true</ns2:singlePart>
        </ns2:MediaContent>
      </ns2:MediaContentArray>
    </ns2:GetMediaContentResponse>
  </S:Body>
</S:Envelope>
```

- [ ] **Step 5: Write `sanmar_get_pricing_pc61.xml`**

Path: `backend/tests/fixtures/sanmar_get_pricing_pc61.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
  <S:Body>
    <ns2:getConfigurationAndPricingResponse xmlns:ns2="http://www.promostandards.org/WSDL/PricingAndConfigurationService/1.0.0/" xmlns="http://www.promostandards.org/WSDL/PricingAndConfigurationService/1.0.0/SharedObjects/">
      <ns2:Configuration>
        <PartArray>
          <Part>
            <partId>PC61-BLK-S</partId>
            <PartPriceArray>
              <PartPrice>
                <minQuantity>1</minQuantity>
                <price>4.98</price>
                <discountCode>MSRP</discountCode>
                <priceUom>EA</priceUom>
                <priceEffectiveDate>2024-01-01T00:00:00</priceEffectiveDate>
              </PartPrice>
              <PartPrice>
                <minQuantity>72</minQuantity>
                <price>3.98</price>
                <discountCode>Net</discountCode>
                <priceUom>EA</priceUom>
                <priceEffectiveDate>2024-01-01T00:00:00</priceEffectiveDate>
              </PartPrice>
            </PartPriceArray>
          </Part>
          <Part>
            <partId>PC61-BLK-L</partId>
            <PartPriceArray>
              <PartPrice>
                <minQuantity>1</minQuantity>
                <price>4.98</price>
                <discountCode>MSRP</discountCode>
                <priceUom>EA</priceUom>
                <priceEffectiveDate>2024-01-01T00:00:00</priceEffectiveDate>
              </PartPrice>
            </PartPriceArray>
          </Part>
        </PartArray>
      </ns2:Configuration>
    </ns2:getConfigurationAndPricingResponse>
  </S:Body>
</S:Envelope>
```

- [ ] **Step 6: Write `sanmar_get_product_sellable.xml`**

Path: `backend/tests/fixtures/sanmar_get_product_sellable.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
  <S:Body>
    <ns2:GetProductSellableResponse xmlns:ns2="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/" xmlns="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/">
      <ns2:ProductSellableArray>
        <ns2:ProductSellable><productId>PC61</productId><partId>PC61-BLK-S</partId></ns2:ProductSellable>
        <ns2:ProductSellable><productId>PC61</productId><partId>PC61-BLK-L</partId></ns2:ProductSellable>
        <ns2:ProductSellable><productId>MM1000</productId><partId>1878771</partId></ns2:ProductSellable>
        <ns2:ProductSellable><productId>K500</productId><partId>K500-NVY-M</productId></ns2:ProductSellable>
        <ns2:ProductSellable><productId>L500</productId><partId>L500-NVY-S</productId></ns2:ProductSellable>
      </ns2:ProductSellableArray>
    </ns2:GetProductSellableResponse>
  </S:Body>
</S:Envelope>
```

- [ ] **Step 7: Write `sanmar_get_product_date_modified.xml`**

Path: `backend/tests/fixtures/sanmar_get_product_date_modified.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
  <S:Body>
    <ns2:GetProductDateModifiedResponse xmlns:ns2="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/" xmlns="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/">
      <ns2:ProductDateModifiedArray>
        <ns2:ProductDateModified><productId>PC61</productId><partId>PC61-BLK-S</partId></ns2:ProductDateModified>
        <ns2:ProductDateModified><productId>MM1000</productId><partId>1878771</partId></ns2:ProductDateModified>
      </ns2:ProductDateModifiedArray>
    </ns2:GetProductDateModifiedResponse>
  </S:Body>
</S:Envelope>
```

- [ ] **Step 8: Write `sanmar_get_product_closeout.xml`**

Path: `backend/tests/fixtures/sanmar_get_product_closeout.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
  <S:Body>
    <ns2:GetProductCloseOutResponse xmlns:ns2="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/" xmlns="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/">
      <ns2:ProductCloseOutArray>
        <ns2:ProductCloseOut><productId>DM104CL</productId><partId>764961</partId></ns2:ProductCloseOut>
      </ns2:ProductCloseOutArray>
    </ns2:GetProductCloseOutResponse>
  </S:Body>
</S:Envelope>
```

- [ ] **Step 9: Write `sanmar_get_inventory_pc61.xml`**

Path: `backend/tests/fixtures/sanmar_get_inventory_pc61.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
  <S:Body>
    <ns2:GetInventoryLevelsResponse xmlns:ns2="http://www.promostandards.org/WSDL/Inventory/2.0.0/" xmlns="http://www.promostandards.org/WSDL/Inventory/2.0.0/SharedObjects/">
      <Inventory>
        <productId>PC61</productId>
        <PartInventoryArray>
          <PartInventory>
            <partId>PC61-BLK-S</partId>
            <quantityAvailable><Quantity><value>500</value></Quantity></quantityAvailable>
            <InventoryLocationArray>
              <InventoryLocation>
                <inventoryLocationId>2</inventoryLocationId>
                <inventoryLocationName>Cincinnati</inventoryLocationName>
                <inventoryLocationQuantity><Quantity><value>320</value></Quantity></inventoryLocationQuantity>
              </InventoryLocation>
              <InventoryLocation>
                <inventoryLocationId>4</inventoryLocationId>
                <inventoryLocationName>Reno</inventoryLocationName>
                <inventoryLocationQuantity><Quantity><value>180</value></Quantity></inventoryLocationQuantity>
              </InventoryLocation>
            </InventoryLocationArray>
          </PartInventory>
        </PartInventoryArray>
      </Inventory>
    </ns2:GetInventoryLevelsResponse>
  </S:Body>
</S:Envelope>
```

- [ ] **Step 10: Write `sanmar_auth_failure.xml`**

Path: `backend/tests/fixtures/sanmar_auth_failure.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
  <S:Body>
    <S:Fault>
      <faultcode>S:Server</faultcode>
      <faultstring>Authentication Credentials failed</faultstring>
      <detail>
        <ns2:errorMessage xmlns:ns2="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/">
          <code>105</code>
          <message>Authentication Credentials failed</message>
        </ns2:errorMessage>
      </detail>
    </S:Fault>
  </S:Body>
</S:Envelope>
```

- [ ] **Step 11: Write `sanmar_product_not_found.xml`**

Path: `backend/tests/fixtures/sanmar_product_not_found.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
  <S:Body>
    <S:Fault>
      <faultcode>S:Server</faultcode>
      <faultstring>Product Id not found</faultstring>
      <detail>
        <ns2:errorMessage xmlns:ns2="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/">
          <code>130</code>
          <message>Product Id not found</message>
        </ns2:errorMessage>
      </detail>
    </S:Fault>
  </S:Body>
</S:Envelope>
```

- [ ] **Step 12: Sanity-check fixtures parse as well-formed XML**

Run:

```bash
cd backend && python -c "
from pathlib import Path
from lxml import etree
for p in sorted(Path('tests/fixtures').glob('sanmar_*.xml')):
    etree.parse(str(p))
    print(f'OK {p}')
"
```

Expected output: 10 lines starting with `OK`.

- [ ] **Step 13: Commit**

```bash
git add backend/tests/fixtures/sanmar_*.xml
git commit -m "test(promostandards): add SanMar SOAP response fixtures"
```

---

### Task 5: PS XML → `ProductIngest` normalizer (`ps_normalizer_v2.py`)

**Files:**
- Create: `backend/modules/promostandards/ps_normalizer_v2.py`
- Test: `backend/tests/test_promostandards_adapter.py`

The legacy `normalizer.py` writes directly to DB. The new normalizer is pure: parsed-zeep-object → `ProductIngest` (with `apparel_details`, `variants`, `variant_prices`, `images`). The adapter then hands it to `persist_product`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_promostandards_adapter.py`:

```python
def test_ps_normalizer_builds_apparel_product_ingest_from_pc61_fixture():
    from lxml import etree
    from zeep.xsd.valueobjects import CompoundValue  # noqa: F401  (import shape only)

    from modules.promostandards.ps_normalizer_v2 import (
        normalize_get_product_xml,
        merge_media,
        merge_pricing,
    )

    pc61_xml = (FIXTURES_DIR / "sanmar_get_product_pc61.xml").read_bytes()
    media_xml = (FIXTURES_DIR / "sanmar_get_media_pc61.xml").read_bytes()
    pricing_xml = (FIXTURES_DIR / "sanmar_get_pricing_pc61.xml").read_bytes()

    ingest = normalize_get_product_xml(pc61_xml)

    assert ingest.supplier_sku == "PC61"
    assert ingest.product_type == "apparel"
    assert ingest.pricing_method == "tiered_variants"
    assert ingest.brand == "Port & Company"
    assert "essential tee" in (ingest.description or "").lower()
    assert ingest.apparel_details is not None
    assert ingest.apparel_details.is_closeout is False
    assert ingest.apparel_details.fob_points == [
        {"fobId": "6", "fobCity": "Jacksonville", "fobState": "FL", "fobPostalCode": "32219", "fobCountry": "USA"}
    ]
    assert "Tee" in (ingest.apparel_details.keywords or [])
    # Two variants from ProductPartArray
    assert len(ingest.variants) == 2
    parts_by_id = {v.part_id: v for v in ingest.variants}
    assert "PC61-BLK-S" in parts_by_id
    s_variant = parts_by_id["PC61-BLK-S"]
    assert s_variant.color == "Jet Black"
    assert s_variant.size == "S"
    assert s_variant.gtin == "00191265111111"
    assert s_variant.flags["pms_color"] == "BLACK C"

    # MSRP single tier from GetProduct ProductPriceGroupArray seeds variant_prices.
    assert len(s_variant.prices) == 1
    assert s_variant.prices[0].group_name == "MSRP"
    assert str(s_variant.prices[0].price) == "4.98"

    merged = merge_pricing(ingest, pricing_xml)
    s_after = {v.part_id: v for v in merged.variants}["PC61-BLK-S"]
    # PartPriceArray adds a Net tier at minQuantity 72
    assert any(t.group_name == "Net" and t.qty_min == 72 for t in s_after.prices)

    final = merge_media(merged, media_xml)
    assert len(final.images) == 4
    types = sorted({img.image_type for img in final.images})
    assert "primary" in types
    assert "front" in types
    assert "rear" in types
    assert "swatch" in types


def test_ps_normalizer_handles_mm1000_fixture():
    from modules.promostandards.ps_normalizer_v2 import normalize_get_product_xml

    raw = (FIXTURES_DIR / "sanmar_get_product_mm1000.xml").read_bytes()
    ingest = normalize_get_product_xml(raw)
    assert ingest.supplier_sku == "MM1000"
    assert ingest.brand == "Mercer+Mettle"
    assert ingest.apparel_details.apparel_style == "Mens"
    assert len(ingest.variants) == 1
    assert ingest.variants[0].part_id == "1878771"
    assert ingest.variants[0].gtin == "00191265938235"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_promostandards_adapter.py::test_ps_normalizer_builds_apparel_product_ingest_from_pc61_fixture tests/test_promostandards_adapter.py::test_ps_normalizer_handles_mm1000_fixture -v`
Expected: 2 FAILS — `ImportError`.

- [ ] **Step 3: Implement the normalizer**

Create `backend/modules/promostandards/ps_normalizer_v2.py`:

```python
"""Pure XML → ProductIngest normalizer for PromoStandards apparel.

Stateless. The adapter wraps SOAP transport; this module just translates
shape. Parses raw XML bytes via lxml so it works equally well against
recorded fixtures and live zeep responses (zeep stringifies the envelope
when needed).

PS field mapping is locked in spec §6.7. This module is the single place
that mapping lives — both SanMar and other PS apparel suppliers share it.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from lxml import etree

from modules.catalog.schemas import (
    ApparelDetailsIngest,
    ImageIngest,
    PriceTier,
    ProductIngest,
    VariantIngest,
)


_NS = {
    "soap": "http://schemas.xmlsoap.org/soap/envelope/",
    "S": "http://schemas.xmlsoap.org/soap/envelope/",
    # PS namespaces vary across the response — we use local-name() in XPath
    # to stay tolerant. Declared here for documentation only.
}

# Map MediaContent classTypeName → product_images.image_type.
_MEDIA_CLASS_TO_TYPE = {
    "primary": "primary",
    "front": "front",
    "rear": "rear",
    "swatch": "swatch",
    "high": "high",
    "side": "side",
    "back": "rear",
    "detail": "detail",
}


def _text(node, xpath: str) -> Optional[str]:
    """Run XPath and return the first node's stripped text, or None."""
    if node is None:
        return None
    found = node.xpath(xpath)
    if not found:
        return None
    el = found[0]
    if isinstance(el, etree._Element):
        text = "".join(el.itertext()).strip()
    else:
        text = str(el).strip()
    return text or None


def _all_texts(node, xpath: str) -> list[str]:
    if node is None:
        return []
    out: list[str] = []
    for el in node.xpath(xpath):
        if isinstance(el, etree._Element):
            t = "".join(el.itertext()).strip()
        else:
            t = str(el).strip()
        if t:
            out.append(t)
    return out


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_get_product_xml(xml_bytes: bytes) -> ProductIngest:
    """Translate a single GetProduct response envelope to a ProductIngest."""
    root = etree.fromstring(xml_bytes)
    product = root.xpath("//*[local-name()='Product']")
    if not product:
        raise ValueError("GetProductResponse missing Product element")
    product = product[0]

    product_id = _text(product, "*[local-name()='productId']") or ""
    if not product_id:
        raise ValueError("Product missing productId")

    name = _text(product, "*[local-name()='productName']")
    descriptions = _all_texts(product, "*[local-name()='description']")
    description = "\n".join(descriptions) if descriptions else None
    brand = _text(product, "*[local-name()='productBrand']")
    primary_image = _text(product, "*[local-name()='primaryImageUrl']")

    # Categories
    cat_external_id: Optional[str] = None
    cat_name: Optional[str] = None
    first_cat = product.xpath(
        "*[local-name()='ProductCategoryArray']/*[local-name()='ProductCategory']"
    )
    if first_cat:
        cat_name = _text(first_cat[0], "*[local-name()='category']")
        cat_external_id = (cat_name or "").lower().replace(" ", "_") or None

    # Apparel details
    keywords = _all_texts(
        product,
        "*[local-name()='ProductKeywordArray']/*[local-name()='ProductKeyword']/*[local-name()='keyword']",
    )
    is_closeout = _text(product, "*[local-name()='isCloseout']") == "true"
    is_caution = _text(product, "*[local-name()='isCaution']") == "true"
    caution_comment = _text(product, "*[local-name()='cautionComment']")
    last_change = _parse_iso(_text(product, "*[local-name()='lastChangeDate']"))

    fob_points: list[dict] = []
    for fob in product.xpath("*[local-name()='FobPointArray']/*[local-name()='FobPoint']"):
        fob_points.append({
            "fobId": _text(fob, "*[local-name()='fobId']") or "",
            "fobCity": _text(fob, "*[local-name()='fobCity']") or "",
            "fobState": _text(fob, "*[local-name()='fobState']") or "",
            "fobPostalCode": _text(fob, "*[local-name()='fobPostalCode']") or "",
            "fobCountry": _text(fob, "*[local-name()='fobCountry']") or "",
        })

    # Walk parts
    variants: list[VariantIngest] = []
    apparel_styles: set[str] = set()
    fabric_specs_collected: dict = {}
    for part in product.xpath(
        "*[local-name()='ProductPartArray']/*[local-name()='ProductPart']"
    ):
        part_id = _text(part, "*[local-name()='partId']")
        if not part_id:
            continue
        primary_color_node = part.xpath(
            "*[local-name()='primaryColor']/*[local-name()='Color']"
        )
        std_color = None
        pms = None
        color_name = None
        if primary_color_node:
            cnode = primary_color_node[0]
            std_color = _text(cnode, "*[local-name()='standardColorName']")
            color_name = _text(cnode, "*[local-name()='colorName']")
        first_color_array = part.xpath(
            "*[local-name()='ColorArray']/*[local-name()='Color']"
        )
        if first_color_array:
            cnode = first_color_array[0]
            pms = _text(cnode, "*[local-name()='approximatePms']")
            std_color = std_color or _text(cnode, "*[local-name()='standardColorName']")
            color_name = color_name or _text(cnode, "*[local-name()='colorName']")
        size_node = part.xpath("*[local-name()='ApparelSize']")
        apparel_style = label_size = None
        if size_node:
            apparel_style = _text(size_node[0], "*[local-name()='apparelStyle']")
            label_size = _text(size_node[0], "*[local-name()='labelSize']")
            if apparel_style:
                apparel_styles.add(apparel_style)
        weight_uom = _text(part, "*[local-name()='Dimension']/*[local-name()='weightUom']")
        weight = _text(part, "*[local-name()='Dimension']/*[local-name()='weight']")
        if weight:
            fabric_specs_collected.setdefault("weight_uom", weight_uom or "OZ")
            fabric_specs_collected.setdefault("weight", weight)
        gtin = _text(part, "*[local-name()='gtin']")

        variants.append(VariantIngest(
            part_id=part_id,
            color=std_color or color_name,
            size=label_size,
            sku=part_id,
            gtin=gtin,
            flags={
                "standard_color": std_color,
                "pms_color": pms,
                "label_size": label_size,
                "color_name_mainframe": color_name,
                "weight_uom": weight_uom,
                "weight": weight,
            },
            prices=[],
        ))

    # Seed each variant's price list with the product-level MSRP tier.
    msrp_tiers: list[PriceTier] = []
    for group in product.xpath(
        "*[local-name()='ProductPriceGroupArray']/*[local-name()='ProductPriceGroup']"
    ):
        group_name = _text(group, "*[local-name()='groupName']") or "MSRP"
        currency = _text(group, "*[local-name()='currency']") or "USD"
        for price in group.xpath(
            "*[local-name()='ProductPriceArray']/*[local-name()='ProductPrice']"
        ):
            qmin = _text(price, "*[local-name()='quantityMin']")
            qmax = _text(price, "*[local-name()='quantityMax']")
            value = _text(price, "*[local-name()='price']")
            if value is None:
                continue
            msrp_tiers.append(PriceTier(
                group_name=group_name,
                qty_min=int(qmin) if qmin else 1,
                qty_max=int(qmax) if qmax else 2147483647,
                price=Decimal(value),
                currency=currency,
            ))
    if msrp_tiers:
        for v in variants:
            v.prices = list(msrp_tiers)

    apparel_details = ApparelDetailsIngest(
        ps_part_id=variants[0].part_id if variants else None,
        ps_last_change=last_change,
        apparel_style=next(iter(apparel_styles), None),
        is_closeout=is_closeout,
        is_caution=is_caution,
        caution_comment=caution_comment,
        is_hazmat=None,
        is_on_demand=False,
        fabric_specs=fabric_specs_collected or None,
        fob_points=fob_points or None,
        keywords=keywords or None,
    )

    images: list[ImageIngest] = []
    if primary_image:
        images.append(ImageIngest(url=primary_image, image_type="primary"))

    return ProductIngest(
        supplier_sku=product_id,
        product_name=name or product_id,
        brand=brand,
        description=description,
        product_type="apparel",
        pricing_method="tiered_variants",
        image_url=primary_image,
        category_external_id=cat_external_id,
        category_name=cat_name,
        apparel_details=apparel_details,
        variants=variants,
        images=images,
    )


def merge_pricing(ingest: ProductIngest, pricing_xml: bytes) -> ProductIngest:
    """Append PartPriceArray tiers (Net, Sale, Case, …) onto each variant."""
    root = etree.fromstring(pricing_xml)
    parts = root.xpath("//*[local-name()='Part']")
    by_part = {v.part_id: v for v in ingest.variants}
    for part in parts:
        pid = _text(part, "*[local-name()='partId']")
        if not pid or pid not in by_part:
            continue
        for pp in part.xpath(
            "*[local-name()='PartPriceArray']/*[local-name()='PartPrice']"
        ):
            qmin = _text(pp, "*[local-name()='minQuantity']")
            value = _text(pp, "*[local-name()='price']")
            discount_code = _text(pp, "*[local-name()='discountCode']") or "Net"
            effective = _parse_iso(_text(pp, "*[local-name()='priceEffectiveDate']"))
            if not value:
                continue
            qmin_int = int(qmin) if qmin else 1
            # Skip duplicates that match an existing tier exactly.
            existing = by_part[pid].prices
            if any(
                t.group_name == discount_code and t.qty_min == qmin_int
                and str(t.price) == value
                for t in existing
            ):
                continue
            existing.append(PriceTier(
                group_name=discount_code,
                qty_min=qmin_int,
                qty_max=2147483647,
                price=Decimal(value),
                currency="USD",
                effective_from=effective,
            ))
    return ingest


def merge_media(ingest: ProductIngest, media_xml: bytes) -> ProductIngest:
    """Append MediaContentArray entries to ingest.images."""
    root = etree.fromstring(media_xml)
    seen_urls = {img.url for img in ingest.images}
    for media in root.xpath("//*[local-name()='MediaContent']"):
        url = _text(media, "*[local-name()='url']")
        if not url or url in seen_urls:
            continue
        class_name = _text(
            media,
            "*[local-name()='ClassTypeArray']/*[local-name()='ClassType']/*[local-name()='classTypeName']",
        )
        kind = _MEDIA_CLASS_TO_TYPE.get((class_name or "").strip().lower(), "front")
        color = _text(media, "*[local-name()='color']")
        ingest.images.append(ImageIngest(
            url=url,
            image_type=kind,
            color=color,
            sort_order=len(ingest.images),
        ))
        seen_urls.add(url)
    return ingest
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_promostandards_adapter.py::test_ps_normalizer_builds_apparel_product_ingest_from_pc61_fixture tests/test_promostandards_adapter.py::test_ps_normalizer_handles_mm1000_fixture -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/promostandards/ps_normalizer_v2.py backend/tests/test_promostandards_adapter.py
git commit -m "feat(promostandards): pure XML → ProductIngest normalizer (apparel)"
```

---

### Task 6: Skeleton `PromoStandardsAdapter` (auth + WSDL plumbing, hydrate_product stub)

**Files:**
- Create: `backend/modules/promostandards/adapter.py`
- Test: `backend/tests/test_promostandards_adapter.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_promostandards_adapter.py`:

```python
@pytest.mark.asyncio
async def test_promostandards_adapter_requires_id_password(seed_supplier: Supplier):
    """PromoStandardsAdapter raises AuthError if id/password missing on supplier."""
    from modules.import_jobs.base import AuthError, DiscoveryMode
    from modules.promostandards.adapter import PromoStandardsAdapter

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.auth_config = {}
        loaded.adapter_class = "PromoStandardsAdapter"
        await s.commit()
        await s.refresh(loaded)
        adapter = PromoStandardsAdapter(supplier=loaded, db=s)
        with pytest.raises(AuthError):
            await adapter.discover(DiscoveryMode.EXPLICIT_LIST, 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_promostandards_adapter.py::test_promostandards_adapter_requires_id_password -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Create the adapter skeleton**

Create `backend/modules/promostandards/adapter.py`:

```python
"""Generic PromoStandards adapter.

Wraps modules.promostandards.client.PromoStandardsClient (zeep-based) and
modules.promostandards.ps_normalizer_v2 (pure XML → ProductIngest). Resolves
WSDL URLs via supplier.endpoint_cache (PS Directory) — SanMar overrides this
in sanmar_adapter.py.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from modules.catalog.schemas import ProductIngest
from modules.import_jobs.base import (
    AuthError,
    BaseAdapter,
    DiscoveryMode,
    ProductRef,
    SupplierError,
)
from modules.suppliers.models import Supplier
from sqlalchemy.ext.asyncio import AsyncSession

from .resolver import resolve_wsdl_url

log = logging.getLogger(__name__)


class PromoStandardsAdapter(BaseAdapter):
    product_type = "apparel"

    def _require_auth(self) -> dict:
        auth = dict(self.supplier.auth_config or {})
        ps_id = auth.get("id")
        password = auth.get("password")
        if not ps_id or not password:
            raise AuthError(
                f"Supplier {self.supplier.name!r} missing PromoStandards id/password"
            )
        return {"id": ps_id, "password": password}

    def _wsdl_for(self, service_type: str) -> str:
        cache = self.supplier.endpoint_cache or []
        url = resolve_wsdl_url(cache, service_type)
        if not url:
            raise SupplierError(
                "wsdl_missing",
                f"WSDL for service {service_type!r} not in endpoint_cache for "
                f"supplier {self.supplier.name!r}",
            )
        return url

    async def discover(
        self, mode: DiscoveryMode, limit: Optional[int]
    ) -> list[ProductRef]:
        self._require_auth()
        cfg = dict(self.supplier.protocol_config or {})
        if mode is DiscoveryMode.EXPLICIT_LIST:
            ids = cfg.get("explicit_list") or []
            if limit is not None:
                ids = ids[:limit]
            return [ProductRef(product_id=str(i)) for i in ids]
        # FIRST_N / FILTERED_SAMPLE / FULL_SELLABLE all hit GetProductSellable.
        if mode in (
            DiscoveryMode.FIRST_N,
            DiscoveryMode.FILTERED_SAMPLE,
            DiscoveryMode.FULL_SELLABLE,
        ):
            refs = await self._call_get_product_sellable()
            if mode is DiscoveryMode.FILTERED_SAMPLE:
                wanted = cfg.get("explicit_list") or []
                wanted_set = set(map(str, wanted))
                refs = [r for r in refs if r.product_id in wanted_set]
            if limit is not None:
                refs = refs[:limit]
            return refs
        if mode is DiscoveryMode.DELTA:
            since = cfg.get("delta_since")
            if not since:
                raise SupplierError(
                    "delta_since_missing",
                    "DiscoveryMode.DELTA requires protocol_config.delta_since",
                )
            return await self.discover_changed(datetime.fromisoformat(since))
        if mode is DiscoveryMode.CLOSEOUTS:
            return await self.discover_closeouts()
        raise NotImplementedError(f"discovery mode {mode!r} not supported")

    async def hydrate_product(self, ref: ProductRef) -> ProductIngest:
        self._require_auth()
        get_product_xml = await self._call_get_product(ref)
        from .ps_normalizer_v2 import (
            merge_media,
            merge_pricing,
            normalize_get_product_xml,
        )

        ingest = normalize_get_product_xml(get_product_xml)
        try:
            pricing_xml = await self._call_get_pricing(ref)
            ingest = merge_pricing(ingest, pricing_xml)
        except SupplierError as exc:                # pricing optional; log and continue
            log.warning("Pricing fetch failed for %s: %s", ref.product_id, exc)
        try:
            media_xml = await self._call_get_media(ref)
            ingest = merge_media(ingest, media_xml)
        except SupplierError as exc:
            log.warning("Media fetch failed for %s: %s", ref.product_id, exc)
        return ingest

    async def discover_changed(self, since: datetime) -> list[ProductRef]:
        self._require_auth()
        return await self._call_get_product_date_modified(since)

    async def discover_closeouts(self) -> list[ProductRef]:
        self._require_auth()
        return await self._call_get_product_closeout()

    # ----- Transport hooks (overridden in tests via patching) -----

    async def _call_get_product_sellable(self) -> list[ProductRef]:
        raise NotImplementedError("transport plumbing in Task 7")

    async def _call_get_product(self, ref: ProductRef) -> bytes:
        raise NotImplementedError("transport plumbing in Task 7")

    async def _call_get_pricing(self, ref: ProductRef) -> bytes:
        raise NotImplementedError("transport plumbing in Task 7")

    async def _call_get_media(self, ref: ProductRef) -> bytes:
        raise NotImplementedError("transport plumbing in Task 7")

    async def _call_get_product_date_modified(self, since: datetime) -> list[ProductRef]:
        raise NotImplementedError("transport plumbing in Task 7")

    async def _call_get_product_closeout(self) -> list[ProductRef]:
        raise NotImplementedError("transport plumbing in Task 7")
```

Update `backend/modules/promostandards/__init__.py`:

```python
"""PromoStandards adapter package."""
from .adapter import PromoStandardsAdapter   # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_promostandards_adapter.py::test_promostandards_adapter_requires_id_password -v`
Expected: PASS (the auth check raises before transport stubs).

- [ ] **Step 5: Commit**

```bash
git add backend/modules/promostandards/adapter.py backend/modules/promostandards/__init__.py backend/tests/test_promostandards_adapter.py
git commit -m "feat(promostandards): adapter skeleton with auth + discovery routing"
```

---

### Task 7: Wire PS adapter transport hooks to fixture loader (test) + zeep (production)

**Files:**
- Modify: `backend/modules/promostandards/adapter.py`
- Test: `backend/tests/test_promostandards_adapter.py`

The transport hooks load XML bytes. In production each calls the existing `PromoStandardsClient` and returns its raw envelope. In tests we monkeypatch each hook to return on-disk fixtures. This keeps the adapter logic SOAP-implementation-agnostic.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_promostandards_adapter.py`:

```python
class FixtureBackedPSAdapter:
    """Mixin that overrides transport hooks to read XML from fixtures.

    Used in tests instead of monkeypatching, so the import is explicit and
    the transcript shows the test wiring directly.
    """

    fixture_map: dict[str, str] = {}

    async def _call_get_product(self, ref):
        path = self.fixture_map[f"product:{ref.product_id}"]
        return (FIXTURES_DIR / path).read_bytes()

    async def _call_get_pricing(self, ref):
        path = self.fixture_map[f"pricing:{ref.product_id}"]
        return (FIXTURES_DIR / path).read_bytes()

    async def _call_get_media(self, ref):
        path = self.fixture_map[f"media:{ref.product_id}"]
        return (FIXTURES_DIR / path).read_bytes()

    async def _call_get_product_sellable(self):
        from modules.import_jobs.base import ProductRef
        from lxml import etree
        path = self.fixture_map["sellable"]
        root = etree.fromstring((FIXTURES_DIR / path).read_bytes())
        out = []
        for p in root.xpath("//*[local-name()='ProductSellable']"):
            pid = p.xpath("*[local-name()='productId']/text()")
            qid = p.xpath("*[local-name()='partId']/text()")
            if pid:
                out.append(ProductRef(product_id=pid[0], part_id=qid[0] if qid else None))
        return out

    async def _call_get_product_date_modified(self, since):
        from modules.import_jobs.base import ProductRef
        from lxml import etree
        path = self.fixture_map["date_modified"]
        root = etree.fromstring((FIXTURES_DIR / path).read_bytes())
        return [
            ProductRef(
                product_id=p.xpath("*[local-name()='productId']/text()")[0],
                part_id=(p.xpath("*[local-name()='partId']/text()") or [None])[0],
            )
            for p in root.xpath("//*[local-name()='ProductDateModified']")
        ]

    async def _call_get_product_closeout(self):
        from modules.import_jobs.base import ProductRef
        from lxml import etree
        path = self.fixture_map["closeout"]
        root = etree.fromstring((FIXTURES_DIR / path).read_bytes())
        return [
            ProductRef(
                product_id=p.xpath("*[local-name()='productId']/text()")[0],
                part_id=(p.xpath("*[local-name()='partId']/text()") or [None])[0],
            )
            for p in root.xpath("//*[local-name()='ProductCloseOut']")
        ]


@pytest.mark.asyncio
async def test_promostandards_adapter_hydrates_pc61_via_fixtures(seed_supplier: Supplier):
    from modules.import_jobs.base import DiscoveryMode, ProductRef
    from modules.promostandards.adapter import PromoStandardsAdapter

    class TestAdapter(FixtureBackedPSAdapter, PromoStandardsAdapter):
        fixture_map = {
            "product:PC61": "sanmar_get_product_pc61.xml",
            "pricing:PC61": "sanmar_get_pricing_pc61.xml",
            "media:PC61": "sanmar_get_media_pc61.xml",
            "sellable": "sanmar_get_product_sellable.xml",
            "date_modified": "sanmar_get_product_date_modified.xml",
            "closeout": "sanmar_get_product_closeout.xml",
        }

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.auth_config = {"id": "user", "password": "pw"}
        loaded.protocol_config = {
            "discovery_mode": "explicit_list",
            "explicit_list": ["PC61"],
            "max_products": 5,
        }
        await s.commit()
        await s.refresh(loaded)
        adapter = TestAdapter(supplier=loaded, db=s)

        refs = await adapter.discover(DiscoveryMode.EXPLICIT_LIST, 5)
        assert refs == [ProductRef(product_id="PC61")]

        ingest = await adapter.hydrate_product(refs[0])
        assert ingest.supplier_sku == "PC61"
        assert len(ingest.variants) == 2
        assert any(t.group_name == "Net" for t in ingest.variants[0].prices)
        assert len(ingest.images) == 4


@pytest.mark.asyncio
async def test_promostandards_adapter_full_sellable_with_limit(seed_supplier: Supplier):
    from modules.import_jobs.base import DiscoveryMode
    from modules.promostandards.adapter import PromoStandardsAdapter

    class TestAdapter(FixtureBackedPSAdapter, PromoStandardsAdapter):
        fixture_map = {"sellable": "sanmar_get_product_sellable.xml"}

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.auth_config = {"id": "user", "password": "pw"}
        loaded.protocol_config = {}
        await s.commit()
        await s.refresh(loaded)

        refs = await TestAdapter(loaded, s).discover(DiscoveryMode.FULL_SELLABLE, 3)
        assert len(refs) == 3
        assert refs[0].product_id == "PC61"


@pytest.mark.asyncio
async def test_promostandards_adapter_discover_closeouts(seed_supplier: Supplier):
    from modules.import_jobs.base import DiscoveryMode
    from modules.promostandards.adapter import PromoStandardsAdapter

    class TestAdapter(FixtureBackedPSAdapter, PromoStandardsAdapter):
        fixture_map = {"closeout": "sanmar_get_product_closeout.xml"}

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.auth_config = {"id": "user", "password": "pw"}
        await s.commit()
        await s.refresh(loaded)

        refs = await TestAdapter(loaded, s).discover(DiscoveryMode.CLOSEOUTS, None)
        assert refs[0].product_id == "DM104CL"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_promostandards_adapter.py -v -k "hydrates_pc61 or full_sellable_with_limit or discover_closeouts"`
Expected: 3 FAILS — `NotImplementedError`.

- [ ] **Step 3: Implement the production transport hooks**

Edit `backend/modules/promostandards/adapter.py`. Replace each `_call_*` stub with a zeep-backed implementation. Add at top:

```python
import asyncio
from lxml import etree
from zeep import Client as ZeepClient
from zeep.cache import SqliteCache
from zeep.helpers import serialize_object  # noqa: F401
from zeep.transports import Transport
```

Then the implementations:

```python
def _zeep_client(self, wsdl_url: str) -> ZeepClient:
    transport = Transport(cache=SqliteCache(timeout=86400))
    return ZeepClient(wsdl=wsdl_url, transport=transport)

async def _to_xml(self, op_result) -> bytes:
    """Convert a zeep response object into an XML envelope bytestring.

    zeep doesn't expose the original envelope by default, so we serialize
    the response into a deterministic XML envelope ourselves.
    """
    raise NotImplementedError("see _call_get_product for serialization shape")
```

A simpler concrete approach: use zeep's `_op_call.history.last_received["envelope"]` which is the raw lxml element. Update each hook accordingly:

```python
async def _call_get_product(self, ref: ProductRef) -> bytes:
    auth = self._require_auth()
    wsdl = self._wsdl_for("product_data")
    client = self._zeep_client(wsdl)

    def _call() -> bytes:
        client.service.getProduct(
            wsVersion="2.0.0",
            id=auth["id"],
            password=auth["password"],
            localizationCountry="us",
            localizationLanguage="en",
            productId=ref.product_id,
            partId=ref.part_id,
        )
        envelope = client.transport.history.last_received["envelope"]
        return etree.tostring(envelope)
    return await asyncio.to_thread(_call)


async def _call_get_pricing(self, ref: ProductRef) -> bytes:
    auth = self._require_auth()
    wsdl = self._wsdl_for("ppc")
    client = self._zeep_client(wsdl)

    def _call() -> bytes:
        client.service.getConfigurationAndPricing(
            wsVersion="1.0.0",
            id=auth["id"],
            password=auth["password"],
            productId=ref.product_id,
            currency="USD",
            fobId="1",
            priceType="List",
            localizationCountry="US",
            localizationLanguage="en",
            configurationType="Blank",
        )
        envelope = client.transport.history.last_received["envelope"]
        return etree.tostring(envelope)
    return await asyncio.to_thread(_call)


async def _call_get_media(self, ref: ProductRef) -> bytes:
    auth = self._require_auth()
    wsdl = self._wsdl_for("media")
    client = self._zeep_client(wsdl)

    def _call() -> bytes:
        client.service.getMediaContent(
            wsVersion="1.1.0",
            id=auth["id"],
            password=auth["password"],
            mediaType="Image",
            productId=ref.product_id,
            partId=ref.part_id,
        )
        envelope = client.transport.history.last_received["envelope"]
        return etree.tostring(envelope)
    return await asyncio.to_thread(_call)


async def _call_get_product_sellable(self) -> list[ProductRef]:
    auth = self._require_auth()
    wsdl = self._wsdl_for("product_data")
    client = self._zeep_client(wsdl)

    def _call():
        return client.service.getProductSellable(
            wsVersion="2.0.0",
            id=auth["id"],
            password=auth["password"],
            isSellable=True,
        )
    raw = await asyncio.to_thread(_call)
    out: list[ProductRef] = []
    for item in (raw or []):
        pid = getattr(item, "productId", None)
        qid = getattr(item, "partId", None)
        if pid:
            out.append(ProductRef(product_id=str(pid), part_id=str(qid) if qid else None))
    return out


async def _call_get_product_date_modified(self, since: datetime) -> list[ProductRef]:
    auth = self._require_auth()
    wsdl = self._wsdl_for("product_data")
    client = self._zeep_client(wsdl)

    def _call():
        return client.service.getProductDateModified(
            wsVersion="2.0.0",
            id=auth["id"],
            password=auth["password"],
            changeTimeStamp=since.isoformat(),
        )
    raw = await asyncio.to_thread(_call)
    out: list[ProductRef] = []
    for item in (raw or []):
        pid = getattr(item, "productId", None)
        qid = getattr(item, "partId", None)
        if pid:
            out.append(ProductRef(product_id=str(pid), part_id=str(qid) if qid else None))
    return out


async def _call_get_product_closeout(self) -> list[ProductRef]:
    auth = self._require_auth()
    wsdl = self._wsdl_for("product_data")
    client = self._zeep_client(wsdl)

    def _call():
        return client.service.getProductCloseOut(
            wsVersion="2.0.0",
            id=auth["id"],
            password=auth["password"],
        )
    raw = await asyncio.to_thread(_call)
    out: list[ProductRef] = []
    for item in (raw or []):
        pid = getattr(item, "productId", None)
        qid = getattr(item, "partId", None)
        if pid:
            out.append(ProductRef(product_id=str(pid), part_id=str(qid) if qid else None))
    return out
```

The tests use `FixtureBackedPSAdapter` to override these — they never run zeep. Production code paths run them as written.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_promostandards_adapter.py -v -k "hydrates_pc61 or full_sellable_with_limit or discover_closeouts"`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/promostandards/adapter.py backend/tests/test_promostandards_adapter.py
git commit -m "feat(promostandards): wire adapter transport hooks (zeep prod, fixture test)"
```

---

### Task 8: SOAP fault → adapter exception mapping

**Files:**
- Modify: `backend/modules/promostandards/adapter.py`
- Modify: `backend/modules/promostandards/ps_normalizer_v2.py` (or new `errors.py`)
- Test: `backend/tests/test_promostandards_adapter.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_promostandards_adapter.py`:

```python
def test_ps_fault_xml_maps_to_auth_error_and_supplier_error():
    from modules.promostandards.adapter import _classify_fault_xml
    from modules.import_jobs.base import AuthError, SupplierError

    auth_xml = (FIXTURES_DIR / "sanmar_auth_failure.xml").read_bytes()
    with pytest.raises(AuthError):
        _classify_fault_xml(auth_xml)

    not_found_xml = (FIXTURES_DIR / "sanmar_product_not_found.xml").read_bytes()
    with pytest.raises(SupplierError) as exc:
        _classify_fault_xml(not_found_xml)
    assert exc.value.code == "130"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_promostandards_adapter.py::test_ps_fault_xml_maps_to_auth_error_and_supplier_error -v`
Expected: FAIL — no `_classify_fault_xml`.

- [ ] **Step 3: Add the helper**

In `backend/modules/promostandards/adapter.py`, near the top (under imports), add:

```python
_AUTH_CODES = {"100", "104", "105", "110"}


def _classify_fault_xml(xml_bytes: bytes) -> None:
    """Translate a SOAP Fault envelope into AuthError or SupplierError.

    Returns silently if the envelope is not a Fault (caller continues).
    """
    root = etree.fromstring(xml_bytes)
    fault = root.xpath("//*[local-name()='Fault']")
    if not fault:
        return
    code_node = root.xpath(
        "//*[local-name()='errorMessage']/*[local-name()='code']"
    )
    msg_node = root.xpath(
        "//*[local-name()='errorMessage']/*[local-name()='message']"
    )
    code = (code_node[0].text or "").strip() if code_node else ""
    message = (msg_node[0].text or "").strip() if msg_node else "Unknown PS fault"
    if code in _AUTH_CODES:
        raise AuthError(f"[{code}] {message}")
    raise SupplierError(code or "999", message)
```

Then in each `_call_*` hook, wrap parsing the response:

```python
def _call() -> bytes:
    try:
        client.service.getProduct(...)
    except Exception:                      # zeep wraps faults
        envelope = client.transport.history.last_received and \
            client.transport.history.last_received.get("envelope")
        if envelope is not None:
            _classify_fault_xml(etree.tostring(envelope))
        raise
    envelope = client.transport.history.last_received["envelope"]
    body = etree.tostring(envelope)
    _classify_fault_xml(body)
    return body
```

Apply the same wrap to `_call_get_pricing`, `_call_get_media`, `_call_get_product_sellable`, `_call_get_product_date_modified`, `_call_get_product_closeout`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_promostandards_adapter.py::test_ps_fault_xml_maps_to_auth_error_and_supplier_error -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/promostandards/adapter.py backend/tests/test_promostandards_adapter.py
git commit -m "feat(promostandards): map SOAP faults to AuthError / SupplierError"
```

---

### Task 9: `SanMarAdapter` subclass — WSDL overrides + auth shape + FTP flag

**Files:**
- Create: `backend/modules/promostandards/sanmar_adapter.py`
- Modify: `backend/modules/promostandards/__init__.py`
- Test: `backend/tests/test_sanmar_adapter.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_sanmar_adapter.py`:

```python
"""SanMarAdapter override tests."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from modules.suppliers.models import Supplier


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_sanmar_adapter_resolves_default_wsdls(seed_supplier: Supplier):
    """SanMarAdapter knows the canonical SanMar WSDL URLs without endpoint_cache."""
    from modules.promostandards.sanmar_adapter import SanMarAdapter

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.endpoint_cache = None       # force defaults
        loaded.protocol_config = {"environment": "production"}
        loaded.auth_config = {"id": "user", "password": "pw"}
        await s.commit()
        await s.refresh(loaded)

        adapter = SanMarAdapter(supplier=loaded, db=s)
        assert adapter._wsdl_for("product_data").endswith(
            "ProductDataServiceV2.xml?wsdl"
        )
        assert adapter._wsdl_for("media").endswith(
            "MediaContentServiceBinding?wsdl"
        )
        assert adapter._wsdl_for("ppc").endswith(
            "PricingAndConfigurationServiceBinding?WSDL"
        )
        assert adapter._wsdl_for("inventory").endswith(
            "InventoryServiceBindingV2final?WSDL"
        )


@pytest.mark.asyncio
async def test_sanmar_adapter_test_environment_uses_test_host(seed_supplier: Supplier):
    from modules.promostandards.sanmar_adapter import SanMarAdapter

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.endpoint_cache = None
        loaded.protocol_config = {"environment": "test"}
        loaded.auth_config = {"id": "user", "password": "pw"}
        await s.commit()
        await s.refresh(loaded)

        adapter = SanMarAdapter(supplier=loaded, db=s)
        assert "test-ws.sanmar.com" in adapter._wsdl_for("product_data")


@pytest.mark.asyncio
async def test_sanmar_adapter_ftp_flag_recognized(seed_supplier: Supplier):
    """enable_ftp_bulk flag is read and exposed (even though impl is deferred)."""
    from modules.promostandards.sanmar_adapter import SanMarAdapter

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.protocol_config = {
            "enable_ftp_bulk": True,
            "ftp_user": "u",
            "ftp_password": "p",
        }
        loaded.auth_config = {"id": "user", "password": "pw"}
        await s.commit()
        await s.refresh(loaded)

        adapter = SanMarAdapter(supplier=loaded, db=s)
        assert adapter.is_ftp_bulk_enabled() is True
        with pytest.raises(NotImplementedError):
            await adapter.discover_via_ftp_bulk()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_sanmar_adapter.py -v`
Expected: 3 FAILS — `ImportError`.

- [ ] **Step 3: Create `sanmar_adapter.py`**

Create `backend/modules/promostandards/sanmar_adapter.py`:

```python
"""SanMar-specific PromoStandards overrides.

Per CLAUDE.md ("no per-supplier code") this stays a SUBCLASS of
PromoStandardsAdapter — it does not duplicate the SOAP machinery, only
overrides the supplier-specific bits:

- Default WSDL URLs (SanMar publishes deterministic per-service URLs)
- Test-vs-production environment switch via protocol_config.environment
- FTP-bulk discovery FLAG (impl deferred — caller can detect intent)
- Live inventory helper (PS Inventory v2 — runtime-only, never stored)
"""
from __future__ import annotations

from typing import Optional

from .adapter import PromoStandardsAdapter
from modules.import_jobs.base import ProductRef, SupplierError


_PROD_WSDLS = {
    "product_data": "https://ws.sanmar.com:8080/promostandards/ProductDataServiceV2.xml?wsdl",
    "inventory": "https://ws.sanmar.com:8080/promostandards/InventoryServiceBindingV2final?WSDL",
    "media": "https://ws.sanmar.com:8080/promostandards/MediaContentServiceBinding?wsdl",
    "ppc": "https://ws.sanmar.com:8080/promostandards/PricingAndConfigurationServiceBinding?WSDL",
}

_TEST_WSDLS = {
    "product_data": "https://test-ws.sanmar.com:8080/promostandards/ProductDataServiceV2.xml?wsdl",
    "inventory": "https://test-ws.sanmar.com:8080/promostandards/InventoryServiceBindingV2final?WSDL",
    "media": "https://test-ws.sanmar.com:8080/promostandards/MediaContentServiceBinding?wsdl",
    "ppc": "https://test-ws.sanmar.com:8080/promostandards/PricingAndConfigurationServiceBinding?WSDL",
}


class SanMarAdapter(PromoStandardsAdapter):
    """SanMar PromoStandards adapter."""

    def _wsdl_for(self, service_type: str) -> str:
        # First, honor any explicit override in protocol_config.wsdl_overrides.
        cfg = dict(self.supplier.protocol_config or {})
        overrides = cfg.get("wsdl_overrides") or {}
        if service_type in overrides:
            return overrides[service_type]

        # Next, the supplier's PS Directory cache (rarely populated for SanMar
        # because we publish deterministic URLs in this class).
        try:
            return super()._wsdl_for(service_type)
        except SupplierError:
            pass

        env = (cfg.get("environment") or "production").lower()
        table = _TEST_WSDLS if env == "test" else _PROD_WSDLS
        if service_type not in table:
            raise SupplierError(
                "wsdl_unknown_service",
                f"SanMarAdapter has no default WSDL for service {service_type!r}",
            )
        return table[service_type]

    def is_ftp_bulk_enabled(self) -> bool:
        cfg = dict(self.supplier.protocol_config or {})
        return bool(cfg.get("enable_ftp_bulk"))

    async def discover_via_ftp_bulk(self) -> list[ProductRef]:
        """Bulk discovery via SanMar SFTP files (sanmar_epdd.csv).

        Implementation deferred — Phase 6 (or a dedicated SanMar FTP plan)
        will land the parser. This stub exists so the protocol_config flag
        round-trips and tests can assert intent without forcing impl now.
        """
        raise NotImplementedError(
            "FTP-bulk discovery is plumbed but not yet implemented; "
            "set enable_ftp_bulk=False or wait for the SanMar FTP plan."
        )

    async def live_inventory(self, ref: ProductRef) -> dict:
        """Runtime inventory check via PS Inventory v2.

        Returns a dict shaped like
            {"part_id": str, "available": int, "by_warehouse": {wh_id: qty}}
        Never writes to the DB. Caller composes this into checkout flows.
        """
        # Fixtures + production hookup are added in a later task if/when
        # frontend needs it. For now, expose the contract.
        raise NotImplementedError("live_inventory wiring deferred to Phase 4/5")
```

Update `backend/modules/promostandards/__init__.py`:

```python
"""PromoStandards adapter package."""
from .adapter import PromoStandardsAdapter   # noqa: F401
from .sanmar_adapter import SanMarAdapter    # noqa: F401
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_sanmar_adapter.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/promostandards/sanmar_adapter.py backend/modules/promostandards/__init__.py backend/tests/test_sanmar_adapter.py
git commit -m "feat(promostandards): SanMarAdapter subclass with default WSDLs + FTP flag"
```

---

### Task 10: Adapter registration on startup

**Files:**
- Modify: `backend/modules/import_jobs/__init__.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_promostandards_adapter.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_promostandards_adapter.py`:

```python
def test_default_adapters_registered_on_import():
    """Importing modules.import_jobs registers PromoStandards + SanMar adapters."""
    import modules.import_jobs   # noqa: F401  (registration is import side-effect)
    from modules.import_jobs.registry import _REGISTRY
    assert "PromoStandardsAdapter" in _REGISTRY
    assert "SanMarAdapter" in _REGISTRY
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_promostandards_adapter.py::test_default_adapters_registered_on_import -v`
Expected: FAIL.

- [ ] **Step 3: Wire registrations**

Update `backend/modules/import_jobs/__init__.py`:

```python
"""Supplier-agnostic import job orchestration."""
from .registry import register_adapter

# Register canonical adapters at import time. New adapters added here.
from modules.promostandards.adapter import PromoStandardsAdapter
from modules.promostandards.sanmar_adapter import SanMarAdapter

register_adapter("PromoStandardsAdapter", PromoStandardsAdapter)
register_adapter("SanMarAdapter", SanMarAdapter)
```

In `backend/main.py`, add an import alongside existing model imports (around line 18):

```python
import modules.import_jobs   # noqa: F401  (adapter registry side-effect)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_promostandards_adapter.py::test_default_adapters_registered_on_import -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/import_jobs/__init__.py backend/main.py backend/tests/test_promostandards_adapter.py
git commit -m "feat(import_jobs): register PromoStandards + SanMar adapters at import"
```

---

### Task 11: `run_import` orchestrator service

**Files:**
- Create: `backend/modules/import_jobs/service.py`
- Test: `backend/tests/test_import_service.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_import_service.py`:

```python
"""End-to-end import service tests with recorded fixtures."""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from modules.suppliers.models import Supplier


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sanmar_fixture_adapter_class():
    """A SanMarAdapter that overrides transport hooks with fixture readers."""
    from modules.promostandards.sanmar_adapter import SanMarAdapter
    from modules.import_jobs.base import ProductRef
    from lxml import etree

    class FixtureSanMarAdapter(SanMarAdapter):
        async def _call_get_product(self, ref):
            mapping = {"PC61": "sanmar_get_product_pc61.xml",
                       "MM1000": "sanmar_get_product_mm1000.xml"}
            if ref.product_id not in mapping:
                from modules.import_jobs.base import SupplierError
                raise SupplierError("130", f"Product {ref.product_id} not found")
            return (FIXTURES_DIR / mapping[ref.product_id]).read_bytes()

        async def _call_get_pricing(self, ref):
            mapping = {"PC61": "sanmar_get_pricing_pc61.xml"}
            if ref.product_id not in mapping:
                from modules.import_jobs.base import SupplierError
                raise SupplierError("160", "no pricing fixture")
            return (FIXTURES_DIR / mapping[ref.product_id]).read_bytes()

        async def _call_get_media(self, ref):
            mapping = {"PC61": "sanmar_get_media_pc61.xml"}
            if ref.product_id not in mapping:
                from modules.import_jobs.base import SupplierError
                raise SupplierError("160", "no media fixture")
            return (FIXTURES_DIR / mapping[ref.product_id]).read_bytes()

        async def _call_get_product_sellable(self):
            root = etree.fromstring(
                (FIXTURES_DIR / "sanmar_get_product_sellable.xml").read_bytes()
            )
            return [
                ProductRef(
                    product_id=p.xpath("*[local-name()='productId']/text()")[0],
                    part_id=(p.xpath("*[local-name()='partId']/text()") or [None])[0],
                )
                for p in root.xpath("//*[local-name()='ProductSellable']")
            ]

    return FixtureSanMarAdapter


@pytest.mark.asyncio
async def test_run_import_persists_two_apparel_products(
    seed_supplier: Supplier, sanmar_fixture_adapter_class
):
    from modules.import_jobs.service import run_import
    from modules.import_jobs.base import DiscoveryMode
    from modules.import_jobs.registry import register_adapter
    from modules.catalog.models import (
        ApparelDetails,
        Product,
        ProductImage,
        ProductVariant,
        VariantPrice,
    )

    register_adapter("FixtureSanMarAdapter", sanmar_fixture_adapter_class)

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "FixtureSanMarAdapter"
        loaded.auth_config = {"id": "user", "password": "pw"}
        loaded.protocol_config = {
            "discovery_mode": "explicit_list",
            "explicit_list": ["PC61", "MM1000"],
            "max_products": 20,
        }
        await s.commit()
        await s.refresh(loaded)
        supplier_id: UUID = loaded.id

    summary = await run_import(
        supplier_id=supplier_id,
        mode="explicit_list",
        limit=20,
    )
    assert summary["status"] == "success"
    assert summary["records_processed"] == 2
    assert summary["errors"] == []

    async with async_session() as s:
        rows = (await s.execute(
            select(Product).where(Product.supplier_id == supplier_id)
        )).scalars().all()
        skus = {p.supplier_sku for p in rows}
        assert {"PC61", "MM1000"}.issubset(skus)

        # PC61 → 2 variants (S, L), each with at least one MSRP tier
        pc61 = next(p for p in rows if p.supplier_sku == "PC61")
        details = await s.get(ApparelDetails, pc61.id)
        assert details.apparel_style == "Mens"
        variants = (await s.execute(
            select(ProductVariant).where(ProductVariant.product_id == pc61.id)
        )).scalars().all()
        assert len(variants) == 2
        for v in variants:
            tiers = (await s.execute(
                select(VariantPrice).where(VariantPrice.variant_id == v.id)
            )).scalars().all()
            assert any(t.group_name == "MSRP" for t in tiers)

        images = (await s.execute(
            select(ProductImage).where(ProductImage.product_id == pc61.id)
        )).scalars().all()
        assert len(images) >= 4   # primary + front + rear + swatch


@pytest.mark.asyncio
async def test_run_import_continues_on_per_product_error(
    seed_supplier: Supplier, sanmar_fixture_adapter_class
):
    """A bad productId in the explicit_list logs an error but the others persist."""
    from modules.import_jobs.service import run_import
    from modules.import_jobs.registry import register_adapter
    from modules.catalog.models import Product

    register_adapter("FixtureSanMarAdapter", sanmar_fixture_adapter_class)

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "FixtureSanMarAdapter"
        loaded.auth_config = {"id": "user", "password": "pw"}
        loaded.protocol_config = {
            "discovery_mode": "explicit_list",
            "explicit_list": ["PC61", "DOES-NOT-EXIST", "MM1000"],
            "max_products": 5,
        }
        await s.commit()
        await s.refresh(loaded)
        supplier_id = loaded.id

    summary = await run_import(supplier_id=supplier_id, mode="explicit_list", limit=5)
    assert summary["status"] == "partial_success"
    assert summary["records_processed"] == 2
    assert any(err["product_id"] == "DOES-NOT-EXIST" for err in summary["errors"])

    async with async_session() as s:
        rows = (await s.execute(
            select(Product).where(Product.supplier_id == supplier_id)
        )).scalars().all()
        assert {"PC61", "MM1000"} == {p.supplier_sku for p in rows}


@pytest.mark.asyncio
async def test_run_import_aborts_on_auth_error(seed_supplier: Supplier):
    """Auth failure aborts the whole job — no rows persisted."""
    from modules.import_jobs.service import run_import
    from modules.import_jobs.registry import register_adapter
    from modules.import_jobs.base import (
        AuthError,
        BaseAdapter,
        DiscoveryMode,
        ProductRef,
    )

    class AuthFailingAdapter(BaseAdapter):
        product_type = "apparel"

        async def discover(self, mode, limit):
            raise AuthError("[105] Authentication Credentials failed")

        async def hydrate_product(self, ref):
            raise AuthError("[105] Authentication Credentials failed")

    register_adapter("AuthFailingAdapter", AuthFailingAdapter)

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "AuthFailingAdapter"
        loaded.auth_config = {"id": "bad", "password": "bad"}
        loaded.protocol_config = {"discovery_mode": "explicit_list"}
        await s.commit()
        await s.refresh(loaded)
        supplier_id = loaded.id

    summary = await run_import(supplier_id=supplier_id, mode="explicit_list", limit=5)
    assert summary["status"] == "failed"
    assert "auth" in (summary.get("error") or "").lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_import_service.py -v`
Expected: 3 FAILS — `ImportError`.

- [ ] **Step 3: Implement the orchestrator**

Create `backend/modules/import_jobs/service.py`:

```python
"""Run a supplier import end-to-end.

Resolves the adapter from the supplier row, calls discover → hydrate →
persist for each ref, captures per-product errors, and writes a sync_jobs
row tracking start/finish/records_processed/errors.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
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
)
from .registry import get_adapter

log = logging.getLogger(__name__)


async def run_import(
    supplier_id: UUID,
    mode: str = "explicit_list",
    limit: Optional[int] = None,
) -> dict:
    """Execute one import job. Returns a status summary dict."""
    discovery_mode = DiscoveryMode(mode)

    async with async_session() as s:
        supplier = await s.get(Supplier, supplier_id)
        if supplier is None:
            return {"status": "failed", "error": f"supplier {supplier_id} not found"}

        job = SyncJob(
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            job_type=f"import_{discovery_mode.value}",
            status="running",
            started_at=datetime.now(timezone.utc),
            records_processed=0,
        )
        s.add(job)
        await s.commit()
        await s.refresh(job)
        job_id = job.id

    errors: list[dict] = []
    records_processed = 0
    fatal_error: Optional[str] = None

    try:
        async with async_session() as s:
            supplier = await s.get(Supplier, supplier_id)
            adapter = get_adapter(supplier, s)
            cfg = dict(supplier.protocol_config or {})
            effective_limit = limit if limit is not None else cfg.get("max_products")
            refs = await adapter.discover(discovery_mode, effective_limit)

        for ref in refs:
            async with async_session() as s:
                supplier = await s.get(Supplier, supplier_id)
                adapter = get_adapter(supplier, s)
                try:
                    ingest = await adapter.hydrate_product(ref)
                    await persist_product(ingest, supplier, s)
                    await s.commit()
                    records_processed += 1
                except AuthError:
                    raise
                except (SupplierError, PersistError, AdapterError, ValueError) as exc:
                    await s.rollback()
                    errors.append({
                        "product_id": ref.product_id,
                        "code": getattr(exc, "code", "999"),
                        "message": str(exc),
                    })
                    log.warning("Skipping %s: %s", ref.product_id, exc)

        if discovery_mode is DiscoveryMode.DELTA:
            async with async_session() as s:
                supplier = await s.get(Supplier, supplier_id)
                supplier.last_delta_sync = datetime.now(timezone.utc)
                await s.commit()
        elif discovery_mode is DiscoveryMode.FULL_SELLABLE:
            async with async_session() as s:
                supplier = await s.get(Supplier, supplier_id)
                supplier.last_full_sync = datetime.now(timezone.utc)
                await s.commit()
    except AuthError as exc:
        fatal_error = str(exc)
        log.error("Aborting import for supplier %s: %s", supplier_id, exc)

    if fatal_error:
        status = "failed"
    elif errors:
        status = "partial_success"
    else:
        status = "success"

    async with async_session() as s:
        job = await s.get(SyncJob, job_id)
        job.status = status
        job.records_processed = records_processed
        job.finished_at = datetime.now(timezone.utc)
        if fatal_error:
            job.error_log = fatal_error
        if errors:
            # SyncJob.error_log is a Text column today. Serialize JSON for now;
            # Phase 1 plan adds a JSONB errors column we'll switch to once it lands.
            import json
            job.error_log = (job.error_log or "") + json.dumps(errors)
        await s.commit()

    return {
        "sync_job_id": str(job_id),
        "status": status,
        "records_processed": records_processed,
        "errors": errors,
        "error": fatal_error,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_import_service.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/import_jobs/service.py backend/tests/test_import_service.py
git commit -m "feat(import_jobs): run_import orchestrator with per-product error capture"
```

---

### Task 12: `POST /api/suppliers/{id}/import` route + status polling

**Files:**
- Create: `backend/modules/import_jobs/routes.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_import_routes.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_import_routes.py`:

```python
"""HTTP smoke for the supplier-import endpoint."""
from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy import select

from database import async_session
from modules.suppliers.models import Supplier


@pytest.mark.asyncio
async def test_post_supplier_import_returns_202_with_sync_job_id(
    client, seed_supplier: Supplier, sanmar_fixture_adapter_class
):
    """POSTing to /api/suppliers/{id}/import enqueues a job and returns 202."""
    from modules.import_jobs.registry import register_adapter
    register_adapter("FixtureSanMarAdapter", sanmar_fixture_adapter_class)

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "FixtureSanMarAdapter"
        loaded.auth_config = {"id": "u", "password": "p"}
        loaded.protocol_config = {
            "explicit_list": ["PC61"],
            "max_products": 5,
        }
        await s.commit()
        supplier_id = loaded.id

    headers = {"X-Ingest-Secret": os.environ["INGEST_SHARED_SECRET"]}
    resp = await client.post(
        f"/api/suppliers/{supplier_id}/import",
        json={"mode": "explicit_list", "limit": 5},
        headers=headers,
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert "sync_job_id" in body
    UUID(body["sync_job_id"])  # parses as UUID


@pytest.mark.asyncio
async def test_get_sync_job_status_returns_running_or_completed(
    client, seed_supplier: Supplier, sanmar_fixture_adapter_class
):
    from modules.import_jobs.registry import register_adapter
    register_adapter("FixtureSanMarAdapter", sanmar_fixture_adapter_class)

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "FixtureSanMarAdapter"
        loaded.auth_config = {"id": "u", "password": "p"}
        loaded.protocol_config = {"explicit_list": ["PC61"], "max_products": 1}
        await s.commit()
        supplier_id = loaded.id

    headers = {"X-Ingest-Secret": os.environ["INGEST_SHARED_SECRET"]}
    enq = await client.post(
        f"/api/suppliers/{supplier_id}/import",
        json={"mode": "explicit_list", "limit": 1},
        headers=headers,
    )
    job_id = enq.json()["sync_job_id"]
    status_resp = await client.get(f"/api/sync_jobs/{job_id}", headers=headers)
    assert status_resp.status_code == 200, status_resp.text
    body = status_resp.json()
    assert body["status"] in {"running", "success", "partial_success"}


@pytest.mark.asyncio
async def test_post_supplier_import_409_when_job_already_running(
    client, seed_supplier: Supplier
):
    """A second concurrent import for the same supplier+mode returns 409."""
    from modules.sync_jobs.models import SyncJob
    from datetime import datetime, timezone
    headers = {"X-Ingest-Secret": os.environ["INGEST_SHARED_SECRET"]}
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "PromoStandardsAdapter"
        loaded.auth_config = {"id": "u", "password": "p"}
        loaded.protocol_config = {"explicit_list": []}
        await s.commit()
        # Manually insert a running job for the same mode.
        s.add(SyncJob(
            supplier_id=loaded.id,
            supplier_name=loaded.name,
            job_type="import_explicit_list",
            status="running",
            started_at=datetime.now(timezone.utc),
        ))
        await s.commit()
        supplier_id = loaded.id

    resp = await client.post(
        f"/api/suppliers/{supplier_id}/import",
        json={"mode": "explicit_list", "limit": 5},
        headers=headers,
    )
    assert resp.status_code == 409, resp.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_import_routes.py -v`
Expected: 3 FAILS — endpoint doesn't exist.

- [ ] **Step 3: Implement the routes**

Create `backend/modules/import_jobs/routes.py`:

```python
"""HTTP entrypoints for supplier imports.

POST /api/suppliers/{id}/import — enqueue an import job (202 + sync_job_id)
GET  /api/sync_jobs/{id}        — poll job status
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.catalog.ingest import require_ingest_secret
from modules.suppliers.models import Supplier
from modules.sync_jobs.models import SyncJob

from .base import DiscoveryMode
from .service import run_import

router = APIRouter(tags=["imports"])


class ImportRequest(BaseModel):
    mode: str = "explicit_list"
    limit: Optional[int] = None


@router.post("/api/suppliers/{supplier_id}/import", status_code=202)
async def enqueue_supplier_import(
    supplier_id: UUID,
    body: ImportRequest,
    background: BackgroundTasks,
    _: None = Depends(require_ingest_secret),
    db: AsyncSession = Depends(get_db),
):
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(404, f"Supplier {supplier_id} not found")
    if not supplier.is_active:
        raise HTTPException(409, f"Supplier {supplier.name!r} is not active")

    try:
        DiscoveryMode(body.mode)
    except ValueError as exc:
        raise HTTPException(400, f"Unsupported discovery mode {body.mode!r}") from exc

    job_type = f"import_{body.mode}"
    existing = (await db.execute(
        select(SyncJob).where(
            SyncJob.supplier_id == supplier_id,
            SyncJob.job_type == job_type,
            SyncJob.status == "running",
        )
    )).scalars().first()
    if existing is not None:
        raise HTTPException(409, f"Import already running (sync_job {existing.id})")

    job = SyncJob(
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        job_type=job_type,
        status="pending",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    async def _run():
        try:
            await run_import(
                supplier_id=supplier_id,
                mode=body.mode,
                limit=body.limit,
            )
        except Exception as exc:                    # never let a bg task die silently
            from database import async_session
            async with async_session() as s:
                row = await s.get(SyncJob, job.id)
                if row is not None:
                    row.status = "failed"
                    row.finished_at = datetime.now(timezone.utc)
                    row.error_log = f"unhandled: {exc}"
                    await s.commit()

    def _spawn():
        asyncio.create_task(_run())

    background.add_task(_spawn)

    return {"sync_job_id": str(job.id), "status": "pending"}


@router.get("/api/sync_jobs/{sync_job_id}")
async def get_sync_job(
    sync_job_id: UUID,
    _: None = Depends(require_ingest_secret),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(SyncJob, sync_job_id)
    if job is None:
        raise HTTPException(404, "sync job not found")
    return {
        "id": str(job.id),
        "supplier_id": str(job.supplier_id),
        "supplier_name": job.supplier_name,
        "job_type": job.job_type,
        "status": job.status,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "records_processed": job.records_processed,
        "error_log": job.error_log,
    }
```

In `backend/main.py`, register the router (add near other includes):

```python
from modules.import_jobs.routes import router as import_jobs_router
...
app.include_router(import_jobs_router)
```

- [ ] **Step 4: Move the `sanmar_fixture_adapter_class` fixture to `conftest.py`**

The route test reuses the fixture from Task 11. Move it from `test_import_service.py` to `backend/tests/conftest.py` (append):

```python
@pytest.fixture
def sanmar_fixture_adapter_class():
    """Reusable: a SanMarAdapter that reads recorded SOAP fixtures from disk."""
    from pathlib import Path
    from modules.promostandards.sanmar_adapter import SanMarAdapter
    from modules.import_jobs.base import ProductRef, SupplierError
    from lxml import etree

    fixtures = Path(__file__).parent / "fixtures"

    class FixtureSanMarAdapter(SanMarAdapter):
        async def _call_get_product(self, ref):
            mapping = {"PC61": "sanmar_get_product_pc61.xml",
                       "MM1000": "sanmar_get_product_mm1000.xml"}
            if ref.product_id not in mapping:
                raise SupplierError("130", f"Product {ref.product_id} not found")
            return (fixtures / mapping[ref.product_id]).read_bytes()

        async def _call_get_pricing(self, ref):
            mapping = {"PC61": "sanmar_get_pricing_pc61.xml"}
            if ref.product_id not in mapping:
                raise SupplierError("160", "no pricing fixture")
            return (fixtures / mapping[ref.product_id]).read_bytes()

        async def _call_get_media(self, ref):
            mapping = {"PC61": "sanmar_get_media_pc61.xml"}
            if ref.product_id not in mapping:
                raise SupplierError("160", "no media fixture")
            return (fixtures / mapping[ref.product_id]).read_bytes()

        async def _call_get_product_sellable(self):
            root = etree.fromstring(
                (fixtures / "sanmar_get_product_sellable.xml").read_bytes()
            )
            return [
                ProductRef(
                    product_id=p.xpath("*[local-name()='productId']/text()")[0],
                    part_id=(p.xpath("*[local-name()='partId']/text()") or [None])[0],
                )
                for p in root.xpath("//*[local-name()='ProductSellable']")
            ]

    return FixtureSanMarAdapter
```

Remove the local copy in `test_import_service.py` and rely on the conftest fixture.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_import_routes.py tests/test_import_service.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/import_jobs/routes.py backend/main.py backend/tests/conftest.py backend/tests/test_import_routes.py backend/tests/test_import_service.py
git commit -m "feat(import_jobs): POST /api/suppliers/{id}/import + sync job polling"
```

---

### Task 13: 15-20 product end-to-end test (filtered_sample mode)

**Files:**
- Test: `backend/tests/test_import_service.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_import_service.py`:

```python
@pytest.mark.asyncio
async def test_filtered_sample_caps_to_max_products(
    seed_supplier: Supplier, sanmar_fixture_adapter_class
):
    """filtered_sample mode intersects sellable list with explicit_list and obeys max_products."""
    from modules.import_jobs.service import run_import
    from modules.import_jobs.registry import register_adapter
    from modules.catalog.models import Product

    register_adapter("FixtureSanMarAdapter", sanmar_fixture_adapter_class)

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "FixtureSanMarAdapter"
        loaded.auth_config = {"id": "u", "password": "p"}
        # Sellable fixture lists 5 SKUs; filter to 2 known + 1 unknown; cap at 2.
        loaded.protocol_config = {
            "explicit_list": ["PC61", "MM1000", "K500"],
            "max_products": 2,
        }
        await s.commit()
        await s.refresh(loaded)
        supplier_id = loaded.id

    summary = await run_import(supplier_id=supplier_id, mode="filtered_sample", limit=2)
    assert summary["records_processed"] == 2
    assert summary["status"] == "success"

    async with async_session() as s:
        skus = {
            p.supplier_sku
            for p in (await s.execute(
                select(Product).where(Product.supplier_id == supplier_id)
            )).scalars().all()
        }
        assert skus == {"PC61", "MM1000"}
```

- [ ] **Step 2: Run test**

Run: `cd backend && pytest tests/test_import_service.py::test_filtered_sample_caps_to_max_products -v`
Expected: PASS straight away (orchestrator already supports the mode). If the assertion on `len` fails, it's a real bug — fix the discovery routing in `adapter.py`.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_import_service.py
git commit -m "test(import_jobs): filtered_sample respects explicit_list ∩ sellable cap"
```

---

### Task 14: Sanity script for live SanMar smoke (manual, opt-in)

**Files:**
- Modify: `backend/scripts/sanmar_smoke.py` (extend with adapter path)

The existing `sanmar_smoke.py` calls `PromoStandardsClient` directly. Add a `--use-adapter` mode that runs `run_import` end-to-end against a SanMar supplier row. Tests do not exercise this path.

- [ ] **Step 1: Read the existing script**

Run: `cd backend && head -120 scripts/sanmar_smoke.py`

- [ ] **Step 2: Append the adapter-mode helper**

Edit `backend/scripts/sanmar_smoke.py`. Add at the bottom (above `if __name__ == "__main__":`):

```python
async def run_via_adapter(skus: list[str]) -> int:
    """Manual smoke: run a one-shot import via the SanMarAdapter against
    real SanMar SOAP. Requires Supplier(slug='sanmar') with adapter_class set."""
    from sqlalchemy import select
    from database import async_session
    from modules.suppliers.models import Supplier
    from modules.import_jobs.service import run_import

    async with async_session() as s:
        supplier = (
            await s.execute(select(Supplier).where(Supplier.slug == "sanmar"))
        ).scalar_one_or_none()
        if supplier is None:
            print("Supplier slug='sanmar' not in DB; create via /suppliers UI first.")
            return 1
        if supplier.adapter_class != "SanMarAdapter":
            supplier.adapter_class = "SanMarAdapter"
        cfg = dict(supplier.protocol_config or {})
        cfg["explicit_list"] = skus
        cfg.setdefault("max_products", len(skus))
        supplier.protocol_config = cfg
        await s.commit()
        supplier_id = supplier.id

    summary = await run_import(supplier_id=supplier_id, mode="explicit_list",
                                limit=len(skus))
    print(summary)
    return 0 if summary["status"] in {"success", "partial_success"} else 1
```

Then in the argparse block, add a flag:

```python
parser.add_argument(
    "--use-adapter",
    action="store_true",
    help="Run via SanMarAdapter + run_import (real SOAP) instead of the legacy "
         "PromoStandardsClient direct call.",
)
```

And in `main()`:

```python
if args.use_adapter:
    return asyncio.run(run_via_adapter(skus))
```

- [ ] **Step 3: Verify the script imports cleanly**

Run: `cd backend && python -c "import scripts.sanmar_smoke as m; print(m.run_via_adapter)"`
Expected: prints a coroutine function reference, no import errors.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/sanmar_smoke.py
git commit -m "feat(scripts): sanmar_smoke --use-adapter runs end-to-end via SanMarAdapter"
```

---

### Task 15: Phase 3 runbook + spec cross-link

**Files:**
- Create: `backend/docs/sanmar_adapter_runbook.md`

- [ ] **Step 1: Write the runbook**

Create `backend/docs/sanmar_adapter_runbook.md`:

```markdown
# SanMar / PromoStandards Adapter — Operations Runbook

## Setup

1. Confirm Phase 1 schema is deployed (`apparel_details`, `variant_prices`,
   `Supplier.adapter_class`, `Supplier.protocol_config`).
2. Create or update the SanMar supplier row:

   ```sql
   UPDATE suppliers
   SET adapter_class = 'SanMarAdapter',
       protocol_config = '{
         "environment": "production",
         "discovery_mode": "explicit_list",
         "explicit_list": ["PC61", "MM1000", "K500", "L500", "PC54", "K420", "PC450", "ST650", "F260", "TLST650"],
         "max_products": 20,
         "enable_ftp_bulk": false
       }'::jsonb
   WHERE slug = 'sanmar';
   ```

3. Set `auth_config` (encrypted) via the supplier UI:
   ```json
   {"id": "<sanmar.com username>", "password": "<sanmar.com password>"}
   ```

## Trigger an import

```bash
curl -X POST http://localhost:8000/api/suppliers/<supplier_id>/import \
  -H "X-Ingest-Secret: $INGEST_SHARED_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"mode": "explicit_list", "limit": 20}'
# → 202 {"sync_job_id":"...","status":"pending"}

curl http://localhost:8000/api/sync_jobs/<sync_job_id> \
  -H "X-Ingest-Secret: $INGEST_SHARED_SECRET"
```

## Discovery modes

| Mode               | Behavior |
|--------------------|----------|
| `explicit_list`    | Hydrate exactly the SKUs in `protocol_config.explicit_list` |
| `first_n`          | Take the first `limit` from `GetProductSellable` |
| `filtered_sample`  | Intersect `GetProductSellable` ∩ `explicit_list`, capped to `limit` |
| `full_sellable`    | All sellable refs (use cautiously — 1000s) |
| `delta`            | `GetProductDateModified` since `protocol_config.delta_since` |
| `closeouts`        | `GetProductCloseOut` sweep |

## Error handling

- **AuthError** (PS codes 100/104/105/110): fatal, job → `failed`, no rows persisted.
- **SupplierError** (130/135/140/145/150/160): per-product, logged in
  `sync_jobs.error_log`, other products still persist (`partial_success`).
- **TransientError** (5xx, timeout): logged per-product; retry by re-running
  the import after the supplier recovers.

## Rollback

- Code rollback is safe — schema migrations are forward-compatible.
- If you persisted bad data, archive the supplier's products via
  `POST /api/products/{id}/archive` rather than dropping rows.

## Manual smoke (real SOAP, opt-in)

```bash
cd backend && source .venv/bin/activate
python scripts/sanmar_smoke.py PC61 MM1000 --use-adapter
```

This uses real SanMar credentials from the DB or `SANMAR_ID` / `SANMAR_PASSWORD`
env vars. Tests in CI never run this path — they rely on the recorded XML
fixtures under `backend/tests/fixtures/sanmar_*.xml`.
```

- [ ] **Step 2: Commit**

```bash
git add backend/docs/sanmar_adapter_runbook.md
git commit -m "docs(sanmar): adapter operations runbook"
```

---

### Task 16: Final regression sweep

**Files:**
- (none — verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `cd backend && pytest tests/ -v`
Expected: all tests PASS (Phase 1 tests + the 12+ new tests from this plan).

- [ ] **Step 2: Smoke-import via the new endpoint with the fixture adapter**

Manually verify (in a dev shell with FastAPI running):

```bash
# In one terminal
cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000

# In another, register a fixture adapter via tests' helper, then:
SUPPLIER_ID=<id of seeded SanMar supplier>
curl -X POST http://localhost:8000/api/suppliers/$SUPPLIER_ID/import \
  -H "X-Ingest-Secret: $INGEST_SHARED_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"mode":"explicit_list","limit":2}'
```

Expected: 202 with sync_job_id; polling shows `success` and the DB has
`PC61` + `MM1000` rows under that supplier (when the FixtureSanMarAdapter
is registered — production needs `SanMarAdapter` + creds).

- [ ] **Step 3: Confirm no regressions in the legacy PS routes**

Run: `cd backend && pytest tests/test_promostandards_categories.py tests/test_promostandards_normalizer.py tests/test_ss_normalizer.py -v`
Expected: all PASS. The legacy `/api/sync/*` routes still use `normalizer.py`; we did not delete that path.

- [ ] **Step 4: Commit any incidental fixes from the sweep, then merge-ready**

```bash
# Only if anything needed fixing — otherwise no commit.
git status
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Implemented in |
|--------------|----------------|
| §6.7 PS field mapping (productId, parts, prices, media, FOB, keywords) | Task 5 (ps_normalizer_v2) |
| §7 BaseAdapter contract | Task 2 |
| §7 Adapter registry | Tasks 3, 10 |
| §7 PromoStandardsAdapter (discover + hydrate + delta + closeouts) | Tasks 6, 7 |
| §7.1 SanMarAdapter overrides (WSDLs, environment, FTP flag) | Task 9 |
| §7.2 Discovery modes (explicit, first_n, filtered_sample, full_sellable, delta, closeouts) | Tasks 6, 7, 13 |
| §7.3 Error handling (auth fatal, per-product continue) | Tasks 8, 11 |
| §10 Trigger via POST /api/suppliers/{id}/import | Task 12 |
| §10 Concurrency (409 if job running) | Task 12 |
| §11.2 Adapter tests + auth fail + per-product error | Tasks 5, 7, 8, 11 |
| §12 Phase 3 rollout — recorded fixture-driven test mode | Tasks 4, 11, 13 |
| §12 Phase 3 manual SOAP smoke | Task 14 |
| §13 Open question: live inventory contract surfaced | Task 9 (`live_inventory` stub) |
| §13 Open question: FTP-bulk discovery flag plumbed | Tasks 1, 9 |

**2. Placeholder scan:** Each `NotImplementedError` is intentional and explicitly called out: `BaseAdapter.discover_changed/discover_closeouts` defaults (overridden in PromoStandardsAdapter), `SanMarAdapter.discover_via_ftp_bulk` (deferred per spec §3 / Phase 3 scope), `SanMarAdapter.live_inventory` (deferred to Phase 4/5). All other steps contain real code.

**3. Type consistency:**
- `ProductRef` (frozen dataclass, `product_id` + `part_id`) — used uniformly across base / adapter / fixture adapter / service.
- `DiscoveryMode` (StrEnum) values match those in spec §7.2 and Phase 1 plan: `explicit_list`, `first_n`, `filtered_sample`, `full_sellable`, `delta`, `closeouts`.
- `ProductIngest.apparel_details` (Phase 1 schema) consumed in Task 5 normalizer and validated by `persist_product` (Phase 1, Task 9).
- `PriceTier` fields (`group_name`, `qty_min`, `qty_max`, `price`, `currency`, `effective_from`) match Phase 1 plan Task 8 exactly.
- `AuthError` / `SupplierError` raised by adapter, caught by service, mapped to job statuses `failed` / `partial_success`.
- `Supplier.protocol_config` shape (`environment`, `discovery_mode`, `explicit_list`, `max_products`, `enable_ftp_bulk`, `wsdl_overrides`, `delta_since`) is documented in the runbook and consumed consistently in adapter + service.

**Phase 1 dependency notes:** This plan assumes Phase 1 has been merged. If `persist_product`, `apparel_details`, `variant_prices`, or the polymorphic `ProductIngest.apparel_details` field are not yet in `main`, do NOT start Phase 3 — fix Phase 1 first. The `errors: JSONB` column on `sync_jobs` mentioned in Phase 1 Task 15 is preferred; Task 11 here falls back to JSON-encoded text in `error_log` for forward compatibility if that column has not landed yet.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-29-phase3-sanmar-promostandards-adapter.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
