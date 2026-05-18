# Phase 7 — Decoration Overlay Model

> **STATUS: ⬜ NOT STARTED — blocked on Phase 6 (customer context) and Phase 3 (SanMar adapter).**
>
> **Design decision locked (2026-05-01):** Decorations are **templated** — admin picks from the existing `master_options` catalog, not free-text. This avoids imprint-method typos and keeps the decoration editor consistent with the options already on OPS products.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SanMar apparel products are blank bases with no print options. This phase lets an admin attach a decoration layer (imprint method, location, color, etc.) per (customer, product) by picking from the canonical `master_options` catalog. Phase 8's push pipeline reads this layer and merges it with the base apparel options at push time.

**Architecture:** New `backend/modules/decorations/` module. One new DB table `customer_product_decorations` (composite PK: customer_id + product_id). Decoration options are stored as a JSONB list of `OptionIngest`-shaped dicts — same schema already used by `ProductOption` rows — so the Phase 8 merge is a simple list concatenation. A `has_decoration_overlay` boolean column is added to `suppliers` so the push pipeline (Phase 8) can branch without hard-coding supplier names. Two FastAPI endpoints (GET + PUT). Frontend adds a "Decoration" tab to the SanMar product detail page and a "Needs Decoration" badge on product cards.

**Tech Stack:** FastAPI, async SQLAlchemy 2.0 + asyncpg, Pydantic v2, pytest + pytest-asyncio. Next.js 15 App Router, shadcn/ui, Tailwind. No new dependencies.

**Depends on:**
- Phase 1 ✅ — `OptionIngest` schema, `ProductOption` model
- Phase 3 ✅ — SanMar adapter must exist so `has_decoration_overlay` can be set on the SanMar supplier row
- Phase 6 ✅ — `customer_product_selections` and customer dropdown in UI must exist

**Out of scope:**
- Decoration templates (reusable presets across products) — future
- Per-variant decoration — decoration applies at product level only
- Bulk-decoration (apply same decoration to many products) — future
- Phase 8 push merge — that plan reads this phase's table; do not touch `ops_push` here

---

## File Structure

### Files to create
- `backend/modules/decorations/__init__.py`
- `backend/modules/decorations/models.py` — `CustomerProductDecoration` ORM model
- `backend/modules/decorations/schemas.py` — `DecorationRead`, `DecorationCreate`, `DecoratedOptionRead`
- `backend/modules/decorations/routes.py` — GET + PUT + DELETE endpoints
- `backend/modules/decorations/service.py` — `decoration_required(product, db)` validation helper
- `backend/tests/test_decorations.py`

### Files to modify
- `backend/modules/suppliers/models.py` — add `has_decoration_overlay: bool` column
- `backend/main.py` — import new models, add `_SCHEMA_UPGRADES` entries, register router
- `frontend/src/components/storefront/pdp-layout.tsx` — add "Decoration" tab for SanMar products
- `frontend/src/components/storefront/decoration-editor.tsx` — new component (option picker)
- `frontend/src/components/storefront/product-options.tsx` — add "Needs Decoration" badge

### Files NOT touched
- `backend/modules/ops_push/**` — push merge is Phase 8
- `backend/modules/catalog/persistence.py` — Phase 1 contract, unchanged
- `backend/modules/customer_product_selections/**` — Phase 6 deliverable, unchanged

---

## Data Model

### `customer_product_decorations` table (new)
```
customer_id         UUID FK → customers.id  ON DELETE CASCADE
product_id          UUID FK → products.id   ON DELETE CASCADE
decoration_options  JSONB NOT NULL          -- list of OptionIngest-shaped dicts
updated_at          TIMESTAMP WITH TIME ZONE NOT NULL
PRIMARY KEY (customer_id, product_id)
```

`decoration_options` element shape (same as `OptionIngest`):
```json
{
  "option_key": "imprint_method",
  "title": "Imprint Method",
  "options_type": "radio",
  "sort_order": 1,
  "master_option_id": 42,
  "required": true,
  "attributes": [
    { "title": "Screen Print", "sort_order": 0, "master_attribute_id": 101 }
  ]
}
```

