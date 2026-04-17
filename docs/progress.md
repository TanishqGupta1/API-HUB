# API-HUB — Build Progress

> Source of truth for what is actually implemented in the codebase.
> The master plan lives in `plans/2026-04-14-v0-proof-of-concept.md` — do not edit that file here.

Last updated: 2026-04-16

---

## Quick Status

| Task | Description | Status |
|------|-------------|--------|
| 1 | Project Setup | ✅ DONE |
| 2 | Database + EncryptedJSON | ✅ DONE |
| 3 | Supplier Model + Schemas | ✅ DONE |
| 4 | Product + Variant Models | ✅ DONE |
| 5 | PS Directory Client + Supplier Service | ✅ DONE |
| 6 | API Routes — suppliers, ps_directory, catalog | ⚠️ PARTIAL |
| 7 | FastAPI Main App | ✅ DONE |
| 8 | Demo Seed Script | ✅ DONE |
| 9 | Next.js Scaffold + Blueprint Layout | ❌ TODO |
| 10 | Suppliers Page + Reveal Form | ❌ TODO |
| 11 | Products Page (catalog grid) | ❌ TODO |
| 12 | Product Detail Page | ❌ TODO |
| 13 | Customers Page | ❌ TODO |
| 14 | Workflows Page (pipeline visualizer) | ❌ TODO |
| 15 | Sync Jobs Page | ❌ TODO |
| 16 | Field Mapping Page | ✅ DONE |
| 17 | End-to-End Verification | ❌ TODO |
| 18 | Customer Model (OAuth2) | ✅ DONE |
| 19 | Markup Rules | ✅ DONE |
| 20 | Push Log | ✅ DONE |
| 21 | n8n OPS Push Workflow | ❌ TODO |

**Summary: 12 DONE · 1 PARTIAL · 8 TODO**

---

## What's Unblocked Right Now

| Task | Can start because... |
|------|----------------------|
| **Task 9 — Next.js Scaffold** | Pure frontend, no backend dependency |
| **Task 17 — E2E Verification** | Requires Tasks 1–16 all done; Task 6 still partial |
| **Task 21 — n8n OPS Push Workflow** | Backend ready (18, 19, 20 done); blocked on n8n-nodes-onprintshop external dependency |

---

## Completed Tasks — What Was Built and Why

---

### Task 1 — Project Setup

**Files:** `docker-compose.yml`, `backend/Dockerfile`, `backend/requirements.txt`

**What was done:**
- `docker-compose.yml` — sets up a PostgreSQL 16 container. Maps port 5432 on the host to 5432 inside the container. Includes a health check so other services wait until the DB is ready.
- `backend/Dockerfile` — Python 3.12 image for the FastAPI backend. Used when running the backend inside Docker.
- `backend/requirements.txt` — all Python dependencies: FastAPI, SQLAlchemy (async), asyncpg (Postgres driver), Pydantic, httpx (HTTP client for PS API), cryptography (Fernet encryption), python-dotenv (loads `.env` file).

**Why:** Everything else depends on Postgres being available and Python packages being installed. This is the foundation.

---

### Task 2 — Database + EncryptedJSON

**File:** `backend/database.py`

**What was done:**
- Created the async SQLAlchemy engine that connects to PostgreSQL.
- Created `async_session` — a factory that produces database sessions for each API request.
- Created `get_db()` — a FastAPI dependency. Any route that needs the database just declares `db: AsyncSession = Depends(get_db)` and gets a session automatically.
- Created `EncryptedJSON` — a custom SQLAlchemy type. Any column that uses this type is automatically encrypted before saving to the database and decrypted when reading back. Uses Fernet (AES-128) with a key from the `SECRET_KEY` environment variable. If no key is set (local dev), it stores plain JSON.
- Created `Base` — the SQLAlchemy base class all models inherit from.

**Why:** Supplier credentials (API keys, passwords) must never be stored as plain text in the database. By building encryption into the column type, every module that uses `EncryptedJSON` gets encryption for free without any extra code.

---

### Task 3 — Supplier Model + Schemas

**Files:** `backend/modules/suppliers/models.py`, `backend/modules/suppliers/schemas.py`

**What was done:**

