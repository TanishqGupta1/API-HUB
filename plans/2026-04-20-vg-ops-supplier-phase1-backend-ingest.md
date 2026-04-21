# VG OPS Supplier — Phase 1: Backend Ingest Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let n8n ingest normalized products/variants/pricing/inventory/categories into the FastAPI catalog under a new `ops_graphql` supplier protocol, with shared-secret auth and idempotent upserts.

**Architecture:** Extends existing `catalog` module with new `Category` model + ingest Pydantic schemas + 4 POST endpoints (`/api/ingest/{supplier_id}/{products|inventory|pricing|categories}`). All endpoints share one auth dependency that checks the `X-Ingest-Secret` header against `INGEST_SHARED_SECRET`. Writes a `SyncJob` row per call. Registers `ops_graphql` as a valid supplier protocol (VARCHAR column, Pydantic enum at app layer — per CLAUDE.md).

**Tech Stack:** FastAPI, async SQLAlchemy 2.0 + asyncpg, Pydantic v2, PostgreSQL (`ON CONFLICT DO UPDATE` via SQLAlchemy's `postgresql.insert`). Tests: `pytest-asyncio` with `httpx.AsyncClient` against the ASGI app, running against a live dockerized Postgres (project convention — no SQLite stub).

**Out of scope for this plan:** Medusa service, backend→Medusa push module, n8n workflow JSON, frontend storefront page. Those are follow-up plans.

---

## File Structure

**New files:**
- `backend/tests/__init__.py` — empty marker
- `backend/tests/conftest.py` — async pytest fixtures (`db`, `client`, `seed_supplier`)
- `backend/tests/test_catalog_ingest.py` — 12 behavior tests covering all 4 endpoints
- `backend/modules/catalog/ingest.py` — new router module (keeps the existing `routes.py` read-only and focused)

**Modified files:**
- `backend/modules/catalog/models.py` — add `Category` model + `category_id` FK on `Product` (already done in current working tree — verify)
- `backend/modules/catalog/schemas.py` — add `ProductIngest`, `VariantIngest`, `ImageIngest`, `InventoryIngest`, `PriceIngest`, `CategoryIngest`, `IngestResult` (already done — verify)
- `backend/modules/suppliers/schemas.py` — add `"ops_graphql"` to `SupplierCreate.protocol` literal
- `backend/modules/catalog/__init__.py` — re-export new router if needed
- `backend/main.py` — register `catalog_ingest_router`; import new model so `create_all` picks it up
- `backend/seed_demo.py` — add VG OPS supplier row (`protocol="ops_graphql"`, `is_active=False`)
- `backend/requirements.txt` — add `pytest`, `pytest-asyncio`, `httpx` (if not present — verify)
- `.env.example` (create if missing) — document `INGEST_SHARED_SECRET`

**Why split ingest into its own file:** `routes.py` today is 82 lines of read-only query endpoints. Mixing write-side ingest would push it over a comfortable size and mix two concerns (public read vs. n8n-secret write). One responsibility per file.

---

## Phase 1a — Test harness + auth dependency

### Task 1: Pytest fixtures for async API + database

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Modify: `backend/requirements.txt`

- [x] **Step 1: Add test dependencies**

Edit `backend/requirements.txt`, append:

```
pytest>=8.0
pytest-asyncio>=0.23
httpx>=0.27
```

- [x] **Step 2: Install**

```bash
cd backend && source .venv/bin/activate && pip install -r requirements.txt
```

Expected: successful install; `pytest --version` prints 8.x.

- [x] **Step 3: Write the conftest**

Create `backend/tests/__init__.py` (empty) and `backend/tests/conftest.py`:

```python
"""Shared pytest fixtures for the backend test suite.

Each test function runs inside a transaction that rolls back on teardown,
so test data never persists. Fixtures are async because the app is async.
"""
import os
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# INGEST_SHARED_SECRET must be set before the app imports the ingest module.
os.environ.setdefault("INGEST_SHARED_SECRET", "test-secret-do-not-use-in-prod")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from database import Base, async_session, engine, get_db  # noqa: E402
from main import app  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncClient:
    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_supplier(db: AsyncSession):
    """Insert a VG OPS supplier row and return it."""
    from modules.suppliers.models import Supplier

    supplier = Supplier(
        name="VG OPS Test",
        slug="vg-ops-test",
        protocol="ops_graphql",
        base_url="https://vg.onprintshop.test",
        auth_config={"n8n_credential_id": "test", "store_url": "https://vg.onprintshop.test"},
        is_active=True,
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@pytest_asyncio.fixture
async def inactive_supplier(db: AsyncSession):
    from modules.suppliers.models import Supplier

    supplier = Supplier(
        name="VG OPS Inactive",
        slug="vg-ops-inactive",
        protocol="ops_graphql",
        auth_config={},
        is_active=False,
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier
```

Also add `backend/pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
pythonpath = .
```

- [x] **Step 4: Verify harness loads**

Run:
```bash
cd backend && source .venv/bin/activate
docker compose -f ../docker-compose.yml up -d postgres
pytest --collect-only
```

Expected: "collected 0 items" (no tests yet) with no errors. If import fails, stop and fix before proceeding.

- [x] **Step 5: Commit**

```bash
cd .. && git add backend/tests/__init__.py backend/tests/conftest.py backend/pytest.ini backend/requirements.txt
git commit -m "test: async pytest harness with DB rollback fixture"
```

### Task 2: Shared-secret auth dependency

**Files:**
- Create: `backend/modules/catalog/ingest.py` (stub only — router + dependency)
- Create: `backend/tests/test_catalog_ingest.py`

- [x] **Step 1: Write failing auth tests**

Create `backend/tests/test_catalog_ingest.py`:

```python
"""Behavior tests for /api/ingest/{supplier_id}/* endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ingest_rejects_missing_secret(client: AsyncClient, seed_supplier):
    r = await client.post(f"/api/ingest/{seed_supplier.id}/products", json=[])
    assert r.status_code == 401
    assert "secret" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ingest_rejects_wrong_secret(client: AsyncClient, seed_supplier):
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        headers={"X-Ingest-Secret": "wrong"},
        json=[],
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_ingest_accepts_correct_secret_empty_body(client: AsyncClient, seed_supplier):
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        headers={"X-Ingest-Secret": "test-secret-do-not-use-in-prod"},
        json=[],
    )
    # 200 with 0 records — valid idempotent call
    assert r.status_code == 200
    body = r.json()
    assert body["records_processed"] == 0
    assert body["status"] == "completed"
```

- [x] **Step 2: Run — must fail**

```bash
pytest backend/tests/test_catalog_ingest.py -v
```

Expected: 3 failures, all 404 (endpoint not registered).

- [x] **Step 3: Write minimal ingest.py**

Create `backend/modules/catalog/ingest.py`:

```python
"""Write-side (n8n-facing) catalog endpoints.

Each endpoint requires the X-Ingest-Secret header and writes a SyncJob
row describing the batch. Upserts are idempotent — re-running a workflow
is safe.
"""
import os
from uuid import UUID, uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.suppliers.models import Supplier
from modules.sync_jobs.models import SyncJob

from .schemas import IngestResult

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def _expected_secret() -> str:
    value = os.getenv("INGEST_SHARED_SECRET")
    if not value:
        raise HTTPException(500, "INGEST_SHARED_SECRET not configured")
    return value


async def require_ingest_secret(x_ingest_secret: str | None = Header(default=None)) -> None:
    if x_ingest_secret != _expected_secret():
        raise HTTPException(401, "Invalid or missing X-Ingest-Secret")


async def _load_active_supplier(supplier_id: UUID, db: AsyncSession) -> Supplier:
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, f"Supplier {supplier_id} not found")
    if not supplier.is_active:
        raise HTTPException(409, f"Supplier '{supplier.name}' is not active")
    return supplier


async def _start_sync_job(db: AsyncSession, supplier: Supplier, job_type: str) -> SyncJob:
    job = SyncJob(
        id=uuid4(),
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        job_type=job_type,
        status="running",
    )
    db.add(job)
    await db.flush()
    return job


async def _finish_sync_job(db: AsyncSession, job: SyncJob, records: int) -> None:
    job.status = "completed"
    job.records_processed = records
    job.finished_at = datetime.now(timezone.utc)
    await db.commit()


@router.post(
    "/{supplier_id}/products",
    response_model=IngestResult,
    dependencies=[Depends(require_ingest_secret)],
)
async def ingest_products(
    supplier_id: UUID,
    batch: list,  # typed properly in Task 3
    db: AsyncSession = Depends(get_db),
):
    supplier = await _load_active_supplier(supplier_id, db)
    job = await _start_sync_job(db, supplier, "products")
    await _finish_sync_job(db, job, len(batch))
    return IngestResult(sync_job_id=job.id, records_processed=len(batch), status="completed")
```

- [x] **Step 4: Wire into main.py**

Edit `backend/main.py`. Add import near the other routers:

```python
from modules.catalog.ingest import router as catalog_ingest_router
```

And register after `catalog_router`:

```python
app.include_router(catalog_ingest_router)
```

- [x] **Step 5: Run — must pass**

```bash
pytest backend/tests/test_catalog_ingest.py -v
```

Expected: 3 passed.

- [x] **Step 6: Commit**

```bash
git add backend/modules/catalog/ingest.py backend/main.py backend/tests/test_catalog_ingest.py
git commit -m "feat(catalog): ingest router skeleton with X-Ingest-Secret auth"
```

---

## Phase 1b — Protocol + schema updates

### Task 3: Add `ops_graphql` to supplier protocol list

**Files:**
- Modify: `backend/modules/suppliers/schemas.py`
- Create: `backend/tests/test_suppliers_protocol.py`

- [x] **Step 1: Write failing test**

Create `backend/tests/test_suppliers_protocol.py`:

```python
import pytest
from pydantic import ValidationError

from modules.suppliers.schemas import SupplierCreate


def test_ops_graphql_is_valid_protocol():
    s = SupplierCreate(name="VG", slug="vg", protocol="ops_graphql")
    assert s.protocol == "ops_graphql"


def test_soap_and_rest_still_valid():
    assert SupplierCreate(name="a", slug="a", protocol="soap").protocol == "soap"
    assert SupplierCreate(name="b", slug="b", protocol="rest").protocol == "rest"
    assert SupplierCreate(name="c", slug="c", protocol="hmac").protocol == "hmac"


def test_unknown_protocol_rejected():
    with pytest.raises(ValidationError):
        SupplierCreate(name="x", slug="x", protocol="carrier_pigeon")
```

- [x] **Step 2: Run — must fail on test_unknown_protocol_rejected (no validation yet) and test_ops_graphql test may pass trivially since field is `str`**

```bash
pytest backend/tests/test_suppliers_protocol.py -v
```

Expected: `test_unknown_protocol_rejected` fails (any string currently accepted). The others may pass for now; they're guard-rails.

- [x] **Step 3: Tighten the schema**

Edit `backend/modules/suppliers/schemas.py`. Replace the file contents:

```python
from typing import Literal, Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

Protocol = Literal["soap", "rest", "hmac", "ops_graphql", "promostandards"]


class SupplierCreate(BaseModel):
    name: str
    slug: str
    protocol: Protocol
    promostandards_code: Optional[str] = None
    base_url: Optional[str] = None
    auth_config: dict = {}


class SupplierRead(BaseModel):
    id: UUID
    name: str
    slug: str
    protocol: str
    promostandards_code: Optional[str]
    base_url: Optional[str]
    auth_config: dict
    field_mappings: Optional[dict] = None
    is_active: bool
    created_at: datetime
    product_count: int = 0

    model_config = {"from_attributes": True}
```

Note: `promostandards` is included because `_load_active_supplier` in the sync routes currently treats `soap` and `promostandards` as synonyms. The DB column stays VARCHAR per CLAUDE.md — only the Pydantic layer is tightened.

- [x] **Step 4: Run — all pass**

```bash
pytest backend/tests/test_suppliers_protocol.py -v
```

Expected: 3 passed.

- [x] **Step 5: Commit**

```bash
git add backend/modules/suppliers/schemas.py backend/tests/test_suppliers_protocol.py
git commit -m "feat(suppliers): add ops_graphql to Protocol literal"
```

### Task 4: Confirm ingest Pydantic schemas present

The current working tree already contains `ProductIngest`, `VariantIngest`, `ImageIngest`, `InventoryIngest`, `PriceIngest`, `CategoryIngest`, `IngestResult` in `backend/modules/catalog/schemas.py`. This task verifies they match the plan.

**Files:**
- Modify: `backend/modules/catalog/schemas.py` (verify / reconcile)

- [x] **Step 1: Read the current schema file**

```bash
cat backend/modules/catalog/schemas.py
```

Expected: the ingest classes are present at the bottom of the file, matching this shape:

```python
class VariantIngest(BaseModel):
    part_id: str
    color: Optional[str] = None
    size: Optional[str] = None
    sku: Optional[str] = None
    base_price: Optional[Decimal] = None
    inventory: Optional[int] = None
    warehouse: Optional[str] = None


class ImageIngest(BaseModel):
    url: str
    image_type: str = "front"
    color: Optional[str] = None
    sort_order: int = 0


class ProductIngest(BaseModel):
    supplier_sku: str
    product_name: str
    brand: Optional[str] = None
    description: Optional[str] = None
    product_type: str = "apparel"
    image_url: Optional[str] = None
    ops_product_id: Optional[str] = None
    category_external_id: Optional[str] = None
    category_name: Optional[str] = None
    variants: list[VariantIngest] = Field(default_factory=list)
    images: list[ImageIngest] = Field(default_factory=list)


class InventoryIngest(BaseModel):
    supplier_sku: str
    part_id: str
    quantity_available: int = 0
    warehouse: Optional[str] = None


class PriceIngest(BaseModel):
    supplier_sku: str
    part_id: str
    base_price: Decimal


class CategoryIngest(BaseModel):
    external_id: str
    name: str
    parent_external_id: Optional[str] = None
    sort_order: int = 0


class IngestResult(BaseModel):
    sync_job_id: UUID
    records_processed: int
    status: str
```

If any are missing or differ, edit the file to match exactly.

- [x] **Step 2: Smoke test the imports**

Add to `backend/tests/test_catalog_ingest.py`:

```python
def test_ingest_schemas_importable():
    from modules.catalog.schemas import (
        CategoryIngest,
        ImageIngest,
        IngestResult,
        InventoryIngest,
        PriceIngest,
        ProductIngest,
        VariantIngest,
    )

    p = ProductIngest(supplier_sku="X", product_name="X")
    assert p.variants == [] and p.images == []

    v = VariantIngest(part_id="p", base_price=None)
    assert v.base_price is None
```

- [x] **Step 3: Run**

```bash
pytest backend/tests/test_catalog_ingest.py::test_ingest_schemas_importable -v
```

Expected: passed.

- [x] **Step 4: Commit (only if you had to edit)**

```bash
git add backend/modules/catalog/schemas.py backend/tests/test_catalog_ingest.py
git commit -m "test(catalog): smoke-test ingest schema importability"
```

---

## Phase 1c — Category model + migration

### Task 5: Category model + FK on Product

The current working tree already defines `Category` in `backend/modules/catalog/models.py` with `category_id` FK on `Product`. This task verifies and adds test coverage.

**Files:**
- Modify: `backend/modules/catalog/models.py` (verify)
- Modify: `backend/main.py` (ensure `Category` is imported before `create_all` runs)

- [x] **Step 1: Verify model presence**

```bash
grep -n "class Category" backend/modules/catalog/models.py
grep -n "category_id" backend/modules/catalog/models.py
```

Expected: both match. If not, apply the structure below:

```python
class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("supplier_id", "external_id", name="uq_category_supplier_external"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    supplier_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("suppliers.id"))
    external_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    parent_id: Mapped[Optional[uuid_mod.UUID]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    products: Mapped[list["Product"]] = relationship(back_populates="category_ref")
```

And on `Product`:

```python
category_id: Mapped[Optional[uuid_mod.UUID]] = mapped_column(
    ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
)
category_ref: Mapped[Optional["Category"]] = relationship(back_populates="products")
```

- [x] **Step 2: Add model roundtrip test**

Append to `backend/tests/test_catalog_ingest.py`:

```python
@pytest.mark.asyncio
async def test_category_model_roundtrip(db, seed_supplier):
    from modules.catalog.models import Category

    root = Category(supplier_id=seed_supplier.id, external_id="root", name="All")
    db.add(root)
    await db.flush()

    child = Category(
        supplier_id=seed_supplier.id,
        external_id="shirts",
        name="Shirts",
        parent_id=root.id,
    )
    db.add(child)
    await db.flush()

    assert child.parent_id == root.id
```

- [x] **Step 3: Run — must pass (schema already created by autouse fixture)**

```bash
pytest backend/tests/test_catalog_ingest.py::test_category_model_roundtrip -v
```

Expected: passed.

- [x] **Step 4: Commit (only if you edited the model)**

```bash
git add backend/modules/catalog/models.py backend/tests/test_catalog_ingest.py
git commit -m "test(catalog): Category hierarchy roundtrip"
```

---

## Phase 1d — Ingest endpoints (TDD)

For each of the four endpoints, the TDD rhythm is: failing test → minimal impl → pass → commit.

### Task 6: POST /api/ingest/{supplier_id}/categories

**Files:**
- Modify: `backend/modules/catalog/ingest.py`
- Modify: `backend/tests/test_catalog_ingest.py`

- [x] **Step 1: Write failing tests**

Append to `backend/tests/test_catalog_ingest.py`:

```python
SECRET = {"X-Ingest-Secret": "test-secret-do-not-use-in-prod"}


@pytest.mark.asyncio
async def test_ingest_categories_creates_rows(client, seed_supplier, db):
    from modules.catalog.models import Category
    from sqlalchemy import select

    batch = [
        {"external_id": "root", "name": "All", "sort_order": 0},
        {"external_id": "shirts", "name": "Shirts", "parent_external_id": "root", "sort_order": 1},
        {"external_id": "hats", "name": "Hats", "parent_external_id": "root", "sort_order": 2},
    ]
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/categories", headers=SECRET, json=batch
    )
    assert r.status_code == 200
    assert r.json()["records_processed"] == 3

    rows = (
        await db.execute(select(Category).where(Category.supplier_id == seed_supplier.id))
    ).scalars().all()
    assert len(rows) == 3

    by_ext = {c.external_id: c for c in rows}
    assert by_ext["shirts"].parent_id == by_ext["root"].id
    assert by_ext["hats"].parent_id == by_ext["root"].id


@pytest.mark.asyncio
async def test_ingest_categories_is_idempotent(client, seed_supplier, db):
    from modules.catalog.models import Category
    from sqlalchemy import select, func

    batch = [{"external_id": "root", "name": "All"}]
    await client.post(f"/api/ingest/{seed_supplier.id}/categories", headers=SECRET, json=batch)
    await client.post(f"/api/ingest/{seed_supplier.id}/categories", headers=SECRET, json=batch)

    count = (
        await db.execute(
            select(func.count()).select_from(Category).where(
                Category.supplier_id == seed_supplier.id
            )
        )
    ).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_ingest_categories_rejects_inactive_supplier(client, inactive_supplier):
    r = await client.post(
        f"/api/ingest/{inactive_supplier.id}/categories",
        headers=SECRET,
        json=[{"external_id": "x", "name": "X"}],
    )
    assert r.status_code == 409
```

- [x] **Step 2: Run — must fail**

```bash
pytest backend/tests/test_catalog_ingest.py -k categories -v
```

Expected: failures because the endpoint receives a plain `list` but doesn't actually upsert.

- [x] **Step 3: Implement the endpoint**

Replace the placeholder in `backend/modules/catalog/ingest.py` — add import and endpoint:

```python
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .models import Category, Product, ProductImage, ProductVariant
from .schemas import (
    CategoryIngest,
    ImageIngest,
    IngestResult,
    InventoryIngest,
    PriceIngest,
    ProductIngest,
    VariantIngest,
)
```

Then replace the `ingest_products` stub and add `ingest_categories`:

```python
@router.post(
    "/{supplier_id}/categories",
    response_model=IngestResult,
    dependencies=[Depends(require_ingest_secret)],
)
async def ingest_categories(
    supplier_id: UUID,
    batch: list[CategoryIngest],
    db: AsyncSession = Depends(get_db),
):
    supplier = await _load_active_supplier(supplier_id, db)
    job = await _start_sync_job(db, supplier, "categories")

    # Pass 1: upsert all rows without parent wiring.
    for cat in batch:
        stmt = pg_insert(Category).values(
            supplier_id=supplier.id,
            external_id=cat.external_id,
            name=cat.name,
            sort_order=cat.sort_order,
        ).on_conflict_do_update(
            index_elements=["supplier_id", "external_id"],
            set_={"name": cat.name, "sort_order": cat.sort_order},
        )
        await db.execute(stmt)
    await db.flush()

    # Pass 2: resolve parent_external_id → parent_id.
    ext_to_id = {
        c.external_id: c.id
        for c in (
            await db.execute(
                select(Category).where(Category.supplier_id == supplier.id)
            )
        ).scalars().all()
    }
    for cat in batch:
        if cat.parent_external_id:
            parent_id = ext_to_id.get(cat.parent_external_id)
            if parent_id is not None:
                await db.execute(
                    pg_insert(Category).values(
                        supplier_id=supplier.id,
                        external_id=cat.external_id,
                        name=cat.name,
                        parent_id=parent_id,
                        sort_order=cat.sort_order,
                    ).on_conflict_do_update(
                        index_elements=["supplier_id", "external_id"],
                        set_={"parent_id": parent_id},
                    )
                )

    await _finish_sync_job(db, job, len(batch))
    return IngestResult(
        sync_job_id=job.id, records_processed=len(batch), status="completed"
    )
```

- [x] **Step 4: Run — all pass**

```bash
pytest backend/tests/test_catalog_ingest.py -k categories -v
```

Expected: 3 passed.

- [x] **Step 5: Commit**

```bash
git add backend/modules/catalog/ingest.py backend/tests/test_catalog_ingest.py
git commit -m "feat(ingest): POST /api/ingest/{supplier_id}/categories with idempotent upsert"
```

### Task 7: POST /api/ingest/{supplier_id}/products

**Files:**
- Modify: `backend/modules/catalog/ingest.py`
- Modify: `backend/tests/test_catalog_ingest.py`

- [x] **Step 1: Write failing tests**

Append to `backend/tests/test_catalog_ingest.py`:

```python
@pytest.mark.asyncio
async def test_ingest_products_creates_product_with_variants(client, seed_supplier, db):
    from modules.catalog.models import Product, ProductVariant
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    batch = [
        {
            "supplier_sku": "VG-HAT-001",
            "product_name": "Test Hat",
            "brand": "VG",
            "description": "A hat for testing.",
            "product_type": "apparel",
            "image_url": "https://vg.example/hat.jpg",
            "variants": [
                {"part_id": "VG-HAT-001-RED-L", "color": "red", "size": "L",
                 "sku": "VG-HAT-001-RED-L", "base_price": "9.99", "inventory": 50},
                {"part_id": "VG-HAT-001-BLUE-L", "color": "blue", "size": "L",
                 "sku": "VG-HAT-001-BLUE-L", "base_price": "9.99", "inventory": 30},
            ],
            "images": [
                {"url": "https://vg.example/hat_front.jpg", "image_type": "front"},
                {"url": "https://vg.example/hat_back.jpg", "image_type": "back"},
            ],
        }
    ]

    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/products", headers=SECRET, json=batch
    )
    assert r.status_code == 200
    assert r.json()["records_processed"] == 1

    row = (
        await db.execute(
            select(Product)
            .where(Product.supplier_id == seed_supplier.id)
            .options(selectinload(Product.variants), selectinload(Product.images))
        )
    ).scalar_one()
    assert row.product_name == "Test Hat"
    assert len(row.variants) == 2
    assert len(row.images) == 2
    assert {v.color for v in row.variants} == {"red", "blue"}


@pytest.mark.asyncio
async def test_ingest_products_is_idempotent_and_updates(client, seed_supplier, db):
    from modules.catalog.models import Product
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    v1 = [{
        "supplier_sku": "VG-001",
        "product_name": "Old Name",
        "variants": [{"part_id": "a", "color": "red", "size": "M", "base_price": "1.00"}],
    }]
    v2 = [{
        "supplier_sku": "VG-001",
        "product_name": "New Name",
        "variants": [{"part_id": "a", "color": "red", "size": "M", "base_price": "2.00"}],
    }]

    await client.post(f"/api/ingest/{seed_supplier.id}/products", headers=SECRET, json=v1)
    await client.post(f"/api/ingest/{seed_supplier.id}/products", headers=SECRET, json=v2)

    row = (
        await db.execute(
            select(Product)
            .where(Product.supplier_sku == "VG-001")
            .options(selectinload(Product.variants))
        )
    ).scalar_one()
    assert row.product_name == "New Name"
    assert len(row.variants) == 1
    assert str(row.variants[0].base_price) == "2.00"


@pytest.mark.asyncio
async def test_ingest_products_links_category_by_external_id(client, seed_supplier, db):
    from modules.catalog.models import Product
    from sqlalchemy import select

    await client.post(
        f"/api/ingest/{seed_supplier.id}/categories",
        headers=SECRET,
        json=[{"external_id": "hats", "name": "Hats"}],
    )
    await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        headers=SECRET,
        json=[{
            "supplier_sku": "VG-001",
            "product_name": "Hat",
            "category_external_id": "hats",
            "variants": [],
        }],
    )
    p = (await db.execute(select(Product).where(Product.supplier_sku == "VG-001"))).scalar_one()
    assert p.category_id is not None
```

- [x] **Step 2: Run — must fail**

```bash
pytest backend/tests/test_catalog_ingest.py -k products -v
```

Expected: failures (endpoint body not implemented yet).

- [x] **Step 3: Implement the endpoint**

In `backend/modules/catalog/ingest.py`, add:

```python
@router.post(
    "/{supplier_id}/products",
    response_model=IngestResult,
    dependencies=[Depends(require_ingest_secret)],
)
async def ingest_products(
    supplier_id: UUID,
    batch: list[ProductIngest],
    db: AsyncSession = Depends(get_db),
):
    supplier = await _load_active_supplier(supplier_id, db)
    job = await _start_sync_job(db, supplier, "products")

    # Preload existing categories once for external_id → id lookup.
    ext_to_cat_id = {
        c.external_id: c.id
        for c in (
            await db.execute(select(Category).where(Category.supplier_id == supplier.id))
        ).scalars().all()
    }

    for item in batch:
        category_id = (
            ext_to_cat_id.get(item.category_external_id)
            if item.category_external_id
            else None
        )
        stmt = pg_insert(Product).values(
            supplier_id=supplier.id,
            supplier_sku=item.supplier_sku,
            product_name=item.product_name,
            brand=item.brand,
            category=item.category_name,
            category_id=category_id,
            description=item.description,
            product_type=item.product_type,
            image_url=item.image_url,
            ops_product_id=item.ops_product_id,
            last_synced=datetime.now(timezone.utc),
        ).on_conflict_do_update(
            index_elements=["supplier_id", "supplier_sku"],
            set_={
                "product_name": item.product_name,
                "brand": item.brand,
                "category": item.category_name,
                "category_id": category_id,
                "description": item.description,
                "product_type": item.product_type,
                "image_url": item.image_url,
                "ops_product_id": item.ops_product_id,
                "last_synced": datetime.now(timezone.utc),
            },
        ).returning(Product.id)
        product_id = (await db.execute(stmt)).scalar_one()

        # Variants: upsert; do NOT delete variants not present in this batch
        # (partial syncs are common).
        for v in item.variants:
            vstmt = pg_insert(ProductVariant).values(
                product_id=product_id,
                color=v.color,
                size=v.size,
                sku=v.sku,
                base_price=v.base_price,
                inventory=v.inventory,
                warehouse=v.warehouse,
            ).on_conflict_do_update(
                index_elements=["product_id", "color", "size"],
                set_={
                    "sku": v.sku,
                    "base_price": v.base_price,
                    "inventory": v.inventory,
                    "warehouse": v.warehouse,
                },
            )
            await db.execute(vstmt)

        for i, img in enumerate(item.images):
            istmt = pg_insert(ProductImage).values(
                product_id=product_id,
                url=img.url,
                image_type=img.image_type,
                color=img.color,
                sort_order=img.sort_order or i,
            ).on_conflict_do_update(
                index_elements=["product_id", "url"],
                set_={
                    "image_type": img.image_type,
                    "color": img.color,
                    "sort_order": img.sort_order or i,
                },
            )
            await db.execute(istmt)

    await _finish_sync_job(db, job, len(batch))
    return IngestResult(
        sync_job_id=job.id, records_processed=len(batch), status="completed"
    )
```

- [x] **Step 4: Run — all pass**

```bash
pytest backend/tests/test_catalog_ingest.py -k products -v
```

Expected: all products tests pass (including the earlier empty-body test).

- [x] **Step 5: Commit**

```bash
git add backend/modules/catalog/ingest.py backend/tests/test_catalog_ingest.py
git commit -m "feat(ingest): POST /api/ingest/{supplier_id}/products upsert with variants+images+category"
```

### Task 8: POST /api/ingest/{supplier_id}/inventory

**Files:**
- Modify: `backend/modules/catalog/ingest.py`
- Modify: `backend/tests/test_catalog_ingest.py`

- [x] **Step 1: Write failing test**

Append:

```python
@pytest.mark.asyncio
async def test_ingest_inventory_updates_variants(client, seed_supplier, db):
    from modules.catalog.models import Product, ProductVariant
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    # Seed product + variants via the products ingest first.
    await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        headers=SECRET,
        json=[{
            "supplier_sku": "VG-001",
            "product_name": "Hat",
            "variants": [
                {"part_id": "a", "color": "red", "size": "M", "sku": "a", "inventory": 0},
                {"part_id": "b", "color": "blue", "size": "M", "sku": "b", "inventory": 0},
            ],
        }],
    )

    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/inventory",
        headers=SECRET,
        json=[
            {"supplier_sku": "VG-001", "part_id": "a", "quantity_available": 42, "warehouse": "W1"},
            {"supplier_sku": "VG-001", "part_id": "b", "quantity_available": 7,  "warehouse": "W2"},
        ],
    )
    assert r.status_code == 200
    assert r.json()["records_processed"] == 2

    row = (
        await db.execute(
            select(Product)
            .where(Product.supplier_sku == "VG-001")
            .options(selectinload(Product.variants))
        )
    ).scalar_one()
    by_sku = {v.sku: v for v in row.variants}
    assert by_sku["a"].inventory == 42
    assert by_sku["a"].warehouse == "W1"
    assert by_sku["b"].inventory == 7


@pytest.mark.asyncio
async def test_ingest_inventory_skips_unknown_parts(client, seed_supplier):
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/inventory",
        headers=SECRET,
        json=[{"supplier_sku": "NOPE", "part_id": "x", "quantity_available": 5}],
    )
    # Records processed counts input, not matches — the endpoint is tolerant
    # so upstream n8n doesn't fail the whole batch for one stale SKU.
    assert r.status_code == 200
    assert r.json()["records_processed"] == 1
```

- [x] **Step 2: Run — must fail**

```bash
pytest backend/tests/test_catalog_ingest.py -k inventory -v
```

Expected: failures (endpoint missing).

- [x] **Step 3: Implement**

Add to `backend/modules/catalog/ingest.py`:

```python
from sqlalchemy import update


@router.post(
    "/{supplier_id}/inventory",
    response_model=IngestResult,
    dependencies=[Depends(require_ingest_secret)],
)
async def ingest_inventory(
    supplier_id: UUID,
    batch: list[InventoryIngest],
    db: AsyncSession = Depends(get_db),
):
    supplier = await _load_active_supplier(supplier_id, db)
    job = await _start_sync_job(db, supplier, "inventory")

    # Preload product rows for this supplier once.
    products = (
        await db.execute(
            select(Product.id, Product.supplier_sku).where(
                Product.supplier_id == supplier.id
            )
        )
    ).all()
    sku_to_product_id = {row.supplier_sku: row.id for row in products}

    for item in batch:
        pid = sku_to_product_id.get(item.supplier_sku)
        if pid is None:
            continue
        await db.execute(
            update(ProductVariant)
            .where(
                ProductVariant.product_id == pid,
                ProductVariant.sku == item.part_id,
            )
            .values(inventory=item.quantity_available, warehouse=item.warehouse)
        )

    await _finish_sync_job(db, job, len(batch))
    return IngestResult(
        sync_job_id=job.id, records_processed=len(batch), status="completed"
    )
```

Note: matches variants by `sku == part_id`. If the product-side ingest stores `part_id` on `sku`, this works. That is the convention used in Task 7's seed test.

- [x] **Step 4: Run — pass**

```bash
pytest backend/tests/test_catalog_ingest.py -k inventory -v
```

Expected: 2 passed.

- [x] **Step 5: Commit**

```bash
git add backend/modules/catalog/ingest.py backend/tests/test_catalog_ingest.py
git commit -m "feat(ingest): POST /api/ingest/{supplier_id}/inventory"
```

### Task 9: POST /api/ingest/{supplier_id}/pricing

**Files:**
- Modify: `backend/modules/catalog/ingest.py`
- Modify: `backend/tests/test_catalog_ingest.py`

- [x] **Step 1: Write failing test**

Append:

```python
@pytest.mark.asyncio
async def test_ingest_pricing_updates_base_price(client, seed_supplier, db):
    from decimal import Decimal
    from modules.catalog.models import Product, ProductVariant
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        headers=SECRET,
        json=[{
            "supplier_sku": "VG-001",
            "product_name": "Hat",
            "variants": [{"part_id": "a", "color": "red", "size": "M", "sku": "a"}],
        }],
    )

    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/pricing",
        headers=SECRET,
        json=[{"supplier_sku": "VG-001", "part_id": "a", "base_price": "19.95"}],
    )
    assert r.status_code == 200

    row = (
        await db.execute(
            select(Product)
            .where(Product.supplier_sku == "VG-001")
            .options(selectinload(Product.variants))
        )
    ).scalar_one()
    assert row.variants[0].base_price == Decimal("19.95")
```

- [x] **Step 2: Run — must fail**

```bash
pytest backend/tests/test_catalog_ingest.py -k pricing -v
```

Expected: 1 failure (endpoint missing).

- [x] **Step 3: Implement**

Add to `backend/modules/catalog/ingest.py`:

```python
@router.post(
    "/{supplier_id}/pricing",
    response_model=IngestResult,
    dependencies=[Depends(require_ingest_secret)],
)
async def ingest_pricing(
    supplier_id: UUID,
    batch: list[PriceIngest],
    db: AsyncSession = Depends(get_db),
):
    supplier = await _load_active_supplier(supplier_id, db)
    job = await _start_sync_job(db, supplier, "pricing")

    products = (
        await db.execute(
            select(Product.id, Product.supplier_sku).where(
                Product.supplier_id == supplier.id
            )
        )
    ).all()
    sku_to_product_id = {row.supplier_sku: row.id for row in products}

    for item in batch:
        pid = sku_to_product_id.get(item.supplier_sku)
        if pid is None:
            continue
        await db.execute(
            update(ProductVariant)
            .where(
                ProductVariant.product_id == pid,
                ProductVariant.sku == item.part_id,
            )
            .values(base_price=item.base_price)
        )

    await _finish_sync_job(db, job, len(batch))
    return IngestResult(
        sync_job_id=job.id, records_processed=len(batch), status="completed"
    )
```

- [x] **Step 4: Run**

```bash
pytest backend/tests/test_catalog_ingest.py -k pricing -v
```

Expected: passed.

- [x] **Step 5: Commit**

```bash
git add backend/modules/catalog/ingest.py backend/tests/test_catalog_ingest.py
git commit -m "feat(ingest): POST /api/ingest/{supplier_id}/pricing"
```

---

## Phase 1e — Seed + docs

### Task 10: Seed VG OPS supplier row

**Files:**
- Modify: `backend/seed_demo.py`

- [x] **Step 1: Add VG OPS entry**

Edit the `SUPPLIERS` list in `backend/seed_demo.py`. Append:

```python
{
    "name": "Visual Graphics OPS",
    "slug": "vg-ops",
    "protocol": "ops_graphql",
    "base_url": "https://vg.onprintshop.com",
    "auth_config": {
        "n8n_credential_id": "PLACEHOLDER_CREDENTIAL_ID",
        "store_url": "https://vg.onprintshop.com",
    },
    "is_active": False,  # flip on once Christian provides the real OPS credential
},
```

- [x] **Step 2: Run the seeder**

```bash
cd backend && source .venv/bin/activate && python seed_demo.py
```

Expected: "  [add]  Supplier: Visual Graphics OPS" printed; "Seed complete!" at end.

- [x] **Step 3: Verify via API**

```bash
curl http://localhost:8000/api/suppliers | jq '.[] | select(.slug=="vg-ops")'
```

Expected: the VG row with `"protocol":"ops_graphql"`, `"is_active":false`.

- [x] **Step 4: Commit**

```bash
git add backend/seed_demo.py
git commit -m "feat(seed): add Visual Graphics OPS supplier row (ops_graphql, inactive)"
```

### Task 11: Document `INGEST_SHARED_SECRET`

**Files:**
- Create: `api-hub/.env.example`
- Modify: `api-hub/CLAUDE.md`

- [x] **Step 1: Document the env var**

Create `api-hub/.env.example`:

```
POSTGRES_URL=postgresql+asyncpg://vg_user:vg_pass@localhost:5432/vg_hub
SECRET_KEY=<fernet-key>

# Shared secret for the n8n → FastAPI ingest endpoints.
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
INGEST_SHARED_SECRET=<random-32-chars>
```

- [x] **Step 2: Append a line to CLAUDE.md under the Environment section**

Edit `api-hub/CLAUDE.md`. Under the existing `.env` block, add after `SECRET_KEY=<fernet-key>`:

```
INGEST_SHARED_SECRET=<random-32>    # n8n → FastAPI ingest auth header
```

- [x] **Step 3: Commit**

```bash
git add api-hub/.env.example api-hub/CLAUDE.md
git commit -m "docs: document INGEST_SHARED_SECRET for n8n → FastAPI ingest"
```

---

## Final verification

After Task 11, run the full suite and do an end-to-end curl check.

- [x] **Full test run**

```bash
cd backend && source .venv/bin/activate
pytest -v
```

Expected: all tests pass; no warnings about deprecated Pydantic v1 syntax.

- [x] **End-to-end curl**

Start the app:

```bash
docker compose up -d postgres
uvicorn main:app --reload --port 8000 &
```

Generate a secret and put it in `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))" > /tmp/ingest_secret
export INGEST_SHARED_SECRET=$(cat /tmp/ingest_secret)
```

Flip the VG supplier active (temporarily) and ingest a test payload:

```bash
VG_ID=$(curl -s http://localhost:8000/api/suppliers | jq -r '.[] | select(.slug=="vg-ops") | .id')

curl -X POST "http://localhost:8000/api/suppliers/$VG_ID" \
  -H "Content-Type: application/json" \
  -d '{"is_active": true}'

curl -X POST "http://localhost:8000/api/ingest/$VG_ID/categories" \
  -H "X-Ingest-Secret: $INGEST_SHARED_SECRET" \
  -H "Content-Type: application/json" \
  -d '[{"external_id":"hats","name":"Hats"}]'

curl -X POST "http://localhost:8000/api/ingest/$VG_ID/products" \
  -H "X-Ingest-Secret: $INGEST_SHARED_SECRET" \
  -H "Content-Type: application/json" \
  -d '[{"supplier_sku":"VG-HAT-01","product_name":"Test Hat","category_external_id":"hats","variants":[{"part_id":"VG-HAT-01-RED-M","color":"red","size":"M","sku":"VG-HAT-01-RED-M","base_price":"9.99","inventory":10}]}]'

curl "http://localhost:8000/api/products?supplier_id=$VG_ID"
```

Expected: the last call returns the Test Hat with `variant_count: 1` and the category wired.

- [x] **Restore VG inactive**

```bash
curl -X POST "http://localhost:8000/api/suppliers/$VG_ID" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

- [x] **Final commit (none expected — this step is verification only)**

---

## Follow-up plans (separate files)

- `2026-04-20-vg-ops-supplier-phase2-medusa-service.md` — Docker compose + Medusa v2 scaffold + seed.
- `2026-04-20-vg-ops-supplier-phase3-medusa-push.md` — backend/modules/medusa_push client/service/routes with markup application.
- `2026-04-20-vg-ops-supplier-phase4-n8n-workflow.md` — `n8n-workflows/vg-ops-pull.json` with OnPrintShop node → FastAPI ingest.
- `2026-04-20-vg-ops-supplier-phase5-frontend-storefront.md` — `/storefront/vg` Next.js routes consuming Medusa Store API.
