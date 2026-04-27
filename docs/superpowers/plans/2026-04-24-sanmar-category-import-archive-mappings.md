# Plan: SanMar Category Import + Per-Supplier Mappings + Product Archive

## Context

Next sprint: let users connect a SanMar account and pull products into the hub with real control. Today the SanMar SOAP client only fetches products by ID — there is no browseable category flow. The mappings page is per-supplier but limited to 12 canonical fields with no image previews, and the `/products` admin has no way to archive unwanted items. We need to close these gaps so an operator can: connect SanMar → browse categories → pick how many products to import → archive ones they don't want → configure per-supplier field mappings with visual confirmation.

**Why now:** SanMar catalog is ~100k products. Christian's meeting (2026-04-23) made clear OPS should not receive the full catalog — only what the customer curates. This plan builds the curation layer.

**Intended outcome:**
- SanMar SOAP client gets `get_categories` + `get_products_by_category` methods
- `/api/suppliers/{id}/categories` + `POST /api/suppliers/{id}/import-category` endpoints
- UI category picker with import-limit selector, triggered from supplier page
- Product archive (soft-delete via `archived_at` column) + `/products/archived` page
- Mappings page extended to show supplier-specific fields with image thumbnails

---

## Scope check

This is one coherent feature (SanMar import UX end-to-end) but three distinct subsystems. Delivered as one plan with phases — implementation teams can ship phases independently.

---

## Existing state (from exploration)

| Component | State | File |
|-----------|-------|------|
| SanMar SOAP client | 5 methods (products/inventory/pricing/media). NO category method | `backend/modules/promostandards/client.py:138-543` |
| SanMar docs | `getProductInfoByCategory` SOAP service exposed by SanMar | `sanmar/SanMar-Web-Services-Integration-Guide-24.3.pdf` p25-33 |
| Supplier connect flow | 3-step form, encrypts `auth_config`, no auto-sync | `frontend/src/components/suppliers/reveal-form.tsx:27-431` |
| Mappings page | Per-supplier, 12 canonical fields, JSONB preview | `frontend/src/app/(admin)/mappings/[supplierId]/page.tsx:1-306` |
| Product table | No archive column | `backend/modules/catalog/models.py:30-62` |
| Protocol dispatch | promostandards/rest/rest_hmac wired | `backend/modules/promostandards/routes.py:321-461` |
| Product schema | Already carries `master_attribute_id`, `attribute_key`, `price`, `setup_cost`, `multiplier` per option attribute | `backend/modules/catalog/schemas.py:31-41, 125-133` |

---

## Approach (5 phases)

### Phase 1 — SanMar SOAP: category + category-product methods

**File:** `backend/modules/promostandards/client.py`

Add two methods to `PromoStandardsClient`:

- `async def get_categories() -> list[PSCategoryData]` — calls SanMar's hardcoded category list (per Integration Guide; SanMar ships a fixed ~40-category list that's not a SOAP service — embed as a module constant).
- `async def get_products_by_category(category_name: str, limit: int = 50) -> list[PSProductData]` — calls `getProductInfoByCategory` SOAP service, returns first `limit` products.

Add Pydantic `PSCategoryData(name: str, ops_category_slug: str | None)` to `backend/modules/promostandards/schemas.py`.

**Tests:** `backend/tests/test_promostandards_categories.py` — FakeService harness (matches existing `test_promostandards_client.py` pattern at line 394). Verify wsVersion, correct SOAP operation name, deserialization.

**Reuse:** existing FakeService harness + `_client()` fixture in `backend/tests/test_promostandards_client.py`.

---

### Phase 2 — Backend endpoints for category-driven import

**Files:**
- Create: `backend/modules/suppliers/category_import.py` — service + routes
- Modify: `backend/modules/suppliers/routes.py` — register sub-router
- Create: `backend/tests/test_category_import.py`

**Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/suppliers/{id}/categories` | List SanMar categories (or upstream-supplier categories via its adapter) |
| POST | `/api/suppliers/{id}/import-category` | Trigger category import job. Body: `{category_name, limit}`. Returns `SyncJob` id |

Inside `import-category` handler:
1. Look up supplier, dispatch to protocol-appropriate adapter (reuses existing `if supplier.protocol in ...` pattern at `backend/modules/promostandards/routes.py:340`)
2. For SanMar SOAP: call `client.get_products_by_category(category_name, limit)` in background task
3. Normalize via existing PS normalizer → POST to `/api/ingest/{sid}/products` path (local call, not HTTP)
4. Return `SyncJob` immediately, n8n-style progress polling

**Reuse:**
- `SyncJob` model + `_create_job`/`_mark_job_running`/`_finish_job` helpers → `backend/modules/promostandards/routes.py:81-200`
- `upsert_products` → `backend/modules/promostandards/normalizer.py`
- `PromoStandardsClient` (already instantiated per supplier in `_run_full_product_sync`)

**Tests:** fake SOAP client, fake supplier row, verify job completes + products land in DB.

---

### Phase 3 — Frontend: category picker + import flow

**Files:**
- Create: `frontend/src/app/(admin)/suppliers/[id]/import/page.tsx` — new import page
- Modify: `frontend/src/app/(admin)/suppliers/page.tsx` — add "Import Products" button per supplier row
- Modify: `frontend/src/lib/types.ts` — add `Category` + `ImportJob` types
- Reuse: existing shadcn `Select`, `Button`, `Dialog`, `Input` components

**UI:**
```
/suppliers/[id]/import
├─ Header: "Import from {supplier.name}"
├─ Category dropdown (populated from GET /suppliers/{id}/categories)
├─ Image gallery (first 6 category-preview thumbnails from cached SanMar images)
├─ Import limit: number input (default 10, max 500)
├─ "Import" button → POST /suppliers/{id}/import-category
└─ Progress area: polls GET /api/sync-jobs/{job_id} until complete
```

Show category image tiles from a small seed map (SanMar's 40 categories ship known preview images via their CDN) OR pull first product's `image_url` per category. Start with first-product approach = no seed data needed.

**Reuse:**
- `api<T>(path, opts)` → `frontend/src/lib/api.ts`
- Existing progress bar pattern from `frontend/src/app/(admin)/sync/page.tsx`
- Blueprint design tokens (`#f2f0ed`, `#1e4d92`)

---

### Phase 4 — Product archive (soft-delete)

**Files:**
- Modify: `backend/modules/catalog/models.py` — add `archived_at: Mapped[Optional[datetime]]` column to `Product`
- Modify: `backend/modules/catalog/routes.py` — filter `archived_at IS NULL` by default; add `?archived=true` query param for archived view
- Create endpoint: `POST /api/products/{id}/archive` and `POST /api/products/{id}/restore`
- Modify: `backend/modules/catalog/schemas.py` — expose `archived_at` on `ProductListRead` + `ProductRead`
- Modify: `frontend/src/app/(admin)/products/page.tsx` — per-row "Archive" action + toggle to show archived
- Create: `frontend/src/app/(admin)/products/archived/page.tsx` — dedicated archived list

Add manual SQL migration in the plan (since project auto-creates via `Base.metadata.create_all` — new columns need ALTER on existing DB):
```sql
ALTER TABLE products ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITH TIME ZONE NULL;
CREATE INDEX IF NOT EXISTS idx_products_archived ON products(archived_at);
```

**Reuse:** existing ProductListRead response shape. Frontend uses existing `PushRowAction` pattern for per-row action buttons (just add Archive next to it).

---

### Phase 5 — Mappings page extension with supplier-specific fields + images

**Files:**
- Modify: `frontend/src/app/(admin)/mappings/[supplierId]/page.tsx` — extend canonical fields list + image tiles
- Modify: `backend/modules/suppliers/schemas.py` — extend `field_mappings` schema to accept supplier-specific config
- Create: `frontend/src/components/mappings/sanmar-mapping-panel.tsx` — SanMar-specific UI (category filter, color/size preview)

**Scope:**
- Keep existing 12 canonical fields as the base mapping UI
- Add per-supplier panel below base mapping:
  - **SanMar panel**: dropdown of discovered categories, checkbox to include images from Media service, color/size mapping (already in OptionAttributeIngest schema — expose in UI)
  - **OPS panel**: existing master_option_id / attribute_key mapping (already in schema lines 125-133)
  - **4Over panel**: empty stub placeholder
- Image thumbnails: render first 3 products' images inline next to the mapping form so user sees what their mapping will affect

**Reuse:**
- Existing `PUT /api/suppliers/{id}/mappings` endpoint
- `Supplier.field_mappings` JSONB column (already handles arbitrary JSON)
- Existing 12-field mapping UX — ADD new panel, do not replace

---

## Critical files modified

