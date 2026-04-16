# API-HUB V1 — Full Integration Pipeline Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete pipeline — fetch product catalogs from SanMar, S&S Activewear, Alphabroder, and 4Over, normalize into a canonical schema, and push to OnPrintShop storefronts via n8n with per-customer markup, full product options, images, and pricing.

**Architecture:** FastAPI handles SOAP/REST fetch + normalization + storage + markup rules. n8n orchestrates sync schedules AND owns all OPS push calls via n8n-nodes-onprintshop (extended with product mutations). Suppliers are DB configuration — one protocol adapter per type (SOAP, REST, REST+HMAC), not per vendor.

**Tech Stack:** Python 3.12, FastAPI, zeep (SOAP), httpx (REST), SQLAlchemy async + asyncpg, PostgreSQL 16, Pydantic v2, Next.js 15, shadcn/ui, n8n, n8n-nodes-onprintshop (TypeScript)

---

## Current State (2026-04-16)

**V0: 19/21 tasks done.** Backend: all 8 modules complete. Frontend: 5/7 pages done (Customers + Workflows remaining).

| Component | Status |
|-----------|--------|
| Supplier CRUD + encrypted credentials | ✅ Done |
| Product/Variant models + catalog API | ✅ Done |
| PS directory client (REST) + 24h cache | ✅ Done |
| Customer model (OPS OAuth2 encrypted) | ✅ Done |
| Markup rules model + CRUD | ✅ Done |
| Push log model + CRUD | ✅ Done |
| Sync jobs model | ✅ Done |
| SOAP client (zeep) | ❌ Installed, zero code |
| Normalization/mapping | ❌ Nothing |
| Sync orchestration | ❌ Nothing |
| OPS product mutations (n8n node) | ❌ 11% mutation coverage, setProduct missing |
| n8n workflows | ❌ Nothing |
| product_images table | ❌ Not created |
| Unique constraints for upserts | ❌ Missing |

---

## Phase Map

| Phase | What | Depends On | Blockers |
|-------|------|-----------|----------|
| **V0 Cleanup** | Fix 3 critical bugs, finish 2 frontend pages, install shadcn | Nothing | None |
| **V1a** | SanMar SOAP inbound (fetch → normalize → store) | V0 Cleanup | Christian's SanMar creds (for E2E only) |
| **V1b** | S&S Activewear (REST) + Alphabroder (PS SOAP, zero code) | V1a | S&S API creds |
| **V1c** | OPS Push — n8n node product mutations + markup engine + push workflow | V1a (products in DB) | OPS Postman collection for exact mutation input fields |
| **V1d** | 4Over (REST + HMAC) + field mapping | V1a | 4Over API creds |
| **V1e** | Scheduled sync + inventory + monitoring dashboard | V1a-V1d | n8n deployed |

---

## Phase Dependency Graph

```
                          V0 Cleanup
                    ┌──────┼──────────────────┐
                    │      │                   │
              Task 0.1   Task 0.3           Task 0.4
              Port fix   shadcn             Customers
              Task 0.2     │                Task 0.5
              dotenv fix   │                Workflows
                    │      │                Task 0.6
                    └──────┼──────────────────┘
                           │
                           ▼
    ┌─────────── V1a: SanMar SOAP Inbound ──────────────┐
    │         ┌────┬────┐                                │
    │     Task 1  Task 2  Task 3     (parallel)          │
    │     Schema  PS      WSDL +                         │
    │     Updates Schemas SOAP Client                    │
    │         └────┴──┬───┘                              │
    │                 ▼                                  │
    │            Task 4: Normalizer                      │
    │                 │                                  │
    │                 ▼                                  │
    │            Task 5: Sync Endpoints                  │
    │                 │                                  │
    │                 ▼                                  │
    │            Task 6: E2E Verify (BLOCKED: creds)     │
    └────────────────┬───────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
   V1b: S&S +    V1c: OPS     V1d: 4Over
   Alphabroder   Push          + Field Map
   ┌─────────┐  ┌──────────┐  ┌──────────┐
   │ Task 7  │  │ Task 9   │  │ Task 14  │
   │ Alpha   │  │ Fix P0   │  │ HMAC     │
   │ (0 code)│  │ contracts│  │ client   │
   │         │  │          │  │          │
   │ Task 8  │  │ Task 10  │  │ Task 15  │
   │ S&S REST│  │ Add 11   │  │ 4Over    │
   │ adapter │  │ product  │  │ normaliz.│
   └─────────┘  │ mutations│  │          │
                │          │  │ Task 16  │
   ALL THREE    │ Task 11  │  │ Sync     │
   PHASES RUN   │ Markup   │  │ route    │
   IN PARALLEL  │ engine   │  └──────────┘
                │          │
                │ Task 12  │
                │ n8n push │
                │ workflow  │
                │          │
                │ Task 13  │
                │ Image    │
                │ pipeline │
                └──────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
   V1e: Scheduled Sync      V1e: Dashboard
   ┌──────────────────┐    ┌──────────────┐
   │ Task 17: n8n     │    │ Task 19:     │
   │ cron workflows   │    │ Sync health  │
   │                  │    │ dashboard    │
   │ Task 18: Delta   │    └──────────────┘
   │ sync support     │
   └──────────────────┘
```

