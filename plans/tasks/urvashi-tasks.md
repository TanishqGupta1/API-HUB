# Urvashi — Sprint Tasks

**Total: 5 tasks** | Branch: `urvashi-sprint-v1`

---

## Task 0.1: Fix PostgreSQL Port Mismatch

**Priority:** Do this FIRST — backend is broken without it.
**File:** `api-hub/docker-compose.yml` line 9

### Problem
PR #3 changed the host port from `5432` to `5434`. But `.env` has `POSTGRES_URL=...localhost:5432/vg_hub`. The backend can't connect to PostgreSQL.

### Steps

- [ ] **Step 1:** Open `docker-compose.yml` and find the postgres ports line:
```yaml
    ports:
      - "5434:5432"
```

Change to:
```yaml
    ports:
      - "5432:5432"
```

- [ ] **Step 2:** If postgres is running, recreate it:
```bash
docker compose down
docker compose up -d postgres
```

- [ ] **Step 3:** Verify the backend can connect:
```bash
cd backend && source .venv/bin/activate
python -c "
import asyncio
from database import engine
async def test():
    async with engine.begin() as conn:
        result = await conn.execute(text('SELECT 1'))
        print('DB connected OK')
from sqlalchemy import text
asyncio.run(test())
"
```

- [ ] **Step 4:** Commit
```bash
git add docker-compose.yml
git commit -m "fix: revert PostgreSQL port to 5432 — matches .env POSTGRES_URL"
```

---

## Task 0.2: Fix load_dotenv Path

**Priority:** Right after Task 0.1
**Files:**
- `backend/database.py` line 7
- `backend/seed_demo.py` line 8

### Problem
Both files call `load_dotenv(Path(__file__).parent / ".env")` which points to `backend/.env` — a file that doesn't exist. The actual `.env` is at the repo root (`api-hub/.env`).

### Steps

- [ ] **Step 1:** Open `backend/database.py`. Find line 7:
```python
load_dotenv(Path(__file__).parent / ".env")
```

Change to:
```python
load_dotenv(Path(__file__).parent.parent / ".env")
```

`parent.parent` goes from `backend/` up to `api-hub/` where `.env` lives.

- [ ] **Step 2:** Open `backend/seed_demo.py`. Find line 8:
```python
load_dotenv(Path(__file__).parent / ".env")
```

Change to:
```python
load_dotenv(Path(__file__).parent.parent / ".env")
```

- [ ] **Step 3:** Verify SECRET_KEY is now loaded:
```bash
cd backend && source .venv/bin/activate
python -c "
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / '.env')
print(f'SECRET_KEY loaded: {bool(os.getenv(\"SECRET_KEY\"))}')
print(f'POSTGRES_URL: {os.getenv(\"POSTGRES_URL\", \"NOT SET\")}')
"
```
Expected: `SECRET_KEY loaded: True`

- [ ] **Step 4:** Commit
```bash
git add backend/database.py backend/seed_demo.py
git commit -m "fix: correct load_dotenv path to repo root .env"
```

---

## Task 22: Wire Dashboard to Real API

**Priority:** After Tasks 0.1 + 0.2
**File:** `frontend/src/app/page.tsx`

### Problem
Dashboard shows hardcoded demo data (4 vendors, 32.4k SKUs, 187k variants, 98% uptime). The backend has a working `/api/stats` endpoint that returns real counts.

### Steps

- [ ] **Step 1:** Open `frontend/src/app/page.tsx`. Find the hardcoded stat values.

- [ ] **Step 2:** Add API fetch. At the top of the component, add:
```tsx
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Stats } from "@/lib/types";
```

Add state + fetch:
```tsx
const [stats, setStats] = useState<Stats | null>(null);

useEffect(() => {
  api<Stats>("/api/stats").then(setStats).catch(console.error);
}, []);
```

- [ ] **Step 3:** Replace hardcoded stat card values:
- "Vendors" card value: `stats?.suppliers ?? 0`
- "SKUs Indexed" card value: `stats?.products ?? 0`
- "Total Variants" card value: `stats?.variants ?? 0`
- Keep "System Health" as static for now (no backend endpoint for this yet)

- [ ] **Step 4:** Wire the activity table to real sync jobs. Add:
```tsx
const [recentJobs, setRecentJobs] = useState<SyncJob[]>([]);

useEffect(() => {
  api<SyncJob[]>("/api/sync-jobs?limit=5").then(setRecentJobs).catch(console.error);
}, []);
```

Replace the hardcoded table rows with a map over `recentJobs`.

- [ ] **Step 5:** Verify by running both backend and frontend:
```bash
# Terminal 1:
cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000

# Terminal 2:
cd frontend && npm run dev
```
Open http://localhost:3000 — stat cards should show real numbers (may be 0 if DB is empty, that's OK — run `python seed_demo.py` to add demo data).

- [ ] **Step 6:** Commit
```bash
git add frontend/src/app/page.tsx
git commit -m "feat: wire dashboard to real /api/stats and /api/sync-jobs endpoints"
```

