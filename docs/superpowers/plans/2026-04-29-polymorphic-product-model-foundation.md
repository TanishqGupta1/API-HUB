# Phase 1 — Polymorphic Product Model Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing product data model from a single flat shape into a polymorphic one — a shared `products` spine plus type-specific detail tables (`apparel_details`, `print_details`) and supporting tables (`variant_prices`, `product_sizes`). Ship a `persist_product` service that routes by `product_type` and replaces the inline upsert logic in `catalog/ingest.py`. After this phase, Phases 2–5 can all call `persist_product(item: ProductIngest, ...)` regardless of supplier type.

**Architecture:** New SQLAlchemy models for `ApprelDetails`, `PrintDetails`, `VariantPrice`, `ProductSize` auto-create via `Base.metadata.create_all` in the existing lifespan (they are new tables — no ALTER needed, just import them in `main.py`). Supplier and SyncJob models get new columns via idempotent `_SCHEMA_UPGRADES` ALTER statements. A new `backend/modules/catalog/persistence.py` module owns `persist_product`. The existing `catalog/ingest.py` HTTP endpoints become thin wrappers that call `persist_product`. The existing `ProductIngest` schema gains optional `print_details`, `apparel_details`, `sizes`, and `price_tiers` fields with a `model_validator` enforcing type-consistency at app layer — no DB CHECK constraints.

**Tech Stack:** FastAPI + async SQLAlchemy 2.0 + asyncpg, Pydantic v2, pytest + pytest-asyncio. No Alembic. No new dependencies required for this phase.

**Design decisions (locked):**
- `product_type` is VARCHAR(50), not a PG ENUM. Pydantic validates.
- No DB CHECK constraint enforcing detail-table presence. Enforce in `persist_product` and test.
- `apparel_details` and `print_details` are 1:1 with `products` (same PK = product_id).
- `variant_prices` is 1:N with `product_variants` (tiered pricing bands per variant for apparel).
- `product_sizes` is 1:N with `products` (pre-set W×H options for print configurator).
- Print products have zero `product_variants` rows. Formula pricing lives in `print_details`.
- Apparel products have zero `print_details` rows. Pricing lives in `variant_prices`.
- Existing products in DB are all VG OPS print products — backfill creates their `print_details` rows.
- `persist_product` uses `ON CONFLICT DO UPDATE` everywhere (idempotent re-run).
- Auth errors (bad secret) raise HTTP 401 immediately. Per-product persist errors are collected and continue.

**Depends on:** Nothing — this is Phase 1, the foundation all other phases build on.

**Out of scope (other plans):** OPS adapter (Phase 2), SanMar/PS adapter (Phase 3), pricing API (Phase 4), frontend PDP (Phase 5), n8n scheduling (Phase 6).

---

## Current codebase state (read before writing any code)

Key files:
- `backend/modules/catalog/models.py` — has `Product`, `ProductVariant`, `ProductImage`, `ProductOption`, `ProductOptionAttribute`, `Category`. Does NOT have `ApprelDetails`, `PrintDetails`, `VariantPrice`, `ProductSize`.
- `backend/modules/catalog/schemas.py` — has `ProductIngest`, `VariantIngest`, `OptionIngest`, `ImageIngest`, `OptionAttributeIngest`. Does NOT have `PrintDetailsIngest`, `ApparelDetailsIngest`, `ProductSizeIngest`, `PriceTierIngest`.
- `backend/modules/catalog/ingest.py` — has inline upsert logic for products/variants/images/options. Must be refactored in Task 11.
- `backend/modules/suppliers/models.py` — `Supplier` model. Missing: `adapter_class`, `last_full_sync`, `last_delta_sync`.
- `backend/modules/sync_jobs/models.py` — `SyncJob` model. Missing: `errors JSONB` column.
- `backend/main.py` — has `_SCHEMA_UPGRADES` list, `Base.metadata.create_all` in lifespan. All new models must be imported here.
- `backend/tests/conftest.py` — fixtures: `_create_schema` (session), `_cleanup_around_test` (autouse), `db`, `client`, `seed_supplier`, `inactive_supplier`.

---

## File structure

### Files to create
- `backend/modules/catalog/persistence.py` — `persist_product(supplier_id, item, db, now)` service
- `backend/tests/test_persist_product.py` — TDD tests for persist_product (apparel + print paths)
- `backend/tests/fixtures/ops_decals.json` — two VG OPS decal products as ProductIngest JSON
- `backend/scripts/backfill_product_types.py` — one-shot script: add print_details rows for existing products where product_type="print"

### Files to modify
- `backend/modules/catalog/models.py` — add `ApprelDetails`, `PrintDetails`, `VariantPrice`, `ProductSize` classes + relationships on `Product` and `ProductVariant`
- `backend/modules/catalog/schemas.py` — add `PrintDetailsIngest`, `ApparelDetailsIngest`, `ProductSizeIngest`, `PriceTierIngest`; extend `ProductIngest`; add `model_validator`; extend `ProductRead`
- `backend/modules/catalog/ingest.py` — refactor `ingest_products` to call `persist_product`; remove duplicated upsert logic
- `backend/modules/suppliers/models.py` — add `adapter_class`, `last_full_sync`, `last_delta_sync` columns
- `backend/modules/sync_jobs/models.py` — add `errors JSONB` column
- `backend/main.py` — import new models; append new `_SCHEMA_UPGRADES` entries for supplier + sync_job columns

### Files NOT touched
- `backend/modules/ops_push/**` — outbound push pipeline, Phase 2+
- `backend/modules/promostandards/**` — SanMar adapter, Phase 3
- `frontend/**` — polymorphic PDP, Phase 5

---

## Data model reference

### `apparel_details` table (new)
```
product_id   UUID PK, FK → products.id ON DELETE CASCADE
pricing_method  VARCHAR(50) NOT NULL DEFAULT 'tiered_variant'
raw_payload  JSONB NULL
```