---

## Task-Level Dependency Matrix

| Task | Depends On | Can Parallel With | Blocks |
|------|-----------|-------------------|--------|
| **0.1** Port fix | — | 0.2, 0.3, 0.4, 0.5, 0.6 | V1a |
| **0.2** dotenv fix | — | 0.1, 0.3, 0.4, 0.5, 0.6 | V1a |
| **0.3** shadcn | — | 0.1, 0.2, 0.4, 0.5, 0.6 | 0.4, 0.5, 0.6 (frontend needs shadcn) |
| **0.4** Customers page | 0.3 | 0.5, 0.6 | V1c (push needs customer list) |
| **0.5** Workflows page | 0.3 | 0.4, 0.6 | Nothing |
| **0.6** Dashboard API | 0.3 | 0.4, 0.5 | Nothing |
| **1** Schema updates | V0 done | **2, 3** | 4, 5 |
| **2** PS response schemas | V0 done | **1, 3** | 4 |
| **3** WSDL resolver + SOAP client | V0 done | **1, 2** | 4, 5 |
| **4** Normalizer | 1, 2, 3 | — | 5 |
| **5** Sync endpoints | 4 | — | 6, 7, 8, 14 |
| **6** SanMar E2E verify | 5 + SanMar creds | — | Nothing (validation only) |
| **7** Alphabroder | 5 | **8, 9-13, 14-16** | V1e |
| **8** S&S REST adapter | 5 | **7, 9-13, 14-16** | V1e |
| **9** Fix OPS node P0 | — (TypeScript work) | **7, 8, 11, 14-16** | 10 |
| **10** Add product mutations | 9 + OPS Postman export | — | 12 |
| **11** Markup engine | V1a done | **9, 10, 7, 8, 14-16** | 12 |
| **12** n8n push workflow | 10, 11 | 13 | V1e |
| **13** Image pipeline | V1a done | **12** | V1e |
| **14** 4Over HMAC client | 5 + 4Over creds | **7, 8, 9-13** | 15 |
| **15** 4Over normalizer | 14 | **7, 8, 9-13** | 16 |
| **16** 4Over sync route | 15 | **7, 8, 9-13** | V1e |
| **17** n8n cron workflows | V1a-V1d all done | 18, 19 | — |
| **18** Delta sync | 5 | **17, 19** | — |
| **19** Sync dashboard | V1a done | **17, 18** | — |

---

## Parallel Execution Summary

### Maximum parallelism per phase:

| Phase | Parallel Tracks | Max Agents | Tasks |
|-------|----------------|------------|-------|
| V0 Cleanup | 2 tracks: backend fixes + frontend pages | 3 | 0.1+0.2 together, then 0.4+0.5+0.6 together (after 0.3) |
| V1a | Tasks 1, 2, 3 parallel → then 4 → 5 → 6 sequential | 3 → 1 | Schema + PS schemas + SOAP client can build simultaneously |
| V1b + V1c + V1d | **All 3 phases run in parallel** | 5 | V1b (2 tasks), V1c (5 tasks sequential), V1d (3 tasks sequential) |
| V1e | Tasks 17+18+19 parallel | 3 | All independent once suppliers are syncing |

### Optimal agent dispatch:

**Sprint 1 (V0 Cleanup):** 2 agents
- Agent A: Tasks 0.1, 0.2 (backend fixes)
- Agent B: Task 0.3 (shadcn), then 0.4+0.5+0.6 (frontend)

**Sprint 2 (V1a):** 3 agents → 1 agent
- Agents A+B+C in parallel: Task 1 (schema), Task 2 (PS schemas), Task 3 (SOAP client)
- After all 3 done → Agent A: Task 4 (normalizer) → Task 5 (routes) → Task 6 (verify)

**Sprint 3 (V1b + V1c + V1d):** 3 agents, all parallel
- Agent A — V1b: Task 7 (Alphabroder, 10 min), Task 8 (S&S adapter)
- Agent B — V1c: Task 9 → 10 → 11 → 12 → 13 (sequential, OPS push pipeline)
- Agent C — V1d: Task 14 → 15 → 16 (sequential, 4Over pipeline)

**Sprint 4 (V1e):** 3 agents
- Agent A: Task 17 (n8n workflows)
- Agent B: Task 18 (delta sync)
- Agent C: Task 19 (dashboard)

---

## V0 Cleanup

> **Parallel:** Tasks 0.1 + 0.2 are independent backend fixes (Agent A). Task 0.3 must complete before 0.4-0.6 (Agent B does 0.3 first, then 0.4+0.5+0.6).

### Task 0.1: Fix PostgreSQL port mismatch
**File:** `docker-compose.yml` line 9
**Problem:** PR #3 (Vidhi) changed the host port from 5432→5434 to avoid a local conflict on her machine. But `.env` still has `POSTGRES_URL=...localhost:5432/vg_hub`. The backend cannot connect to PostgreSQL for anyone pulling main.
**Fix:** Revert `"5434:5432"` → `"5432:5432"`. If Vidhi needs 5434 locally, she can override with `docker compose -f docker-compose.override.yml`.
**Impact:** Without this fix, `uvicorn main:app` crashes on startup with connection refused.

