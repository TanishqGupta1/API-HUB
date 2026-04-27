# Master Options Catalog + Per-Product Configure UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.


> **Status:** ASSIGNED TO SINCHANA (In Progress)

**Goal:** Sync OPS master options into hub + build per-product "Assign Options" UI (screenshot parity) with hub-side storage. Push to OPS deferred until beta mutations ship.

**Architecture:** OPS owns master option definitions (one-way sync via n8n). Hub owns per-product assignments (`enabled`, `price`, `numeric_value`, `sort_order` overrides). Reuse existing `ProductOption` + `ProductOptionAttribute` tables by adding columns. Two new mirror tables for global catalog. n8n workflow pulls daily. Push deferred.

**Tech Stack:** FastAPI + SQLAlchemy async + asyncpg + PostgreSQL + Pydantic. Frontend Next.js 15 + shadcn/ui + Tailwind. n8n for orchestration. OnPrintShop GraphQL node.

**Spec:** `/Users/tanishq/.claude/plans/gentle-jingling-starfish.md`

---

## Task 1 — DB Models: `master_options` + `master_option_attributes`

**Files:**
- Create: `backend/modules/master_options/__init__.py`
- Create: `backend/modules/master_options/models.py`
- Modify: `backend/modules/catalog/models.py` (extend `ProductOption` + `ProductOptionAttribute`)

- [ ] **Step 1: Create module dir + empty `__init__.py`**

```bash
mkdir -p backend/modules/master_options
touch backend/modules/master_options/__init__.py
```

- [ ] **Step 2: Write `backend/modules/master_options/models.py`**

```python
import uuid as uuid_mod
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class MasterOption(Base):
    __tablename__ = "master_options"

    id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_mod.uuid4
    )
    ops_master_option_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    option_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    options_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pricing_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    master_option_tag: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    attributes: Mapped[list["MasterOptionAttribute"]] = relationship(
        back_populates="master_option", cascade="all, delete-orphan"
    )


class MasterOptionAttribute(Base):
    __tablename__ = "master_option_attributes"
    __table_args__ = (UniqueConstraint("master_option_id", "ops_attribute_id"),)

    id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_mod.uuid4
    )
    master_option_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("master_options.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ops_attribute_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    default_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    master_option: Mapped[MasterOption] = relationship(back_populates="attributes")
```

- [ ] **Step 3: Extend `ProductOption` + `ProductOptionAttribute` in `backend/modules/catalog/models.py`**

Locate `ProductOption` class (line ~102). After `status` column, add:
```python
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    overridden_sort: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
```

Locate `ProductOptionAttribute` class (line ~127). After `status` column, add:
```python
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    numeric_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    overridden_sort: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
```

Add to top-of-file imports if missing: `from sqlalchemy import Boolean, Numeric`; `from decimal import Decimal`.

- [ ] **Step 4: Restart api so `Base.metadata.create_all` picks up new tables/columns**

Run: `docker compose restart api && sleep 4`

Verify new tables exist:
```bash
docker compose exec postgres psql -U vg_user -d vg_hub -c "\d master_options"
docker compose exec postgres psql -U vg_user -d vg_hub -c "\d master_option_attributes"
docker compose exec postgres psql -U vg_user -d vg_hub -c "\d product_options" | grep enabled
```

Expected: all 3 queries return table/column data, not "does not exist". **Note:** `create_all` does NOT add new columns to existing tables. If `product_options` / `product_option_attributes` already have data, run these ALTERs manually:
```sql
ALTER TABLE product_options ADD COLUMN IF NOT EXISTS enabled BOOLEAN DEFAULT false;
ALTER TABLE product_options ADD COLUMN IF NOT EXISTS overridden_sort INTEGER;
ALTER TABLE product_option_attributes ADD COLUMN IF NOT EXISTS enabled BOOLEAN DEFAULT false;
ALTER TABLE product_option_attributes ADD COLUMN IF NOT EXISTS price NUMERIC(10,2);
ALTER TABLE product_option_attributes ADD COLUMN IF NOT EXISTS numeric_value NUMERIC(10,2);
ALTER TABLE product_option_attributes ADD COLUMN IF NOT EXISTS overridden_sort INTEGER;
```

- [ ] **Step 5: Commit**

```bash
git add backend/modules/master_options/__init__.py backend/modules/master_options/models.py backend/modules/catalog/models.py
git commit -m "feat(master_options): add master_options + master_option_attributes tables, extend product_options/attrs with enabled/price/numeric/sort"
```

---

## Task 2 — Pydantic Schemas

**Files:**
- Create: `backend/modules/master_options/schemas.py`

- [ ] **Step 1: Write `backend/modules/master_options/schemas.py`**

```python
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---- Read (for GET /api/master-options) ----

class MasterOptionAttributeRead(BaseModel):
    id: UUID
    ops_attribute_id: int
    title: str
    sort_order: int
    default_price: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class MasterOptionRead(BaseModel):
    id: UUID
    ops_master_option_id: int
    title: str
    option_key: Optional[str] = None
    options_type: Optional[str] = None
    pricing_method: Optional[str] = None
    status: int
    sort_order: int
    description: Optional[str] = None
    master_option_tag: Optional[str] = None
    attributes: list[MasterOptionAttributeRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ---- Ingest (for POST /api/ingest/master-options — n8n payload) ----

class MasterOptionAttributeIngest(BaseModel):
    ops_attribute_id: int
    title: str
    sort_order: int = 0
    default_price: Optional[Decimal] = None


class MasterOptionIngest(BaseModel):
    ops_master_option_id: int
    title: str
    option_key: Optional[str] = None
    options_type: Optional[str] = None
    pricing_method: Optional[str] = None
    status: int = 1
    sort_order: int = 0
    description: Optional[str] = None
    master_option_tag: Optional[str] = None
    attributes: list[MasterOptionAttributeIngest] = Field(default_factory=list)
    raw_json: Optional[dict] = None


# ---- Per-product config (GET/PUT /api/products/{id}/options-config) ----

class AttributeConfigItem(BaseModel):
    attribute_id: Optional[UUID] = None          # null = master_option_attributes.id lookup
    ops_attribute_id: int
    title: str
    enabled: bool = False
    price: Decimal = Decimal("0")
    numeric_value: Decimal = Decimal("0")
    sort_order: int = 0


class OptionConfigItem(BaseModel):
    master_option_id: UUID                        # master_options.id (hub UUID)
    ops_master_option_id: int
    title: str
    options_type: Optional[str] = None
    master_option_tag: Optional[str] = None
    enabled: bool = False
    attributes: list[AttributeConfigItem] = Field(default_factory=list)


class SyncStatus(BaseModel):
    total: int
    last_synced_at: Optional[str] = None
```

- [ ] **Step 2: Commit**

```bash
git add backend/modules/master_options/schemas.py
git commit -m "feat(master_options): add Pydantic schemas (Read, Ingest, per-product config)"
```

---

## Task 3 — Ingest Endpoint (`POST /api/ingest/master-options`)

**Files:**
- Create: `backend/modules/master_options/ingest.py`
- Modify: `backend/main.py` (register router)
- Test: `backend/tests/test_master_options_ingest.py`

