# Demo Push Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Ship end-to-end demo pipeline — SanMar SOAP → hub → per-row Push → n8n ops-push → VG staging OPS, with master→product option conversion at the backend and a mapping/merge table for source↔target linkage. OPS beta per-product-option mutations stubbed.

**Architecture:** Two new DB tables (`push_mappings` + `push_mapping_options`). One new `/ops-options` endpoint that converts hub master-option config to product-scoped shape (strips master_option_id). One new `/push-mappings` upsert endpoint called by n8n after OPS push. n8n `ops-push` workflow adds 3 nodes: fetch /ops-options, stub Apply Options, POST /push-mappings. Frontend adds per-row Push dialog on `/products`.

**Tech Stack:** FastAPI + SQLAlchemy async + asyncpg + PostgreSQL 16. Pydantic v2. Next.js 15 + shadcn/ui + Tailwind. n8n with OnPrintShop custom node.

**Spec:** `docs/superpowers/specs/2026-04-23-demo-push-pipeline-design.md`

**Pre-work:** branch `fix/onprintshop-nodes` has open merge conflicts (see `git status`). Resolve conflicts before starting Task 1. Keep HEAD side for master-options files — that's the master-options work we already shipped.

---

## Task 1 — DB Models: `push_mappings` + `push_mapping_options`

**Files:**
- Create: `backend/modules/push_mappings/__init__.py`
- Create: `backend/modules/push_mappings/models.py`
- Modify: `backend/main.py` (register model import)

- [x] **Step 1: Create module dir + empty `__init__.py`**

```bash
mkdir -p backend/modules/push_mappings
touch backend/modules/push_mappings/__init__.py
```

- [x] **Step 2: Write `backend/modules/push_mappings/models.py`**

```python
import uuid as uuid_mod
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class PushMapping(Base):
    __tablename__ = "push_mappings"
    __table_args__ = (
        UniqueConstraint("source_product_id", "customer_id", name="uq_push_mapping_product_customer"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_mod.uuid4
    )
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    source_product_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_supplier_sku: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_ops_base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    target_ops_product_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    pushed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")

    options: Mapped[list["PushMappingOption"]] = relationship(
        back_populates="push_mapping", cascade="all, delete-orphan"
    )


class PushMappingOption(Base):
    __tablename__ = "push_mapping_options"

    id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_mod.uuid4
    )
    push_mapping_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("push_mappings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_master_option_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_master_attribute_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_option_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_attribute_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_ops_option_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_ops_attribute_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    sort_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    push_mapping: Mapped[PushMapping] = relationship(back_populates="options")
```

- [x] **Step 3: Register model import in `backend/main.py`**

Near other `import modules.XXX.models` lines at top of file, add:
```python
import modules.push_mappings.models  # noqa: F401
```

- [x] **Step 4: Restart api to trigger `Base.metadata.create_all`**

Run: `docker compose restart api && sleep 4`

Verify tables exist:
```bash
docker compose exec -T postgres psql -U vg_user -d vg_hub -c "\d push_mappings"
docker compose exec -T postgres psql -U vg_user -d vg_hub -c "\d push_mapping_options"
```

Expected: both tables print column listings with FK + unique constraints.

- [x] **Step 5: Commit**

```bash
git add backend/modules/push_mappings/__init__.py backend/modules/push_mappings/models.py backend/main.py
git commit -m "feat(push_mappings): add push_mappings + push_mapping_options tables"
```

---

## Task 2 — Pydantic Schemas

**Files:**
- Create: `backend/modules/push_mappings/schemas.py`

- [x] **Step 1: Write `backend/modules/push_mappings/schemas.py`**

```python
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---- Ingest (n8n POSTs this after successful OPS push) ----

class PushMappingOptionIngest(BaseModel):
    source_master_option_id: Optional[int] = None
    source_master_attribute_id: Optional[int] = None
    source_option_key: Optional[str] = None
    source_attribute_key: Optional[str] = None
    target_ops_option_id: Optional[int] = None
    target_ops_attribute_id: Optional[int] = None
    title: Optional[str] = None
    price: Optional[Decimal] = None
    sort_order: Optional[int] = None


class PushMappingUpsert(BaseModel):
    source_system: str
    source_product_id: UUID
    source_supplier_sku: Optional[str] = None
    customer_id: UUID
    target_ops_base_url: str
    target_ops_product_id: int
    options: list[PushMappingOptionIngest] = Field(default_factory=list)


# ---- Read (for GET endpoints) ----

class PushMappingOptionRead(BaseModel):
    id: UUID
    source_master_option_id: Optional[int] = None
    source_master_attribute_id: Optional[int] = None
    source_option_key: Optional[str] = None
    source_attribute_key: Optional[str] = None
    target_ops_option_id: Optional[int] = None
    target_ops_attribute_id: Optional[int] = None
    title: Optional[str] = None
    price: Optional[Decimal] = None
    sort_order: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PushMappingRead(BaseModel):
    id: UUID
    source_system: str
    source_product_id: UUID
    source_supplier_sku: Optional[str] = None
    customer_id: UUID
    target_ops_base_url: str
    target_ops_product_id: int
    pushed_at: datetime
    updated_at: datetime
    status: str
    options: list[PushMappingOptionRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ---- ops-options (product-scoped shape for n8n) ----

class OPSProductAttribute(BaseModel):
    """Product-scoped attribute — no master_* IDs. This is what gets pushed to OPS."""
    title: str
    price: Decimal = Decimal("0")
    sort_order: int = 0
    numeric_value: Decimal = Decimal("0")
    # retained for push_mapping traceback only (NOT sent to OPS)
    source_master_attribute_id: Optional[int] = None
    source_attribute_key: Optional[str] = None


class OPSProductOption(BaseModel):
    """Product-scoped option — master_option_id DROPPED intentionally."""
    option_key: str
    title: str
    options_type: Optional[str] = None
    attributes: list[OPSProductAttribute] = Field(default_factory=list)
    # retained for push_mapping traceback only
    source_master_option_id: Optional[int] = None
```