`models.py` — defines the `suppliers` database table with these columns:
- `id` — UUID primary key, auto-generated
- `name` — supplier display name (e.g. "SanMar")
- `slug` — URL-safe identifier (e.g. "sanmar"), must be unique
- `protocol` — how we talk to this supplier: `"soap"` or `"rest"`
- `promostandards_code` — the supplier's code in the PromoStandards directory (e.g. `"SANMAR"`). Used to look up their API endpoints automatically.
- `base_url` — their API root URL
- `auth_config` — **EncryptedJSON** — stores credentials (username/password, API key, OAuth tokens, whatever the supplier uses). Encrypted at rest.
- `endpoint_cache` — JSONB column that caches the list of API endpoints from the PromoStandards directory so we don't hit their API on every request
- `endpoint_cache_updated_at` — when the cache was last refreshed (used for 24h TTL)
- `field_mappings` — JSONB column that stores the field mapping config for this supplier (e.g. `{"productTitle": "product_name"}`)
- `is_active` — soft toggle to disable a supplier without deleting it
- `created_at` — timestamp

`schemas.py` — Pydantic models that control what data comes in and goes out of the API:
- `SupplierCreate` — what the frontend sends when adding a supplier
- `SupplierRead` — what the API returns (includes `product_count` — how many products are synced from this supplier)

**Why:** The whole platform is built around suppliers being database configuration, not hardcoded. Adding a new supplier means creating a row, not writing code.

---

### Task 4 — Product + Variant Models

**Files:** `backend/modules/catalog/models.py`, `backend/modules/catalog/schemas.py`

**What was done:**

`models.py` — defines two tables:

`products` table:
- `id` — UUID primary key
- `supplier_id` — foreign key to `suppliers` table (which supplier this came from)
- `supplier_sku` — the supplier's own product code (e.g. "PC61")
- `product_name`, `brand`, `description`, `product_type`, `image_url` — standard product info
- `last_synced` — when n8n last pulled fresh data for this product
- Has a `variants` relationship — one product has many variants

`product_variants` table:
- `id` — UUID primary key
- `product_id` — foreign key to `products` (with CASCADE delete — delete the product, all variants go too)
- `color`, `size`, `sku` — variant identifiers
- `base_price` — wholesale price (Decimal for precision, not float)
- `inventory` — stock count
- `warehouse` — which warehouse it's in

`schemas.py` — three Pydantic models:
- `VariantRead` — a single variant's data
- `ProductRead` — full product detail including all variants (used on the product detail page)
- `ProductListRead` — lighter version for the catalog grid, includes `variant_count` instead of the full variant list

**Why:** Products are the core of the platform. The Product/Variant split matches how PromoStandards represents products — a "PC61 Tee" is one product, "Navy / M" is a variant.

---

### Task 5 — PS Directory Client + Supplier Service

**Files:** `backend/modules/ps_directory/client.py`, `backend/modules/ps_directory/schemas.py`, `backend/modules/suppliers/service.py`

**What was done:**

`ps_directory/client.py` — two async functions that call the PromoStandards directory API:
- `get_ps_companies()` — fetches all 994+ suppliers registered with PromoStandards. Returns a list with each supplier's code, name, and type.
- `get_ps_endpoints(company_code)` — fetches all API service endpoints for one supplier (e.g. their Product Data URL, Inventory URL, Pricing URL). This is how the platform auto-discovers where to call each supplier.

`ps_directory/schemas.py`:
- `PSCompany` — shape of a company record from the PS directory
- `PSEndpoint` — shape of an endpoint record (service type, version, production URL, test URL)

`suppliers/service.py` — the caching logic:
- `get_cached_endpoints(db, supplier_id)` — checks if we have a fresh cache (less than 24 hours old). If yes, returns it from the database. If no, calls the PS directory API, saves the result to `endpoint_cache`, updates `endpoint_cache_updated_at`, and returns it.

**Why:** The PS directory API has rate limits. Calling it on every page load would be slow and could get the platform blocked. Caching the endpoints in the database for 24 hours means we only call the PS API once per day per supplier.

---

### Task 6 — API Routes (PARTIAL)

**Status:** Suppliers routes are complete. PS Directory and Catalog routes are missing.

**File done:** `backend/modules/suppliers/routes.py`

What it provides:
- `GET /api/suppliers` — list all suppliers with their product count
- `POST /api/suppliers` — create a new supplier (credentials go in encrypted)
- `GET /api/suppliers/{id}` — get one supplier
- `PUT /api/suppliers/{id}` — update a supplier
- `DELETE /api/suppliers/{id}` — delete a supplier
- `GET /api/suppliers/{id}/endpoints` — fetch (and cache) PS directory endpoints for this supplier
- `PUT /api/suppliers/{id}/mappings` — save field mappings for a supplier ✅ Added in Task 16