### `print_details` table (new)
```
product_id       UUID PK, FK → products.id ON DELETE CASCADE
pricing_method   VARCHAR(50) NOT NULL DEFAULT 'formula'
min_width        NUMERIC(10,2) NULL
max_width        NUMERIC(10,2) NULL
min_height       NUMERIC(10,2) NULL
max_height       NUMERIC(10,2) NULL
size_unit        VARCHAR(10) NOT NULL DEFAULT 'in'
base_price_per_sq_unit  NUMERIC(10,4) NULL
raw_payload      JSONB NULL
```

### `variant_prices` table (new)
```
id            UUID PK
variant_id    UUID FK → product_variants.id ON DELETE CASCADE, index
price_type    VARCHAR(20) NOT NULL  -- MSRP | Net | Sale | Case
quantity_min  INTEGER NOT NULL
quantity_max  INTEGER NULL
price         NUMERIC(10,2) NOT NULL
UNIQUE (variant_id, price_type, quantity_min)
```

### `product_sizes` table (new)
```
id          UUID PK
product_id  UUID FK → products.id ON DELETE CASCADE, index
width       NUMERIC(10,2) NOT NULL
height      NUMERIC(10,2) NOT NULL
unit        VARCHAR(10) NOT NULL DEFAULT 'in'
label       VARCHAR(100) NULL
UNIQUE (product_id, width, height)
```

### Supplier columns to add (via _SCHEMA_UPGRADES)
```
adapter_class     VARCHAR(64) NULL
last_full_sync    TIMESTAMP WITH TIME ZONE NULL
last_delta_sync   TIMESTAMP WITH TIME ZONE NULL
```

### SyncJob columns to add (via _SCHEMA_UPGRADES)
```
errors JSONB NULL  -- list of {sku, error} dicts from per-product errors
```

---

## Task Breakdown

---

### Task 1: New ORM models — `ApprelDetails`, `PrintDetails`

**Files:**
- Modify: `backend/modules/catalog/models.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_persist_product.py
"""TDD tests for persist_product service — written BEFORE the models exist."""
import pytest
from sqlalchemy import select

# These imports will fail until Task 1 is done — that's expected.
from modules.catalog.models import ApprelDetails, PrintDetails


@pytest.mark.asyncio
async def test_apparel_details_model_has_required_columns(db):
    """ApprelDetails table exists and has the expected columns."""
    cols = {c.name for c in ApprelDetails.__table__.columns}
    assert "product_id" in cols
    assert "pricing_method" in cols
    assert "raw_payload" in cols


@pytest.mark.asyncio
async def test_print_details_model_has_required_columns(db):
    """PrintDetails table exists and has the expected columns."""
    cols = {c.name for c in PrintDetails.__table__.columns}
    assert "product_id" in cols
    assert "pricing_method" in cols
    assert "min_width" in cols
    assert "max_width" in cols
    assert "min_height" in cols
    assert "max_height" in cols
    assert "size_unit" in cols
    assert "base_price_per_sq_unit" in cols
    assert "raw_payload" in cols
```

- [ ] **Step 2: Implement `ApprelDetails` and `PrintDetails` in `models.py`**

Add after the `ProductOptionAttribute` class:

```python
from sqlalchemy.dialects.postgresql import JSONB

class ApprelDetails(Base):
    __tablename__ = "apparel_details"

    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    pricing_method: Mapped[str] = mapped_column(String(50), default="tiered_variant")
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    product: Mapped["Product"] = relationship(back_populates="apparel_details")


class PrintDetails(Base):
    __tablename__ = "print_details"

    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    pricing_method: Mapped[str] = mapped_column(String(50), default="formula")
    min_width: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    max_width: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    min_height: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    max_height: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    size_unit: Mapped[str] = mapped_column(String(10), default="in")
    base_price_per_sq_unit: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    product: Mapped["Product"] = relationship(back_populates="print_details")
```

Add relationships to `Product`:
```python
apparel_details: Mapped[Optional["ApprelDetails"]] = relationship(
    back_populates="product", cascade="all, delete-orphan", uselist=False
)
print_details: Mapped[Optional["PrintDetails"]] = relationship(
    back_populates="product", cascade="all, delete-orphan", uselist=False
)
```

- [ ] **Step 3: Import in `main.py`**

Add after the existing `import modules.ops_config.models  # noqa: F401`:
```python
import modules.catalog.models  # noqa: F401  (already present — ensures ApprelDetails/PrintDetails registered)
```
No extra line needed if catalog.models is already imported (it is). Verify `main.py` already has `import modules.catalog.models`.

- [ ] **Step 4: Run tests and confirm pass**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_persist_product.py::test_apparel_details_model_has_required_columns tests/test_persist_product.py::test_print_details_model_has_required_columns -v
```

---

### Task 2: New ORM models — `VariantPrice`, `ProductSize`

**Files:**
- Modify: `backend/modules/catalog/models.py`

- [ ] **Step 1: Write the failing tests**

Add to `test_persist_product.py`:

```python
from modules.catalog.models import ProductSize, VariantPrice


def test_variant_price_model_has_required_columns():
    cols = {c.name for c in VariantPrice.__table__.columns}
    assert "variant_id" in cols
    assert "price_type" in cols
    assert "quantity_min" in cols
    assert "quantity_max" in cols
    assert "price" in cols


def test_product_size_model_has_required_columns():
    cols = {c.name for c in ProductSize.__table__.columns}
    assert "product_id" in cols
    assert "width" in cols
    assert "height" in cols
    assert "unit" in cols
    assert "label" in cols
```

- [ ] **Step 2: Implement `VariantPrice` and `ProductSize`**

Add to `models.py`:

```python
class VariantPrice(Base):
    __tablename__ = "variant_prices"
    __table_args__ = (
        UniqueConstraint("variant_id", "price_type", "quantity_min", name="uq_variant_price_type_qty"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    variant_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), index=True
    )
    price_type: Mapped[str] = mapped_column(String(20))  # MSRP | Net | Sale | Case
    quantity_min: Mapped[int] = mapped_column(Integer)
    quantity_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    variant: Mapped["ProductVariant"] = relationship(back_populates="prices")


