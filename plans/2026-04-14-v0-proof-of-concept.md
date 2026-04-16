# API-HUB — Master Plan

## Vision

VisualGraphx Integration Hub — pulls product catalogs from 994+ PromoStandards suppliers and pushes them into OnPrintShop (OPS) storefronts. Eliminates $3K/year per customer API fees. Future: SaaS product, MedusaJS replaces OPS.

## Final Architecture

```
┌─────────────────┐       ┌──────────────────────────┐
│  Next.js UI     │◀─────▶│  FastAPI Backend          │
│  shadcn/ui      │       │  (Modular Monolith)       │
│  Tailwind CSS   │       │                            │
│  All config +   │       │  /api/suppliers   (CRUD)   │
│  credentials    │       │  /api/products    (browse) │
│  via UI         │       │  /api/normalize   (ingest) │
└─────────────────┘       │  /api/push        (to OPS) │
                          └─────────────┬──────────────┘
                                        │
                          ┌─────────────┴──────────────┐
                          │  PostgreSQL 16   Redis 7    │
                          └─────────────┬──────────────┘
                                        │
┌───────────────────────────────────────┴───────────────┐
│  n8n + Custom PromoStandards Node (TypeScript)        │
│  One node → 994 suppliers (node-soap, auto-discovery) │
│  Cron workflows: inventory/pricing/delta/full/images  │
└───────────────────────────────────────────────────────┘
```

## Key Decisions
- **n8n IS the data pipeline** — custom PS node fetches via SOAP, not a Python service
- **All credentials via UI** — stored in DB with **Fernet Encryption**, no .env files
- **Modular Monolith** for V1 — clean separation of concerns from day one
- **VARCHAR** for all type columns — no PG ENUMs
- **Endpoint Caching** — cache PS directory responses to avoid rate limits

## Build Phases

| Phase | What | Status |
|-------|------|--------|
| **V0** | Proof of concept — PS directory to browser | **START HERE** |
| **V1a** | n8n custom PromoStandards node (TypeScript + node-soap) | After V0 |
| **V1b** | Normalization + full product catalog UI + data source indicators | After V1a |
| **V1c** | OPS push + markup rules + dashboard (via `n8n-nodes-onprintshop`) | After V1b |
| **V1d** | Field mapping UI for non-PS suppliers (4Over) | After V1c |

## Database (8 tables, all VARCHAR types)

| Table | Purpose |
|-------|---------|
| `suppliers` | Dynamic config — protocol, auth_config (Encrypted), endpoint_cache (JSONB) |
| `products` | Canonical product data |
| `product_variants` | Color/size/option combos with pricing + inventory |
| `product_images` | URLs with type (front, back, swatch, detail) |
| `customers` | OPS instance configs |
| `markup_rules` | Per-customer pricing rules |
| `sync_jobs` | Job tracking |
| `product_push_log` | OPS push audit trail |

---
---

# Task Dependency Map

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Task Status

> Last updated: 2026-04-16. Reflects merged PRs #1 (Urvashi), #2 (Sinchana), #3 (Vidhi) + Vidhi Tasks 15, 16 frontend completed.

