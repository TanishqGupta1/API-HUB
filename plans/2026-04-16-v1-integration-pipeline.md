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
| **V1f** | Frontend UX polish — terminology, simplified supplier form, dashboard API wiring | V0 Cleanup (shadcn) | None |
| **V1g** | Storefront Configuration — OPS category/option/pricing setup UI + backend proxy | V1c (OPS push working) | OPS API creds + OPS Postman collection |

> **Scope change (2026-04-16):** Task 23 (OPS Product Config) was extracted from V1f into its own phase V1g. It is NOT a UX polish task — it's a major new feature requiring a backend module to proxy the OPS API, handle auth token refreshes, cache nested JSON, and manage rate limits. It is hard-blocked on OPS API credentials and should only start after V1c proves the OPS push pipeline works.

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
              ┌────────────┼──────────────────┐
              │            │                   │
              ▼            ▼                   │
    V1f: UX Polish       V1a: SanMar SOAP     │
    Tasks 20-22          Tasks 1-6             │
    (terminology,        (SOAP client,         │
     supplier form,       normalizer,          │
     dashboard)           sync endpoints)      │
    NO BLOCKERS            │                   │
                           │                   │
              ┌────────────┼────────────┐      │
              │            │            │      │
              ▼            ▼            ▼      │
         V1b: S&S +    V1c: OPS     V1d: 4Over│
         Alphabroder   Push          + Mapping │
         Tasks 7-8     Tasks 9-13   Tasks 14-16
         (parallel)    (sequential)  (sequential)
              │            │            │
              └────────────┼────────────┘
                           │
                           ▼
                    V1e: Scheduled Sync
                    Tasks 17-19
                           │
                           ▼
                    V1g: Storefront Config
                    Task 23
                    (OPS category/option/pricing
                     setup UI + backend proxy)
                    BLOCKED: OPS API creds
                    + requires V1c working first
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
| **20** Terminology + sidebar | V0 done (shadcn) | **21, 22**, all V1a | — |
| **21** Simplified supplier form | V0 done (shadcn) | **20, 22**, all V1a | — |
| **22** Dashboard real API | V0 done (shadcn) | **20, 21**, all V1a | — |
| **23** OPS Storefront Config | V1c done + OPS creds | — | — |

---

## Parallel Execution Summary

### Maximum parallelism per phase:

| Phase | Parallel Tracks | Max Agents | Tasks |
|-------|----------------|------------|-------|
| V0 Cleanup | 2 tracks: backend fixes + frontend pages | 3 | 0.1+0.2 together, then 0.4+0.5+0.6 together (after 0.3) |
| V1a + V1f | Tasks 1,2,3 parallel (backend) + Tasks 20,21,22 parallel (frontend) | **6** | Backend SOAP pipeline + frontend UX polish simultaneously |
| V1b + V1c + V1d | **All 3 phases run in parallel** | 5 | V1b (2 tasks), V1c (5 tasks sequential), V1d (3 tasks sequential) |
| V1e | Tasks 17+18+19 parallel | 3 | All independent once suppliers are syncing |
| V1g | Task 23 alone | 1 | Blocked until V1c proves OPS push works |

### Optimal agent dispatch:

**Sprint 1 (V0 Cleanup):** 2 agents
- Agent A: Tasks 0.1, 0.2 (backend fixes)
- Agent B: Task 0.3 (shadcn), then 0.4+0.5+0.6 (frontend)

**Sprint 2 (V1a + V1f in parallel):** up to 6 agents
- Agents A+B+C (backend): Task 1 (schema), Task 2 (PS schemas), Task 3 (SOAP client)
- Agents D+E+F (frontend): Task 20 (terminology), Task 21 (supplier form), Task 22 (dashboard)
- After backend 1-3 done → Agent A: Task 4 → Task 5 → Task 6

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

## V1f — Frontend UX Overhaul

> **Parallel with V1a.** Tasks 20-22 have NO backend dependency and can start immediately after V0 Cleanup. Task 23 (OPS Product Config) needs OPS API credentials. This is intern-friendly work — assign to Sinchana, Urvashi, Vidhi.

**Goal:** Make the UI user-friendly for non-technical users. Remove all jargon, simplify the supplier setup from 5 steps to 3, add help text everywhere, and create a new OPS Product Configuration page.

### Task 20: Terminology + Loading States + Sidebar Rename
**Modify:** All frontend pages + `layout.tsx` / `Sidebar.tsx`
**Can parallel with:** Tasks 21, 22, and ALL of V1a
**No backend changes.**
**Description:** Global find-and-replace of technical jargon with business language. This is the single highest-impact UX change — every page becomes less intimidating.