class ProductSize(Base):
    __tablename__ = "product_sizes"
    __table_args__ = (
        UniqueConstraint("product_id", "width", "height", name="uq_product_size_wh"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    width: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    height: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit: Mapped[str] = mapped_column(String(10), default="in")
    label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="sizes")
```

Add to `ProductVariant`:
```python
prices: Mapped[list["VariantPrice"]] = relationship(
    back_populates="variant", cascade="all, delete-orphan"
)
```

Add to `Product`:
```python
sizes: Mapped[list["ProductSize"]] = relationship(
    back_populates="product", cascade="all, delete-orphan"
)
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_persist_product.py -k "variant_price or product_size" -v
```

---

### Task 3: Supplier model — add `adapter_class`, `last_full_sync`, `last_delta_sync`

**Files:**
- Modify: `backend/modules/suppliers/models.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_persist_product.py  (add to existing file)

def test_supplier_model_has_adapter_class_column():
    from modules.suppliers.models import Supplier
    cols = {c.name for c in Supplier.__table__.columns}
    assert "adapter_class" in cols
    assert "last_full_sync" in cols
    assert "last_delta_sync" in cols
```

- [ ] **Step 2: Update `Supplier` model**

Add to `modules/suppliers/models.py`:
```python
adapter_class: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
last_full_sync: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
last_delta_sync: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 3: Add to `_SCHEMA_UPGRADES` in `main.py`**

```python
"ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS adapter_class VARCHAR(64)",
"ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS last_full_sync TIMESTAMP WITH TIME ZONE",
"ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS last_delta_sync TIMESTAMP WITH TIME ZONE",
```

- [ ] **Step 4: Run test**

```bash
python -m pytest tests/test_persist_product.py::test_supplier_model_has_adapter_class_column -v
```

---

### Task 4: SyncJob model — add `errors JSONB` column

**Files:**
- Modify: `backend/modules/sync_jobs/models.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write the failing test**

```python
def test_sync_job_model_has_errors_column():
    from modules.sync_jobs.models import SyncJob
    cols = {c.name for c in SyncJob.__table__.columns}
    assert "errors" in cols
```

- [ ] **Step 2: Update `SyncJob` model**

Add to `modules/sync_jobs/models.py`:
```python
from sqlalchemy.dialects.postgresql import JSONB

errors: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=None)
```

- [ ] **Step 3: Add to `_SCHEMA_UPGRADES` in `main.py`**

```python
"ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS errors JSONB",
```

- [ ] **Step 4: Run test**

```bash
python -m pytest tests/test_persist_product.py::test_sync_job_model_has_errors_column -v
```

---

### Task 5: New ingest Pydantic schemas — `PrintDetailsIngest`, `ApparelDetailsIngest`, `ProductSizeIngest`, `PriceTierIngest`

**Files:**
- Modify: `backend/modules/catalog/schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_persist_product.py
from modules.catalog.schemas import (
    ApparelDetailsIngest,
    PrintDetailsIngest,
    ProductSizeIngest,
    PriceTierIngest,
)


def test_print_details_ingest_schema():
    d = PrintDetailsIngest(
        min_width="5.0",
        max_width="24.0",
        min_height="3.0",
        max_height="18.0",
        size_unit="in",
        base_price_per_sq_unit="0.15",
    )
    assert d.pricing_method == "formula"
    assert float(d.min_width) == 5.0


def test_apparel_details_ingest_schema():
    d = ApparelDetailsIngest()
    assert d.pricing_method == "tiered_variant"


def test_price_tier_ingest_schema():
    t = PriceTierIngest(price_type="Net", quantity_min=1, quantity_max=11, price="14.99")
    assert t.price_type == "Net"
    assert t.quantity_min == 1


def test_product_size_ingest_schema():
    s = ProductSizeIngest(width="8.5", height="11.0", unit="in", label='8.5"x11"')
    assert float(s.width) == 8.5
```

- [ ] **Step 2: Add schemas to `schemas.py`**

```python
class PrintDetailsIngest(BaseModel):
    pricing_method: str = "formula"
    min_width: Optional[Decimal] = None
    max_width: Optional[Decimal] = None
    min_height: Optional[Decimal] = None
    max_height: Optional[Decimal] = None
    size_unit: str = "in"
    base_price_per_sq_unit: Optional[Decimal] = None
    raw_payload: Optional[dict] = None


class ApparelDetailsIngest(BaseModel):
    pricing_method: str = "tiered_variant"
    raw_payload: Optional[dict] = None


class ProductSizeIngest(BaseModel):
    width: Decimal
    height: Decimal
    unit: str = "in"
    label: Optional[str] = None


class PriceTierIngest(BaseModel):
    price_type: str  # MSRP | Net | Sale | Case
    quantity_min: int
    quantity_max: Optional[int] = None
    price: Decimal
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_persist_product.py -k "ingest_schema or details_ingest or price_tier or product_size_ingest" -v
```

---

### Task 6: Extend `ProductIngest` with polymorphic fields + `model_validator`

**Files:**
- Modify: `backend/modules/catalog/schemas.py`

- [ ] **Step 1: Write the failing tests**

```python
from pydantic import ValidationError
from modules.catalog.schemas import ProductIngest


def test_product_ingest_accepts_print_type_with_print_details():
    item = ProductIngest(
        supplier_sku="DECAL-131",
        product_name="Custom Decal",
        product_type="print",
        print_details=PrintDetailsIngest(min_width="2", max_width="24", min_height="2", max_height="18"),
    )
    assert item.product_type == "print"
    assert item.print_details is not None


def test_product_ingest_print_without_details_raises():
    with pytest.raises(ValidationError):
        ProductIngest(
            supplier_sku="DECAL-999",
            product_name="Bad Print",
            product_type="print",
            # no print_details
        )


def test_product_ingest_apparel_without_details_gets_default():
    """Apparel is backward-compatible: no apparel_details = auto-created default."""
    item = ProductIngest(
        supplier_sku="PC54",
        product_name="Port & Co Essential",
        product_type="apparel",
    )
    assert item.product_type == "apparel"
    # apparel_details is auto-populated with defaults
    assert item.apparel_details is not None
    assert item.apparel_details.pricing_method == "tiered_variant"