- [ ] **Step 1: Write failing test `backend/tests/test_master_options_ingest.py`**

```python
import os
import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from sqlalchemy import select, delete
from database import async_session


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    from modules.master_options.models import MasterOption
    async with async_session() as s:
        await s.execute(delete(MasterOption))
        await s.commit()


@pytest.mark.asyncio
async def test_ingest_master_options_upserts():
    secret = os.environ["INGEST_SHARED_SECRET"]
    payload = [
        {
            "ops_master_option_id": 501,
            "title": "Ink Finish",
            "option_key": "ink_finish",
            "options_type": "checkbox",
            "status": 1,
            "sort_order": 10,
            "attributes": [
                {"ops_attribute_id": 9001, "title": "Gloss", "sort_order": 1, "default_price": 0},
                {"ops_attribute_id": 9002, "title": "Matte", "sort_order": 2, "default_price": 0},
            ],
        }
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/ingest/master-options",
            json=payload,
            headers={"X-Ingest-Secret": secret},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["records_processed"] == 1


@pytest.mark.asyncio
async def test_ingest_master_options_rejects_bad_secret():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/ingest/master-options",
            json=[],
            headers={"X-Ingest-Secret": "wrong"},
        )
    assert r.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_master_options_ingest.py -v`
Expected: FAIL with 404 (route not registered yet).

- [ ] **Step 3: Write `backend/modules/master_options/ingest.py`**

```python
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.catalog.ingest import require_ingest_secret

from .models import MasterOption, MasterOptionAttribute
from .schemas import MasterOptionIngest

router = APIRouter(prefix="/api/ingest", tags=["master_options_ingest"])


@router.post(
    "/master-options",
    dependencies=[Depends(require_ingest_secret)],
)
async def ingest_master_options(
    batch: list[MasterOptionIngest],
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    for item in batch:
        stmt = (
            pg_insert(MasterOption)
            .values(
                ops_master_option_id=item.ops_master_option_id,
                title=item.title,
                option_key=item.option_key,
                options_type=item.options_type,
                pricing_method=item.pricing_method,
                status=item.status,
                sort_order=item.sort_order,
                description=item.description,
                master_option_tag=item.master_option_tag,
                raw_json=item.raw_json,
                synced_at=now,
            )
            .on_conflict_do_update(
                index_elements=["ops_master_option_id"],
                set_={
                    "title": item.title,
                    "option_key": item.option_key,
                    "options_type": item.options_type,
                    "pricing_method": item.pricing_method,
                    "status": item.status,
                    "sort_order": item.sort_order,
                    "description": item.description,
                    "master_option_tag": item.master_option_tag,
                    "raw_json": item.raw_json,
                    "synced_at": now,
                },
            )
            .returning(MasterOption.id)
        )
        mo_id: UUID = (await db.execute(stmt)).scalar_one()

        # Replace attributes: delete-and-reinsert (matches product_option_attributes pattern)
        await db.execute(
            delete(MasterOptionAttribute).where(MasterOptionAttribute.master_option_id == mo_id)
        )
        for attr in item.attributes:
            db.add(
                MasterOptionAttribute(
                    master_option_id=mo_id,
                    ops_attribute_id=attr.ops_attribute_id,
                    title=attr.title,
                    sort_order=attr.sort_order,
                    default_price=attr.default_price,
                )
            )

    await db.commit()
    return {"records_processed": len(batch), "status": "completed"}
```

- [ ] **Step 4: Register router in `backend/main.py`**

Locate the `app.include_router(...)` block (~line 70). Add imports near top with the other module imports:
```python
from modules.master_options.ingest import router as master_options_ingest_router
```

Add with the other `app.include_router` calls:
```python
app.include_router(master_options_ingest_router)
```

- [ ] **Step 5: Run tests, verify pass**

Run: `docker compose restart api && sleep 4 && cd backend && source .venv/bin/activate && pytest tests/test_master_options_ingest.py -v`
Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/master_options/ingest.py backend/main.py backend/tests/test_master_options_ingest.py
git commit -m "feat(master_options): ingest endpoint + upsert with attribute replacement"
```

---

## Task 4 — Read Endpoints (`GET /api/master-options` + `/sync-status`)

**Files:**
- Create: `backend/modules/master_options/routes.py`
- Modify: `backend/main.py`
- Test: extend `backend/tests/test_master_options_ingest.py`

- [ ] **Step 1: Write `backend/modules/master_options/routes.py`**

```python
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db

from .models import MasterOption
from .schemas import MasterOptionRead, SyncStatus

router = APIRouter(prefix="/api/master-options", tags=["master_options"])


@router.get("", response_model=list[MasterOptionRead])
async def list_master_options(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MasterOption)
        .options(selectinload(MasterOption.attributes))
        .order_by(MasterOption.sort_order, MasterOption.title)
    )
    return result.scalars().all()


@router.get("/sync-status", response_model=SyncStatus)
async def sync_status(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(MasterOption.id)))).scalar_one()
    last_synced = (await db.execute(select(func.max(MasterOption.synced_at)))).scalar_one()
    return SyncStatus(
        total=total or 0,
        last_synced_at=last_synced.isoformat() if last_synced else None,
    )


@router.get("/{master_option_id}", response_model=MasterOptionRead)
async def get_master_option(master_option_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MasterOption)
        .where(MasterOption.id == master_option_id)
        .options(selectinload(MasterOption.attributes))
    )
    mo = result.scalar_one_or_none()
    if not mo:
        raise HTTPException(404, "Master option not found")
    return mo
```

- [ ] **Step 2: Add test to `backend/tests/test_master_options_ingest.py`**

```python
@pytest.mark.asyncio
async def test_list_master_options_returns_ingested():
    secret = os.environ["INGEST_SHARED_SECRET"]
    payload = [{
        "ops_master_option_id": 502,
        "title": "Print Sides",
        "options_type": "radio",
        "attributes": [
            {"ops_attribute_id": 9101, "title": "Single", "sort_order": 1},
            {"ops_attribute_id": 9102, "title": "Double", "sort_order": 2},
        ],
    }]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/ingest/master-options", json=payload, headers={"X-Ingest-Secret": secret})
        r = await c.get("/api/master-options")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    found = [m for m in data if m["ops_master_option_id"] == 502]
    assert found
    assert len(found[0]["attributes"]) == 2


@pytest.mark.asyncio
async def test_sync_status_reports_count():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/master-options/sync-status")
    assert r.status_code == 200
    body = r.json()
    assert "total" in body
    assert "last_synced_at" in body
```

- [ ] **Step 3: Register router in `backend/main.py`**

```python
from modules.master_options.routes import router as master_options_router
# ...
app.include_router(master_options_router)
```

- [ ] **Step 4: Run tests**

Run: `docker compose restart api && sleep 4 && cd backend && source .venv/bin/activate && pytest tests/test_master_options_ingest.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/master_options/routes.py backend/main.py backend/tests/test_master_options_ingest.py
git commit -m "feat(master_options): list + sync-status + detail endpoints"
```

---

## Task 5 — Per-Product Config READ (`GET /api/products/{id}/options-config`)

**Files:**
- Create: `backend/modules/master_options/service.py`
- Modify: `backend/modules/master_options/routes.py`
- Test: `backend/tests/test_product_options_config.py`

- [ ] **Step 1: Write `backend/modules/master_options/service.py`**

```python
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.catalog.models import Product, ProductOption, ProductOptionAttribute