**Terminology map:**

| Current (Technical) | New (Business) | Files |
|---------------------|----------------|-------|
| "Vendors" | "Suppliers" | `page.tsx` (dashboard) |
| "Technical Index" | "Product Catalog" | `products/page.tsx` |
| "Customers" | "Storefronts" | `customers/page.tsx`, sidebar |
| "Push to OPS" | "Publish to Store" | `products/[id]/page.tsx` |
| "Sync Jobs" | "Data Updates" | `sync/page.tsx`, sidebar |
| "Markup Rules" | "Pricing Rules" | `markup/page.tsx`, sidebar |
| "Field Mappings" | "Data Configuration" | `mappings/page.tsx`, sidebar |
| "_QUERYING_INDEX..." | "Loading products..." | all pages |
| "_QUERYING_ENDPOINT_REGISTRY..." | "Connecting..." | all pages |
| "_FETCHING_METRICS..." | "Loading dashboard..." | dashboard |
| "Auth_Error" | "Connection Failed" | all status badges |
| "delta" | "Recent Changes" | sync page |
| "full_sync" | "Full Refresh" | sync page |
| "SOAP / WSDL" | Hidden entirely | supplier form |

**Sidebar sections:**
- "Orchestration" → "Products"
- "Management" → "Configuration"
- "Catalog" → "Product Catalog"
- "Customers" → "Storefronts"
- "Markup Rules" → "Pricing Rules"
- "Sync Jobs" → "Data Updates"
- "Field Mapping" → "Data Configuration"
- Remove duplicate "Add Supplier" from Actions section
- Add "Product Setup" link (for Task 23 OPS config page)

**Empty states for every page:**
- Products: "No products yet. Connect a supplier to start syncing products."
- Storefronts: "No storefronts added. Add your OnPrintShop storefront to start publishing."
- Data Updates: "No sync history yet. Activate a supplier to see updates here."
- Pricing Rules: "No pricing rules set. Add a rule to control storefront pricing."

### Task 21: Simplified Add Supplier Form
**Modify:** `frontend/src/components/suppliers/reveal-form.tsx`, `frontend/src/app/suppliers/page.tsx`
**Can parallel with:** Tasks 20, 22, and ALL of V1a
**No backend changes.**
**Description:** Rewrite the 5-step progressive reveal form into a clean 3-step flow with zero jargon.

**Current flow (too complex):**
1. Choose protocol (PromoStandards / REST / HMAC) — jargon
2. Select supplier OR enter custom name + URL — confusing dual mode
3. Enter credentials ("Account ID / Username" + "Password") — vague labels
4. Test connection — shows "11 active services" (meaningless)
5. Set sync schedule (4 separate dropdowns) — technical

**New flow (3 steps):**

**Step 1: "Choose your supplier"**
- Search bar: "Search 994+ suppliers..."
- Grid of popular suppliers with logos: SanMar, S&S Activewear, Alphabroder, 4Over
- "Can't find yours? Add a custom supplier" link at bottom
- **PromoStandards path:** Protocol auto-detected from PS directory — user just picks a name, system knows it's SOAP
- **Custom supplier path:** Name + API URL + simplified API type dropdown:
  - "Standard API" (maps to `rest` protocol — for S&S-style REST APIs)
  - "Secure API (signed requests)" (maps to `rest_hmac` — for 4Over-style HMAC APIs)
  - No mention of SOAP/WSDL/HMAC — just business-friendly labels
  - Help text: "Not sure? Choose 'Standard API' — your supplier's documentation will tell you if signed requests are needed."

> **Design note:** Auto-detecting REST vs REST+HMAC is impossible without user input — HMAC signing is an auth mechanism, not something visible from a URL. The dropdown is the minimum viable input to route to the correct protocol adapter.

**Step 2: "Connect your account"**
- Labels: "API Username" and "API Password" (clear, simple)
- Help text: "Your supplier provides these when you sign up for API access. Contact [SanMar] support if you don't have them."
- "Test Connection" button
- Success: "Connected to SanMar — 994 products available" (one line, no service listing)
- Failure: "Could not connect. Please check your username and password." + "Try Again" button

**Step 3: "Activate"**
- Summary card showing: supplier name, connection status, product count
- Single dropdown: "How often should we check for updates?" — "Recommended (automatic)" / "Every 30 minutes" / "Every hour" / "Once a day"
- Smart defaults behind the scenes (inventory=30min, pricing=daily, products=daily delta, images=weekly)
- "Activate Supplier" button → success state → redirect to suppliers list