- [x] **Step 2: Parse check**

```bash
cd backend && source .venv/bin/activate && python -c "from modules.push_mappings.schemas import PushMappingUpsert, PushMappingRead, OPSProductOption, OPSProductAttribute; print('ok')"
```

Expected: `ok`

- [x] **Step 3: Commit**

```bash
git add backend/modules/push_mappings/schemas.py
git commit -m "feat(push_mappings): Pydantic schemas (Upsert, Read, OPS product-scoped option)"
```

---

## Task 3 — Service layer + POST / GET / DELETE endpoints

**Files:**
- Create: `backend/modules/push_mappings/service.py`
- Create: `backend/modules/push_mappings/routes.py`
- Modify: `backend/main.py` (register router)
- Test: `backend/tests/test_push_mappings.py`

- [x] **Step 1: Write `backend/modules/push_mappings/service.py`**

```python
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import PushMapping, PushMappingOption
from .schemas import PushMappingUpsert


async def upsert_mapping(db: AsyncSession, body: PushMappingUpsert) -> PushMapping:
    now = datetime.now(timezone.utc)
    stmt = (
        pg_insert(PushMapping)
        .values(
            source_system=body.source_system,
            source_product_id=body.source_product_id,
            source_supplier_sku=body.source_supplier_sku,
            customer_id=body.customer_id,
            target_ops_base_url=body.target_ops_base_url,
            target_ops_product_id=body.target_ops_product_id,
            pushed_at=now,
            updated_at=now,
            status="active",
        )
        .on_conflict_do_update(
            index_elements=["source_product_id", "customer_id"],
            set_={
                "source_system": body.source_system,
                "source_supplier_sku": body.source_supplier_sku,
                "target_ops_base_url": body.target_ops_base_url,
                "target_ops_product_id": body.target_ops_product_id,
                "updated_at": now,
                "status": "active",
            },
        )
        .returning(PushMapping.id)
    )
    mapping_id: UUID = (await db.execute(stmt)).scalar_one()

    # Replace options
    await db.execute(
        delete(PushMappingOption).where(PushMappingOption.push_mapping_id == mapping_id)
    )
    for opt in body.options:
        db.add(
            PushMappingOption(
                push_mapping_id=mapping_id,
                source_master_option_id=opt.source_master_option_id,
                source_master_attribute_id=opt.source_master_attribute_id,
                source_option_key=opt.source_option_key,
                source_attribute_key=opt.source_attribute_key,
                target_ops_option_id=opt.target_ops_option_id,
                target_ops_attribute_id=opt.target_ops_attribute_id,
                title=opt.title,
                price=opt.price,
                sort_order=opt.sort_order,
                created_at=now,
            )
        )
    await db.commit()
    result = await db.execute(
        select(PushMapping)
        .where(PushMapping.id == mapping_id)
        .options(selectinload(PushMapping.options))
    )
    return result.scalar_one()


async def list_mappings(
    db: AsyncSession,
    customer_id: Optional[UUID] = None,
    source_product_id: Optional[UUID] = None,
    limit: int = 100,
) -> list[PushMapping]:
    query = select(PushMapping).options(selectinload(PushMapping.options))
    if customer_id:
        query = query.where(PushMapping.customer_id == customer_id)
    if source_product_id:
        query = query.where(PushMapping.source_product_id == source_product_id)
    query = query.limit(limit).order_by(PushMapping.updated_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def soft_delete_mapping(db: AsyncSession, mapping_id: UUID) -> bool:
    now = datetime.now(timezone.utc)
    mapping = (
        await db.execute(select(PushMapping).where(PushMapping.id == mapping_id))
    ).scalar_one_or_none()
    if not mapping:
        return False
    mapping.status = "deleted"
    mapping.updated_at = now
    await db.commit()
    return True
```

- [x] **Step 2: Write `backend/modules/push_mappings/routes.py`**