```

- [ ] **Step 2: Extend `ProductIngest` in `schemas.py`**

```python
from pydantic import model_validator

class ProductIngest(BaseModel):
    supplier_sku: str
    product_name: str
    brand: Optional[str] = None
    description: Optional[str] = None
    product_type: str = "apparel"
    image_url: Optional[str] = None
    ops_product_id: Optional[str] = None
    external_catalogue: Optional[int] = None
    category_external_id: Optional[str] = None
    category_name: Optional[str] = None
    variants: list[VariantIngest] = Field(default_factory=list)
    images: list[ImageIngest] = Field(default_factory=list)
    options: list[OptionIngest] = Field(default_factory=list)
    sizes: list[ProductSizeIngest] = Field(default_factory=list)
    price_tiers: list[PriceTierIngest] = Field(default_factory=list)
    print_details: Optional[PrintDetailsIngest] = None
    apparel_details: Optional[ApparelDetailsIngest] = None

    @model_validator(mode="after")
    def _validate_type_details(self) -> "ProductIngest":
        if self.product_type == "print" and self.print_details is None:
            raise ValueError("print products require print_details")
        if self.product_type == "apparel" and self.apparel_details is None:
            self.apparel_details = ApparelDetailsIngest()
        return self
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_persist_product.py -k "product_ingest" -v
```

---

### Task 7: `persist_product` service skeleton — product spine upsert

**Files:**
- Create: `backend/modules/catalog/persistence.py`

- [ ] **Step 1: Write the failing test**

```python
# test_persist_product.py
from uuid import UUID
from datetime import datetime, timezone
from modules.catalog.persistence import persist_product
from modules.catalog.schemas import ProductIngest, PrintDetailsIngest
from modules.catalog.models import Product


@pytest.mark.asyncio
async def test_persist_product_creates_product_row(db, seed_supplier):
    item = ProductIngest(
        supplier_sku="DECAL-T1",
        product_name="Test Decal",
        product_type="print",
        print_details=PrintDetailsIngest(min_width="2", max_width="24", min_height="2", max_height="18"),
    )
    product_id = await persist_product(seed_supplier.id, item, db, datetime.now(timezone.utc))
    await db.commit()

    result = await db.get(Product, product_id)
    assert result is not None
    assert result.supplier_sku == "DECAL-T1"
    assert result.product_type == "print"


@pytest.mark.asyncio
async def test_persist_product_is_idempotent(db, seed_supplier):
    item = ProductIngest(
        supplier_sku="DECAL-IDEM",
        product_name="Idempotent Decal",
        product_type="print",
        print_details=PrintDetailsIngest(),
    )
    now = datetime.now(timezone.utc)
    id1 = await persist_product(seed_supplier.id, item, db, now)
    await db.commit()

    item.product_name = "Idempotent Decal Updated"
    id2 = await persist_product(seed_supplier.id, item, db, now)
    await db.commit()

    assert id1 == id2

    result = await db.get(Product, id1)
    assert result.product_name == "Idempotent Decal Updated"
```

- [ ] **Step 2: Create `persistence.py`**

```python
"""Polymorphic product persistence service.

Routes ingest payloads by product_type to the correct detail table.
Called by catalog/ingest.py (HTTP endpoints) and adapter orchestrators (Phase 2+).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Product
from .schemas import ProductIngest

if TYPE_CHECKING:
    pass


async def persist_product(
    supplier_id: uuid.UUID,
    item: ProductIngest,
    db: AsyncSession,
    now: datetime,
    category_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Upsert one product and return its UUID.

    Caller is responsible for commit.
    """
    stmt = (
        pg_insert(Product)
        .values(
            supplier_id=supplier_id,
            supplier_sku=item.supplier_sku,
            product_name=item.product_name,
            brand=item.brand,
            category=item.category_name,
            category_id=category_id,
            description=item.description,
            product_type=item.product_type,
            image_url=item.image_url,
            ops_product_id=item.ops_product_id,
            external_catalogue=item.external_catalogue,
            last_synced=now,
        )
        .on_conflict_do_update(
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
                "external_catalogue": item.external_catalogue,
                "last_synced": now,
            },
        )
        .returning(Product.id)
    )
    product_id = (await db.execute(stmt)).scalar_one()
    return product_id
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_persist_product.py -k "creates_product_row or is_idempotent" -v
```

---

### Task 8: `persist_product` — print path (print_details + product_sizes + options)

**Files:**
- Modify: `backend/modules/catalog/persistence.py`

- [ ] **Step 1: Write the failing tests**

```python
from modules.catalog.models import PrintDetails, ProductSize


@pytest.mark.asyncio
async def test_persist_print_product_creates_print_details(db, seed_supplier):
    item = ProductIngest(
        supplier_sku="DECAL-PD",
        product_name="Print Details Decal",
        product_type="print",
        print_details=PrintDetailsIngest(
            min_width="2.0",
            max_width="24.0",
            min_height="2.0",
            max_height="18.0",
            size_unit="in",
            base_price_per_sq_unit="0.12",
        ),
    )
    product_id = await persist_product(seed_supplier.id, item, db, datetime.now(timezone.utc))
    await db.commit()

    pd = await db.get(PrintDetails, product_id)
    assert pd is not None
    assert pd.pricing_method == "formula"
    assert float(pd.min_width) == 2.0
    assert float(pd.max_width) == 24.0


@pytest.mark.asyncio
async def test_persist_print_product_creates_sizes(db, seed_supplier):
    item = ProductIngest(
        supplier_sku="DECAL-SZ",
        product_name="Sized Decal",
        product_type="print",
        print_details=PrintDetailsIngest(),
        sizes=[
            ProductSizeIngest(width="4", height="6", label='4"x6"'),
            ProductSizeIngest(width="8", height="10", label='8"x10"'),
        ],
    )
    product_id = await persist_product(seed_supplier.id, item, db, datetime.now(timezone.utc))
    await db.commit()

    sizes = (
        await db.execute(
            select(ProductSize).where(ProductSize.product_id == product_id)
        )
    ).scalars().all()
    assert len(sizes) == 2
    widths = {float(s.width) for s in sizes}
    assert widths == {4.0, 8.0}