### Task 22: Dashboard Wired to Real API + Business Language
**Modify:** `frontend/src/app/page.tsx`
**Can parallel with:** Tasks 20, 21, and ALL of V1a
**No backend changes** (endpoints already exist).
**Description:** Replace hardcoded demo data with real API calls. Rename all technical labels.

**Changes:**
- Stat cards: `api<Stats>("/api/stats")` → shows real supplier/product/variant counts
- Recent activity table: `api("/api/sync-jobs?limit=5")` → shows real sync history
- Rename "Recent Pipeline Activity" → "Recent Data Updates"
- Rename operation names: "inventory_sync_v2" → "Inventory Update", "delta_product_ingest" → "Product Sync", "push_to_ops" → "Published to Store"
- Remove hardcoded baselines (32.4k SKUs, 187k variants, 98% uptime)

---

## V1g — Storefront Configuration (extracted from V1f)

> **WARNING: This is a major new feature, NOT a UX polish task.** It was originally Task 23 inside V1f but was extracted into its own phase because it requires: (1) a new backend module to proxy the OPS API, (2) handling OPS OAuth2 token refresh, rate limits, and caching of complex nested JSON, (3) OPS API credentials, and (4) V1c to be working (OPS push pipeline must be proven before building a config UI on top of it).

### Task 23: OPS Storefront Product Configuration Page
**Create:** `frontend/src/app/products/configure/page.tsx` + components
**Create:** `backend/modules/ops_config/` — new backend module
**Depends on:** V1c (OPS push working) + OPS API credentials (Client ID + Secret) + OPS Postman collection for response shapes
**Cannot start until:** V1c Tasks 9-13 are complete and at least one product has been successfully pushed to OPS
**Description:** New page showing all OPS product options available via the API. Users configure how products appear in OPS storefronts BEFORE publishing. Three sections:

**Section A: Product Categories**
- Fetches OPS categories via API (getCategories)
- Assign categories to synced products: "Which category should SanMar T-Shirts go into?"
- Auto-suggest based on supplier product types

**Section B: Product Options & Attributes**
- Shows OPS master options: Color, Size, Material, Paper Type, Coating, etc.
- Visual mapping editor: "SanMar 'Navy' → OPS Color 'Navy Blue'"
- Option rules: "If Paper = Glossy, then available Coatings: Matte, UV, Lamination"
- Status per product: Configured / Needs Mapping / Not Applicable

**Section C: Pricing Preview**
- Base price from supplier → markup applied → final storefront price
- Live preview: "SanMar PC61 base $3.99 → 45% markup → $5.79 → rounded to $5.99"
- Option-level pricing: "Add $2.00 for XL", "Add $1.50 for premium colors"
- Links to Pricing Rules page for rule management

**Data flow:**
```
OPS API (via backend proxy)     Frontend
┌─────────────────────┐       ┌────────────────────────┐
│ getCategories       │──────▶│ Category assignment     │
│ getMasterOptions    │──────▶│ Options mapping         │
│ getOptionPrices     │──────▶│ Pricing preview         │
│ getProductDetailed  │──────▶│ Product config status   │
└─────────────────────┘       └────────────────────────┘
                                        │
                              User configures mappings
                                        │
                              Saved to DB → n8n reads
                              when pushing to OPS
```

**Backend endpoints needed:**
- `GET /api/ops/{customer_id}/categories` — proxy/cache OPS categories
- `GET /api/ops/{customer_id}/master-options` — proxy/cache OPS options
- `POST /api/ops-config/{customer_id}/product/{product_id}` — save product config

**Files to create:**
- `frontend/src/app/products/configure/page.tsx`
- `frontend/src/components/products/category-assign.tsx`
- `frontend/src/components/products/options-mapping.tsx`
- `frontend/src/components/products/pricing-preview.tsx`
- `backend/modules/ops_config/__init__.py`
- `backend/modules/ops_config/routes.py`
- `backend/modules/ops_config/models.py`
- `backend/modules/ops_config/schemas.py`

---

## Team Assignment — Current Sprint

> Detailed task files with full code and step-by-step instructions: [`plans/tasks/`](tasks/)

### Sinchana — 4 tasks ([full details](tasks/sinchana-tasks.md))

| Task | What | Phase | Priority |
|------|------|-------|----------|
| **0.3** | Install shadcn/ui | V0 Cleanup | **DO FIRST** — blocks all frontend |
| **20** | Terminology + sidebar rename (all jargon → business language) | V1f | After 0.3 |
| **21** | Rewrite supplier form from 5 steps to 3 | V1f | After 20 |
| **2** | PromoStandards response Pydantic schemas | V1a | Parallel with Urvashi's Task 1 |

### Urvashi — 5 tasks ([full details](tasks/urvashi-tasks.md))