```python
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.catalog.ingest import require_ingest_secret

from .schemas import PushMappingRead, PushMappingUpsert
from .service import list_mappings, soft_delete_mapping, upsert_mapping

router = APIRouter(prefix="/api/push-mappings", tags=["push_mappings"])


@router.post(
    "",
    response_model=PushMappingRead,
    status_code=201,
    dependencies=[Depends(require_ingest_secret)],
)
async def create_or_update_mapping(
    body: PushMappingUpsert,
    db: AsyncSession = Depends(get_db),
):
    return await upsert_mapping(db, body)


@router.get("", response_model=list[PushMappingRead])
async def get_mappings(
    customer_id: Optional[UUID] = None,
    source_product_id: Optional[UUID] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    return await list_mappings(db, customer_id, source_product_id, limit)


@router.delete("/{mapping_id}")
async def delete_mapping(mapping_id: UUID, db: AsyncSession = Depends(get_db)):
    ok = await soft_delete_mapping(db, mapping_id)
    if not ok:
        raise HTTPException(404, "Mapping not found")
    return {"status": "deleted"}
```

- [x] **Step 3: Register router in `backend/main.py`**

Add import near other router imports:
```python
from modules.push_mappings.routes import router as push_mappings_router
```

Add with other `app.include_router` calls:
```python
app.include_router(push_mappings_router)
```

- [x] **Step 4: Write failing test `backend/tests/test_push_mappings.py`**

```python
import os
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from main import app
from database import async_session


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    from modules.push_mappings.models import PushMapping
    from modules.customers.models import Customer
    from modules.catalog.models import Product
    from modules.suppliers.models import Supplier
    async with async_session() as s:
        await s.execute(delete(PushMapping))
        await s.execute(delete(Product).where(Product.supplier_sku.like("PM-%")))
        await s.execute(delete(Customer).where(Customer.name.like("PM-%")))
        await s.execute(delete(Supplier).where(Supplier.slug.like("vg-ops-test%")))
        await s.commit()


async def _seed():
    from modules.suppliers.models import Supplier
    from modules.catalog.models import Product
    from modules.customers.models import Customer
    async with async_session() as s:
        sup = Supplier(name="TestSup", slug="vg-ops-test", protocol="soap", auth_config={})
        s.add(sup); await s.commit(); await s.refresh(sup)
        prod = Product(supplier_id=sup.id, supplier_sku="PM-1", product_name="Test")
        cust = Customer(name="PM-Cust", ops_base_url="https://ops.test",
                        ops_token_url="https://ops.test/token",
                        ops_client_id="cid", ops_auth_config={"secret": "s"})
        s.add(prod); s.add(cust)
        await s.commit(); await s.refresh(prod); await s.refresh(cust)
        return prod.id, cust.id


@pytest.mark.asyncio
async def test_upsert_mapping_creates_row():
    secret = os.environ["INGEST_SHARED_SECRET"]
    pid, cid = await _seed()
    body = {
        "source_system": "sanmar",
        "source_product_id": str(pid),
        "source_supplier_sku": "PC61",
        "customer_id": str(cid),
        "target_ops_base_url": "https://vg-staging.ops",
        "target_ops_product_id": 9999,
        "options": [
            {
                "source_master_option_id": 112,
                "source_master_attribute_id": 184,
                "source_option_key": "inkFinish",
                "source_attribute_key": "Gloss",
                "target_ops_option_id": None,
                "target_ops_attribute_id": None,
                "title": "Gloss",
                "price": "0.00",
                "sort_order": 1,
            }
        ],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/push-mappings", json=body, headers={"X-Ingest-Secret": secret})
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["target_ops_product_id"] == 9999
    assert len(data["options"]) == 1
    assert data["options"][0]["source_attribute_key"] == "Gloss"


@pytest.mark.asyncio
async def test_upsert_is_idempotent_on_product_customer_conflict():
    secret = os.environ["INGEST_SHARED_SECRET"]
    pid, cid = await _seed()
    body = {
        "source_system": "sanmar",
        "source_product_id": str(pid),
        "customer_id": str(cid),
        "target_ops_base_url": "https://vg-staging.ops",
        "target_ops_product_id": 1111,
        "options": [],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/push-mappings", json=body, headers={"X-Ingest-Secret": secret})
        body["target_ops_product_id"] = 2222
        r = await c.post("/api/push-mappings", json=body, headers={"X-Ingest-Secret": secret})
    assert r.status_code == 201
    assert r.json()["target_ops_product_id"] == 2222

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/push-mappings?source_product_id={pid}")
    rows = r.json()
    assert len(rows) == 1  # UPSERT, not duplicate


@pytest.mark.asyncio
async def test_ingest_rejects_bad_secret():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/push-mappings", json={}, headers={"X-Ingest-Secret": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_delete_marks_status():
    secret = os.environ["INGEST_SHARED_SECRET"]
    pid, cid = await _seed()
    body = {
        "source_system": "sanmar", "source_product_id": str(pid), "customer_id": str(cid),
        "target_ops_base_url": "x", "target_ops_product_id": 1, "options": [],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/push-mappings", json=body, headers={"X-Ingest-Secret": secret})
        mid = r.json()["id"]
        r = await c.delete(f"/api/push-mappings/{mid}")
        assert r.status_code == 200
        r = await c.get("/api/push-mappings")
        row = [m for m in r.json() if m["id"] == mid][0]
        assert row["status"] == "deleted"
```