| File | Phase | Action |
|------|-------|--------|
| `backend/modules/promostandards/client.py` | 1 | Add `get_categories` + `get_products_by_category` methods |
| `backend/modules/promostandards/schemas.py` | 1 | Add `PSCategoryData` |
| `backend/tests/test_promostandards_categories.py` | 1 | New |
| `backend/modules/suppliers/category_import.py` | 2 | New — service + routes |
| `backend/modules/suppliers/routes.py` | 2 | Register sub-router |
| `backend/tests/test_category_import.py` | 2 | New |
| `frontend/src/app/(admin)/suppliers/[id]/import/page.tsx` | 3 | New |
| `frontend/src/app/(admin)/suppliers/page.tsx` | 3 | Add "Import Products" button |
| `frontend/src/lib/types.ts` | 3 | Add `Category`, `ImportJob` types |
| `backend/modules/catalog/models.py` | 4 | Add `archived_at` column |
| `backend/modules/catalog/routes.py` | 4 | Filter + archive/restore endpoints |
| `backend/modules/catalog/schemas.py` | 4 | Expose `archived_at` |
| `frontend/src/app/(admin)/products/page.tsx` | 4 | Per-row Archive + toggle |
| `frontend/src/app/(admin)/products/archived/page.tsx` | 4 | New |
| `frontend/src/app/(admin)/mappings/[supplierId]/page.tsx` | 5 | Extend with per-supplier panel |
| `frontend/src/components/mappings/sanmar-mapping-panel.tsx` | 5 | New |

## Reused utilities

- `PromoStandardsClient` SOAP harness — `backend/modules/promostandards/client.py`
- `SyncJob` helpers `_create_job`, `_mark_job_running`, `_finish_job` — `backend/modules/promostandards/routes.py:81-200`
- `upsert_products` normalizer — `backend/modules/promostandards/normalizer.py`
- Protocol-dispatch pattern — `backend/modules/promostandards/routes.py:340`
- FakeService test harness — `backend/tests/test_promostandards_client.py`
- `api<T>` helper — `frontend/src/lib/api.ts`
- Blueprint styling tokens — `frontend/src/app/globals.css`
- Per-row action pattern — `frontend/src/components/products/push-row-action.tsx`

## Out of scope (defer to future specs)

- Automatic sync scheduling after supplier connect (user still runs imports manually via UI)
- 4Over + S&S category import parity (pattern from SanMar is reusable; ship SanMar first)
- Bulk archive (single archive per click for MVP)
- Archive retention policy (archived forever until manually restored)
- Hierarchical category trees (SanMar is flat list; OPS has hierarchy but that's a separate spec)
- Real OPS push for category-imported products (existing demo-push-pipeline plan covers that)

## Verification

```bash
# Phase 1
docker compose exec -T api pytest tests/test_promostandards_categories.py -v
# Expected: categories method returns list of 40 SanMar categories; get_products_by_category returns products with real prices

# Phase 2
curl -s http://localhost:8000/api/suppliers/<sanmar_id>/categories | python3 -m json.tool | head -20
# Expected: ~40 category names
SID=<sanmar_id>
curl -s -X POST http://localhost:8000/api/suppliers/$SID/import-category \
  -H "Content-Type: application/json" \
  -d '{"category_name":"T-Shirts","limit":10}' | python3 -m json.tool
# Expected: {job_id: "...", status: "queued"}

# Phase 3
# Visit http://localhost:3000/suppliers/<sanmar_id>/import
# Pick "T-Shirts", limit 10, click Import. Progress bar completes. 10 products visible at /products.

# Phase 4
curl -s -X POST http://localhost:8000/api/products/<prod_id>/archive
curl -s "http://localhost:8000/api/products?archived=true" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))'
# Expected: archived product count matches; default list (without ?archived=true) shows 1 fewer
# Visit /products → archived row gone. /products/archived → shows archived product.

# Phase 5
# Visit /mappings/<sanmar_id>. Scroll below base fields — SanMar panel visible with category dropdown + 3 image thumbnails.
# Save → reload → config persists.

# Full regression
docker compose exec -T api pytest tests/ -v 2>&1 | tail -20
# Expected: all tests pass including phase 1 + phase 2 additions.
```

## Open questions (not blocking — sensible defaults locked)

1. **Category images** — use first product's `image_url` per category (no seed data). If SanMar docs mention a canonical category-image CDN path, swap later.
2. **Archive behavior on Product Options / Variants** — cascade not triggered (Product row kept, just marked archived). Variants + options remain intact for audit / restore.
3. **`getProductInfoByCategory` timeout fallback** — SanMar docs mention FTP fallback for timeouts. Skip for now; if users hit timeouts, separate ticket.