| Task | What | Phase | Priority |
|------|------|-------|----------|
| **0.1** | Fix PostgreSQL port (5434→5432) | V0 Cleanup | **DO FIRST** — backend broken |
| **0.2** | Fix load_dotenv path (backend/.env → repo root) | V0 Cleanup | Right after 0.1 |
| **22** | Wire dashboard to real /api/stats + /api/sync-jobs | V1f | After 0.1+0.2 |
| **1** | Schema updates (unique constraints, ProductImage, category) | V1a | Parallel with Sinchana's Task 2 |
| **5** | Sync trigger endpoints (POST /api/sync/{id}/products) | V1a | After Tasks 1+2+3+4 all merged |

### Vidhi — 3 tasks ([full details](tasks/vidhi-tasks.md))

| Task | What | Phase | Priority |
|------|------|-------|----------|
| **0.4** | Customers (Storefronts) page — list + add form | V0 Cleanup | After Sinchana's 0.3 |
| **0.5** | Workflows page — pipeline visualizer | V0 Cleanup | After 0.4 |
| **3** | WSDL Resolver (resolver.py) — maps PS service types to WSDL URLs | V1a | Parallel with Tasks 1+2 |

### Tanishq — 3 tasks + PR reviews ([full details](tasks/tanishq-tasks.md))

| Task | What | Phase | Priority |
|------|------|-------|----------|
| **3b** | SOAP Client (client.py) — zeep integration, the complex part | V1a | After Tasks 2+3 merged |
| **4** | Normalizer — PS data → DB upserts | V1a | After Tasks 1+2+3 merged |
| **6** | E2E Verification — real SanMar data test | V1a | After Task 5 + SanMar creds |

Plus: review all intern PRs, chase Christian for credentials.

### Sprint Execution Timeline

```
Week 1: V0 Cleanup (all interns) + V1f (Sinchana, Urvashi)
         Tanishq reviews PRs, starts Task 3b when Tasks 2+3 are merged

         Sinchana: 0.3 → 20 → 21 → 2
         Urvashi:  0.1 → 0.2 → 22 → 1
         Vidhi:    0.4 → 0.5 → 3
         Tanishq:  reviews → 3b

Week 2: V1a core pipeline
         Tanishq: 4 (normalizer, needs 1+2+3 done)
         Urvashi: 5 (sync routes, needs 4 done)
         Tanishq: 6 (E2E verify, needs 5 + SanMar creds)
```

### Future phases (not assigned yet)

| Phase | Tasks | Notes |
|-------|-------|-------|
| V1b Task 7 | Alphabroder (zero code) | Anyone — just a DB row |
| V1b Task 8 | S&S REST adapter | Urvashi |
| V1c Tasks 9-13 | OPS Push (n8n node + markup + workflow) | Tanishq — TypeScript + core logic |
| V1d Tasks 14-16 | 4Over adapter | Vidhi |
| V1e Tasks 17-19 | n8n workflows + dashboard | Any dev |
| V1g Task 23 | OPS Storefront Config | Tanishq + Vidhi — after V1c works |

---

## Blockers Tracker

| Blocker | Needed For | Owner | Status |
|---------|-----------|-------|--------|
| SanMar API credentials | V1a Task 6 E2E test | Christian → Tanishq | Waiting |
| S&S API credentials | V1b Task 8 | Christian → Tanishq | Waiting |
| 4Over API credentials | V1d Task 14 | Christian → Tanishq | Waiting |
| **OPS Postman collection export** | **V1c Task 10 + V1g Task 23** | **Tanishq (export from browser)** | **Waiting** |
| n8n-nodes-onprintshop P0 fixes | V1c Task 9 | Tanishq | Not started |
| OPS custom dev requests | V1c if OPS needs new endpoints | Christian | Waiting |
| OPS API credentials (Client ID + Secret) | V1g Task 23 (storefront config) | Christian → Tanishq | Waiting |
| shadcn/ui installation | All remaining frontend + V1f | Sinchana | Not started |

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

**V1f:** Walk through every page as a non-technical user:
- Zero instances of SOAP, WSDL, HMAC, delta, OPS, or _QUERYING visible
- Add SanMar in 3 clicks (search → credentials → activate)
- Custom supplier form shows simplified API type dropdown (Standard API / Secure API) instead of protocol jargon
- Dashboard shows real stats, not hardcoded demo data
- Every page has helpful empty state with next action

**V1g:** Open storefront config page → see OPS categories, master options, pricing preview from real OPS API. Configure a product's category + option mappings. Verify config is saved and used by the push workflow.
- OPS product config page shows categories, options, pricing preview from real OPS API

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