- [x] **Step 5: Run tests**

```bash
docker compose restart api && sleep 4
docker compose exec -T api pytest tests/test_push_mappings.py -v
```

Expected: 4 PASS.

- [x] **Step 6: Commit**

```bash
git add backend/modules/push_mappings/service.py backend/modules/push_mappings/routes.py backend/main.py backend/tests/test_push_mappings.py
git commit -m "feat(push_mappings): POST/GET/DELETE endpoints + upsert service + tests"
```

---

## Task 4 — `GET /api/push/{customer_id}/product/{product_id}/ops-options` endpoint

**Files:**
- Modify: `backend/modules/markup/routes.py` (add to existing `push_router`)
- Modify: `backend/modules/markup/schemas.py` (append schemas)
- Test: `backend/tests/test_ops_options_endpoint.py`

- [ ] **Step 1: Append schemas to `backend/modules/markup/schemas.py`**

```python
# ---- OPS product-scoped option shape (strips master_option_id) ----

class OPSProductAttributeSchema(BaseModel):
    title: str
    price: float = 0.0
    sort_order: int = 0
    numeric_value: float = 0.0
    source_master_attribute_id: Optional[int] = None
    source_attribute_key: Optional[str] = None


class OPSProductOptionSchema(BaseModel):
    option_key: str
    title: str
    options_type: Optional[str] = None
    attributes: list[OPSProductAttributeSchema] = Field(default_factory=list)
    source_master_option_id: Optional[int] = None
```

Add `from pydantic import Field` and `from typing import Optional` at top if missing.

- [ ] **Step 2: Add endpoint to `backend/modules/markup/routes.py`**

Near the top, extend imports:
```python
from .schemas import (
    MarkupRuleCreate, MarkupRuleRead, PushPayload,
    OPSProductSizeInput, OPSProductPriceEntry, OPSVariantsBundle,
    OPSProductOptionSchema, OPSProductAttributeSchema,
)
from modules.catalog.models import Product, ProductOption, ProductOptionAttribute
from modules.master_options.models import MasterOption, MasterOptionAttribute
from sqlalchemy.orm import selectinload
```

Append endpoint (after existing `ops_variants_bundle`):

```python
@push_router.get(
    "/{customer_id}/product/{product_id}/ops-options",
    response_model=list[OPSProductOptionSchema],
    dependencies=[Depends(require_ingest_secret)],
)
async def ops_product_options(
    customer_id: UUID, product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return product-scoped option shape for OPS push.

    Converts hub's master-option-based config into product-scoped shape.
    Output intentionally excludes master_option_id + ops_attribute_id from
    the core push body — those are kept only as source_* fields for
    traceability in push_mappings.
    """
    # Load enabled product options with attributes
    po_rows = (
        await db.execute(
            select(ProductOption)
            .where(ProductOption.product_id == product_id, ProductOption.enabled == True)  # noqa: E712
            .options(selectinload(ProductOption.attributes))
        )
    ).scalars().all()

    # Lookup master option attribute_keys via raw_json
    mo_ids = {po.master_option_id for po in po_rows if po.master_option_id is not None}
    moa_map: dict[tuple[int, int], Optional[str]] = {}
    if mo_ids:
        moas = (
            await db.execute(
                select(MasterOption, MasterOptionAttribute)
                .join(MasterOptionAttribute, MasterOption.id == MasterOptionAttribute.master_option_id)
                .where(MasterOption.ops_master_option_id.in_(mo_ids))
            )
        ).all()
        for mo, ma in moas:
            raw = ma.raw_json or {}
            attr_key = raw.get("attribute_key") if isinstance(raw, dict) else None
            moa_map[(mo.ops_master_option_id, ma.ops_attribute_id)] = attr_key

    out: list[OPSProductOptionSchema] = []
    for po in po_rows:
        enabled_attrs = [a for a in po.attributes if a.enabled]
        if not enabled_attrs:
            continue
        attrs_out = [
            OPSProductAttributeSchema(
                title=a.title,
                price=float(a.price or 0),
                numeric_value=float(a.numeric_value or 0),
                sort_order=a.overridden_sort if a.overridden_sort is not None else a.sort_order,
                source_master_attribute_id=a.ops_attribute_id,
                source_attribute_key=moa_map.get((po.master_option_id, a.ops_attribute_id)),
            )
            for a in sorted(enabled_attrs, key=lambda x: x.sort_order)
        ]
        out.append(
            OPSProductOptionSchema(
                option_key=po.option_key,
                title=po.title or "",
                options_type=po.options_type,
                attributes=attrs_out,
                source_master_option_id=po.master_option_id,
            )
        )
    return out
```

- [ ] **Step 3: Write failing test `backend/tests/test_ops_options_endpoint.py`**