**Still missing:**
- `backend/modules/ps_directory/routes.py` — `GET /api/ps-directory/companies` and `GET /api/ps-directory/companies/{code}/endpoints`
- `backend/modules/catalog/routes.py` — `GET /api/products` (with search/filter) and `GET /api/products/{id}`

---

### Task 7 — FastAPI Main App

**File:** `backend/main.py`

**What was done:**
- Created the FastAPI application with a title and version.
- Added `lifespan` — runs on startup to create all database tables automatically (no manual migrations needed for V0).
- Added CORS middleware — allows the frontend running on `localhost:3000` or `localhost:5173` to call the API without browser security errors.
- Registered the suppliers router.
- Added `GET /health` — a simple health check endpoint that returns `{"status": "ok"}`. Used by Docker and monitoring to know the app is running.

---

### Task 8 — Demo Seed Script

**File:** `backend/seed_demo.py`

**What was done:**
- Creates 3 demo suppliers: SanMar (SOAP), S&S Activewear (REST), 4Over (REST, no PromoStandards code)
- Creates 3 demo products with 10 variants total:
  - Port & Company Essential Tee (SanMar) — 4 variants (Navy S/M/L, White M)
  - Port Authority Silk Touch Polo (SanMar) — 3 variants (Black S/M/L)
  - Alternative Eco-Jersey Crew (S&S Activewear) — 3 variants (Smoke XS/S/M)
- Skips records that already exist (safe to run multiple times)
- Loads the `.env` file before anything else so encryption uses the real `SECRET_KEY`

**How to run:**
```bash
cd backend && source venv/bin/activate
python seed_demo.py
```

---

### Task 16 — Field Mapping Page ✅ DONE (2026-04-16)

**Files:**
- `frontend/src/app/mappings/page.tsx` — supplier picker (lists all suppliers, links to editor)
- `frontend/src/app/mappings/[supplierId]/page.tsx` — mapping editor with live JSON preview
- `backend/modules/suppliers/models.py` — added `field_mappings` JSONB column
- `backend/modules/suppliers/routes.py` — added `PUT /api/suppliers/{id}/mappings` endpoint

**What was done:**

Frontend — two-page UI:
1. `/mappings` — lists all suppliers as cards. Each card shows name, slug, protocol, PromoStandards code. "Configure Mappings" button opens the editor for that supplier.
2. `/mappings/[supplierId]` — side-by-side editor. Left column: type the supplier's raw field name. Right column: shows the canonical field name (read-only). Live JSON preview updates in real time as you type. Save button calls the backend.

Backend:
- Added `field_mappings` JSONB column to `suppliers` table to persist mappings
- Added `PUT /api/suppliers/{id}/mappings` endpoint — accepts a JSON object like `{"productTitle": "product_name"}` and saves it to the supplier row
- Returns `{"saved": true, "supplier_id": "...", "mappings": {...}}`

**11 canonical fields supported:** `product_name`, `supplier_sku`, `brand`, `description`, `product_type`, `color`, `size`, `base_price`, `inventory`, `image_url`, `warehouse`

**Why:** Different suppliers name their fields differently. This mapping tells n8n how to translate raw supplier data into the platform's standard format before pushing to OPS.

---

### Task 18 — Customer Model (OAuth2) ✅ DONE (2026-04-16)

**Files:** `backend/modules/customers/models.py`, `schemas.py`, `routes.py`, `__init__.py`, `frontend/src/app/customers/page.tsx`

**What was done:**

`models.py` — defines the `customers` table. A "customer" is an OnPrintShop storefront that products get pushed into:
- `id` — UUID primary key
- `name` — storefront name (e.g. "Acme Corp")
- `ops_base_url` — the OPS GraphQL API URL
- `ops_token_url` — the OAuth2 token endpoint URL
- `ops_client_id` — the OAuth2 client ID (stored plain)
- `ops_auth_config` — **EncryptedJSON** — stores `{"client_secret": "..."}`. Write-only: never returned by the API.
- `is_active`, `created_at`

`routes.py` — full CRUD:
- `GET /api/customers` — list all customers (secret never returned)
- `POST /api/customers` — create a customer (encrypts secret before saving)
- `GET /api/customers/{id}` — get one customer
- `DELETE /api/customers/{id}` — delete a customer

Frontend — customers page with:
- Table: Name | OPS Base URL | Auth (OAuth2 badge) | Products Pushed | Markup Rules count | Status
- "+ Add Customer" inline form with all OAuth2 fields (Store Name, Base URL, Token URL, Client ID, Client Secret)
- Markup rule count fetched live per customer from `/api/markup-rules/{id}`