| Task | Description | Status | Done By | Files |
|------|-------------|--------|---------|-------|
| 1 | Project Setup | ✅ DONE | — | `.env`, `.gitignore`, `docker-compose.yml`, `backend/Dockerfile`, `backend/requirements.txt` |
| 2 | Database + EncryptedJSON | ✅ DONE | — | `backend/database.py` |
| 3 | Supplier Model + Schemas | ✅ DONE | — | `backend/modules/suppliers/models.py`, `schemas.py` |
| 4 | Product + Variant Models | ✅ DONE | — | `backend/modules/catalog/models.py`, `schemas.py` |
| 5 | PS Directory Client + Supplier Service | ✅ DONE | — | `backend/modules/ps_directory/client.py`, `schemas.py`, `backend/modules/suppliers/service.py` |
| 6 | API Routes (suppliers, ps_directory, catalog) | ✅ DONE | PR #1 Urvashi | `suppliers/routes.py`, `ps_directory/routes.py`, `catalog/routes.py` |
| 7 | FastAPI Main App | ✅ DONE | PR #1 Urvashi | `backend/main.py` — all 6 routers registered, `/health`, `/api/stats` |
| 8 | Demo Seed Script | ✅ DONE | PR #1 Urvashi | `backend/seed_demo.py` — 3 suppliers, 3 products, variants |
| 9 | Next.js Scaffold + Blueprint Layout | ✅ DONE | PR #2 Sinchana | `frontend/` — layout, globals.css, dashboard page, Sidebar, api.ts, types.ts |
| 10 | Suppliers Page + Reveal Form | ✅ DONE | PR #4 Sinchana | `frontend/src/app/suppliers/page.tsx`, `components/suppliers/reveal-form.tsx` |
| 11 | Products Page (catalog grid) | ✅ DONE | PR #4 Sinchana | `frontend/src/app/products/page.tsx`, `components/products/product-card.tsx` |
| 12 | Product Detail Page | ✅ DONE | PR #4 Sinchana | `frontend/src/app/products/[id]/page.tsx` |
| 13 | Customers Page | ⬜ TODO | — | `frontend/src/app/customers/page.tsx` |
| 14 | Workflows Page (pipeline visualizer) | ⬜ TODO | — | `frontend/src/app/workflows/page.tsx`, `components/workflows/pipeline-view.tsx` |
| 15 | Sync Jobs Page | ✅ DONE | Vidhi | `frontend/src/app/sync/page.tsx` |
| 16 | Field Mapping Page | ✅ DONE | Vidhi | `frontend/src/app/mappings/page.tsx` (supplier picker) + `mappings/[supplierId]/page.tsx` (editor + live JSON preview), `PUT /api/suppliers/{id}/mappings` backend endpoint |
| 17 | End-to-End Verification | ⬜ TODO | — | No files — manual testing |
| 18 | Customer Model (OAuth2) | ✅ DONE | PR #3 Vidhi | `backend/modules/customers/` — models, schemas, routes |
| 19 | Markup Rules | ✅ DONE | PR #3 Vidhi | `backend/modules/markup/` — models, schemas, routes |
| 20 | Push Log | ✅ DONE | PR #3 Vidhi | `backend/modules/push_log/` — models, schemas, routes |
| 21 | n8n OPS Push Workflow | ⬜ TODO | — | `n8n-workflows/ops-push.json` |
| 22 | API Registry | ✅ DONE | PR #6 Sinchana | `frontend/src/app/api-registry/page.tsx` |

**Summary: 19 tasks DONE, 4 tasks TODO.** Backend complete. Frontend pages 10, 11, 12 (Sinchana), 15, 16 (Vidhi), 22 (Antigravity) done. Remaining: Task 13 (Customers page), 14 (Workflows page), 17 (E2E verification), 21 (n8n workflow).

---

## Execution Order

Tasks are grouped into phases. Within each phase, all tasks are **independent** and can be built in parallel by separate agents. Phases must be completed in order — do not start a phase until ALL tasks in the previous phase are done.

---

### Phases 0-3 — ✅ ALL DONE

| Phase | Tasks | Status |
|-------|-------|--------|
| 0 — Foundation | Task 1 (setup), Task 2 (database) | ✅ DONE |
| 1 — Models + Scaffold | Task 3 (supplier), Task 4 (product), Task 9 (Next.js), Task 18 (customer) | ✅ DONE |
| 2 — Services + V1c Models | Task 5 (PS client), Task 19 (markup), Task 20 (push log) | ✅ DONE |
| 3 — Routes + App Assembly | Task 6 (routes), Task 7 (main.py), Task 8 (seed) | ✅ DONE |

**Completed by:** PR #1 Urvashi (Tasks 6-8), PR #2 Sinchana (Task 9), PR #3 Vidhi (Tasks 18-20)

---