```python
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from main import app
from database import async_session


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    from modules.customers.models import Customer
    from modules.catalog.models import Product
    from modules.suppliers.models import Supplier
    from modules.master_options.models import MasterOption
    async with async_session() as s:
        await s.execute(delete(Product).where(Product.supplier_sku.like("OPO-%")))
        await s.execute(delete(Customer).where(Customer.name.like("OPO-%")))
        await s.execute(delete(Supplier).where(Supplier.slug.like("vg-ops-test%")))
        await s.execute(delete(MasterOption).where(MasterOption.ops_master_option_id >= 9000))
        await s.commit()


@pytest.mark.asyncio
async def test_ops_options_returns_product_scoped_shape():
    """Verify master_option_id is STRIPPED from each attribute (core shape),
    only retained as source_master_option_id for traceability."""
    secret = os.environ["INGEST_SHARED_SECRET"]
    from modules.suppliers.models import Supplier
    from modules.catalog.models import Product
    from modules.customers.models import Customer

    async with async_session() as s:
        sup = Supplier(name="OPO-Sup", slug="vg-ops-test", protocol="soap", auth_config={})
        s.add(sup); await s.commit(); await s.refresh(sup)
        prod = Product(supplier_id=sup.id, supplier_sku="OPO-1", product_name="P")
        cust = Customer(name="OPO-Cust", ops_base_url="x", ops_token_url="x",
                        ops_client_id="c", ops_auth_config={"s": "s"})
        s.add(prod); s.add(cust); await s.commit()
        await s.refresh(prod); await s.refresh(cust)
        pid, cid = prod.id, cust.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # seed master options
        await c.post("/api/ingest/master-options", headers={"X-Ingest-Secret": secret}, json=[{
            "ops_master_option_id": 9001,
            "title": "Ink Finish",
            "option_key": "inkFinish",
            "options_type": "combo",
            "attributes": [
                {"ops_attribute_id": 9991, "title": "Gloss", "sort_order": 1, "default_price": 0},
            ],
        }])
        # enable on product
        r = await c.get(f"/api/products/{pid}/options-config")
        cfg = r.json()
        target = next(i for i, mo in enumerate(cfg) if mo["ops_master_option_id"] == 9001)
        cfg[target]["enabled"] = True
        cfg[target]["attributes"][0]["enabled"] = True
        cfg[target]["attributes"][0]["price"] = "5.00"
        await c.put(f"/api/products/{pid}/options-config", json=cfg)

        # read ops-options
        r = await c.get(
            f"/api/push/{cid}/product/{pid}/ops-options",
            headers={"X-Ingest-Secret": secret},
        )

    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 1
    opt = data[0]
    assert opt["option_key"] == "inkFinish"
    assert opt["title"] == "Ink Finish"
    # Core push fields have no master_option_id/attribute_id
    assert "master_option_id" not in opt
    # But source trace fields are present
    assert opt["source_master_option_id"] == 9001
    # Attribute shape
    assert len(opt["attributes"]) == 1
    attr = opt["attributes"][0]
    assert attr["title"] == "Gloss"
    assert float(attr["price"]) == 5.0
    assert "master_attribute_id" not in attr
    assert attr["source_master_attribute_id"] == 9991


@pytest.mark.asyncio
async def test_ops_options_empty_when_nothing_enabled():
    secret = os.environ["INGEST_SHARED_SECRET"]
    from modules.suppliers.models import Supplier
    from modules.catalog.models import Product
    from modules.customers.models import Customer
    async with async_session() as s:
        sup = Supplier(name="OPO-Sup2", slug="vg-ops-test", protocol="soap", auth_config={})
        s.add(sup); await s.commit(); await s.refresh(sup)
        prod = Product(supplier_id=sup.id, supplier_sku="OPO-2", product_name="P2")
        cust = Customer(name="OPO-Cust2", ops_base_url="x", ops_token_url="x",
                        ops_client_id="c", ops_auth_config={"s": "s"})
        s.add(prod); s.add(cust); await s.commit()
        await s.refresh(prod); await s.refresh(cust)
        pid, cid = prod.id, cust.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            f"/api/push/{cid}/product/{pid}/ops-options",
            headers={"X-Ingest-Secret": secret},
        )
    assert r.status_code == 200
    assert r.json() == []
```

- [ ] **Step 4: Run tests**

```bash
docker compose restart api && sleep 4
docker compose exec -T api pytest tests/test_ops_options_endpoint.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/markup/routes.py backend/modules/markup/schemas.py backend/tests/test_ops_options_endpoint.py
git commit -m "feat(markup): GET /ops-options returns product-scoped option shape (master→product conversion)"
```

---

## Task 5 — n8n `ops-push` workflow: add ops-options + stub + push-mappings

**Files:**
- Modify: `n8n-workflows/ops-push.json`

- [ ] **Step 1: Locate insertion point**

Open `n8n-workflows/ops-push.json`. Find the existing `POST /push-log` node (the success log). New nodes get inserted BEFORE that, in order: Get ops-options → Stub Apply Options → Build push-mapping payload → POST /push-mappings → (existing POST /push-log).

- [ ] **Step 2: Add 4 nodes to `nodes` array**