```

- [ ] **Step 2: Implement print path in `persistence.py`**

Add `_persist_print_path` helper and call it from `persist_product`:

```python
from .models import PrintDetails, ProductSize, ProductOption, ProductOptionAttribute
from .schemas import OptionIngest

async def _persist_print_path(product_id, item: ProductIngest, db: AsyncSession) -> None:
    # Upsert print_details (1:1 — PK = product_id)
    pd = item.print_details
    stmt = (
        pg_insert(PrintDetails)
        .values(
            product_id=product_id,
            pricing_method=pd.pricing_method,
            min_width=pd.min_width,
            max_width=pd.max_width,
            min_height=pd.min_height,
            max_height=pd.max_height,
            size_unit=pd.size_unit,
            base_price_per_sq_unit=pd.base_price_per_sq_unit,
            raw_payload=pd.raw_payload,
        )
        .on_conflict_do_update(
            index_elements=["product_id"],
            set_={
                "pricing_method": pd.pricing_method,
                "min_width": pd.min_width,
                "max_width": pd.max_width,
                "min_height": pd.min_height,
                "max_height": pd.max_height,
                "size_unit": pd.size_unit,
                "base_price_per_sq_unit": pd.base_price_per_sq_unit,
                "raw_payload": pd.raw_payload,
            },
        )
    )
    await db.execute(stmt)

    # Upsert product_sizes
    for sz in item.sizes:
        size_stmt = (
            pg_insert(ProductSize)
            .values(product_id=product_id, width=sz.width, height=sz.height, unit=sz.unit, label=sz.label)
            .on_conflict_do_update(
                index_elements=["product_id", "width", "height"],
                set_={"unit": sz.unit, "label": sz.label},
            )
        )
        await db.execute(size_stmt)

    # Upsert options (reuse logic from ingest.py)
    if item.options:
        await _upsert_options(db, product_id, item.options)
```

Move `_upsert_options` from `ingest.py` to `persistence.py` (ingest.py will import from persistence).

Call `_persist_print_path` from `persist_product` after getting `product_id`:
```python
if item.product_type == "print":
    await _persist_print_path(product_id, item, db)
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_persist_product.py -k "print" -v
```

---

### Task 9: `persist_product` — apparel path (apparel_details + variants + variant_prices + images)

**Files:**
- Modify: `backend/modules/catalog/persistence.py`

- [ ] **Step 1: Write the failing tests**

```python
from modules.catalog.models import ApprelDetails, ProductVariant, VariantPrice
from modules.catalog.schemas import (
    ApparelDetailsIngest,
    PriceTierIngest,
    VariantIngest,
)


@pytest.mark.asyncio
async def test_persist_apparel_product_creates_apparel_details(db, seed_supplier):
    item = ProductIngest(
        supplier_sku="PC54",
        product_name="Port & Company Essential Tee",
        product_type="apparel",
    )
    product_id = await persist_product(seed_supplier.id, item, db, datetime.now(timezone.utc))
    await db.commit()

    ad = await db.get(ApprelDetails, product_id)
    assert ad is not None
    assert ad.pricing_method == "tiered_variant"


@pytest.mark.asyncio
async def test_persist_apparel_product_creates_variants_with_price_tiers(db, seed_supplier):
    item = ProductIngest(
        supplier_sku="PC54-VAR",
        product_name="Port & Company Tee With Tiers",
        product_type="apparel",
        variants=[
            VariantIngest(part_id="PC54-BLK-S", color="Black", size="S", sku="PC54-BLK-S"),
        ],
        price_tiers=[
            PriceTierIngest(price_type="Net", quantity_min=1, quantity_max=11, price="14.99"),
            PriceTierIngest(price_type="Net", quantity_min=12, quantity_max=None, price="11.99"),
        ],
    )
    product_id = await persist_product(seed_supplier.id, item, db, datetime.now(timezone.utc))
    await db.commit()

    variants = (
        await db.execute(
            select(ProductVariant).where(ProductVariant.product_id == product_id)
        )
    ).scalars().all()
    assert len(variants) == 1
    variant = variants[0]

    tiers = (
        await db.execute(
            select(VariantPrice).where(VariantPrice.variant_id == variant.id)
        )
    ).scalars().all()
    assert len(tiers) == 2
    assert {t.price_type for t in tiers} == {"Net"}
```

- [ ] **Step 2: Implement apparel path in `persistence.py`**

```python
from .models import ApprelDetails, ProductVariant, VariantPrice, ProductImage

async def _persist_apparel_path(product_id, item: ProductIngest, db: AsyncSession) -> None:
    # Upsert apparel_details (1:1 — PK = product_id)
    ad = item.apparel_details or ApparelDetailsIngest()
    stmt = (
        pg_insert(ApprelDetails)
        .values(product_id=product_id, pricing_method=ad.pricing_method, raw_payload=ad.raw_payload)
        .on_conflict_do_update(
            index_elements=["product_id"],
            set_={"pricing_method": ad.pricing_method, "raw_payload": ad.raw_payload},
        )
    )
    await db.execute(stmt)

    # Upsert variants + price tiers
    for v in item.variants:
        var_stmt = (
            pg_insert(ProductVariant)
            .values(
                product_id=product_id,
                color=v.color,
                size=v.size,
                sku=v.sku,
                base_price=v.base_price,
                inventory=v.inventory,
                warehouse=v.warehouse,
            )
            .on_conflict_do_update(
                index_elements=["product_id", "color", "size"],
                set_={
                    "sku": v.sku,
                    "base_price": v.base_price,
                    "inventory": v.inventory,
                    "warehouse": v.warehouse,
                },
            )
            .returning(ProductVariant.id)
        )
        variant_id = (await db.execute(var_stmt)).scalar_one()

        for tier in item.price_tiers:
            tier_stmt = (
                pg_insert(VariantPrice)
                .values(
                    variant_id=variant_id,
                    price_type=tier.price_type,
                    quantity_min=tier.quantity_min,
                    quantity_max=tier.quantity_max,
                    price=tier.price,
                )
                .on_conflict_do_update(
                    index_elements=["variant_id", "price_type", "quantity_min"],
                    set_={"quantity_max": tier.quantity_max, "price": tier.price},
                )
            )
            await db.execute(tier_stmt)

    # Upsert images
    for idx, img in enumerate(item.images):
        img_stmt = (
            pg_insert(ProductImage)
            .values(
                product_id=product_id,
                url=img.url,
                image_type=img.image_type,
                color=img.color,
                sort_order=img.sort_order or idx,
            )
            .on_conflict_do_update(
                index_elements=["product_id", "url"],
                set_={"image_type": img.image_type, "color": img.color, "sort_order": img.sort_order or idx},
            )
        )
        await db.execute(img_stmt)