### `suppliers` column to add (via `_SCHEMA_UPGRADES`)
```
has_decoration_overlay  BOOLEAN NOT NULL DEFAULT FALSE
```
Set to `TRUE` on the SanMar supplier row after migration.

---

## Task Breakdown

---

### Task 1: Add `has_decoration_overlay` to `Supplier` model

**Files:**
- Modify: `backend/modules/suppliers/models.py`
- Modify: `backend/main.py`

**Why:** Phase 8 push routing branches on this flag. Setting it here (on the SanMar supplier row) means Phase 7 validation and Phase 8 push both use the same source of truth — no hard-coded adapter class names.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_decorations.py
"""Phase 7 — decoration overlay tests."""
from __future__ import annotations
import pytest


def test_supplier_model_has_decoration_overlay_column():
    from modules.suppliers.models import Supplier
    cols = {c.name for c in Supplier.__table__.columns}
    assert "has_decoration_overlay" in cols
```

- [ ] **Step 2: Add the column to `Supplier`**

In `backend/modules/suppliers/models.py`, add after the `last_delta_sync` column:

```python
from sqlalchemy import Boolean

has_decoration_overlay: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

- [ ] **Step 3: Add `_SCHEMA_UPGRADES` entry in `main.py`**

```python
"ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS has_decoration_overlay BOOLEAN NOT NULL DEFAULT FALSE",
```

- [ ] **Step 4: Run test**

```bash
cd backend && pytest tests/test_decorations.py::test_supplier_model_has_decoration_overlay_column -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/suppliers/models.py backend/main.py backend/tests/test_decorations.py
git commit -m "feat(suppliers): add has_decoration_overlay column"
```

---

### Task 2: `CustomerProductDecoration` ORM model

**Files:**
- Create: `backend/modules/decorations/__init__.py`
- Create: `backend/modules/decorations/models.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_decorations.py`:

```python
def test_customer_product_decoration_model_has_required_columns():
    from modules.decorations.models import CustomerProductDecoration
    cols = {c.name for c in CustomerProductDecoration.__table__.columns}
    assert "customer_id" in cols
    assert "product_id" in cols
    assert "decoration_options" in cols
    assert "updated_at" in cols
```

- [ ] **Step 2: Create the package**

Create `backend/modules/decorations/__init__.py` (empty).

- [ ] **Step 3: Create the model**

Create `backend/modules/decorations/models.py`:

```python
import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class CustomerProductDecoration(Base):
    __tablename__ = "customer_product_decorations"

    customer_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    decoration_options: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
```

- [ ] **Step 4: Import in `main.py`**

After existing module model imports add:

```python
import modules.decorations.models  # noqa: F401
```

Also add to `_SCHEMA_UPGRADES`:

```python
"""CREATE TABLE IF NOT EXISTS customer_product_decorations (
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    product_id  UUID NOT NULL REFERENCES products(id)  ON DELETE CASCADE,
    decoration_options JSONB NOT NULL DEFAULT '[]',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (customer_id, product_id)
)""",
```

- [ ] **Step 5: Run test**

```bash
cd backend && pytest tests/test_decorations.py::test_customer_product_decoration_model_has_required_columns -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/decorations/ backend/main.py backend/tests/test_decorations.py
git commit -m "feat(decorations): CustomerProductDecoration model + table"
```

---

### Task 3: Pydantic schemas

**Files:**
- Create: `backend/modules/decorations/schemas.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_decorations.py`:

```python
def test_decoration_create_validates_options_list():
    from modules.decorations.schemas import DecorationCreate
    from pydantic import ValidationError

    ok = DecorationCreate(decoration_options=[
        {
            "option_key": "imprint_method",
            "title": "Imprint Method",
            "options_type": "radio",
            "sort_order": 1,
            "master_option_id": 42,
            "required": True,
            "attributes": [
                {"title": "Screen Print", "sort_order": 0, "master_attribute_id": 101}
            ],
        }
    ])
    assert len(ok.decoration_options) == 1
    assert ok.decoration_options[0].option_key == "imprint_method"

    with pytest.raises(ValidationError):
        DecorationCreate(decoration_options=[])  # empty list not allowed


def test_decoration_read_serializes_from_attributes():
    from modules.decorations.schemas import DecorationRead
    import uuid, datetime
    r = DecorationRead(
        customer_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        decoration_options=[],
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )
    assert r.decoration_options == []
```

- [ ] **Step 2: Create schemas**

Create `backend/modules/decorations/schemas.py`:

```python
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from modules.catalog.schemas import OptionIngest


class DecorationCreate(BaseModel):
    decoration_options: list[OptionIngest] = Field(min_length=1)


class DecorationRead(BaseModel):
    customer_id: UUID
    product_id: UUID
    decoration_options: list[OptionIngest]
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Run tests**

```bash
cd backend && pytest tests/test_decorations.py -k "schema" -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/modules/decorations/schemas.py backend/tests/test_decorations.py
git commit -m "feat(decorations): DecorationCreate + DecorationRead schemas"
```

---

### Task 4: `decoration_required()` service helper

**Files:**
- Create: `backend/modules/decorations/service.py`

This helper is called by the PUT (upsert decoration) endpoint and by the push pipeline (Phase 8) to gate pushes. It answers: "does this product's supplier require a decoration before push?"

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_decorations.py`:

```python
@pytest.mark.asyncio
async def test_decoration_required_true_for_sanmar_supplier(seed_supplier, db):
    from modules.decorations.service import decoration_required
    from modules.catalog.models import Product
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    # Mark the seed supplier as requiring decoration
    from modules.suppliers.models import Supplier
    async with __import__("database").async_session() as s:
        sup = await s.get(Supplier, seed_supplier.id)
        sup.has_decoration_overlay = True
        await s.commit()

    # Create a product for that supplier
    from database import async_session
    async with async_session() as s:
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="DEC-TEST-1",
            product_name="Decoration Required Test",
            product_type="apparel",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        await s.commit()

    async with async_session() as s:
        product = await s.get(Product, pid)
        result = await decoration_required(product, s)
        assert result is True


@pytest.mark.asyncio
async def test_decoration_required_false_for_vg_ops_supplier(seed_supplier, db):
    from modules.decorations.service import decoration_required
    from modules.catalog.models import Product
    from modules.suppliers.models import Supplier
    from database import async_session
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    # Ensure seed_supplier has has_decoration_overlay = False
    async with async_session() as s:
        sup = await s.get(Supplier, seed_supplier.id)
        sup.has_decoration_overlay = False
        await s.commit()

    async with async_session() as s:
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="NO-DEC-1",
            product_name="No Decoration Needed",
            product_type="print",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        await s.commit()

    async with async_session() as s:
        product = await s.get(Product, pid)
        result = await decoration_required(product, s)
        assert result is False
```

- [ ] **Step 2: Create service**

Create `backend/modules/decorations/service.py`:

```python
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import Product
from modules.suppliers.models import Supplier


async def decoration_required(product: Product, db: AsyncSession) -> bool:
    """Return True if this product's supplier requires a decoration before push."""
    supplier = await db.get(Supplier, product.supplier_id)
    if supplier is None:
        return False
    return bool(supplier.has_decoration_overlay)
```

- [ ] **Step 3: Run tests**

```bash
cd backend && pytest tests/test_decorations.py -k "decoration_required" -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/modules/decorations/service.py backend/tests/test_decorations.py
git commit -m "feat(decorations): decoration_required() service helper"
```

---

### Task 5: `PUT /api/customers/{id}/products/{product_id}/decorations` — upsert

**Files:**
- Create: `backend/modules/decorations/routes.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_decorations.py`:

```python
@pytest.mark.asyncio
async def test_put_decoration_creates_row(client, seed_supplier):
    from modules.catalog.models import Product
    from modules.customers.models import Customer
    from modules.decorations.models import CustomerProductDecoration
    from database import async_session
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy import select

    async with async_session() as s:
        cust = Customer(
            name="Dec Co",
            ops_base_url="https://decco.ops.com",
            ops_token_url="https://decco.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(cust)
        await s.flush()
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="PUT-DEC-1",
            product_name="Put Dec Product",
            product_type="apparel",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        await s.commit()
        cid = cust.id

    body = {
        "decoration_options": [
            {
                "option_key": "imprint_method",
                "title": "Imprint Method",
                "options_type": "radio",
                "sort_order": 1,
                "master_option_id": 42,
                "required": True,
                "attributes": [
                    {"title": "Screen Print", "sort_order": 0, "master_attribute_id": 101}
                ],
            }
        ]
    }
    resp = await client.put(
        f"/api/customers/{cid}/products/{pid}/decorations",
        json=body,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["customer_id"] == str(cid)
    assert data["product_id"] == str(pid)
    assert len(data["decoration_options"]) == 1
    assert data["decoration_options"][0]["option_key"] == "imprint_method"

    async with async_session() as s:
        row = await s.get(CustomerProductDecoration, (cid, pid))
        assert row is not None
        assert len(row.decoration_options) == 1


@pytest.mark.asyncio
async def test_put_decoration_is_idempotent(client, seed_supplier):
    """Second PUT replaces, not appends."""
    from modules.customers.models import Customer
    from modules.catalog.models import Product
    from database import async_session
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async with async_session() as s:
        cust = Customer(
            name="Dec Idem",
            ops_base_url="https://decimp.ops.com",
            ops_token_url="https://decimp.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(cust)
        await s.flush()
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="IDEM-DEC-1",
            product_name="Idem Dec Product",
            product_type="apparel",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        await s.commit()
        cid = cust.id

    option = lambda key: {
        "option_key": key,
        "title": key,
        "options_type": "radio",
        "sort_order": 0,
        "required": False,
        "attributes": [{"title": "A", "sort_order": 0}],
    }
    await client.put(f"/api/customers/{cid}/products/{pid}/decorations",
                     json={"decoration_options": [option("first")]})
    resp = await client.put(f"/api/customers/{cid}/products/{pid}/decorations",
                            json={"decoration_options": [option("second")]})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["decoration_options"]) == 1
    assert data["decoration_options"][0]["option_key"] == "second"
```

- [ ] **Step 2: Create routes**

Create `backend/modules/decorations/routes.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.catalog.models import Product
from modules.customers.models import Customer

from .models import CustomerProductDecoration
from .schemas import DecorationCreate, DecorationRead

router = APIRouter(prefix="/api/customers", tags=["decorations"])


@router.put(
    "/{customer_id}/products/{product_id}/decorations",
    response_model=DecorationRead,
)
async def upsert_decoration(
    customer_id: uuid.UUID,
    product_id: uuid.UUID,
    body: DecorationCreate,
    db: AsyncSession = Depends(get_db),
) -> DecorationRead:
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(404, f"Customer {customer_id} not found")

    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, f"Product {product_id} not found")

    now = datetime.now(timezone.utc)
    options_json = [opt.model_dump() for opt in body.decoration_options]

    stmt = (
        pg_insert(CustomerProductDecoration)
        .values(
            customer_id=customer_id,
            product_id=product_id,
            decoration_options=options_json,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["customer_id", "product_id"],
            set_={"decoration_options": options_json, "updated_at": now},
        )
        .returning(CustomerProductDecoration)
    )
    row = (await db.execute(stmt)).scalar_one()
    await db.commit()
    return DecorationRead.model_validate(row)
```

- [ ] **Step 3: Register router in `main.py`**

```python
from modules.decorations.routes import router as decorations_router
# ...
app.include_router(decorations_router)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest tests/test_decorations.py -k "put_decoration" -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/decorations/routes.py backend/main.py backend/tests/test_decorations.py
git commit -m "feat(decorations): PUT /api/customers/{id}/products/{id}/decorations"
```