```json
{
  "id": "http-opsopts-001",
  "name": "Get /ops-options",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "position": [3100, 400],
  "parameters": {
    "method": "GET",
    "url": "=http://host.docker.internal:8000/api/push/{{ $('Parse Params').item.json.customer_id }}/product/{{ $('Parse Params').item.json.product_id }}/ops-options",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "X-Ingest-Secret", "value": "={{ $env.INGEST_SHARED_SECRET }}" }
      ]
    },
    "options": {}
  }
},
{
  "id": "code-stub-apply-options",
  "name": "Stub Apply Options",
  "type": "n8n-nodes-base.code",
  "typeVersion": 2,
  "position": [3320, 400],
  "parameters": {
    "jsCode": "// STUB: OPS beta mutations (setAdditionalOption, setAdditionalOptionAttributes,\n// setProductsAttributePrice) are not yet shipped.\n// When they ship, replace this Code node with:\n//   1. Split In Batches over options\n//   2. OPS: setAdditionalOption (per option) → captures target_ops_option_id\n//   3. Split In Batches over attributes\n//   4. OPS: setAdditionalOptionAttributes → captures target_ops_attribute_id\n//   5. OPS: setProductsAttributePrice → applies price\n// For now: annotate each attribute with null target IDs and pass through.\nconst options = $input.all().map(i => i.json);\nconsole.log('[STUB] ops-push options payload:', JSON.stringify(options));\nreturn options.map(opt => ({\n  json: {\n    ...opt,\n    _stub: true,\n    target_ops_option_id: null,\n    attributes: (opt.attributes || []).map(a => ({\n      ...a,\n      target_ops_attribute_id: null,\n    })),\n  }\n}));"
  }
},
{
  "id": "code-build-mapping",
  "name": "Build Push Mapping",
  "type": "n8n-nodes-base.code",
  "typeVersion": 2,
  "position": [3540, 400],
  "parameters": {
    "jsCode": "// Build push_mappings payload. Requires:\n//  - upstream OPS: Set Product output has products_id\n//  - Parse Params has product_id, customer_id\n//  - /payload has supplier_sku and supplier.slug (or we synthesize)\nconst params = $('Parse Params').item.json;\nconst payload = $('Get Push Payload').item.json;\nconst setProd = $('OPS: Set Product').item.json;\nconst opsOpts = $input.all().map(i => i.json);\n\nconst flatOptions = [];\nfor (const opt of opsOpts) {\n  for (const a of (opt.attributes || [])) {\n    flatOptions.push({\n      source_master_option_id: opt.source_master_option_id,\n      source_master_attribute_id: a.source_master_attribute_id,\n      source_option_key: opt.option_key,\n      source_attribute_key: a.source_attribute_key || a.title,\n      target_ops_option_id: opt.target_ops_option_id,\n      target_ops_attribute_id: a.target_ops_attribute_id,\n      title: a.title,\n      price: a.price,\n      sort_order: a.sort_order,\n    });\n  }\n}\n\nreturn [{\n  json: {\n    source_system: payload.product?.source_system || 'sanmar',\n    source_product_id: params.product_id,\n    source_supplier_sku: payload.product?.supplier_sku || null,\n    customer_id: params.customer_id,\n    target_ops_base_url: payload.customer?.ops_base_url || '',\n    target_ops_product_id: setProd.products_id,\n    options: flatOptions,\n  }\n}];"
  }
},
{
  "id": "http-pushmap-001",
  "name": "POST /push-mappings",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "position": [3760, 400],
  "parameters": {
    "method": "POST",
    "url": "http://host.docker.internal:8000/api/push-mappings",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "X-Ingest-Secret", "value": "={{ $env.INGEST_SHARED_SECRET }}" },
        { "name": "Content-Type", "value": "application/json" }
      ]
    },
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "={{ $json }}",
    "options": {}
  }
}
```

- [ ] **Step 3: Update `connections` object**

Add (keyed by node name):

```json
"OPS: Set Product Price": {
  "main": [[{ "node": "Get /ops-options", "type": "main", "index": 0 }]]
},
"Get /ops-options": {
  "main": [[{ "node": "Stub Apply Options", "type": "main", "index": 0 }]]
},
"Stub Apply Options": {
  "main": [[{ "node": "Build Push Mapping", "type": "main", "index": 0 }]]
},
"Build Push Mapping": {
  "main": [[{ "node": "POST /push-mappings", "type": "main", "index": 0 }]]
},
"POST /push-mappings": {
  "main": [[{ "node": "POST Push Log", "type": "main", "index": 0 }]]
}
```

Remove the old `"OPS: Set Product Price": { main: [[{ "node": "POST Push Log" ...}]] }` entry if present — it's now chained through the new nodes.

- [ ] **Step 4: Validate JSON + import**

```bash
python3 -c "import json; json.load(open('n8n-workflows/ops-push.json'))"
docker cp n8n-workflows/ops-push.json api-hub-n8n-1:/tmp/opspush.json
docker exec api-hub-n8n-1 n8n import:workflow --input=/tmp/opspush.json
```

Expected: `Successfully imported 1 workflow.`

- [ ] **Step 5: Verify in n8n UI**

Open `http://localhost:5678` → find `Hub → OPS Push` workflow. Confirm 4 new nodes visible + chain Set Product Price → Get /ops-options → Stub Apply Options → Build Push Mapping → POST /push-mappings → POST Push Log.

- [ ] **Step 6: Commit**