from .models import MasterOption, MasterOptionAttribute
from .schemas import AttributeConfigItem, OptionConfigItem


async def load_product_config(db: AsyncSession, product_id: UUID) -> list[OptionConfigItem]:
    """Build the card-grid payload for the product.

    For each master option (global catalog), merge in the product's saved
    override if any. Products that have never saved a config get defaults
    (enabled=False, prices from master_option_attributes.default_price).
    """
    # 1. Load all master options with their attributes
    mos = (
        await db.execute(
            select(MasterOption)
            .options(selectinload(MasterOption.attributes))
            .order_by(MasterOption.sort_order, MasterOption.title)
        )
    ).scalars().all()

    # 2. Load product's existing overrides (product_options keyed by master_option_id int)
    po_rows = (
        await db.execute(
            select(ProductOption)
            .where(ProductOption.product_id == product_id)
            .options(selectinload(ProductOption.attributes))
        )
    ).scalars().all()
    po_by_mo: dict[int, ProductOption] = {
        po.master_option_id: po for po in po_rows if po.master_option_id is not None
    }

    out: list[OptionConfigItem] = []
    for mo in mos:
        po = po_by_mo.get(mo.ops_master_option_id)
        po_attrs_by_ops_id: dict[int, ProductOptionAttribute] = {}
        if po:
            po_attrs_by_ops_id = {
                a.ops_attribute_id: a for a in po.attributes if a.ops_attribute_id is not None
            }

        attrs: list[AttributeConfigItem] = []
        for ma in sorted(mo.attributes, key=lambda a: a.sort_order):
            poa = po_attrs_by_ops_id.get(ma.ops_attribute_id)
            attrs.append(
                AttributeConfigItem(
                    attribute_id=poa.id if poa else None,
                    ops_attribute_id=ma.ops_attribute_id,
                    title=ma.title,
                    enabled=poa.enabled if poa else False,
                    price=poa.price if (poa and poa.price is not None) else (ma.default_price or 0),
                    numeric_value=poa.numeric_value if (poa and poa.numeric_value is not None) else 0,
                    sort_order=poa.overridden_sort if (poa and poa.overridden_sort is not None) else ma.sort_order,
                )
            )

        out.append(
            OptionConfigItem(
                master_option_id=mo.id,
                ops_master_option_id=mo.ops_master_option_id,
                title=mo.title,
                options_type=mo.options_type,
                master_option_tag=mo.master_option_tag,
                enabled=po.enabled if po else False,
                attributes=attrs,
            )
        )
    return out
```

- [ ] **Step 2: Add route in `backend/modules/master_options/routes.py`**

Append at the bottom of `routes.py`:
```python
from .service import load_product_config


@router.get("/../products/{product_id}/options-config", include_in_schema=False)
async def _redirect_helper():
    pass  # FastAPI doesn't support this — use a second router below
```

Instead, create a **second router** at the bottom of `routes.py` (cleaner):

```python
product_config_router = APIRouter(prefix="/api/products", tags=["master_options"])


@product_config_router.get("/{product_id}/options-config", response_model=list[OptionConfigItem])
async def get_product_options_config(product_id: UUID, db: AsyncSession = Depends(get_db)):
    # Verify product exists
    from modules.catalog.models import Product
    exists = (await db.execute(select(Product.id).where(Product.id == product_id))).scalar_one_or_none()
    if not exists:
        raise HTTPException(404, "Product not found")
    return await load_product_config(db, product_id)
```

Add import at top of `routes.py`:
```python
from .schemas import MasterOptionRead, SyncStatus, OptionConfigItem
```

- [ ] **Step 3: Register `product_config_router` in `backend/main.py`**

```python
from modules.master_options.routes import router as master_options_router, product_config_router as master_options_product_config_router
# ...
app.include_router(master_options_product_config_router)
```

- [ ] **Step 4: Write failing test `backend/tests/test_product_options_config.py`**

```python
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from main import app
from database import async_session


@pytest.mark.asyncio
async def test_get_product_options_config_defaults_to_disabled():
    from modules.suppliers.models import Supplier
    from modules.catalog.models import Product

    secret = os.environ["INGEST_SHARED_SECRET"]

    # seed: supplier + product
    async with async_session() as s:
        sup = Supplier(name="TestSup", slug="vg-ops-test", protocol="soap", auth_config={})
        s.add(sup)
        await s.commit()
        await s.refresh(sup)
        prod = Product(supplier_id=sup.id, supplier_sku="TS-1", product_name="Test")
        s.add(prod)
        await s.commit()
        await s.refresh(prod)
        pid = prod.id

    # seed master options via ingest endpoint
    payload = [{
        "ops_master_option_id": 601,
        "title": "Ink Finish",
        "options_type": "checkbox",
        "attributes": [
            {"ops_attribute_id": 7001, "title": "Gloss", "sort_order": 1, "default_price": 0},
            {"ops_attribute_id": 7002, "title": "Matte", "sort_order": 2, "default_price": 10},
        ],
    }]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/ingest/master-options", json=payload, headers={"X-Ingest-Secret": secret})
        r = await c.get(f"/api/products/{pid}/options-config")

    assert r.status_code == 200, r.text
    data = r.json()
    ink = [m for m in data if m["ops_master_option_id"] == 601][0]
    assert ink["enabled"] is False
    assert len(ink["attributes"]) == 2
    matte = [a for a in ink["attributes"] if a["ops_attribute_id"] == 7002][0]
    assert matte["enabled"] is False
    assert float(matte["price"]) == 10.0  # falls back to default_price


@pytest.mark.asyncio
async def test_get_product_options_config_404_for_unknown_product():
    fake = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/products/{fake}/options-config")
    assert r.status_code == 404
```

- [ ] **Step 5: Run tests**

Run: `docker compose restart api && sleep 4 && cd backend && source .venv/bin/activate && pytest tests/test_product_options_config.py -v`
Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/master_options/service.py backend/modules/master_options/routes.py backend/main.py backend/tests/test_product_options_config.py
git commit -m "feat(master_options): GET /api/products/{id}/options-config merges master catalog with per-product overrides"
```

---

## Task 6 — Per-Product Config WRITE (PUT + PATCH + DELETE)

**Files:**
- Modify: `backend/modules/master_options/service.py` (add save functions)
- Modify: `backend/modules/master_options/routes.py` (add endpoints)
- Test: extend `backend/tests/test_product_options_config.py`

- [ ] **Step 1: Add save functions to `service.py`**

Append to `service.py`:

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

from modules.catalog.models import ProductOption, ProductOptionAttribute