---

### Task 6: `GET /api/customers/{id}/products/{product_id}/decorations`

**Files:**
- Modify: `backend/modules/decorations/routes.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_decorations.py`:

```python
@pytest.mark.asyncio
async def test_get_decoration_returns_existing(client, seed_supplier):
    from modules.customers.models import Customer
    from modules.catalog.models import Product
    from modules.decorations.models import CustomerProductDecoration
    from database import async_session
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from datetime import datetime, timezone

    async with async_session() as s:
        cust = Customer(
            name="Get Dec Co",
            ops_base_url="https://getdec.ops.com",
            ops_token_url="https://getdec.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(cust)
        await s.flush()
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="GET-DEC-1",
            product_name="Get Dec Product",
            product_type="apparel",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        s.add(CustomerProductDecoration(
            customer_id=cust.id,
            product_id=pid,
            decoration_options=[{"option_key": "location", "title": "Location",
                                  "options_type": "radio", "sort_order": 0,
                                  "required": False, "attributes": []}],
            updated_at=datetime.now(timezone.utc),
        ))
        await s.commit()
        cid = cust.id

    resp = await client.get(f"/api/customers/{cid}/products/{pid}/decorations")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["decoration_options"][0]["option_key"] == "location"


@pytest.mark.asyncio
async def test_get_decoration_returns_404_when_none(client, seed_supplier):
    import uuid
    fake_cid = uuid.uuid4()
    fake_pid = uuid.uuid4()
    resp = await client.get(f"/api/customers/{fake_cid}/products/{fake_pid}/decorations")
    assert resp.status_code == 404
```

- [ ] **Step 2: Add GET route**

In `backend/modules/decorations/routes.py`, add:

```python
from sqlalchemy import select


@router.get(
    "/{customer_id}/products/{product_id}/decorations",
    response_model=DecorationRead,
)
async def get_decoration(
    customer_id: uuid.UUID,
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DecorationRead:
    row = await db.get(CustomerProductDecoration, (customer_id, product_id))
    if row is None:
        raise HTTPException(404, "No decoration found for this customer + product")
    return DecorationRead.model_validate(row)
```

- [ ] **Step 3: Run tests**

```bash
cd backend && pytest tests/test_decorations.py -k "get_decoration" -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/modules/decorations/routes.py backend/tests/test_decorations.py
git commit -m "feat(decorations): GET /api/customers/{id}/products/{id}/decorations"
```

---

### Task 7: `DELETE /api/customers/{id}/products/{product_id}/decorations`

**Files:**
- Modify: `backend/modules/decorations/routes.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_decorations.py`:

```python
@pytest.mark.asyncio
async def test_delete_decoration_removes_row(client, seed_supplier):
    from modules.customers.models import Customer
    from modules.catalog.models import Product
    from modules.decorations.models import CustomerProductDecoration
    from database import async_session
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from datetime import datetime, timezone

    async with async_session() as s:
        cust = Customer(
            name="Del Dec Co",
            ops_base_url="https://deldec.ops.com",
            ops_token_url="https://deldec.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(cust)
        await s.flush()
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="DEL-DEC-1",
            product_name="Del Dec Product",
            product_type="apparel",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        s.add(CustomerProductDecoration(
            customer_id=cust.id,
            product_id=pid,
            decoration_options=[{"option_key": "loc", "title": "Loc",
                                  "options_type": "radio", "sort_order": 0,
                                  "required": False, "attributes": []}],
            updated_at=datetime.now(timezone.utc),
        ))
        await s.commit()
        cid = cust.id

    resp = await client.delete(f"/api/customers/{cid}/products/{pid}/decorations")
    assert resp.status_code == 204

    async with async_session() as s:
        row = await s.get(CustomerProductDecoration, (cid, pid))
        assert row is None
```

- [ ] **Step 2: Add DELETE route**