```bash
git add n8n-workflows/ops-push.json
git commit -m "feat(n8n): ops-push adds ops-options fetch + stub Apply Options + push-mappings post"
```

---

## Task 6 — Frontend: per-row Push button on `/products` admin catalog

**Files:**
- Create: `frontend/src/components/products/push-row-action.tsx`
- Modify: `frontend/src/app/(admin)/products/page.tsx`

- [ ] **Step 1: Write `frontend/src/components/products/push-row-action.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Customer } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

interface Props {
  productId: string;
  productName: string;
}

export function PushRowAction({ productId, productName }: Props) {
  const [open, setOpen] = useState(false);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    api<Customer[]>("/api/customers").then((list) => {
      setCustomers(list);
      const first = list.find((c) => c.is_active);
      if (first) setCustomerId(first.id);
    });
  }, [open]);

  async function run() {
    if (!customerId) {
      setMessage("Pick a storefront first");
      return;
    }
    setBusy(true);
    setMessage("Triggering push…");
    try {
      const res = await api<{ triggered: boolean }>(
        `/api/n8n/workflows/vg-ops-push-001/trigger?product_id=${productId}&customer_id=${customerId}`,
        { method: "POST" },
      );
      setMessage(res.triggered ? "Push started. Check history." : "Push failed.");
      if (res.triggered) setTimeout(() => setOpen(false), 1500);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" className="border-[#1e4d92] text-[#1e4d92]">
          Push to OPS
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Push to OPS</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3 py-2">
          <div className="text-sm text-[#484852]">{productName}</div>
          <select
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            className="h-9 px-3 text-sm border border-[#cfccc8] rounded bg-white"
          >
            <option value="">Select Storefront…</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id} disabled={!c.is_active}>
                {c.name} {c.is_active ? "" : "(inactive)"}
              </option>
            ))}
          </select>
          {message && (
            <div className="text-xs font-mono px-3 py-2 rounded bg-[#f9f7f4] text-[#484852] border border-[#ebe8e3]">
              {message}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          <Button
            onClick={run}
            disabled={busy || !customerId}
            className="bg-[#1e4d92] hover:bg-[#173d74]"
          >
            {busy ? "Pushing…" : "Push"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Modify `frontend/src/app/(admin)/products/page.tsx`**

At the top of the file, add import:
```tsx
import { PushRowAction } from "@/components/products/push-row-action";
```

Find the products table `<tr>` row rendering. Add an Action column. Before closing `</tr>` for each row add:
```tsx
<td className="px-4 py-3">
  <PushRowAction productId={p.id} productName={p.product_name} />