```

Call from `persist_product`:
```python
elif item.product_type == "apparel":
    await _persist_apparel_path(product_id, item, db)
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_persist_product.py -k "apparel" -v
```

---

### Task 10: OPS decal fixture + fixture-driven persist test

**Files:**
- Create: `backend/tests/fixtures/ops_decals.json`
- Modify: `backend/tests/test_persist_product.py`

The VG OPS decal products are Decal (product_id 131) and Decal (product_id 262) from the supplier sample. Represent them as `ProductIngest`-compatible JSON.

- [ ] **Step 1: Create fixture file**

```json
[
  {
    "supplier_sku": "DECAL-131",
    "product_name": "Decal",
    "product_type": "print",
    "ops_product_id": "131",
    "print_details": {
      "pricing_method": "formula",
      "min_width": 1.0,
      "max_width": 24.0,
      "min_height": 1.0,
      "max_height": 18.0,
      "size_unit": "in"
    },
    "options": [
      {
        "option_key": "turnaround_time",
        "title": "Turnaround Time",
        "options_type": "radio",
        "sort_order": 1,
        "master_option_id": 51,
        "ops_option_id": 2205,
        "required": false,
        "attributes": [
          {"title": "Standard (5-7 Bus Days)", "sort_order": 0, "ops_attribute_id": 13461, "master_attribute_id": 286, "multiplier": "1.00"},
          {"title": "Rush (3-4 Bus Days)", "sort_order": 1, "ops_attribute_id": 13462, "master_attribute_id": 292, "multiplier": "1.25"}
        ]
      },
      {
        "option_key": "material",
        "title": "Material",
        "options_type": "radio",
        "sort_order": 2,
        "master_option_id": 52,
        "ops_option_id": 2206,
        "required": false,
        "attributes": [
          {"title": "White Vinyl", "sort_order": 0, "ops_attribute_id": 13463, "master_attribute_id": 293, "multiplier": "1.00"},
          {"title": "Clear Vinyl", "sort_order": 1, "ops_attribute_id": 13464, "master_attribute_id": 294, "multiplier": "1.15"}
        ]
      }
    ],
    "images": [],
    "variants": [],
    "sizes": [
      {"width": 2.0, "height": 2.0, "label": "2\"x2\""},
      {"width": 3.0, "height": 3.0, "label": "3\"x3\""},
      {"width": 4.0, "height": 4.0, "label": "4\"x4\""},
      {"width": 4.0, "height": 6.0, "label": "4\"x6\""}
    ]
  }
]
```

- [ ] **Step 2: Write fixture-driven test**

```python
import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_persist_ops_decal_fixture(db, seed_supplier):
    """Full round-trip: load OPS decal fixture → persist → assert DB state."""
    raw = json.loads((FIXTURE_DIR / "ops_decals.json").read_text())
    items = [ProductIngest(**p) for p in raw]

    now = datetime.now(timezone.utc)
    for item in items:
        pid = await persist_product(seed_supplier.id, item, db, now)
    await db.commit()

    # Verify print_details created
    from modules.catalog.models import PrintDetails, ProductOption, ProductSize
    pd = (
        await db.execute(
            select(PrintDetails).join(Product, PrintDetails.product_id == Product.id)
            .where(Product.supplier_sku == "DECAL-131")
        )
    ).scalars().first()
    assert pd is not None
    assert pd.pricing_method == "formula"

    # Verify sizes
    sizes = (
        await db.execute(
            select(ProductSize).where(ProductSize.product_id == pd.product_id)
        )
    ).scalars().all()
    assert len(sizes) == 4

    # Verify options
    options = (
        await db.execute(
            select(ProductOption).where(ProductOption.product_id == pd.product_id)
        )
    ).scalars().all()
    assert len(options) == 2