```python
from sqlalchemy import delete as sa_delete


@router.delete(
    "/{customer_id}/products/{product_id}/decorations",
    status_code=204,
)
async def delete_decoration(
    customer_id: uuid.UUID,
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    row = await db.get(CustomerProductDecoration, (customer_id, product_id))
    if row is None:
        raise HTTPException(404, "No decoration to delete")
    await db.delete(row)
    await db.commit()
```

- [ ] **Step 3: Run tests**

```bash
cd backend && pytest tests/test_decorations.py -k "delete_decoration" -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/modules/decorations/routes.py backend/tests/test_decorations.py
git commit -m "feat(decorations): DELETE /api/customers/{id}/products/{id}/decorations"
```

---

### Task 8: Push gate — validate decoration exists before push

**Files:**
- Modify: `backend/modules/decorations/service.py`

This adds `assert_decoration_ready(customer_id, product, db)` — a function Phase 8's push route calls before pushing a SanMar product. If decoration is required but missing, raises `DecorationMissingError`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_decorations.py`:

```python
@pytest.mark.asyncio
async def test_assert_decoration_ready_raises_when_missing(seed_supplier):
    from modules.decorations.service import assert_decoration_ready, DecorationMissingError
    from modules.catalog.models import Product
    from modules.suppliers.models import Supplier
    from database import async_session
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    import uuid

    async with async_session() as s:
        sup = await s.get(Supplier, seed_supplier.id)
        sup.has_decoration_overlay = True
        await s.commit()

    async with async_session() as s:
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="GATE-1",
            product_name="Gate Product",
            product_type="apparel",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        await s.commit()

    fake_customer_id = uuid.uuid4()
    async with async_session() as s:
        product = await s.get(Product, pid)
        with pytest.raises(DecorationMissingError):
            await assert_decoration_ready(fake_customer_id, product, s)


@pytest.mark.asyncio
async def test_assert_decoration_ready_passes_when_present(seed_supplier):
    from modules.decorations.service import assert_decoration_ready
    from modules.decorations.models import CustomerProductDecoration
    from modules.catalog.models import Product
    from modules.customers.models import Customer
    from modules.suppliers.models import Supplier
    from database import async_session
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from datetime import datetime, timezone

    async with async_session() as s:
        sup = await s.get(Supplier, seed_supplier.id)
        sup.has_decoration_overlay = True
        cust = Customer(
            name="Gate Pass",
            ops_base_url="https://gatepass.ops.com",
            ops_token_url="https://gatepass.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(cust)
        await s.flush()
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="GATE-OK-1",
            product_name="Gate OK Product",
            product_type="apparel",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        s.add(CustomerProductDecoration(
            customer_id=cust.id,
            product_id=pid,
            decoration_options=[{"option_key": "m", "title": "M",
                                  "options_type": "radio", "sort_order": 0,
                                  "required": True, "attributes": []}],
            updated_at=datetime.now(timezone.utc),
        ))
        await s.commit()
        cid = cust.id

    async with async_session() as s:
        product = await s.get(Product, pid)
        await assert_decoration_ready(cid, product, s)  # must not raise
```

- [ ] **Step 2: Add to `service.py`**

```python
class DecorationMissingError(Exception):
    """Raised when a supplier requires decoration but none is saved."""


async def assert_decoration_ready(
    customer_id: uuid_mod.UUID,
    product: Product,
    db: AsyncSession,
) -> None:
    """Raise DecorationMissingError if decoration is required but absent."""
    import uuid as uuid_mod
    from modules.decorations.models import CustomerProductDecoration

    if not await decoration_required(product, db):
        return

    row = await db.get(CustomerProductDecoration, (customer_id, product.id))
    if row is None or not row.decoration_options:
        raise DecorationMissingError(
            f"Product {product.supplier_sku} requires decoration before push "
            f"for customer {customer_id}"
        )
```

Also add `import uuid as uuid_mod` at the top of `service.py`.

- [ ] **Step 3: Run tests**

```bash
cd backend && pytest tests/test_decorations.py -k "assert_decoration_ready" -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/modules/decorations/service.py backend/tests/test_decorations.py
git commit -m "feat(decorations): assert_decoration_ready push gate + DecorationMissingError"
```