### Task 0.2: Fix load_dotenv path
**Files:** `backend/database.py` line 7, `backend/seed_demo.py` line 8
**Problem:** Both files call `load_dotenv(Path(__file__).parent / ".env")` which resolves to `backend/.env` — a file that doesn't exist. The actual `.env` is at the repo root (`api-hub/.env`).
**Fix:** Change to `Path(__file__).parent.parent / ".env"` (goes up one level to repo root). Alternatively, remove `load_dotenv` entirely and rely on Docker Compose env injection or shell exports.
**Impact:** Without this fix, `SECRET_KEY` is empty (no encryption), and `POSTGRES_URL` falls back to the hardcoded default which may not match the docker-compose port.

### Task 0.3: Install shadcn/ui
**Problem:** The V0 plan spec requires shadcn/ui components (button, card, input, table, badge, separator, scroll-area) but PR #2 (Sinchana) didn't install them. No `components/ui/` directory exists. All remaining frontend pages need these components.
**Fix:**
```bash
cd frontend && npx shadcn@latest init -d
npx shadcn@latest add button card input table badge separator scroll-area
```
**Impact:** Blocks ALL frontend work in V0 Cleanup (Tasks 0.4-0.6) and all V1 frontend work.

### Task 0.4: Customers Page (V0 Task 13)
**Depends on:** Task 0.3 (needs shadcn components)
**File:** `frontend/src/app/customers/page.tsx`
**Description:** List OPS storefronts with name, base URL, active toggle. Inline add form with OAuth2 fields (ops_base_url, ops_token_url, ops_client_id, ops_client_secret). The client_secret is write-only — never returned by the API. Calls `GET/POST /api/customers`.
**Why it matters:** V1c OPS push workflow loops over customers — the customer list must be populated before push works.

### Task 0.5: Workflows Page (V0 Task 14)
**Depends on:** Task 0.3 (needs shadcn components)
**File:** `frontend/src/app/workflows/page.tsx`, `frontend/src/components/workflows/pipeline-view.tsx`
**Description:** Animated pipeline diagram: Supplier → Fetch → Normalize → Store → Push to OPS. Each node shows status (idle/running/done/error). Links to n8n editor URL. Mostly static for V0 — becomes live when n8n workflows are deployed in V1e.

### Task 0.6: Wire dashboard to real API
**Depends on:** Task 0.3 (needs shadcn components)
**File:** `frontend/src/app/page.tsx`
**Description:** Replace hardcoded stats (4 vendors, 32.4k SKUs) with `useEffect` → `api<Stats>("/api/stats")` call. The `/api/stats` endpoint already exists and returns `{suppliers, products, variants}`. Also wire the pipeline activity table to `GET /api/sync-jobs?limit=5`.

---

## V1a — SanMar PromoStandards Inbound

> **Parallel:** Tasks 1, 2, 3 are independent and can run on 3 agents simultaneously. Task 4 needs all three. Tasks 5→6 are sequential after Task 4.

### Task 1: Schema Updates
**Modify:** `backend/modules/catalog/models.py`, `backend/modules/catalog/schemas.py`
**Can parallel with:** Tasks 2, 3
**Description:** Prepare the database for sync operations. Currently, products have no unique constraints, so re-syncing would create duplicates instead of updating. This task adds upsert support and richer product data fields.

**Changes:**
- Add `UniqueConstraint("supplier_id", "supplier_sku")` on Product — enables `ON CONFLICT DO UPDATE` so re-syncing updates existing products instead of duplicating
- Add `UniqueConstraint("product_id", "color", "size")` on ProductVariant — same pattern for variants
- Add `Product.category` (String, nullable) — PromoStandards products have categories like "T-Shirts", "Polos", "Outerwear"
- Add `Product.ops_product_id` (String, nullable) — stores the ID returned by OPS after a successful push, used to decide create vs update on subsequent pushes
- Create `ProductImage` model — `product_id` FK (CASCADE), `url` (Text), `image_type` (String: front/back/side/swatch/detail), `color` (String, nullable — which color variant the image shows), `sort_order` (Integer), `UniqueConstraint("product_id", "url")` for image dedup
- Add `images` relationship on Product with cascade delete
- Update Pydantic schemas: new `ProductImageRead`, add `category`, `ops_product_id`, `images: list[ProductImageRead]` to `ProductRead`, add `category` to `ProductListRead`

**Migration:** Drop + recreate tables (project uses `Base.metadata.create_all`, no Alembic). Re-seed with `python seed_demo.py`.

### Task 2: PromoStandards Response Schemas
**Create:** `backend/modules/promostandards/__init__.py`, `backend/modules/promostandards/schemas.py`
**Can parallel with:** Tasks 1, 3
**Description:** Define typed Pydantic models for deserialized SOAP XML responses. These are NOT database models — they are intermediate containers between the SOAP client (raw zeep output) and the normalizer (which maps them to DB rows). Having typed models means the normalizer gets clean, validated input regardless of which supplier the data came from.