```

- [ ] **Step 3: Run fixture test**

```bash
python -m pytest tests/test_persist_product.py::test_persist_ops_decal_fixture -v
```

---

### Task 11: Refactor `ingest_products` to call `persist_product`

**Files:**
- Modify: `backend/modules/catalog/ingest.py`

The goal: `ingest_products` becomes a thin loop that calls `persist_product` per item. Move `_upsert_options` into `persistence.py` (already done in Task 8). Remove duplicate upsert blocks from `ingest.py`.

- [ ] **Step 1: Write regression test**

```python
# backend/tests/test_persist_product.py
@pytest.mark.asyncio
async def test_ingest_endpoint_still_works_after_refactor(client, seed_supplier):
    """POST /api/ingest/{id}/products returns 200 and creates product."""
    payload = [
        {
            "supplier_sku": "INGEST-TEST-01",
            "product_name": "Ingest Regression Test",
            "product_type": "print",
            "print_details": {"pricing_method": "formula"},
        }
    ]
    resp = await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        json=payload,
        headers={"X-Ingest-Secret": "test-secret-do-not-use-in-prod"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["records_processed"] == 1
```

- [ ] **Step 2: Refactor `ingest_products` in `ingest.py`**

Replace the inner for-loop body (product upsert + variants + images + options) with:

```python
from .persistence import persist_product

for item in batch:
    category_id = (
        ext_to_cat_id.get(item.category_external_id)
        if item.category_external_id
        else None
    )
    await persist_product(supplier.id, item, db, now, category_id=category_id)
```

Remove the now-unused imports for `ProductVariant`, `ProductImage` from ingest.py if they're only used in the deleted upsert block. Keep `Product` import for the category preload query.

- [ ] **Step 3: Run tests (all existing + new regression)**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

All tests that passed before must still pass.

---

### Task 12: Update `ProductRead` schema to include polymorphic detail fields

**Files:**
- Modify: `backend/modules/catalog/schemas.py`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_product_read_includes_print_details_field(client, seed_supplier):
    """GET /api/catalog/products/{id} returns print_details for print products."""
    # First persist a print product via the ingest endpoint
    payload = [{
        "supplier_sku": "READ-TEST-01",
        "product_name": "Read Test Decal",
        "product_type": "print",
        "print_details": {"min_width": "2", "max_width": "24", "min_height": "2", "max_height": "18"},
    }]
    ingest_resp = await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        json=payload,
        headers={"X-Ingest-Secret": "test-secret-do-not-use-in-prod"},
    )
    assert ingest_resp.status_code == 200

    # Find the product via list endpoint
    list_resp = await client.get(f"/api/catalog/products?supplier_id={seed_supplier.id}")
    assert list_resp.status_code == 200
    products = list_resp.json()
    assert len(products) > 0
```

- [ ] **Step 2: Add read schemas**

Add to `schemas.py`:

```python
class PrintDetailsRead(BaseModel):
    pricing_method: str
    min_width: Optional[Decimal] = None
    max_width: Optional[Decimal] = None
    min_height: Optional[Decimal] = None
    max_height: Optional[Decimal] = None
    size_unit: str = "in"
    base_price_per_sq_unit: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class ApparelDetailsRead(BaseModel):
    pricing_method: str

    model_config = {"from_attributes": True}


class ProductSizeRead(BaseModel):
    id: UUID
    width: Decimal
    height: Decimal
    unit: str
    label: Optional[str] = None

    model_config = {"from_attributes": True}


class VariantPriceRead(BaseModel):
    id: UUID
    price_type: str
    quantity_min: int
    quantity_max: Optional[int] = None
    price: Decimal

    model_config = {"from_attributes": True}
```

Extend `ProductRead`:
```python
class ProductRead(BaseModel):
    # ... existing fields ...
    print_details: Optional[PrintDetailsRead] = None
    apparel_details: Optional[ApparelDetailsRead] = None
    sizes: list[ProductSizeRead] = []

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Run test**

```bash
python -m pytest tests/test_persist_product.py -k "product_read" -v
```

---

### Task 13: Update product query routes to eager-load new relationships

**Files:**
- Modify: `backend/modules/catalog/routes.py`

Product detail and list routes must eager-load `print_details`, `apparel_details`, `sizes` when returning `ProductRead`.

- [ ] **Step 1: Find product detail route**

```bash
grep -n "get_product\|products/{" backend/modules/catalog/routes.py | head -20
```

- [ ] **Step 2: Add `selectinload` for new relationships**

Wherever `Product` is queried for detail view, add:

```python
from sqlalchemy.orm import selectinload

query = (
    select(Product)
    .options(
        selectinload(Product.variants),
        selectinload(Product.images),
        selectinload(Product.options).selectinload(ProductOption.attributes),
        selectinload(Product.print_details),
        selectinload(Product.apparel_details),
        selectinload(Product.sizes),
    )
    .where(Product.id == product_id)
)
```

- [ ] **Step 3: Run existing catalog route tests**

```bash
python -m pytest tests/ -k "catalog or product" -v --tb=short
```

---

### Task 14: Wire all new models in `main.py` + run full test suite

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Verify new model classes are reachable via `modules.catalog.models`**

`main.py` already has `import modules.catalog.models`. Verify by checking that all new classes (`ApprelDetails`, `PrintDetails`, `VariantPrice`, `ProductSize`) are defined in that file and will be picked up by `Base.metadata.create_all`.

- [ ] **Step 2: Verify `_SCHEMA_UPGRADES` has all new entries**

Check that these are present (added in Tasks 3 and 4):
```python
"ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS adapter_class VARCHAR(64)",
"ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS last_full_sync TIMESTAMP WITH TIME ZONE",
"ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS last_delta_sync TIMESTAMP WITH TIME ZONE",
"ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS errors JSONB",
```

- [ ] **Step 3: Run full test suite**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -v --tb=short 2>&1 | tail -50
```

All pre-existing tests must pass. Zero regressions allowed.

- [ ] **Step 4: Start the backend and verify no startup errors**

```bash
uvicorn main:app --port 8001 --timeout-graceful-shutdown 1 &
sleep 3
curl -s http://localhost:8001/api/suppliers | python3 -m json.tool | head -10
kill %1
```

---

### Task 15: Backfill script for existing VG OPS print products

**Files:**
- Create: `backend/scripts/backfill_product_types.py`

Existing products in the database (synced before this phase) have no `print_details` or `apparel_details` rows. This script creates the missing rows.

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""One-shot backfill: create print_details rows for existing print products.

Run once after deploying Phase 1:
    cd backend && source .venv/bin/activate
    python scripts/backfill_product_types.py
"""
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database import async_session
from modules.catalog.models import ApprelDetails, PrintDetails, Product


async def backfill():
    async with async_session() as db:
        products = (
            await db.execute(select(Product))
        ).scalars().all()

        print_count = 0
        apparel_count = 0
        for p in products:
            if p.product_type == "print":
                stmt = (
                    pg_insert(PrintDetails)
                    .values(product_id=p.id, pricing_method="formula")
                    .on_conflict_do_nothing(index_elements=["product_id"])
                )
                await db.execute(stmt)
                print_count += 1
            else:
                stmt = (
                    pg_insert(ApprelDetails)
                    .values(product_id=p.id, pricing_method="tiered_variant")
                    .on_conflict_do_nothing(index_elements=["product_id"])
                )
                await db.execute(stmt)
                apparel_count += 1

        await db.commit()
        print(f"Backfilled: {print_count} print_details, {apparel_count} apparel_details")


if __name__ == "__main__":
    asyncio.run(backfill())
```

- [ ] **Step 2: Verify the script is importable**

```bash
cd backend && source .venv/bin/activate && python -c "import scripts.backfill_product_types; print('OK')"
```

---

### Task 16: Final integration test — HTTP round-trip for both product types

**Files:**
- Modify: `backend/tests/test_persist_product.py`

- [ ] **Step 1: Write end-to-end HTTP tests**

```python
@pytest.mark.asyncio
async def test_http_ingest_print_product_end_to_end(client, db, seed_supplier):
    """Full HTTP ingest → DB verification for a print product."""
    payload = [{
        "supplier_sku": "E2E-PRINT-01",
        "product_name": "E2E Print Decal",
        "product_type": "print",
        "print_details": {
            "min_width": "2.0",
            "max_width": "24.0",
            "min_height": "2.0",
            "max_height": "18.0",
            "base_price_per_sq_unit": "0.10",
        },
        "sizes": [
            {"width": "4", "height": "4", "label": "4x4"},
            {"width": "6", "height": "9", "label": "6x9"},
        ],
        "options": [],
        "variants": [],
        "images": [],
    }]
    resp = await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        json=payload,
        headers={"X-Ingest-Secret": "test-secret-do-not-use-in-prod"},
    )
    assert resp.status_code == 200
    assert resp.json()["records_processed"] == 1

    from modules.catalog.models import PrintDetails, ProductSize
    pd = (
        await db.execute(
            select(PrintDetails)
            .join(Product, PrintDetails.product_id == Product.id)
            .where(Product.supplier_sku == "E2E-PRINT-01")
        )
    ).scalars().first()
    assert pd is not None
    assert float(pd.base_price_per_sq_unit) == 0.10

    sizes = (
        await db.execute(select(ProductSize).where(ProductSize.product_id == pd.product_id))
    ).scalars().all()
    assert len(sizes) == 2


@pytest.mark.asyncio
async def test_http_ingest_apparel_product_end_to_end(client, db, seed_supplier):
    """Full HTTP ingest → DB verification for an apparel product."""
    payload = [{
        "supplier_sku": "E2E-APP-01",
        "product_name": "E2E Port & Co Tee",
        "product_type": "apparel",
        "variants": [
            {"part_id": "PC54-BLK-M", "color": "Black", "size": "M", "sku": "PC54-BLK-M", "base_price": "14.99"},
            {"part_id": "PC54-WHT-M", "color": "White", "size": "M", "sku": "PC54-WHT-M", "base_price": "14.99"},
        ],
        "price_tiers": [
            {"price_type": "Net", "quantity_min": 1, "quantity_max": 11, "price": "14.99"},
            {"price_type": "Net", "quantity_min": 12, "price": "11.49"},
        ],
        "images": [],
        "options": [],
    }]
    resp = await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        json=payload,
        headers={"X-Ingest-Secret": "test-secret-do-not-use-in-prod"},
    )
    assert resp.status_code == 200
    assert resp.json()["records_processed"] == 1

    from modules.catalog.models import ApprelDetails, ProductVariant, VariantPrice
    ad = (
        await db.execute(
            select(ApprelDetails)
            .join(Product, ApprelDetails.product_id == Product.id)
            .where(Product.supplier_sku == "E2E-APP-01")
        )
    ).scalars().first()
    assert ad is not None

    variants = (
        await db.execute(
            select(ProductVariant).where(ProductVariant.product_id == ad.product_id)
        )
    ).scalars().all()
    assert len(variants) == 2

    # Each variant should have 2 price tiers
    for v in variants:
        tiers = (
            await db.execute(select(VariantPrice).where(VariantPrice.variant_id == v.id))
        ).scalars().all()
        assert len(tiers) == 2
```

- [ ] **Step 2: Run full suite one final time**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -60
```

Zero failures. Commit.

- [ ] **Step 3: Commit all Phase 1 work**

```bash
git add backend/modules/catalog/models.py \
        backend/modules/catalog/schemas.py \
        backend/modules/catalog/ingest.py \
        backend/modules/catalog/persistence.py \
        backend/modules/suppliers/models.py \
        backend/modules/sync_jobs/models.py \
        backend/main.py \
        backend/tests/test_persist_product.py \
        backend/tests/fixtures/ops_decals.json \
        backend/scripts/backfill_product_types.py

git commit -m "feat(catalog): polymorphic product model foundation (Phase 1)"
```

---

## Phase 1 completion criteria

- [ ] `apparel_details`, `print_details`, `variant_prices`, `product_sizes` tables exist and auto-create via `Base.metadata.create_all`
- [ ] `suppliers` table has `adapter_class`, `last_full_sync`, `last_delta_sync` columns
- [ ] `sync_jobs` table has `errors JSONB` column
- [ ] `ProductIngest` schema accepts `print_details` / `apparel_details` / `sizes` / `price_tiers` fields
- [ ] `model_validator` on `ProductIngest` enforces: print products must have `print_details`, apparel products auto-get default `apparel_details`
- [ ] `persist_product(supplier_id, item, db, now)` exists in `modules/catalog/persistence.py`
- [ ] Print path: upserts `print_details` + `product_sizes` + `product_options` + `product_option_attributes`
- [ ] Apparel path: upserts `apparel_details` + `product_variants` + `variant_prices` + `product_images`
- [ ] `ingest_products` HTTP endpoint delegates to `persist_product` (no duplicate upsert logic)
- [ ] OPS decal fixture test passes end-to-end
- [ ] All pre-existing tests still pass (zero regressions)
- [ ] Backfill script runs without error

**Next plan:** `2026-04-29-phase2-ops-adapter.md` — builds `OPSAdapter` that calls `persist_product` for live VG OPS products.