### Phase 4 — Frontend Pages (7 parallel tracks) ← START HERE

All prerequisites are met: backend API is running (Task 7 ✅) and frontend scaffold exists (Task 9 ✅). All 7 pages are independent — can dispatch 7 agents in parallel:

| Track | Task | API Dependency | Notes |
|-------|------|---------------|-------|
| A | **Task 10:** Suppliers Page + Reveal Form | `/api/suppliers`, `/api/ps-directory` | Most complex — progressive reveal 5-section form |
| B | **Task 11:** Products Page (catalog grid) | `/api/products` | Search + filter + supplier badges |
| C | **Task 12:** Product Detail Page | `/api/products/{id}` | Variant table + data source badges |
| D | **Task 13:** Customers Page | `/api/customers` | Simple list + inline add form |
| E | **Task 14:** Workflows Page | None (mostly static) | Pipeline visualizer — barely needs API |
| F | **Task 15:** Sync Jobs Page | `/api/sync-jobs` | Filterable table + expandable error log |
| G | **Task 16:** Field Mapping Page | `/api/suppliers/{id}` | Visual source→target mapping editor |

---

### Phase 5 — Verification + n8n

```
Task 17: End-to-End Verification    →  requires ALL of Tasks 10-16
Task 21: n8n OPS Push Workflow      →  requires n8n-nodes-onprintshop setProduct + setProductPrice
```

Task 21 has an **external dependency**: `n8n-nodes-onprintshop` must have `setProduct` and `setProductPrice` mutations (tracked in `OPS-NODE-GAP-ANALYSIS.md`).

---

## Dependency Graph

```
                    ✅ Task 1: Project Setup
                              │
                    ✅ Task 2: Database + EncryptedJSON
                       ╱      │      ╲            ╲
              ✅ Task 3   ✅ Task 4   ✅ Task 9    ✅ Task 18
              Supplier     Product    Next.js      Customer
              Model        Model      Scaffold     Model
                   │         │         │          ╱      ╲
              ✅ Task 5      │         │     ✅ Task 19  ✅ Task 20
              PS Client      │         │     Markup      Push Log
                   ╲         │         │
                  ✅ Task 6: API Routes │
                        │              │
                  ✅ Task 7: Main App   │
                     ╱     │           │
              ✅ Task 8    │           │
              Seed         │           │
                           ╰─────┬─────╯
                                 │
                    ┌────────────┼────────────┐
                    │            │             │
              ⬜ Tasks 10-11  ⬜ Tasks 12-13  ⬜ Tasks 14-16
              Suppliers       Product         Workflows
              Products        Customers       Sync/Mappings
                    │            │             │
                    └────────────┼─────────────┘
                                 │
                        ⬜ Task 17: E2E Verify
                        ⬜ Task 21: n8n Workflow
```

`✅` = Done  `⬜` = Todo

---

## Parallelization Summary

| Phase | Tasks | Parallel Agents | Status |
|-------|-------|----------------|--------|
| 0 | 1, 2 | — | ✅ DONE |
| 1 | 3, 4, 9, 18 | — | ✅ DONE |
| 2 | 5, 19, 20 | — | ✅ DONE |
| 3 | 6, 7, 8 | — | ✅ DONE |
| 4 | **10**, **11**, **12**, **13**, **14**, **15**, **16** | 7 | ⬜ **START HERE** |
| 5 | **17**, **21** | 2 | ⬜ Blocked on ALL above |

**Critical path:** Task 18 → Task 19/20 → Task 6 → Task 7 → Task 8 → Tasks 10-16 → Task 17

**Biggest parallelization win:** Phase 4 — all 7 frontend pages are independent of each other.

---
---

# V0: Proof of Concept — PromoStandards to Browser

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Call the PromoStandards directory API, store supplier config via UI with encryption, display 994 suppliers in a searchable dropdown — end-to-end in one session.