---

## Task 1: Schema Updates — Unique Constraints + New Columns + ProductImage

**Priority:** After V0 fixes. Can start in parallel with Sinchana's Task 2 and Vidhi's Task 3.
**Files:**
- Modify: `backend/modules/catalog/models.py`
- Modify: `backend/modules/catalog/schemas.py`

### What this does
Adds unique constraints so sync operations can use `ON CONFLICT DO UPDATE` (upserts) instead of creating duplicate products. Also adds `category`, `ops_product_id`, and a new `ProductImage` table.

### Steps

- [ ] **Step 1:** Open `backend/modules/catalog/models.py`. Replace the entire file with:

```python
from typing import Optional
import uuid as uuid_mod
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("supplier_id", "supplier_sku", name="uq_product_supplier_sku"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    supplier_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("suppliers.id"))
    supplier_sku: Mapped[str] = mapped_column(String(255))
    product_name: Mapped[str] = mapped_column(String(500))
    brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    product_type: Mapped[str] = mapped_column(String(50), default="apparel")
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ops_product_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_synced: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("product_id", "color", "size", name="uq_variant_product_color_size"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    color: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    base_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    inventory: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="variants")


class ProductImage(Base):
    __tablename__ = "product_images"
    __table_args__ = (
        UniqueConstraint("product_id", "url", name="uq_product_image_url"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    url: Mapped[str] = mapped_column(Text)
    image_type: Mapped[str] = mapped_column(String(50), default="front")
    color: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped["Product"] = relationship(back_populates="images")
```

- [ ] **Step 2:** Open `backend/modules/catalog/schemas.py`. Replace the entire file with:

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class VariantRead(BaseModel):
    id: UUID
    color: str | None
    size: str | None
    sku: str | None
    base_price: float | None
    inventory: int | None
    warehouse: str | None

    model_config = {"from_attributes": True}


class ProductImageRead(BaseModel):
    id: UUID
    url: str
    image_type: str
    color: str | None
    sort_order: int

    model_config = {"from_attributes": True}