async def save_product_option(
    db: AsyncSession,
    product_id: UUID,
    item: OptionConfigItem,
) -> None:
    """Upsert one master option assignment for a product."""
    mo = (
        await db.execute(select(MasterOption).where(MasterOption.id == item.master_option_id))
    ).scalar_one_or_none()
    if not mo:
        return

    stmt = (
        pg_insert(ProductOption)
        .values(
            product_id=product_id,
            option_key=mo.option_key or f"mo_{mo.ops_master_option_id}",
            title=mo.title,
            options_type=mo.options_type,
            sort_order=mo.sort_order,
            master_option_id=mo.ops_master_option_id,
            required=False,
            status=1,
            enabled=item.enabled,
        )
        .on_conflict_do_update(
            index_elements=["product_id", "option_key"],
            set_={
                "title": mo.title,
                "options_type": mo.options_type,
                "master_option_id": mo.ops_master_option_id,
                "enabled": item.enabled,
            },
        )
        .returning(ProductOption.id)
    )
    po_id: UUID = (await db.execute(stmt)).scalar_one()

    # Replace attributes
    await db.execute(
        delete(ProductOptionAttribute).where(ProductOptionAttribute.product_option_id == po_id)
    )
    for attr in item.attributes:
        db.add(
            ProductOptionAttribute(
                product_option_id=po_id,
                ops_attribute_id=attr.ops_attribute_id,
                title=attr.title,
                sort_order=attr.sort_order,
                status=1,
                enabled=attr.enabled,
                price=attr.price,
                numeric_value=attr.numeric_value,
                overridden_sort=attr.sort_order,
            )
        )


async def save_product_config(
    db: AsyncSession,
    product_id: UUID,
    items: list[OptionConfigItem],
) -> None:
    for item in items:
        await save_product_option(db, product_id, item)
    await db.commit()


async def delete_product_option(
    db: AsyncSession,
    product_id: UUID,
    master_option_id: UUID,
) -> None:
    mo = (
        await db.execute(select(MasterOption).where(MasterOption.id == master_option_id))
    ).scalar_one_or_none()
    if not mo:
        return
    await db.execute(
        delete(ProductOption).where(
            ProductOption.product_id == product_id,
            ProductOption.master_option_id == mo.ops_master_option_id,
        )
    )
    await db.commit()
```

- [ ] **Step 2: Add endpoints to `routes.py`**

Append after `get_product_options_config`:

```python
from .service import load_product_config, save_product_config, save_product_option, delete_product_option


@product_config_router.put("/{product_id}/options-config")
async def put_product_options_config(
    product_id: UUID,
    body: list[OptionConfigItem],
    db: AsyncSession = Depends(get_db),
):
    from modules.catalog.models import Product
    exists = (await db.execute(select(Product.id).where(Product.id == product_id))).scalar_one_or_none()
    if not exists:
        raise HTTPException(404, "Product not found")
    await save_product_config(db, product_id, body)
    return {"saved": len(body), "status": "ok"}


@product_config_router.patch("/{product_id}/options-config/{master_option_id}")
async def patch_product_option(
    product_id: UUID,
    master_option_id: UUID,
    body: OptionConfigItem,
    db: AsyncSession = Depends(get_db),
):
    if body.master_option_id != master_option_id:
        raise HTTPException(400, "Path master_option_id must match body")
    await save_product_option(db, product_id, body)
    await db.commit()
    return {"status": "ok"}


@product_config_router.delete("/{product_id}/options-config/{master_option_id}")
async def delete_product_option_route(
    product_id: UUID,
    master_option_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    await delete_product_option(db, product_id, master_option_id)
    return {"status": "deleted"}
```

- [ ] **Step 3: Write failing tests**

Append to `backend/tests/test_product_options_config.py`:

```python
@pytest.mark.asyncio
async def test_put_product_options_config_persists():
    from modules.suppliers.models import Supplier
    from modules.catalog.models import Product

    secret = os.environ["INGEST_SHARED_SECRET"]
    async with async_session() as s:
        sup = Supplier(name="PutSup", slug="vg-ops-test", protocol="soap", auth_config={})
        s.add(sup)
        await s.commit(); await s.refresh(sup)
        prod = Product(supplier_id=sup.id, supplier_sku="PUT-1", product_name="P")
        s.add(prod)
        await s.commit(); await s.refresh(prod)
        pid = prod.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/ingest/master-options", headers={"X-Ingest-Secret": secret}, json=[{
            "ops_master_option_id": 701,
            "title": "Put Option",
            "attributes": [{"ops_attribute_id": 7111, "title": "A", "sort_order": 1, "default_price": 0}],
        }])
        # load default config
        r = await c.get(f"/api/products/{pid}/options-config")
        cfg = r.json()
        cfg[0]["enabled"] = True
        cfg[0]["attributes"][0]["enabled"] = True
        cfg[0]["attributes"][0]["price"] = "5.50"
        # save
        r = await c.put(f"/api/products/{pid}/options-config", json=cfg)
        assert r.status_code == 200
        # reload
        r = await c.get(f"/api/products/{pid}/options-config")
        data = r.json()

    item = [m for m in data if m["ops_master_option_id"] == 701][0]
    assert item["enabled"] is True
    assert item["attributes"][0]["enabled"] is True
    assert float(item["attributes"][0]["price"]) == 5.5


@pytest.mark.asyncio
async def test_delete_product_option():
    from modules.suppliers.models import Supplier
    from modules.catalog.models import Product

    secret = os.environ["INGEST_SHARED_SECRET"]
    async with async_session() as s:
        sup = Supplier(name="DelSup", slug="vg-ops-test", protocol="soap", auth_config={})
        s.add(sup); await s.commit(); await s.refresh(sup)
        prod = Product(supplier_id=sup.id, supplier_sku="DEL-1", product_name="D")
        s.add(prod); await s.commit(); await s.refresh(prod)
        pid = prod.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/ingest/master-options", headers={"X-Ingest-Secret": secret}, json=[{
            "ops_master_option_id": 801, "title": "DelOpt",
            "attributes": [{"ops_attribute_id": 8111, "title": "X", "sort_order": 1}],
        }])
        r = await c.get(f"/api/products/{pid}/options-config")
        cfg = r.json()
        cfg[0]["enabled"] = True
        await c.put(f"/api/products/{pid}/options-config", json=cfg)
        mo_id = cfg[0]["master_option_id"]
        r = await c.delete(f"/api/products/{pid}/options-config/{mo_id}")
        assert r.status_code == 200
```

- [ ] **Step 4: Run tests**

Run: `docker compose restart api && sleep 4 && cd backend && source .venv/bin/activate && pytest tests/test_product_options_config.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/master_options/service.py backend/modules/master_options/routes.py backend/tests/test_product_options_config.py
git commit -m "feat(master_options): PUT/PATCH/DELETE product options config"
```

---

## Task 7 — Duplicate Options Endpoint

**Files:**
- Modify: `backend/modules/master_options/service.py`
- Modify: `backend/modules/master_options/routes.py`
- Test: extend `backend/tests/test_product_options_config.py`

- [ ] **Step 1: Add `duplicate_product_config` to service.py**

```python
async def duplicate_product_config(
    db: AsyncSession, src_product_id: UUID, dest_product_id: UUID
) -> int:
    """Copy src product's options + attributes to dest product. Returns count copied."""
    src_cfg = await load_product_config(db, src_product_id)
    # Only copy items where master option is enabled in source
    enabled_items = [item for item in src_cfg if item.enabled]
    for item in enabled_items:
        await save_product_option(db, dest_product_id, item)
    await db.commit()
    return len(enabled_items)