**Why:** Each OPS storefront has its own OAuth2 credentials. Credentials must be encrypted — same Fernet pattern as supplier `auth_config`.

---

### Task 19 — Markup Rules ✅ DONE (2026-04-16)

**Files:** `backend/modules/markup/models.py`, `schemas.py`, `routes.py`, `__init__.py`, `frontend/src/app/markup/page.tsx`

**What was done:**

`models.py` — defines `markup_rules` table:
- `id` — UUID primary key
- `customer_id` — FK to `customers` (CASCADE delete)
- `scope` — what the rule applies to: `"all"`, `"category:T-Shirts"`, `"product:PC61"`, `"supplier:SanMar"`
- `markup_pct` — markup percentage (e.g. `45.00` = 45%)
- `min_margin` — optional minimum margin floor
- `rounding` — `"none"`, `"nearest_99"`, `"nearest_dollar"`
- `priority` — higher number = higher priority when multiple rules match
- `created_at`

`routes.py`:
- `GET /api/markup-rules/{customer_id}` — list rules ordered by priority descending
- `POST /api/markup-rules` — create a rule
- `DELETE /api/markup-rules/{rule_id}` — delete a rule

Frontend — full Markup Rules page matching demo HTML:
- Customer dropdown in header (auto-loads from API, auto-selects first)
- Subtitle shows "Pricing configuration for {customer name}"
- **Panel 1: Active Rules table** — Priority (blue number + highest/lowest label) | Scope badge | Target | Markup % | Min Margin | Rounding | Delete button
- **Panel 2: Pricing Preview** — editable base price input, one row per rule showing `$base → $marked-up → $rounded`, highest priority rule highlighted in blue with "✓ Applied" badge, others dimmed
- **Add Rule modal** — scope type select, conditional target input, all fields, saves via POST

**Why:** Different customers want different markup percentages. The scope+priority system allows layered pricing: e.g. 45% for a specific product, 40% for a category, 30% for everything else.

---

### Task 20 — Push Log ✅ DONE (2026-04-16)

**Files:** `backend/modules/push_log/models.py`, `schemas.py`, `routes.py`, `__init__.py`

**What was done:**

`models.py` — defines `product_push_log` table:
- `id` — UUID primary key
- `product_id` — FK to `products` (CASCADE delete)
- `customer_id` — FK to `customers` (CASCADE delete)
- `ops_product_id` — ID assigned by OPS after a successful push (`null` on failure)
- `status` — `"pushed"`, `"failed"`, or `"skipped"`
- `error` — error message if status is `"failed"`, otherwise `null`
- `pushed_at` — UTC timestamp of the push attempt

`routes.py`:
- `POST /api/push-log` — called by n8n after each push attempt to record the result
- `GET /api/products/{product_id}/push-status` — returns the **latest** push status per customer (not full history — always shows current state)

**Test results (all passed):**
- POST — log successful push ✅
- POST — log failed push with error message ✅
- GET — returns latest status correctly ✅
- GET — updates after re-push ✅

**Why:** Complete audit trail of every push attempt. The team can see which products were pushed to which storefronts and why any push may have failed.

---

## Known Issues / Gaps

| Issue | File | Fix Applied |
|-------|------|-------------|
| `python-dotenv` used but was missing from deps | `requirements.txt` | ✅ Added `python-dotenv>=1.0.0` |
| `main.py` only registers suppliers router | `backend/main.py` | Will add ps_directory + catalog routers when Task 6 completes |
| No `ProductImage` model | `backend/modules/catalog/` | Plan lists `product_images` table; current impl uses single `image_url` on `Product` instead |
| `Customer` type had wrong `ops_api_key` field | `frontend/src/lib/types.ts` | ✅ Fixed to `ops_token_url` + `ops_client_id` |

---

## Backend Module Map

```
backend/
  main.py                    ✅  FastAPI app — lifespan, CORS, health
  database.py                ✅  Async engine + EncryptedJSON type decorator
  seed_demo.py               ✅  Demo data — 3 suppliers, 3 products, 10 variants
  requirements.txt           ✅  All Python deps including python-dotenv
  modules/
    suppliers/               ✅  Model, schemas, full CRUD routes, endpoint cache service, field mappings endpoint
    ps_directory/            ✅  Client + schemas  |  ❌ routes.py missing
    catalog/                 ✅  Models + schemas  |  ❌ routes.py missing
    customers/               ✅  Model, schemas, full CRUD routes, __init__
    markup/                  ✅  Model, schemas, full CRUD routes, __init__
    push_log/                ✅  Model, schemas, routes, __init__
```