**Models:**
- `PSProductData` — productId, productName, description, brand, categories: list[str], productType, primaryImageUrl, parts: list[PSProductPart]. Represents one product from `getProduct` or `getProductSellable`.
- `PSProductPart` — partId, colorName, sizeName, description. A single color/size variant within a product. SanMar calls these "parts" — one "PC61 Essential Tee" product has parts like "Navy/M", "Navy/L", "White/S".
- `PSInventoryLevel` — productId, partId, quantityAvailable (int, capped at 500 per PS convention), warehouseCode. From `getInventoryLevels`.
- `PSPricePoint` — productId, partId, price (float), quantityMin (int), quantityMax (int|None), priceType (piece/dozen/case). From PPC service.
- `PSMediaItem` — productId, url, mediaType (front/back/side/swatch/detail), colorName. From Media Content service.

### Task 3: WSDL Resolver + SOAP Client
**Create:** `backend/modules/promostandards/resolver.py`, `backend/modules/promostandards/client.py`
**Can parallel with:** Tasks 1, 2
**Description:** The core protocol adapter. One class that talks to ANY PromoStandards-compliant supplier — SanMar, Alphabroder, or any of the 994+ registered suppliers. It takes a WSDL URL and credentials dict, both from the database (never hardcoded). The WSDL URL comes from the PS directory endpoint cache (already implemented in `suppliers/service.py`).

**Resolver** (`resolver.py`):
Resolves service type names to WSDL URLs from the cached endpoint data. The PS directory uses inconsistent naming across suppliers ("Product Data" vs "ProductData", "Inventory Levels" vs "Inventory"), so the resolver normalizes strings before matching.

**SOAP Client** (`client.py`) — `PromoStandardsClient` class:
- Constructor: `wsdl_url` + `credentials` dict from `supplier.auth_config`. Uses `zeep.cache.SqliteCache` for WSDL parse caching (avoids re-fetching WSDL on every sync).
- `get_sellable_product_ids(ws_version="2.0.0")` → list[str] — calls PS `getProductSellable`, returns all active product IDs for this supplier
- `get_product(product_id, ws_version="2.0.0")` → PSProductData — calls PS `getProduct` for a single product, parses the XML response into our typed schema
- `get_products_batch(product_ids, batch_size=50)` → list[PSProductData] — fetches multiple products in batches to avoid rate limits. SanMar has 5000+ styles — fetching one at a time is too slow, fetching all at once may trigger rate limits.
- `get_inventory(product_ids, ws_version="2.0.0")` → list[PSInventoryLevel] — calls PS `getInventoryLevels` per product
- **Critical:** zeep is synchronous. All SOAP calls wrapped with `asyncio.to_thread()` to avoid blocking the FastAPI event loop.

### Task 4: Normalization Layer
**Create:** `backend/modules/promostandards/normalizer.py`
**Depends on:** Tasks 1 (DB models), 2 (PS schemas), 3 (client output types)
**Description:** The mapping + storage layer. Takes typed PS response data (from Task 2) and upserts it into the canonical Product/ProductVariant/ProductImage tables (from Task 1) using PostgreSQL `INSERT ... ON CONFLICT DO UPDATE`. This is where supplier-specific data becomes supplier-agnostic.

**Field mapping:**

| PS Field | → | Canonical Field | Notes |
|----------|---|----------------|-------|
| productId | → | Product.supplier_sku | The supplier's own product code (e.g., "PC61") |
| productName | → | Product.product_name | e.g., "Port & Company Essential Tee" |
| productBrand | → | Product.brand | e.g., "Port & Company" |
| categories[0] | → | Product.category | Take first category from the PS category array |
| description | → | Product.description | Full product description text |
| Part.partId | → | Variant.sku | The part-level SKU — unique within a product |
| Part.colorName | → | Variant.color | e.g., "Navy", "White" |
| Part.sizeName | → | Variant.size | e.g., "S", "M", "L", "XL" |
| Inventory.quantityAvailable | → | Variant.inventory | Capped at 500 (PS convention) |
| Inventory.warehouseCode | → | Variant.warehouse | Which warehouse has this stock |
| Pricing.price (lowest tier) | → | Variant.base_price | Wholesale piece price before markup |
| Media.url | → | ProductImage.url | Full CDN URL for the image |
| Media.mediaType | → | ProductImage.image_type | Mapped to front/back/side/swatch/detail |

**Three sync paths (same normalizer, different scope):**
- `upsert_products(db, supplier_id, products, inventory?, pricing?, media?)` — full sync: products + variants + images. Uses `pg_insert().on_conflict_do_update()` with the unique constraints from Task 1. Processes in batches, commits every 100 products.
- `update_inventory_only(db, supplier_id, inventory)` — lightweight sync: updates only `Variant.inventory` + `Variant.warehouse` on existing variants. No product or image changes. Used for the 30-min inventory cron.
- `update_pricing_only(db, supplier_id, pricing)` — updates only `Variant.base_price` on existing variants. Used for the daily pricing cron.