</td>
```

And at the `<thead><tr>` add an "Action" `<th>`:
```tsx
<th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-[0.1em] text-[#888894]">Action</th>
```

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E "push-row-action|products/page" | head -5
```

Expected: no new errors related to these files. Pre-existing errors (e.g. active-filter-chips SortKey) unrelated.

- [ ] **Step 4: Manual check**

Reload `http://localhost:3000/products`. Expect new Action column. Click "Push to OPS" → dialog opens with customer dropdown. Select a customer → Push → toast/message shows trigger started.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/products/push-row-action.tsx frontend/src/app/\(admin\)/products/page.tsx
git commit -m "feat(frontend): per-row Push to OPS action on /products catalog"
```

---

## Task 7 — Ingest 5–10 SanMar products via SOAP

**Files:** none to commit. Operations only.

- [ ] **Step 1: Verify SanMar SOAP creds present**

```bash
docker compose exec -T postgres psql -U vg_user -d vg_hub -c \
  "SELECT name, slug, protocol, base_url FROM suppliers WHERE slug = 'sanmar';"
```

Expected: row with `slug='sanmar'`, `protocol='soap'`, `base_url` set. If missing, create via:
```bash
curl -X POST http://localhost:8000/api/suppliers \
  -H "Content-Type: application/json" \
  -d '{"name":"SanMar","slug":"sanmar","protocol":"soap","promostandards_code":"SANMAR","base_url":"https://ws.sanmar.com:8080/SanMarWebService/SanMarWebServicePort","auth_config":{"id":"<ID>","password":"<PW>","customer_number":"<CUSTNO>"}}'
```

- [ ] **Step 2: Run the SanMar smoke script against 10 styles**

```bash
cd backend && source .venv/bin/activate && python scripts/sanmar_smoke.py --limit 10
```

Expected: prints 10 products with live pricing + inventory. No SOAP faults.

- [ ] **Step 3: Run n8n sanmar-soap-pull workflow**

Open `http://localhost:5678`. Find `SanMar SOAP → Hub` workflow. Set environment-like parameter (or edit workflow) so the style list is 10 styles (e.g. `["PC61", "PC54", "ST350", "DT6100", "G200", "PC78", "K500", "L500", "PC90H", "PC55"]`). Execute manually.

Expected: workflow completes green. Check hub:
```bash
curl -s "http://localhost:8000/api/products?supplier_id=<sanmar_uuid>&limit=20" | python3 -c "import sys,json; print(f'count={len(json.load(sys.stdin))}')"
```

Expected: `count=10` (or close — depends on SanMar API availability).

- [ ] **Step 4: Verify in /products UI**

Open `http://localhost:3000/products`. 10 SanMar products visible with real prices.

No commit — this is data setup, not code.

---

## Task 8 — E2E demo run

- [ ] **Step 1: Stack sanity**

```bash
docker compose ps
```

Expected: postgres healthy, api/frontend/n8n up.

- [ ] **Step 2: All backend tests green**

```bash
docker compose exec -T api pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests PASS. New tests: `test_push_mappings.py` (4), `test_ops_options_endpoint.py` (2), existing master-options tests still pass.

- [ ] **Step 3: Ensure VG staging OPS customer row exists**

Via `/customers` UI or curl:
```bash
curl -X POST http://localhost:8000/api/customers \
  -H "Content-Type: application/json" \
  -d '{"name":"VG Staging OPS","ops_base_url":"https://vg-staging.onprintshop.com","ops_token_url":"https://vg-staging.onprintshop.com/oauth/token","ops_client_id":"<CID>","ops_client_secret":"<SECRET>"}'
```

- [ ] **Step 4: Configure options on one SanMar product**

Visit `http://localhost:3000/products/<sanmar_product_id>/options`. Enable one master option (e.g. "Print Sides") with a couple of attributes. Save.

(If the page blocks because supplier is not `ops_graphql`, the earlier change restricts Configure Options to VG OPS supplier products only — demo may need to run on a VG OPS product OR we temporarily disable that guard. For initial demo on SanMar products: expected UX says options don't apply. Pivot: run options-config via curl to seed a row directly, OR pick a VG OPS product if any exist. Note this in demo script.)

- [ ] **Step 5: Trigger Push from /products catalog**

Open `http://localhost:3000/products`. Locate a SanMar product. Click "Push to OPS" → pick VG Staging OPS → Push.

Expected: toast "Push started". n8n execution history shows workflow green. Each OPS node returns a products_id / response.

- [ ] **Step 6: Verify push_mappings row created**

```bash
PID=<the_pushed_product_id>
curl -s "http://localhost:8000/api/push-mappings?source_product_id=$PID" | python3 -m json.tool
```

Expected: 1 row. `target_ops_product_id` has an integer (from setProduct response). `options` array has N rows (one per enabled attribute) with `target_ops_option_id=null` (stub) but `source_*` fields populated.

- [ ] **Step 7: Verify push_log row created**

```bash
curl -s "http://localhost:8000/api/push-log?product_id=$PID&limit=5" | python3 -m json.tool
```

Expected: 1 row, `status: "pushed"`, `ops_product_id` populated.

- [ ] **Step 8: Verify product visible in OPS staging**

Log into VG staging OPS admin. Find the pushed product by `target_ops_product_id`. Expect: product exists with name + sizes + pricing. Options NOT yet configured (stubbed) — this is expected. Configure manually or wait for beta.

- [ ] **Step 9: Capture demo log**

Screenshot or log the above for Christian. Commit log to repo:
```bash
mkdir -p docs/superpowers/demo-logs
# Save any screenshots or run logs to docs/superpowers/demo-logs/2026-04-23-demo-run.md
git add docs/superpowers/demo-logs/2026-04-23-demo-run.md
git commit -m "docs: 2026-04-23 demo push pipeline E2E run log"
```

---

## Deferred follow-ups (NOT in this plan)

1. Replace Stub Apply Options node with real OPS beta mutations when shipped.
2. Multi-tenant schema (`customer_products`, `customer_product_options`).
3. Customer auth + self-serve login.
4. Mapping audit UI.
5. Order routing back to supplier via mappings.
6. Dynamic style list for sanmar-soap-pull (replace hardcoded 10 with DB-driven list).

---

## Critical files summary

| File | Task |
|------|------|
| `backend/modules/push_mappings/__init__.py` | 1 |
| `backend/modules/push_mappings/models.py` | 1 |
| `backend/modules/push_mappings/schemas.py` | 2 |
| `backend/modules/push_mappings/service.py` | 3 |
| `backend/modules/push_mappings/routes.py` | 3 |
| `backend/main.py` | 1 + 3 |
| `backend/modules/markup/schemas.py` | 4 |
| `backend/modules/markup/routes.py` | 4 |
| `backend/tests/test_push_mappings.py` | 3 |
| `backend/tests/test_ops_options_endpoint.py` | 4 |
| `n8n-workflows/ops-push.json` | 5 |
| `frontend/src/components/products/push-row-action.tsx` | 6 |
| `frontend/src/app/(admin)/products/page.tsx` | 6 |

## Reused utilities

- `require_ingest_secret` dep → `backend/modules/catalog/ingest.py:56`
- `pg_insert(...).on_conflict_do_update` pattern → established across ingest modules
- `api<T>(path, opts)` frontend helper → `frontend/src/lib/api.ts`
- shadcn `Dialog` → installed earlier via master-options work
- Existing `PublishButton` patterns → `frontend/src/components/products/publish-button.tsx` (reference, not modified)
- `EncryptedJSON` for customer ops_auth_config → `backend/database.py`