---

### Task 9: Full backend test suite + set `has_decoration_overlay` on SanMar supplier row

- [ ] **Step 1: Run full backend suite**

```bash
cd backend && pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all PASS. Zero regressions.

- [ ] **Step 2: Set flag on SanMar supplier row in dev DB**

Once Phase 3 SanMar adapter ships and the SanMar supplier row exists in the DB:

```bash
docker compose exec -T postgres psql -U vg_user -d vg_hub -c \
  "UPDATE suppliers SET has_decoration_overlay = TRUE WHERE adapter_class = 'SanMarAdapter';"
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/
git commit -m "test(decorations): full suite green"
```

---

### Task 10: Frontend — "Needs Decoration" badge on product card

**Files:**
- Modify: `frontend/src/components/storefront/product-options.tsx`

The Customer Catalog view (Phase 6) renders product cards. Cards for SanMar products that have no saved decoration should show a yellow "Needs Decoration" badge so the admin knows to add one before pushing.

- [ ] **Step 1: Fetch decoration status alongside customer catalog**

In the Customer Catalog API call (Phase 6 frontend), include a `has_decoration` flag per product. This requires the backend to join `customer_product_decorations` when returning the customer catalog. Add a query param or response field — `decoration_ready: bool` per product in the customer catalog list.

Add to the existing `GET /api/customers/{id}/catalog` response shape (Phase 6 endpoint):
```json
{ "product_id": "...", "status": "selected", "decoration_ready": false }
```

Modify the Phase 6 catalog route to left-join `customer_product_decorations` and set `decoration_ready = row is not None`.

- [ ] **Step 2: Render badge**

In `frontend/src/components/storefront/product-options.tsx`, add:

```tsx
{!decorationReady && supplierHasDecorationOverlay && (
  <span className="inline-flex items-center rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800 border border-yellow-300">
    Needs Decoration
  </span>
)}
```

Pass `decorationReady: boolean` and `supplierHasDecorationOverlay: boolean` as props from the catalog page.

- [ ] **Step 3: Verify in browser**

Run `cd frontend && npm run dev`, open the Customer Catalog, confirm SanMar product cards show the yellow badge when no decoration is saved.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/storefront/product-options.tsx
git commit -m "feat(frontend): Needs Decoration badge on SanMar product cards"
```

---

### Task 11: Frontend — "Decoration" tab on SanMar product detail page

**Files:**
- Create: `frontend/src/components/storefront/decoration-editor.tsx`
- Modify: `frontend/src/components/storefront/pdp-layout.tsx`

- [ ] **Step 1: Create `<DecorationEditor>` component**