class ProductRead(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str | None = None
    supplier_sku: str
    product_name: str
    brand: str | None
    category: str | None
    description: str | None
    product_type: str
    image_url: str | None
    ops_product_id: str | None
    last_synced: datetime | None
    variants: list[VariantRead] = []
    images: list[ProductImageRead] = []

    model_config = {"from_attributes": True}


class ProductListRead(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str | None = None
    supplier_sku: str
    product_name: str
    brand: str | None
    category: str | None
    product_type: str
    image_url: str | None
    variant_count: int = 0

    model_config = {"from_attributes": True}
```

- [ ] **Step 3:** Drop and recreate tables (new constraints need fresh tables):
```bash
docker exec api-hub-postgres-1 psql -U vg_user -d vg_hub -c "
DROP TABLE IF EXISTS product_push_log CASCADE;
DROP TABLE IF EXISTS product_variants CASCADE;
DROP TABLE IF EXISTS product_images CASCADE;
DROP TABLE IF EXISTS products CASCADE;
"
```

- [ ] **Step 4:** Restart backend (tables auto-recreate on startup):
```bash
cd backend && source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

- [ ] **Step 5:** Re-seed demo data:
```bash
python seed_demo.py
```

- [ ] **Step 6:** Verify constraints exist:
```bash
docker exec api-hub-postgres-1 psql -U vg_user -d vg_hub -c "\d products"
# Should show: uq_product_supplier_sku UNIQUE constraint

docker exec api-hub-postgres-1 psql -U vg_user -d vg_hub -c "\d product_variants"
# Should show: uq_variant_product_color_size UNIQUE constraint

docker exec api-hub-postgres-1 psql -U vg_user -d vg_hub -c "\d product_images"
# Should show: uq_product_image_url UNIQUE constraint
```

- [ ] **Step 7:** Commit
```bash
git add backend/modules/catalog/models.py backend/modules/catalog/schemas.py
git commit -m "feat: add unique constraints for upserts, category, ops_product_id, ProductImage model"
```

---

## Task 5: Sync Trigger Endpoints

**Priority:** After Task 1 is merged AND Sinchana's Task 2 AND Vidhi's Task 3 are merged AND Tanishq's Task 4 (normalizer) is done.
**Files:**
- Create: `backend/modules/promostandards/routes.py`
- Modify: `backend/main.py` — add one import + one `include_router` call

### What this does
Creates FastAPI endpoints that n8n (or curl) calls to trigger product syncs. Each endpoint returns immediately with a job ID (HTTP 202). The actual SOAP work runs in the background.

### Steps

- [ ] **Step 1:** Create `backend/modules/promostandards/routes.py`:

```python
"""Sync trigger endpoints — n8n calls these via HTTP Request node."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session, get_db
from modules.suppliers.models import Supplier
from modules.suppliers.service import get_cached_endpoints
from modules.sync_jobs.models import SyncJob

from .client import PromoStandardsClient
from .normalizer import upsert_products, update_inventory_only
from .resolver import resolve_wsdl_url

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/{supplier_id}/products", status_code=202)
async def trigger_product_sync(
    supplier_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a full product sync. Returns immediately with job ID."""
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    if not supplier.promostandards_code:
        raise HTTPException(400, "Supplier has no PromoStandards code")

    endpoints = await get_cached_endpoints(db, supplier_id)
    if not endpoints:
        raise HTTPException(400, "No endpoints found for this supplier")

    product_wsdl = resolve_wsdl_url(endpoints, "product_data")
    if not product_wsdl:
        raise HTTPException(400, "No Product Data WSDL found")

    job = SyncJob(
        supplier_id=supplier_id,
        supplier_name=supplier.name,
        job_type="full_sync",
        status="running",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(
        _run_product_sync, supplier_id, job.id, supplier.auth_config, endpoints
    )
    return {"job_id": str(job.id), "status": "running"}


@router.post("/{supplier_id}/inventory", status_code=202)
async def trigger_inventory_sync(
    supplier_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger inventory-only sync. Returns immediately with job ID."""
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, "Supplier not found")

    endpoints = await get_cached_endpoints(db, supplier_id)
    inv_wsdl = resolve_wsdl_url(endpoints, "inventory")
    if not inv_wsdl:
        raise HTTPException(400, "No Inventory WSDL found")

    job = SyncJob(
        supplier_id=supplier_id,
        supplier_name=supplier.name,
        job_type="inventory",
        status="running",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(
        _run_inventory_sync, supplier_id, job.id, supplier.auth_config, endpoints
    )
    return {"job_id": str(job.id), "status": "running"}


@router.get("/{supplier_id}/status")
async def get_sync_status(supplier_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get the latest sync job for a supplier."""
    result = await db.execute(
        select(SyncJob)
        .where(SyncJob.supplier_id == supplier_id)
        .order_by(SyncJob.started_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if not job:
        return {"status": "never_synced"}
    return {
        "job_id": str(job.id),
        "status": job.status,
        "job_type": job.job_type,
        "records_processed": job.records_processed,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "error_log": job.error_log,
    }


async def _run_product_sync(
    supplier_id: UUID, job_id: UUID, auth_config: dict, endpoints: list[dict]
):
    """Background task: full product sync via SOAP."""
    async with async_session() as db:
        job = await db.get(SyncJob, job_id)
        try:
            product_wsdl = resolve_wsdl_url(endpoints, "product_data")
            client = PromoStandardsClient(product_wsdl, auth_config)

            product_ids = await client.get_sellable_product_ids()
            if not product_ids:
                job.status = "completed"
                job.records_processed = 0
                job.finished_at = datetime.now(timezone.utc)
                await db.commit()
                return

            products = await client.get_products_batch(product_ids)

            inventory = []
            inv_wsdl = resolve_wsdl_url(endpoints, "inventory")
            if inv_wsdl:
                inv_client = PromoStandardsClient(inv_wsdl, auth_config)
                inventory = await inv_client.get_inventory(product_ids)

            count = await upsert_products(db, supplier_id, products, inventory)

            job.status = "completed"
            job.records_processed = count
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as e:
            job.status = "failed"
            job.error_log = str(e)[:2000]
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()


async def _run_inventory_sync(
    supplier_id: UUID, job_id: UUID, auth_config: dict, endpoints: list[dict]
):
    """Background task: inventory-only sync."""
    async with async_session() as db:
        job = await db.get(SyncJob, job_id)
        try:
            inv_wsdl = resolve_wsdl_url(endpoints, "inventory")
            client = PromoStandardsClient(inv_wsdl, auth_config)

            from modules.catalog.models import Product
            result = await db.execute(
                select(Product.supplier_sku).where(Product.supplier_id == supplier_id)
            )
            product_ids = [row[0] for row in result.all()]

            if not product_ids:
                job.status = "completed"
                job.records_processed = 0
                job.finished_at = datetime.now(timezone.utc)
                await db.commit()
                return

            inventory = await client.get_inventory(product_ids)
            count = await update_inventory_only(db, supplier_id, inventory)

            job.status = "completed"
            job.records_processed = count
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as e:
            job.status = "failed"
            job.error_log = str(e)[:2000]
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
```

- [ ] **Step 2:** Open `backend/main.py`. Add import and router registration:

Add with the other imports:
```python
from modules.promostandards.routes import router as sync_router
```

Add with the other `app.include_router()` calls:
```python
app.include_router(sync_router)
```

- [ ] **Step 3:** Verify the backend starts without errors:
```bash
cd backend && source .venv/bin/activate
uvicorn main:app --reload --port 8000
```
Check http://localhost:8000/docs — you should see the sync endpoints listed.

- [ ] **Step 4:** Commit
```bash
git add backend/modules/promostandards/routes.py backend/main.py
git commit -m "feat: sync trigger endpoints — POST /api/sync/{supplier_id}/products + /inventory"
```