### Task 5: Sync Trigger Endpoints
**Create:** `backend/modules/promostandards/routes.py`
**Modify:** `backend/main.py` — register sync router
**Depends on:** Task 4
**Description:** FastAPI endpoints that n8n calls to trigger syncs. Each returns immediately (HTTP 202 Accepted) with a job ID — the actual SOAP work runs as a background task. n8n polls `GET /api/sync-jobs/{job_id}` until the status changes to "completed" or "failed".

**Endpoints:**
```
POST /api/sync/{supplier_id}/products    → full product sync (202 + job_id)
POST /api/sync/{supplier_id}/inventory   → inventory-only update (202 + job_id)
POST /api/sync/{supplier_id}/pricing     → pricing-only update (202 + job_id)
GET  /api/sync/{supplier_id}/status      → latest sync job for this supplier
```

**Request flow:**
1. Load supplier from DB, validate it exists, is active, and has a `promostandards_code`
2. Refresh endpoint cache if stale (calls existing `get_cached_endpoints`)
3. Resolve required WSDL URLs (Product Data, Inventory, PPC, Media) using the resolver
4. Create `SyncJob` record with `status="running"`, `job_type="full_sync"` (or "inventory"/"pricing")
5. Add background task that: creates SOAP client → fetches data → normalizes → upserts → updates SyncJob to "completed" with `records_processed` count
6. Return `{"job_id": "...", "status": "running"}` immediately

**Why background tasks?** SanMar has 5000+ products. A full sync takes minutes. The HTTP request from n8n should not block. Using FastAPI's `BackgroundTasks` for V1. If sync duration exceeds worker timeout at scale, graduate to a task queue (arq/Celery) in V2.

### Task 6: SanMar E2E Verification
**Depends on:** Task 5 + Christian's SanMar API credentials
**Blocker:** Cannot run until Christian provides real SanMar API credentials.
**Description:** End-to-end test of the full inbound pipeline against real SanMar data.

**Steps:**
1. Update SanMar supplier `auth_config` with real credentials: `{"id": "USERNAME", "password": "PASSWORD"}`
2. Verify endpoint cache: `curl http://localhost:8000/api/suppliers/{sanmar_id}/endpoints` — should show WSDL URLs
3. Trigger full sync: `curl -X POST http://localhost:8000/api/sync/{sanmar_id}/products`
4. Poll job: `curl http://localhost:8000/api/sync-jobs/{job_id}` — wait for `status: "completed"`
5. Verify products: `curl "http://localhost:8000/api/products?supplier_id={sanmar_id}"` — should show real SanMar products
6. Verify variants: `curl http://localhost:8000/api/products/{product_id}` — should show color/size variants with pricing
7. Verify in frontend: open `http://localhost:3000/products` — SanMar products visible with correct supplier badges

---

## V1b — S&S Activewear + Alphabroder

> **Parallel with V1c and V1d.** Both tasks here are independent of each other. Task 7 takes ~10 minutes (just a DB row). Task 8 needs the normalizer from V1a.

### Task 7: Alphabroder (zero code — just configuration)
**Can parallel with:** Task 8, and ALL of V1c + V1d
**Description:** Alphabroder is PromoStandards-compliant. The SOAP client from V1a Task 3 is supplier-agnostic — it works for any PS supplier given the right company code and credentials. Adding Alphabroder = creating a supplier row in the database. Zero Python code, zero TypeScript code. This is the payoff of the protocol adapter pattern.

**Steps:**
```bash
curl -X POST http://localhost:8000/api/suppliers \
  -H "Content-Type: application/json" \
  -d '{"name": "Alphabroder", "slug": "alphabroder", "protocol": "promostandards", "promostandards_code": "ALPHA", "auth_config": {"id": "USERNAME", "password": "PASSWORD"}}'
```
Then trigger sync: `POST /api/sync/{alphabroder_id}/products` — same pipeline, different supplier.

### Task 8: S&S Activewear REST Adapter
**Create:** `backend/modules/rest_connector/__init__.py`, `client.py`, `ss_normalizer.py`
**Depends on:** V1a Task 4 (normalizer — reuses `upsert_products()`)
**Can parallel with:** Task 7, and ALL of V1c + V1d
**Description:** S&S Activewear uses REST/JSON (not SOAP), so it needs a new protocol adapter. This is the second adapter type — while PromoStandards uses SOAP via zeep, S&S uses a straightforward REST API with HTTP Basic Auth.

**S&S API:** `https://api.ssactivewear.com/V2`
- Auth: HTTP Basic Auth — account number + API key from `supplier.auth_config`
- `GET /V2/Products/` → full product catalog (JSON array)
- `GET /V2/Styles/` → styles with color/size variants
- `GET /V2/Categories/` → category hierarchy

**REST Client** (`client.py`): `RESTConnectorClient` — takes `base_url` + `auth_config` from supplier row. Uses httpx AsyncClient (already in requirements.txt). Methods: `get_products()`, `get_styles()`, `get_categories()`.

**S&S Normalizer** (`ss_normalizer.py`): Maps S&S JSON response fields → canonical `PSProductData` format (same Pydantic models used by the SOAP client). This means the existing `upsert_products()` normalizer works unchanged — it doesn't care if the PSProductData came from SOAP or REST.