**Architecture:** Modular FastAPI backend + Next.js frontend + PostgreSQL. n8n custom node comes after this works. No microservices, no Redis — just prove the pipeline works securely.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, asyncpg, zeep, cryptography (Fernet), PostgreSQL 16, Next.js, shadcn/ui, Tailwind, Docker Compose

---

## File Structure

```
api-hub/
  .gitignore
  .env
  docker-compose.yml
  backend/
    main.py                          # FastAPI app — imports all routers
    database.py                      # Engine + EncryptedJSON type decorator
    requirements.txt
    Dockerfile
    modules/
      __init__.py
      suppliers/
        __init__.py
        models.py                    # Supplier model (EncryptedJSON auth_config)
        schemas.py                   # SupplierCreate, SupplierRead
        routes.py                    # APIRouter — CRUD + test connection
        service.py                   # Endpoint caching logic
      ps_directory/
        __init__.py
        client.py                    # PromoStandards directory API (httpx)
        schemas.py                   # PSCompany, PSEndpoint
        routes.py                    # APIRouter — list companies, list endpoints
      catalog/
        __init__.py
        models.py                    # Product, ProductVariant
        schemas.py                   # ProductRead, ProductListRead, VariantRead
        routes.py                    # APIRouter — search/filter/detail
    seed_demo.py                     # Demo seed script
  frontend/
    src/
      app/
        layout.tsx                       # Blueprint layout — Outfit + Fira Code, paper bg, sidebar (10 nav items)
        globals.css                      # Blueprint CSS vars, dot-grid background
        page.tsx                         # Dashboard — stats cards + recent sync table
        suppliers/
          page.tsx                       # Supplier list table + progressive reveal add form
        products/
          page.tsx                       # Product catalog grid with supplier badges
          [id]/
            page.tsx                     # Product detail — variant table, data sources, OPS push status
        customers/
          page.tsx                       # Customer list with OPS base URL
        workflows/
          page.tsx                       # Pipeline visualizer + n8n editor link
        sync/
          page.tsx                       # Sync job history — filterable, expandable error log
        mappings/
          [supplierId]/
            page.tsx                     # Field mapping editor + JSON preview
      components/
        suppliers/
          reveal-form.tsx                # Progressive reveal 5-section add-supplier form
        products/
          product-card.tsx              # Card with supplier badge + click-through
          product-detail.tsx            # Variant table, data source badges
        workflows/
          pipeline-view.tsx             # Animated pipeline node diagram
        sync/
          job-table.tsx                 # Filterable table with expandable error traces
        mappings/
          mapping-editor.tsx            # Visual source → target field mapping
      lib/
        api.ts                           # Fetch wrapper for /api/*
        types.ts                         # TypeScript types (extended)
```

---

### Task 1: Project Setup — ✅ DONE

**Files:** `.gitignore`, `.env`, `docker-compose.yml`, `backend/requirements.txt`, `backend/Dockerfile`

Already done. These files exist in the repo. Verify:

- [ ] **Step 1: Verify project state**

```bash
cd api-hub
ls -la
# Expected: .env, .gitignore, docker-compose.yml, backend/
```

- [ ] **Step 2: Create __init__.py files for modules**

```bash
touch backend/modules/__init__.py
touch backend/modules/suppliers/__init__.py
touch backend/modules/ps_directory/__init__.py
touch backend/modules/catalog/__init__.py
```

- [ ] **Step 3: Start PostgreSQL**

```bash
docker compose up -d postgres
```

- [ ] **Step 4: Install Python deps**

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 5: Commit**

```bash
cd api-hub
git add -A
git commit -m "chore: project setup with PostgreSQL and encryption support"
```

---

### Task 2: Database + EncryptedJSON — ✅ DONE

**Files:**
- Create: `backend/database.py`

- [ ] **Step 1: Write database.py**

Write `api-hub/backend/database.py`:

```python
import json
import os
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy import Text, TypeDecorator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv("POSTGRES_URL", "postgresql+asyncpg://vg_user:vg_pass@localhost:5432/vg_hub")
SECRET_KEY = os.getenv("SECRET_KEY", "")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class EncryptedJSON(TypeDecorator):
    """Transparently encrypts/decrypts JSON data in the database."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        if not SECRET_KEY:
            return json.dumps(value)
        f = Fernet(SECRET_KEY.encode())
        return f.encrypt(json.dumps(value).encode()).decode()

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if not SECRET_KEY:
            return json.loads(value)
        try:
            f = Fernet(SECRET_KEY.encode())
            return json.loads(f.decrypt(value.encode()))
        except Exception:
            return json.loads(value)


async def get_db():
    async with async_session() as session:
        yield session
```

- [ ] **Step 2: Commit**

```bash
git add backend/database.py
git commit -m "feat: database engine with EncryptedJSON type decorator"
```

---

### Task 3: Supplier Model + Schemas — ✅ DONE

**Files:**
- Create: `backend/modules/suppliers/models.py`
- Create: `backend/modules/suppliers/schemas.py`

- [ ] **Step 1: Write suppliers/models.py**

Write `api-hub/backend/modules/suppliers/models.py`:

```python
import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base, EncryptedJSON


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    protocol: Mapped[str] = mapped_column(String(50))
    promostandards_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_config: Mapped[dict] = mapped_column(EncryptedJSON, default=dict)
    endpoint_cache: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    endpoint_cache_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Write suppliers/schemas.py**

Write `api-hub/backend/modules/suppliers/schemas.py`:

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SupplierCreate(BaseModel):
    name: str
    slug: str
    protocol: str
    promostandards_code: str | None = None
    base_url: str | None = None
    auth_config: dict = {}


class SupplierRead(BaseModel):
    id: UUID
    name: str
    slug: str
    protocol: str
    promostandards_code: str | None
    base_url: str | None
    auth_config: dict
    is_active: bool
    created_at: datetime
    product_count: int = 0

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Commit**

```bash
git add backend/modules/suppliers/
git commit -m "feat: Supplier model with encrypted auth_config and schemas"
```

---

### Task 4: Product + Variant Models + Schemas — ✅ DONE

**Files:**
- Create: `backend/modules/catalog/models.py`
- Create: `backend/modules/catalog/schemas.py`

- [ ] **Step 1: Write catalog/models.py**

Write `api-hub/backend/modules/catalog/models.py`:

```python
import uuid as uuid_mod
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    supplier_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("suppliers.id"))
    supplier_sku: Mapped[str] = mapped_column(String(255))
    product_name: Mapped[str] = mapped_column(String(500))
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_type: Mapped[str] = mapped_column(String(50), default="apparel")
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    color: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    inventory: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warehouse: Mapped[str | None] = mapped_column(String(255), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="variants")
```

- [ ] **Step 2: Write catalog/schemas.py**

Write `api-hub/backend/modules/catalog/schemas.py`:

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


class ProductRead(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_sku: str
    product_name: str
    brand: str | None
    description: str | None
    product_type: str
    image_url: str | None
    last_synced: datetime | None
    variants: list[VariantRead] = []

    model_config = {"from_attributes": True}


class ProductListRead(BaseModel):
    id: UUID
    supplier_sku: str
    product_name: str
    brand: str | None
    product_type: str
    image_url: str | None
    variant_count: int = 0

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Commit**

```bash
git add backend/modules/catalog/
git commit -m "feat: Product and ProductVariant models with schemas"
```

---

### Task 5: PromoStandards Directory Client + Supplier Service — ✅ DONE

**Files:**
- Create: `backend/modules/ps_directory/client.py`
- Create: `backend/modules/ps_directory/schemas.py`
- Create: `backend/modules/suppliers/service.py`

- [ ] **Step 1: Write ps_directory/client.py**

Write `api-hub/backend/modules/ps_directory/client.py`:

```python
import httpx

PS_DIRECTORY_URL = (
    "https://services.promostandards.org"
    "/WebServiceRepository/WebServiceRepository.svc/json"
)