```

- [ ] **Step 2: Add endpoint to routes.py**

```python
@product_config_router.post("/{product_id}/options-config/duplicate-from/{src_product_id}")
async def duplicate_from(
    product_id: UUID,
    src_product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    from modules.catalog.models import Product
    for pid in (product_id, src_product_id):
        exists = (await db.execute(select(Product.id).where(Product.id == pid))).scalar_one_or_none()
        if not exists:
            raise HTTPException(404, f"Product {pid} not found")
    from .service import duplicate_product_config
    copied = await duplicate_product_config(db, src_product_id, product_id)
    return {"copied": copied, "status": "ok"}
```

- [ ] **Step 3: Add test**

```python
@pytest.mark.asyncio
async def test_duplicate_options_copies_enabled_cards():
    from modules.suppliers.models import Supplier
    from modules.catalog.models import Product

    secret = os.environ["INGEST_SHARED_SECRET"]
    async with async_session() as s:
        sup = Supplier(name="DupSup", slug="vg-ops-test", protocol="soap", auth_config={})
        s.add(sup); await s.commit(); await s.refresh(sup)
        src = Product(supplier_id=sup.id, supplier_sku="SRC-1", product_name="src")
        dst = Product(supplier_id=sup.id, supplier_sku="DST-1", product_name="dst")
        s.add(src); s.add(dst); await s.commit()
        await s.refresh(src); await s.refresh(dst)
        src_id, dst_id = src.id, dst.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/ingest/master-options", headers={"X-Ingest-Secret": secret}, json=[{
            "ops_master_option_id": 901, "title": "DupOpt",
            "attributes": [{"ops_attribute_id": 9111, "title": "A", "sort_order": 1}],
        }])
        # enable on src
        r = await c.get(f"/api/products/{src_id}/options-config")
        cfg = r.json()
        cfg[0]["enabled"] = True
        cfg[0]["attributes"][0]["enabled"] = True
        await c.put(f"/api/products/{src_id}/options-config", json=cfg)
        # duplicate to dst
        r = await c.post(f"/api/products/{dst_id}/options-config/duplicate-from/{src_id}")
        assert r.status_code == 200
        assert r.json()["copied"] >= 1
        # verify dst has it enabled
        r = await c.get(f"/api/products/{dst_id}/options-config")
        data = r.json()
        dup = [m for m in data if m["ops_master_option_id"] == 901][0]
        assert dup["enabled"] is True
```

- [ ] **Step 4: Run tests**

Run: `docker compose restart api && sleep 4 && cd backend && source .venv/bin/activate && pytest tests/test_product_options_config.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/master_options/service.py backend/modules/master_options/routes.py backend/tests/test_product_options_config.py
git commit -m "feat(master_options): duplicate-from endpoint copies enabled config"
```

---

## Task 8 — Sync Trigger Endpoint

**Files:**
- Modify: `backend/modules/master_options/routes.py`

- [ ] **Step 1: Add sync endpoint**

```python
@router.post("/sync")
async def trigger_sync():
    """Trigger the n8n master options pull workflow.

    Delegates to /api/n8n/workflows/{id}/trigger for consistency with other
    sync flows.
    """
    import httpx
    workflow_id = "ops-master-options-pull-001"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"http://localhost:8000/api/n8n/workflows/{workflow_id}/trigger",
            json={},
        )
    if r.status_code >= 300:
        raise HTTPException(502, f"n8n trigger failed: {r.text[:200]}")
    return r.json()
```

- [ ] **Step 2: Smoke test (manual, no pytest — depends on n8n running)**

```bash
curl -X POST http://localhost:8000/api/master-options/sync
```
Expected: 200 with `{"status": "..."}` OR 502 if workflow not imported yet. Either OK — next task imports the workflow.

- [ ] **Step 3: Commit**

```bash
git add backend/modules/master_options/routes.py
git commit -m "feat(master_options): POST /sync proxies to n8n master options pull workflow"
```

---

## Task 9 — n8n Pull Workflow

**Files:**
- Create: `n8n-workflows/ops-master-options-pull.json`
- Modify: `n8n-workflows/README.md`

- [ ] **Step 1: Write `n8n-workflows/ops-master-options-pull.json`**

```json
{
  "id": "ops-master-options-pull-001",
  "name": "OPS → Hub (Master Options)",
  "active": false,
  "nodes": [
    {
      "parameters": {},
      "id": "trigger-001",
      "name": "When clicking 'Execute workflow'",
      "type": "n8n-nodes-base.manualTrigger",
      "typeVersion": 1,
      "position": [240, 320]
    },
    {
      "parameters": {
        "resource": "product",
        "operation": "getManyMasterOptions",
        "queryParametersManyMasterOptions": { "limit": 100, "offset": 0 },
        "masterOptionsFieldsMany": [
          "master_option_id", "title", "description", "option_key",
          "pricing_method", "status", "sort_order", "options_type",
          "hide_from_calc", "enable_assoc_qty", "allow_price_cal",
          "hire_designer_option", "attributes"
        ]
      },
      "id": "ops-001",
      "name": "OPS: Get Master Options",
      "type": "n8n-nodes-onprintshop.onPrintShop",
      "typeVersion": 1,
      "position": [460, 320],
      "credentials": {
        "onPrintShopApi": {
          "id": "ops-creds",
          "name": "OnPrintShop"
        }
      }
    },
    {
      "parameters": {
        "jsCode": "return $input.all().map(item => {\n  const mo = item.json;\n  let attrs = mo.attributes;\n  if (typeof attrs === 'string') {\n    try { attrs = JSON.parse(attrs); } catch { attrs = []; }\n  }\n  if (!Array.isArray(attrs)) attrs = [];\n  return {\n    json: {\n      ops_master_option_id: parseInt(mo.master_option_id, 10),\n      title: mo.title,\n      option_key: mo.option_key || null,\n      options_type: mo.options_type || null,\n      pricing_method: mo.pricing_method || null,\n      status: parseInt(mo.status ?? 1, 10),\n      sort_order: parseInt(mo.sort_order ?? 0, 10),\n      description: mo.description || null,\n      master_option_tag: mo.master_option_tag || null,\n      attributes: attrs.map(a => ({\n        ops_attribute_id: parseInt(a.attribute_id ?? a.id, 10),\n        title: a.title || a.name,\n        sort_order: parseInt(a.sort_order ?? 0, 10),\n        default_price: parseFloat(a.price ?? a.default_price ?? 0),\n      })),\n      raw_json: mo,\n    }\n  };\n});"
      },
      "id": "code-001",
      "name": "Shape Master Options",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [680, 320]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "http://host.docker.internal:8000/api/ingest/master-options",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            { "name": "X-Ingest-Secret", "value": "={{ $env.INGEST_SHARED_SECRET }}" },
            { "name": "Content-Type", "value": "application/json" }
          ]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ $items().map(i => i.json) }}",
        "options": {},
        "onError": "continueErrorOutput"
      },
      "id": "http-001",
      "name": "POST /ingest/master-options",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [900, 320]
    },
    {
      "parameters": {
        "jsCode": "const err = $input.first().json;\nreturn [{ json: { event: 'ops_master_options_sync_failed', error: err.message || JSON.stringify(err), timestamp: new Date().toISOString() }}];"
      },
      "id": "code-error-001",
      "name": "Format Error",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [1100, 450]
    }
  ],
  "connections": {
    "When clicking 'Execute workflow'": {
      "main": [[{ "node": "OPS: Get Master Options", "type": "main", "index": 0 }]]
    },
    "OPS: Get Master Options": {
      "main": [[{ "node": "Shape Master Options", "type": "main", "index": 0 }]]
    },
    "Shape Master Options": {
      "main": [[{ "node": "POST /ingest/master-options", "type": "main", "index": 0 }]]
    },
    "POST /ingest/master-options": {
      "error": [[{ "node": "Format Error", "type": "main", "index": 0 }]]
    }
  },
  "pinData": {},
  "meta": { "templateCredsSetupCompleted": false }
}
```

- [ ] **Step 2: Import into n8n**

```bash
docker cp n8n-workflows/ops-master-options-pull.json api-hub-n8n-1:/tmp/mo.json
docker exec api-hub-n8n-1 n8n import:workflow --input=/tmp/mo.json
```
Expected: `Successfully imported 1 workflow.`

- [ ] **Step 3: Verify in n8n UI**

Open `http://localhost:5678`. Workflow `OPS → Hub (Master Options)` should appear. No "unknown node" errors. Attach `OnPrintShop` credential to `OPS: Get Master Options` node.