**Sync route update:** The `POST /api/sync/{supplier_id}/products` endpoint checks `supplier.protocol`:
- `"promostandards"` → uses SOAP client (existing from V1a)
- `"rest"` → uses REST client (new)

This branching happens in the sync route, not in the normalizer — the normalizer always receives PSProductData regardless of source.

---

## V1c — OPS Push via n8n

> **Parallel with V1b and V1d.** Tasks 9→10→11→12→13 are sequential within V1c. Task 9 (fix broken contracts) and Task 11 (markup engine) can start in parallel since they touch different repos (n8n node vs FastAPI).

**This is the outbound pipeline.** n8n calls FastAPI for product data + markup pricing, then uses the OnPrintShop node to push to OPS. This is the most complex phase — it spans TypeScript (n8n node), Python (markup engine), and n8n workflow JSON.

**Blocker:** Need the OPS Postman collection exported to get exact `input` field structures for each mutation. The gap analysis lists operation names and variables but NOT the `input` object shapes.

### Task 9: n8n-nodes-onprintshop — Fix Broken Contracts (P0)

**File:** `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts`

Fix `updateOrderStatus`:
- Add `type` variable (distinguishes order vs order-product status)
- Add `orders_products_id` variable
- Add `input` variable (status payload)
- Remove direct `orders_status_id` top-level variable

Remove legacy `mutation > updateProductStock` (the correct version exists under `product > updateStock`).

### Task 10: n8n-nodes-onprintshop — Add Product Mutations (P1)

**File:** `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts`

All product-related mutations to implement:

| # | Operation | GraphQL Mutation | Variables | What It Does |
|---|-----------|-----------------|-----------|-------------|
| 1 | **Set Product** | `setProduct` | `input` | Create or update a product in OPS |
| 2 | **Set Product Price** | `setProductPrice` | `input` | Set pricing tiers for a product |
| 3 | **Set Product Category** | `setProductCategory` | `input` | Assign category to a product |
| 4 | **Assign Options** | `setAssignOptions` | `input` | Link option groups to a product |
| 5 | **Set Product Size** | `setProductSize` | `input` | Set product dimensions |
| 6 | **Set Product Pages** | `setProductPages` | `input` | Set page count (for print products) |
| 7 | **Set Master Option Attributes** | `setMasterOptionAttributes` | `input` | Define option attributes (colors, materials, etc.) |
| 8 | **Set Master Option Attribute Price** | `setMasterOptionAttributePrice` | `input` | Price per option attribute |
| 9 | **Set Master Option Rules** | `setProductOptionRules` | `input` | Rules between options (if X then Y) |
| 10 | **Update Order Product Images** | `setOrderProductImage` | `order_product_id, input` | Upload/assign images to order products |
| 11 | **Set Product Design** | `setProductDesign` | `order_product_id, ziflow_link, ziflow_preflight_link` | Ziflow design proof integration |

**Each mutation needs:**
- UI fields in the n8n node (input parameters the user fills in)
- GraphQL query string with proper variables
- Execution logic that maps UI fields → GraphQL variables
- Error handling for API failures

**Action required:** Export the OPS Postman collection to get the exact `input` object shapes (field names, types, required vs optional). Without this, we can write the n8n node scaffold but not the exact GraphQL payloads.

### Task 11: Markup Rule Execution Engine

**Create:** `backend/modules/markup/engine.py`

```python
async def calculate_price(db, customer_id, product_id) -> dict:
    """Apply markup rules and return final pricing for a product + customer."""
```

Rule resolution (sorted by priority desc, first match wins):
1. `scope = "product:{supplier_sku}"` — product-level override
2. `scope = "category:{category}"` — category-level
3. `scope = "all"` — global default

Calculation:
```
markup_price = base_price × (1 + markup_pct / 100)
if min_margin and markup_price < base_price × (1 + min_margin / 100):
    markup_price = base_price × (1 + min_margin / 100)
if rounding == "nearest_99": markup_price = floor(markup_price) + 0.99
if rounding == "nearest_dollar": markup_price = round(markup_price)
```

**Endpoint:** `GET /api/push/{customer_id}/product/{product_id}/payload`
Returns the complete product payload ready for OPS, with:
- Product fields (name, description, brand, category, SKU)
- All variants with markup-applied pricing
- Image URLs
- Option mappings

This is what n8n fetches before calling setProduct.

### Task 12: n8n OPS Push Workflow

**Create:** `n8n-workflows/ops-push.json`

```
1. Trigger (manual or cron)
2. HTTP Request → GET /api/customers (active storefronts)
3. Loop over customers:
   a. HTTP Request → GET /api/products?not_pushed_to={customer_id}
   b. Loop over products:
      i.   HTTP Request → GET /api/push/{customer_id}/product/{id}/payload
      ii.  OnPrintShop node → setProduct (create/update product in OPS)
      iii. OnPrintShop node → setProductPrice (set markup-applied pricing)
      iv.  OnPrintShop node → setProductCategory (assign category)
      v.   OnPrintShop node → setAssignOptions (link options)
      vi.  OnPrintShop node → setProductSize (dimensions)
      vii. OnPrintShop node → setOrderProductImage (upload images)
      viii.HTTP Request → POST /api/push-log (log result: success/fail)
4. On error → notification webhook (Slack/email)
```