async def get_ps_companies() -> list[dict]:
    """Fetch all 1800+ companies from PromoStandards directory."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{PS_DIRECTORY_URL}/companies", timeout=30)
        resp.raise_for_status()
        return resp.json()


async def get_ps_endpoints(company_code: str) -> list[dict]:
    """Fetch all service endpoints for a given company code."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PS_DIRECTORY_URL}/companies/{company_code}/endpoints",
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 2: Write ps_directory/schemas.py**

Write `api-hub/backend/modules/ps_directory/schemas.py`:

```python
from pydantic import BaseModel


class PSCompany(BaseModel):
    Code: str
    Name: str
    Type: str


class PSEndpoint(BaseModel):
    Name: str | None = None
    ServiceType: str | None = None
    Version: str | None = None
    Status: str | None = None
    ProductionURL: str | None = None
    TestURL: str | None = None
```

- [ ] **Step 3: Write suppliers/service.py**

Write `api-hub/backend/modules/suppliers/service.py`:

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.ps_directory.client import get_ps_endpoints

from .models import Supplier


async def get_cached_endpoints(db: AsyncSession, supplier_id) -> list[dict]:
    """Return cached PS endpoints, refreshing if older than 24 hours."""
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier or not supplier.promostandards_code:
        return []

    # Check cache freshness
    if supplier.endpoint_cache and supplier.endpoint_cache_updated_at:
        age = datetime.now(timezone.utc) - supplier.endpoint_cache_updated_at
        if age < timedelta(hours=24):
            return supplier.endpoint_cache

    # Refresh from PS directory API
    endpoints = await get_ps_endpoints(supplier.promostandards_code)
    supplier.endpoint_cache = endpoints
    supplier.endpoint_cache_updated_at = datetime.now(timezone.utc)
    await db.commit()
    return endpoints
```

- [ ] **Step 4: Commit**

```bash
git add backend/modules/ps_directory/ backend/modules/suppliers/service.py
git commit -m "feat: PS directory client and supplier endpoint caching service"
```

---

### Task 6: API Routes — Suppliers, PS Directory, Catalog — ✅ DONE (PR #1 Urvashi)

**Files:**
- `backend/modules/suppliers/routes.py`
- `backend/modules/ps_directory/routes.py`
- `backend/modules/catalog/routes.py`

- [ ] **Step 1: Write suppliers/routes.py**

Write `api-hub/backend/modules/suppliers/routes.py`:

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.catalog.models import Product

from .models import Supplier
from .schemas import SupplierCreate, SupplierRead
from .service import get_cached_endpoints

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("", response_model=list[SupplierRead])
async def list_suppliers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Supplier).order_by(Supplier.created_at.desc()))
    suppliers = result.scalars().all()
    out = []
    for s in suppliers:
        count = (
            await db.execute(
                select(func.count()).select_from(Product).where(Product.supplier_id == s.id)
            )
        ).scalar() or 0
        data = SupplierRead.model_validate(s)
        data.product_count = count
        out.append(data)
    return out


@router.post("", response_model=SupplierRead, status_code=201)
async def create_supplier(body: SupplierCreate, db: AsyncSession = Depends(get_db)):
    supplier = Supplier(**body.model_dump())
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    data = SupplierRead.model_validate(supplier)
    data.product_count = 0
    return data


@router.get("/{supplier_id}", response_model=SupplierRead)
async def get_supplier(supplier_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    count = (
        await db.execute(
            select(func.count()).select_from(Product).where(Product.supplier_id == supplier.id)
        )
    ).scalar() or 0
    data = SupplierRead.model_validate(supplier)
    data.product_count = count
    return data


@router.put("/{supplier_id}", response_model=SupplierRead)
async def update_supplier(
    supplier_id: UUID, body: SupplierCreate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    for key, val in body.model_dump().items():
        setattr(supplier, key, val)
    await db.commit()
    await db.refresh(supplier)
    data = SupplierRead.model_validate(supplier)
    return data


@router.delete("/{supplier_id}")
async def delete_supplier(supplier_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