- [ ] **Step 4: Append to `n8n-workflows/README.md`**

Add under the workflow table:
```markdown
| `ops-master-options-pull.json` | Daily | OPS `getManyMasterOptions` → hub `/api/ingest/master-options` |
```

- [ ] **Step 5: Commit**

```bash
git add n8n-workflows/ops-master-options-pull.json n8n-workflows/README.md
git commit -m "feat(n8n): add OPS master options pull workflow"
```

---

## Task 10 — Frontend Types + Install Missing shadcn

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Create: `frontend/src/components/ui/switch.tsx` (via shadcn CLI)
- Create: `frontend/src/components/ui/checkbox.tsx` (via shadcn CLI)
- Create: `frontend/src/components/ui/dialog.tsx` (via shadcn CLI)

- [ ] **Step 1: Install shadcn components**

```bash
cd frontend && npx shadcn@latest add switch checkbox dialog
```

- [ ] **Step 2: Append types to `frontend/src/lib/types.ts`**

```ts
/* ─── Master Options ─────────────────────────────────────────────────────── */
export interface MasterOptionAttribute {
  id: string;
  ops_attribute_id: number;
  title: string;
  sort_order: number;
  default_price: number | null;
}

export interface MasterOption {
  id: string;
  ops_master_option_id: number;
  title: string;
  option_key: string | null;
  options_type: string | null;
  pricing_method: string | null;
  status: number;
  sort_order: number;
  description: string | null;
  master_option_tag: string | null;
  attributes: MasterOptionAttribute[];
}

export interface MasterOptionsSyncStatus {
  total: number;
  last_synced_at: string | null;
}

/* Per-product config */
export interface AttributeConfigItem {
  attribute_id: string | null;
  ops_attribute_id: number;
  title: string;
  enabled: boolean;
  price: number;
  numeric_value: number;
  sort_order: number;
}

export interface OptionConfigItem {
  master_option_id: string;
  ops_master_option_id: number;
  title: string;
  options_type: string | null;
  master_option_tag: string | null;
  enabled: boolean;
  attributes: AttributeConfigItem[];
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/components/ui/switch.tsx frontend/src/components/ui/checkbox.tsx frontend/src/components/ui/dialog.tsx
git commit -m "feat(frontend): add master options types + install switch/checkbox/dialog shadcn components"
```

---

## Task 11 — Global Catalog Page (`/products/configure`)

**Files:**
- Modify: `frontend/src/app/(admin)/products/configure/page.tsx` (replace stub)

- [ ] **Step 1: Replace `frontend/src/app/(admin)/products/configure/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { MasterOption, MasterOptionsSyncStatus } from "@/lib/types";
import { Button } from "@/components/ui/button";

export default function MasterOptionsCatalogPage() {
  const [options, setOptions] = useState<MasterOption[]>([]);
  const [status, setStatus] = useState<MasterOptionsSyncStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [opts, st] = await Promise.all([
        api<MasterOption[]>("/api/master-options"),
        api<MasterOptionsSyncStatus>("/api/master-options/sync-status"),
      ]);
      setOptions(opts);
      setStatus(st);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const triggerSync = async () => {
    setSyncing(true);
    try {
      await api("/api/master-options/sync", { method: "POST" });
      await new Promise((r) => setTimeout(r, 3000));
      await load();
    } catch (e) {
      console.error(e);
      alert("Sync failed. Check n8n at http://localhost:5678.");
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#1e1e24]">Master Options Catalog</h1>
          <p className="text-sm text-[#888894] mt-1">
            Global option templates synced from OPS. Attach them to individual products via Configure Options.
          </p>
          {status && (
            <p className="text-xs text-[#888894] mt-2 font-mono">
              {status.total} synced
              {status.last_synced_at ? ` · last ${new Date(status.last_synced_at).toLocaleString()}` : " · never synced"}
            </p>
          )}
        </div>
        <Button onClick={triggerSync} disabled={syncing}>
          {syncing ? "Syncing..." : "Sync from OPS"}
        </Button>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-40 bg-white rounded-[10px] border border-[#cfccc8] animate-pulse" />
          ))}
        </div>
      ) : options.length === 0 ? (
        <div className="bg-white rounded-[10px] border border-[#cfccc8] p-10 text-center">
          <div className="text-[15px] font-semibold text-[#1e1e24] mb-2">No master options synced yet</div>
          <p className="text-sm text-[#888894] mb-4">Click Sync from OPS to pull master options from your OPS account.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {options.map((mo) => (
            <div key={mo.id}
                 className="bg-white rounded-[10px] border border-[#cfccc8] shadow-[4px_5px_0_rgba(30,77,146,0.08)] p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="font-bold text-[#1e4d92]">{mo.title}</div>
                <span className="text-[10px] font-mono text-[#888894]">#{mo.ops_master_option_id}</span>
              </div>
              <div className="text-xs text-[#888894] mb-3">
                {mo.options_type || "—"} · {mo.attributes.length} attributes
              </div>
              <div className="flex flex-wrap gap-1">
                {mo.attributes.slice(0, 6).map((a) => (
                  <span key={a.id} className="text-[10px] px-2 py-0.5 bg-[#ebe8e3] rounded">
                    {a.title}
                  </span>
                ))}
                {mo.attributes.length > 6 && (
                  <span className="text-[10px] text-[#888894]">+{mo.attributes.length - 6}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Manual check**

Visit `http://localhost:3000/products/configure`. Should see empty state or list. Click Sync — triggers n8n if configured.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\(admin\)/products/configure/page.tsx
git commit -m "feat(frontend): master options catalog page at /products/configure"
```

---

## Task 12 — Option Card + Attribute Row Components

**Files:**
- Create: `frontend/src/components/options/attribute-row.tsx`
- Create: `frontend/src/components/options/option-card.tsx`

- [ ] **Step 1: Write `frontend/src/components/options/attribute-row.tsx`**

```tsx
"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import type { AttributeConfigItem } from "@/lib/types";