Create `frontend/src/components/storefront/decoration-editor.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface MasterOption {
  id: string;
  ops_master_option_id: number;
  title: string;
  option_key: string;
  options_type: string;
  attributes: { id: string; title: string; ops_attribute_id: number }[];
}

interface Props {
  customerId: string;
  productId: string;
}

export function DecorationEditor({ customerId, productId }: Props) {
  const [masterOptions, setMasterOptions] = useState<MasterOption[]>([]);
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api<{ items: MasterOption[] }>("/api/master-options").then((r) =>
      setMasterOptions(r.items ?? [])
    );
    api<{ decoration_options: { option_key: string; attributes: { title: string }[] }[] }>(
      `/api/customers/${customerId}/products/${productId}/decorations`
    )
      .then((r) => {
        const init: Record<string, string[]> = {};
        for (const opt of r.decoration_options) {
          init[opt.option_key] = opt.attributes.map((a) => a.title);
        }
        setSelected(init);
      })
      .catch(() => {});
  }, [customerId, productId]);

  const toggle = (optionKey: string, attrTitle: string) => {
    setSelected((prev) => {
      const cur = prev[optionKey] ?? [];
      return {
        ...prev,
        [optionKey]: cur.includes(attrTitle)
          ? cur.filter((t) => t !== attrTitle)
          : [...cur, attrTitle],
      };
    });
  };

  const save = async () => {
    setSaving(true);
    const decoration_options = masterOptions
      .filter((o) => (selected[o.option_key] ?? []).length > 0)
      .map((o) => ({
        option_key: o.option_key,
        title: o.title,
        options_type: o.options_type,
        sort_order: 0,
        required: false,
        master_option_id: o.ops_master_option_id,
        attributes: o.attributes
          .filter((a) => (selected[o.option_key] ?? []).includes(a.title))
          .map((a, i) => ({
            title: a.title,
            sort_order: i,
            master_attribute_id: a.ops_attribute_id,
          })),
      }));
    await api(`/api/customers/${customerId}/products/${productId}/decorations`, {
      method: "PUT",
      body: JSON.stringify({ decoration_options }),
    });
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Select the decoration options that apply to this product for this customer.
      </p>
      {masterOptions.map((opt) => (
        <div key={opt.id} className="space-y-1">
          <p className="text-sm font-medium">{opt.title}</p>
          <div className="flex flex-wrap gap-2">
            {opt.attributes.map((attr) => {
              const active = (selected[opt.option_key] ?? []).includes(attr.title);
              return (
                <button
                  key={attr.id}
                  onClick={() => toggle(opt.option_key, attr.title)}
                  className={`rounded border px-2 py-1 text-xs transition-colors ${
                    active
                      ? "border-blue-600 bg-blue-50 text-blue-700"
                      : "border-zinc-200 bg-white text-zinc-600 hover:border-zinc-400"
                  }`}
                >
                  {attr.title}
                </button>
              );
            })}
          </div>
        </div>
      ))}
      <Button onClick={save} disabled={saving} size="sm">
        {saving ? "Saving…" : saved ? "Saved ✓" : "Save Decoration"}
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Add "Decoration" tab to PDP layout**

In `frontend/src/components/storefront/pdp-layout.tsx`, add a "Decoration" tab that renders `<DecorationEditor>` when `product.supplier?.has_decoration_overlay === true` and a `customerId` is in context (from the Phase 6 customer dropdown).

```tsx
{product.supplier?.has_decoration_overlay && customerId && (
  <TabsTrigger value="decoration">Decoration</TabsTrigger>
)}
// ...
{product.supplier?.has_decoration_overlay && customerId && (
  <TabsContent value="decoration">
    <DecorationEditor customerId={customerId} productId={product.id} />
  </TabsContent>
)}
```

- [ ] **Step 3: Verify in browser**

Open a SanMar product detail page with the customer dropdown set. Confirm the Decoration tab appears, master options load, selections save, and a second visit restores saved state.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/storefront/decoration-editor.tsx \
        frontend/src/components/storefront/pdp-layout.tsx
git commit -m "feat(frontend): Decoration tab + editor on SanMar product detail page"
```

---

## Phase 7 Completion Criteria

- [ ] `customer_product_decorations` table exists (composite PK: customer_id + product_id)
- [ ] `suppliers.has_decoration_overlay` column exists; SanMar supplier row has it set to `TRUE`
- [ ] `PUT /api/customers/{id}/products/{id}/decorations` upserts decoration (idempotent)
- [ ] `GET /api/customers/{id}/products/{id}/decorations` returns saved decoration or 404
- [ ] `DELETE /api/customers/{id}/products/{id}/decorations` removes row
- [ ] `decoration_required(product, db)` returns `True` when supplier has `has_decoration_overlay=True`
- [ ] `assert_decoration_ready(customer_id, product, db)` raises `DecorationMissingError` when decoration missing
- [ ] "Needs Decoration" badge appears on SanMar product cards in Customer Catalog (Phase 6 UI)
- [ ] "Decoration" tab visible on SanMar PDP; editor loads `master_options`; selections persist
- [ ] All existing tests pass (zero regressions)

**Next plan:** `phase8-push-pipeline-polish.md` — calls `assert_decoration_ready` before push, merges `decoration_options` with base apparel options, adds push routing on `has_decoration_overlay`.