### Task 13: Image Pipeline

**Create:** `backend/modules/ops_push/__init__.py`, `backend/modules/ops_push/image_pipeline.py`

For each product being pushed to OPS:
1. Download image from supplier CDN (httpx streaming — never load full image into memory)
2. Resize to 800×800 (Pillow)
3. Convert to WebP quality 85
4. Return processed image bytes for n8n to upload via `setOrderProductImage`

**Endpoint:** `GET /api/push/image/{image_id}/processed`
Returns the processed image binary. n8n fetches this and passes to the OPS node.

---

## V1d — 4Over + Field Mapping

> **Parallel with V1b and V1c.** Tasks 14→15→16 are sequential within V1d. This phase leverages the Field Mapping UI already built by Vidhi (V0 Task 16).

### Task 14: 4Over REST + HMAC Adapter
**Create:** `backend/modules/rest_connector/fourover_client.py`
**Can parallel with:** All of V1b + V1c
**Description:** 4Over is NOT PromoStandards-compliant — it uses a proprietary REST API with HMAC-SHA256 request signing. This is the third protocol adapter type. Every request must include a signature: `HMAC-SHA256(private_key, method + path + timestamp)` in the Authorization header.

**4Over API:** `https://api.4over.com` (production), `https://sandbox-api.4over.com` (sandbox)
- Auth: HMAC-SHA256 — `api_key` + `private_key` from `supplier.auth_config`
- `GET /printproducts/categories` → category tree (print products are categorized differently from apparel)
- `GET /printproducts/products` → product catalog
- `GET /printproducts/products/{uuid}/optiongroups` → product options (paper type, coating, folding, etc.)
- `POST /printproducts/productquote` → pricing (quote-based, not fixed-price like apparel)

**`FourOverClient` class:** Constructor takes `base_url` + `auth_config`. Generates HMAC signature per request. Methods: `get_categories()`, `get_products()`, `get_product_options(uuid)`, `get_quote(uuid, options)`. Uses httpx AsyncClient.

### Task 15: 4Over Normalizer with Field Mapping
**Create:** `backend/modules/rest_connector/fourover_normalizer.py`
**Depends on:** Task 14
**Description:** 4Over's product structure is fundamentally different from PromoStandards — print products have paper types, coatings, and folds instead of colors and sizes. The field mapping UI (already built by Vidhi in V0 Task 16) lets users visually map 4Over's fields to the canonical schema. This normalizer reads that mapping from the DB and applies it.

**How it works:**
1. Fetch raw 4Over JSON via the HMAC client
2. Load field mapping from supplier config (stored in DB, configured via `/mappings/{supplierId}` UI)
3. Apply mapping: each source_field → target_field transform
4. Output `PSProductData` format (same Pydantic models as SOAP + REST) → feeds into existing `upsert_products()` unchanged

**Why reuse PSProductData?** The normalizer always outputs the same intermediate format regardless of supplier. This means the upsert logic is written once and works for all 4 supplier types (PS SOAP, S&S REST, 4Over REST+HMAC, and any future suppliers).

### Task 16: Sync route update for 4Over
**Modify:** `backend/modules/promostandards/routes.py`
**Depends on:** Task 15
**Description:** Add `protocol = "rest_hmac"` branch to the sync endpoint.

The `POST /api/sync/{supplier_id}/products` endpoint now handles 3 protocols:
- `"promostandards"` → SOAP client (V1a)
- `"rest"` → REST client for S&S (V1b)
- `"rest_hmac"` → 4Over HMAC client (V1d)

---

## V1e — Scheduled Sync + Inventory + Dashboard

> **Parallel:** Tasks 17, 18, 19 are independent and can run on 3 agents simultaneously. This phase only starts after V1a-V1d are complete (all suppliers syncing).

### Task 17: n8n Sync Workflows
**Create:** `n8n-workflows/inventory-sync-30min.json`, `pricing-sync-daily.json`, `delta-sync-daily.json`, `full-sync-weekly.json`
**Depends on:** All sync endpoints working (V1a-V1d)
**Can parallel with:** Tasks 18, 19
**Description:** Create n8n workflow JSON files for automated sync schedules. These are the production heartbeat of the platform — they keep product catalogs, inventory, and pricing fresh.

| Schedule | Workflow File | What | Endpoint Called |
|----------|-------------|------|----------------|
| Every 30 min | `inventory-sync-30min.json` | Inventory sync — all active suppliers | `POST /api/sync/{id}/inventory` per supplier |
| Daily 2 AM | `pricing-sync-daily.json` | Pricing sync — wholesale price updates | `POST /api/sync/{id}/pricing` per supplier |
| Daily 3 AM | `delta-sync-daily.json` | Delta product sync — only changed products | `POST /api/sync/{id}/products?delta=true` per supplier |
| Weekly Sun 1 AM | `full-sync-weekly.json` | Full catalog re-pull — catches anything delta missed | `POST /api/sync/{id}/products` per supplier |