interface Props {
  attr: AttributeConfigItem;
  onChange: (patch: Partial<AttributeConfigItem>) => void;
}

export function AttributeRow({ attr, onChange }: Props) {
  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-dashed border-[#ebe8e3] last:border-b-0">
      <Checkbox
        checked={attr.enabled}
        onCheckedChange={(v) => onChange({ enabled: Boolean(v) })}
      />
      <div className="flex-1 text-sm text-[#1e1e24] truncate">{attr.title}</div>
      <div className="flex items-center gap-1 text-xs text-[#888894]">
        <span>$</span>
        <Input
          type="number"
          step="0.01"
          value={attr.price}
          onChange={(e) => onChange({ price: parseFloat(e.target.value) || 0 })}
          className="h-7 w-20 text-xs"
        />
      </div>
      <div className="flex items-center gap-1 text-xs text-[#888894]">
        <span>#</span>
        <Input
          type="number"
          value={attr.numeric_value}
          onChange={(e) => onChange({ numeric_value: parseFloat(e.target.value) || 0 })}
          className="h-7 w-16 text-xs"
        />
      </div>
      <div className="flex items-center gap-1 text-xs text-[#888894]">
        <span>↕</span>
        <Input
          type="number"
          value={attr.sort_order}
          onChange={(e) => onChange({ sort_order: parseInt(e.target.value) || 0 })}
          className="h-7 w-14 text-xs"
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write `frontend/src/components/options/option-card.tsx`**

```tsx
"use client";

import { useState } from "react";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { AttributeRow } from "./attribute-row";
import type { OptionConfigItem, AttributeConfigItem } from "@/lib/types";

interface Props {
  card: OptionConfigItem;
  dirty: boolean;
  onChange: (next: OptionConfigItem) => void;
  onSave: () => void | Promise<void>;
  onDelete: () => void | Promise<void>;
}

export function OptionCard({ card, dirty, onChange, onSave, onDelete }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);

  const visible = expanded ? card.attributes : card.attributes.slice(0, 5);

  const updateAttr = (idx: number, patch: Partial<AttributeConfigItem>) => {
    const next = { ...card, attributes: card.attributes.map((a, i) => (i === idx ? { ...a, ...patch } : a)) };
    onChange(next);
  };

  const handleSave = async () => {
    setSaving(true);
    try { await onSave(); } finally { setSaving(false); }
  };

  return (
    <div className="bg-white rounded-[10px] border border-[#cfccc8] shadow-[4px_5px_0_rgba(30,77,146,0.08)]">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#cfccc8] bg-[#ebe8e3] rounded-t-[10px]">
        <div className="font-bold text-[#1e4d92] text-sm flex items-center gap-2">
          <span className="w-1 h-4 bg-[#1e4d92]" />
          {card.title}
        </div>
        <Switch
          checked={card.enabled}
          onCheckedChange={(v) => onChange({ ...card, enabled: Boolean(v) })}
          className="data-[state=checked]:bg-green-500"
        />
      </div>

      <div className="px-4 py-2">
        {visible.map((attr, i) => (
          <AttributeRow key={attr.ops_attribute_id} attr={attr} onChange={(p) => updateAttr(i, p)} />
        ))}
        {card.attributes.length > 5 && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-[#1e4d92] font-semibold mt-2"
          >
            {expanded ? "Show Less ▲" : `Show More ▼ (${card.attributes.length - 5})`}
          </button>
        )}
      </div>

      <div className="flex items-center justify-end gap-2 px-4 py-2 border-t border-[#cfccc8]">
        <Button variant="ghost" size="sm" onClick={onDelete} className="text-[#b93232]">
          Delete
        </Button>
        <Button
          size="sm"
          onClick={handleSave}
          disabled={!dirty || saving}
          className="bg-[#1e4d92] hover:bg-[#173d74]"
        >
          {saving ? "Saving..." : "Save"}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/options/attribute-row.tsx frontend/src/components/options/option-card.tsx
git commit -m "feat(frontend): option-card + attribute-row components"
```

---

## Task 13 — Per-Product Options Page (`/products/[id]/options`)

**Files:**
- Create: `frontend/src/app/(admin)/products/[id]/options/page.tsx`

- [ ] **Step 1: Write the page**

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { OptionConfigItem, Product } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { OptionCard } from "@/components/options/option-card";

export default function ConfigureProductOptionsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [product, setProduct] = useState<Product | null>(null);
  const [cards, setCards] = useState<OptionConfigItem[]>([]);
  const [dirty, setDirty] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [savingAll, setSavingAll] = useState(false);
  const [search, setSearch] = useState("");
  const [tag, setTag] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [p, cfg] = await Promise.all([
          api<Product>(`/api/products/${id}`),
          api<OptionConfigItem[]>(`/api/products/${id}/options-config`),
        ]);
        setProduct(p);
        setCards(cfg);
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const tags = useMemo(() => {
    const s = new Set<string>();
    cards.forEach((c) => c.master_option_tag && s.add(c.master_option_tag));
    return Array.from(s);
  }, [cards]);

  const visible = useMemo(() => {
    return cards.filter((c) => {
      if (tag && c.master_option_tag !== tag) return false;
      if (search && !c.title.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [cards, search, tag]);

  const updateCard = (idx: number, next: OptionConfigItem) => {
    setCards((prev) => prev.map((c, i) => (i === idx ? next : c)));
    setDirty((d) => new Set(d).add(next.master_option_id));
  };

  const saveOne = async (card: OptionConfigItem) => {
    await api(`/api/products/${id}/options-config/${card.master_option_id}`, {
      method: "PATCH",
      body: JSON.stringify(card),
    });
    setDirty((d) => {
      const n = new Set(d);
      n.delete(card.master_option_id);
      return n;
    });
  };

  const saveAll = async () => {
    setSavingAll(true);
    try {
      await api(`/api/products/${id}/options-config`, {
        method: "PUT",
        body: JSON.stringify(cards),
      });
      setDirty(new Set());
    } finally {
      setSavingAll(false);
    }
  };

  const deleteCard = async (card: OptionConfigItem) => {
    await api(`/api/products/${id}/options-config/${card.master_option_id}`, { method: "DELETE" });
    setCards((prev) => prev.map((c) => (c.master_option_id === card.master_option_id
      ? { ...c, enabled: false, attributes: c.attributes.map((a) => ({ ...a, enabled: false })) }
      : c)));
  };

  if (loading) return <div className="p-6 text-[#888894]">Loading…</div>;

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-[#888894]">
            <button onClick={() => router.back()} className="hover:underline">← Back</button>
          </div>
          <h1 className="text-xl font-bold text-[#1e1e24] mt-1">
            Assign Product Options » <span className="text-[#1e4d92]">{product?.product_name}</span>
          </h1>
        </div>
        <Button
          onClick={saveAll}
          disabled={savingAll || dirty.size === 0}
          className="bg-[#1e4d92] hover:bg-[#173d74]"
        >
          {savingAll ? "Saving..." : `Save All ${dirty.size ? `(${dirty.size})` : ""}`}
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <Input
          placeholder="Search..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <select
          value={tag}
          onChange={(e) => setTag(e.target.value)}
          className="h-9 px-3 text-sm border border-[#cfccc8] rounded bg-white"
        >
          <option value="">All tags</option>
          {tags.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <Button variant="ghost" onClick={() => { setSearch(""); setTag(""); }}>Reset</Button>
      </div>

      {visible.length === 0 ? (
        <div className="bg-white rounded-[10px] border border-[#cfccc8] p-10 text-center text-[#888894]">
          {cards.length === 0
            ? "No master options synced. Visit /products/configure and click Sync from OPS."
            : "No matches for the current filter."}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {visible.map((card) => {
            const idx = cards.indexOf(card);
            return (
              <OptionCard
                key={card.master_option_id}
                card={card}
                dirty={dirty.has(card.master_option_id)}
                onChange={(next) => updateCard(idx, next)}
                onSave={() => saveOne(cards[idx])}
                onDelete={() => deleteCard(card)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Manual check**

Visit `http://localhost:3000/products/<some-product-uuid>/options` where `<some-product-uuid>` is a real SanMar product ID. Expect 3-col grid of master option cards with toggles + attribute rows + Save/Delete buttons.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\(admin\)/products/\[id\]/options/page.tsx
git commit -m "feat(frontend): per-product Assign Options page at /products/[id]/options"
```

---

## Task 14 — Wire Product Detail Page: "Configure Options" Button + Banner

**Files:**
- Modify: `frontend/src/app/(admin)/products/[id]/page.tsx`

- [ ] **Step 1: Add Configure Options button + banner**

Locate line ~125 in the product detail page (near PublishButton). Add button next to Publish:

```tsx
import Link from "next/link";

// Inside the header action buttons block, near PublishButton:
<Link href={`/products/${product.id}/options`}>
  <Button variant="outline" className="border-[#1e4d92] text-[#1e4d92]">
    Configure Options
  </Button>
</Link>
```

- [ ] **Step 2: Add banner showing at top of product detail when product has any enabled options**

Near top of the page JSX (after loading guard), add:

```tsx
{product.options?.some((o: any) => o.enabled) && (
  <div className="bg-yellow-50 border border-yellow-300 rounded-lg px-4 py-3 mb-4 text-sm text-yellow-900">
    <strong>Options saved to hub.</strong> OPS push is pending beta API — configure manually in OPS admin for now.
  </div>
)}
```

- [ ] **Step 3: Manual verify**

Open a product detail page. Expect Configure Options button in header. Once any option is enabled + saved, banner appears.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/\(admin\)/products/\[id\]/page.tsx
git commit -m "feat(frontend): product detail page Configure Options button + OPS push pending banner"
```

---

## Task 15 — End-to-End Verification

- [ ] **Step 1: Full backend test suite green**

```bash
cd backend && source .venv/bin/activate && pytest tests/ -v
```
Expected: all master options tests + existing tests pass.

- [ ] **Step 2: Start stack, sync master options**

```bash
docker compose up -d
sleep 5
curl -X POST http://localhost:8000/api/master-options/sync
sleep 10
curl "http://localhost:8000/api/master-options/sync-status" | python3 -m json.tool
```
Expected: `total > 0` after n8n run.

- [ ] **Step 3: Visit `/products/configure`**

Browser: `http://localhost:3000/products/configure`. Expect:
- Header with Sync from OPS button
- Grid of master option cards

- [ ] **Step 4: Visit a product's options page**

```bash
PID=$(curl -s "http://localhost:8000/api/products?limit=1" | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["id"])')
echo "$PID"
```
Open `http://localhost:3000/products/$PID/options`. Expect screenshot-parity 3-col grid. Toggle a card on, enable a checkbox, set a price, click per-card Save. Refresh — values persist.

- [ ] **Step 5: Duplicate Options**

Pick a second product. From its options page, the UI needs a Duplicate button (currently only backend). Run manual curl:
```bash
SRC=$PID
DST=$(curl -s "http://localhost:8000/api/products?limit=2" | python3 -c 'import sys,json; print(json.load(sys.stdin)[1]["id"])')
curl -X POST "http://localhost:8000/api/products/$DST/options-config/duplicate-from/$SRC"
```
Expected: `{copied: N, status: "ok"}`. Reload `/products/$DST/options` — DST should mirror SRC.

- [ ] **Step 6: Banner visibility**

Open the SRC product's detail page — yellow banner visible.

- [ ] **Step 7: Commit verification log**

```bash
git add .
git commit --allow-empty -m "chore: E2E verification complete for master options MVP"
```

---

## Deferred (not in this plan)

- Push mutations to OPS (`setAdditionalOption`, `setAdditionalOptionAttributes`, `setProductsAttributePrice`) — beta, unshipped. When OPS ships them: add to `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts`, extend `ops-push.json`, swap banner for real push trigger. ~1 day follow-up.
- Duplicate Options dialog UI button (backend endpoint done — adding a dialog trigger in `/products/[id]/options` is a small frontend-only follow-up).
- Option Groups, Tags, Rules — future spec.

---

## Critical files summary

| File | Task |
|------|------|
| `backend/modules/master_options/__init__.py` | 1 |
| `backend/modules/master_options/models.py` | 1 |
| `backend/modules/catalog/models.py` (extend) | 1 |
| `backend/modules/master_options/schemas.py` | 2 |
| `backend/modules/master_options/ingest.py` | 3 |
| `backend/modules/master_options/routes.py` | 4, 5, 6, 7, 8 |
| `backend/modules/master_options/service.py` | 5, 6, 7 |
| `backend/main.py` (include_router) | 3, 4, 5 |
| `backend/tests/test_master_options_ingest.py` | 3, 4 |
| `backend/tests/test_product_options_config.py` | 5, 6, 7 |
| `n8n-workflows/ops-master-options-pull.json` | 9 |
| `n8n-workflows/README.md` | 9 |
| `frontend/src/lib/types.ts` | 10 |
| `frontend/src/components/ui/{switch,checkbox,dialog}.tsx` | 10 |
| `frontend/src/app/(admin)/products/configure/page.tsx` | 11 |
| `frontend/src/components/options/attribute-row.tsx` | 12 |
| `frontend/src/components/options/option-card.tsx` | 12 |
| `frontend/src/app/(admin)/products/[id]/options/page.tsx` | 13 |
| `frontend/src/app/(admin)/products/[id]/page.tsx` | 14 |

## Reuse notes

- `require_ingest_secret` from `backend/modules/catalog/ingest.py:56`
- `pg_insert.on_conflict_do_update` pattern from `backend/modules/catalog/ingest.py:117–150`
- Delete-and-reinsert attribute pattern from `backend/modules/catalog/ingest.py:146–170`
- `api<T>()` helper from `frontend/src/lib/api.ts`
- Blueprint card styling matches `frontend/src/app/(admin)/products/[id]/page.tsx:370+`