**Each workflow pattern:** Cron trigger → `GET /api/suppliers?is_active=true` → loop over suppliers → trigger sync → poll until done → on failure: notification webhook (Slack/email/Discord). Workflows use n8n environment variables for the API base URL so they work in dev (localhost:8000) and production.

### Task 18: Delta Sync Support
**Modify:** `backend/modules/promostandards/client.py`, `backend/modules/promostandards/routes.py`
**Can parallel with:** Tasks 17, 19
**Description:** Full syncs pull ALL products every time (5000+ for SanMar). Delta sync pulls only products modified since the last sync — massively faster for daily runs. PromoStandards has a `getProductDateModified` method that returns product IDs with modification timestamps.

**Changes:**
- Add `get_product_date_modified(since: datetime)` method to `PromoStandardsClient` — calls PS `getProductDateModified`, returns only product IDs changed after the given timestamp
- The sync endpoint accepts `?delta=true` query param. When set, it reads the last completed sync job's `finished_at` timestamp and uses that as the `since` parameter instead of fetching all sellable product IDs
- Falls back to full sync if no previous completed sync exists

### Task 19: Sync Dashboard
**Modify:** `frontend/src/app/page.tsx` (dashboard), `frontend/src/app/sync/page.tsx` (sync jobs)
**Can parallel with:** Tasks 17, 18
**Description:** Make sync health visible to non-technical users (per Christian's meeting requirement). The sync jobs page already exists (built by Vidhi) — this task wires it to real data and adds summary metrics to the main dashboard.

**Dashboard additions:**
- Last sync time per supplier (green if <1h, amber if <24h, red if >24h)
- Sync health indicator badge per supplier
- Total products synced count
- Inventory freshness (time since last inventory sync)
- Latest failed sync with error preview (click to expand)

**Sync jobs page:** Verify it renders real data from `GET /api/sync-jobs`. Add filters: by supplier, by job_type, by status. Add auto-refresh every 30 seconds while a sync is running.

---

## Team Assignment

| Phase | Tasks | Suggested Owner | Rationale |
|-------|-------|----------------|-----------|
| V0 Cleanup (0.1-0.3) | Bug fixes + shadcn | Any dev | Quick fixes |
| V0 Cleanup (0.4-0.6) | Frontend pages | Sinchana / Urvashi | Frontend work |
| V1a Tasks 1-2 | Schema + PS schemas | Intern | Model changes |
| V1a Tasks 3-5 | SOAP client + normalizer + routes | Tanishq / Senior | Core pipeline |
| V1b Task 7 | Alphabroder | Anyone | Just a DB row |
| V1b Task 8 | S&S REST adapter | Urvashi | She built the API routes |
| V1c Tasks 9-10 | n8n node mutations | Tanishq / Senior | TypeScript + OPS GraphQL |
| V1c Tasks 11-13 | Markup engine + push workflow + images | Tanishq / Senior | Core business logic |
| V1d Tasks 14-16 | 4Over adapter | Vidhi | She built field mapping UI |
| V1e Tasks 17-19 | n8n workflows + dashboard | Any dev | n8n JSON + minor frontend |

---

## Blockers Tracker

| Blocker | Needed For | Owner | Status |
|---------|-----------|-------|--------|
| SanMar API credentials | V1a Task 6 E2E test | Christian → Tanishq | Waiting |
| S&S API credentials | V1b Task 8 | Christian → Tanishq | Waiting |
| 4Over API credentials | V1d Task 14 | Christian → Tanishq | Waiting |
| **OPS Postman collection export** | **V1c Task 10 — exact mutation input fields** | **Tanishq (export from browser)** | **Waiting** |
| n8n-nodes-onprintshop P0 fixes | V1c Task 9 | Tanishq | Not started |
| OPS custom dev requests | V1c if OPS needs new endpoints | Christian | Waiting |
| shadcn/ui installation | All remaining frontend | Sinchana | Not started |

---

## Verification per Phase

**V1a:** `POST /api/sync/{sanmar_id}/products` → products in catalog with variants + images → sync job "completed"

**V1b:** Alphabroder sync (zero code) + S&S sync → 3 suppliers in catalog with correct badges

**V1c:** Select products → n8n push workflow → products appear in OPS with:
- Correct product name, description, brand, category
- All variants with markup-applied pricing
- Options assigned
- Images uploaded
- Push log shows success per product per customer

**V1d:** Configure 4Over field mapping in UI → sync → 4Over products in catalog

**V1e:** n8n cron workflows running → inventory every 30 min → delta sync daily → dashboard shows real-time health

---

## What's Out of V1 Scope (V2+)

| Feature | Phase | Notes |
|---------|-------|-------|
| VG as vendor (overflow orders) | V2 | VG becomes a supplier, products flow FROM VG TO customers |
| Network-wide marketplace | V3 | Graphics Dash integration |
| MedusaJS ecommerce layer | V3+ | Replace OPS entirely |
| Alembic migrations | V2 | Replace drop+recreate with proper migrations |
| Background task queue (Celery/ARQ) | V2 | Replace BackgroundTasks when sync volume grows |
| Multi-tenant auth (JWT) | V2 | Currently no API authentication |
