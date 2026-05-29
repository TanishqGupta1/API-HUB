# Task 2 — Turn Off Mock Mode in the Push Pipeline

**Date:** 2026-05-15
**Author:** Vidhi
**Branch:** Vidhi
**Status:** Done locally, pending approval

---

## What type of task is this?

**Frontend + Backend — connecting the push pipeline to real OPS.**

---

## What was the problem?

The Push page — where admin reviews a product and clicks "Push to OPS" — was completely fake. When you clicked Push, nothing went to OPS. The page returned hardcoded dummy data. There was even a "mock mode" badge on the page.

This was done on purpose during development so the UI could be built without a working backend. That phase is now done. The backend push pipeline exists and is ready. Mock mode needed to be turned off.

---

## How does this relate to the existing codebase?

**File:** `frontend/src/lib/use-push-preview.ts`

This file controls the push page. One flag decides everything:

```typescript
const LIVE_MODE = process.env.NEXT_PUBLIC_PHASE8_LIVE === "true";
export const IS_MOCK_MODE = !LIVE_MODE;
```

When mock mode is on — every push call returns fake fixture data from `push-fixtures.ts`.
When mock mode is off — every push call goes to the real backend.

**File:** `frontend/.env.local`

The variable was commented out — defaulting to mock mode:
```
# NEXT_PUBLIC_PHASE8_LIVE=true        ← was commented out
# NEXT_PUBLIC_PHASE8_ADMIN_PROXY=true ← was commented out
```

---

## What changed and why

### Fix 1 — Turn on live mode
**File:** `frontend/.env.local`

```
NEXT_PUBLIC_PHASE8_LIVE=true
NEXT_PUBLIC_PHASE8_ADMIN_PROXY=true
```

`NEXT_PUBLIC_PHASE8_LIVE=true` — switches push page from fake data to real backend calls.

`NEXT_PUBLIC_PHASE8_ADMIN_PROXY=true` — tells frontend to use JWT auth (logged-in admin) instead of requiring a manual integration key. So any logged-in admin can push directly from the UI.

---

### Fix 2 — CORS header missing
**File:** `backend/main.py`

**Before:**
```python
_CORS_HEADERS = ["Authorization", "Content-Type", "X-Ingest-Secret"]
```

**After:**
```python
_CORS_HEADERS = ["Authorization", "Content-Type", "X-Ingest-Secret", "Idempotency-Key"]
```

**Why:** The push page sends an `Idempotency-Key` header with every request. The browser first sends a CORS preflight OPTIONS request asking "is this header allowed?" The backend was returning 400 because `Idempotency-Key` was not in the allowed headers list. This meant every push request was blocked before it even reached the backend. Adding it to the list fixed the block.

**What is Idempotency-Key?** It is a unique ID sent with each push request so that if the same request is sent twice (for example, user clicks Push twice by mistake), the backend recognizes it as a duplicate and does not create two pushes.

---

### Fix 3 — Product ID sent as wrong field
**File:** `frontend/src/lib/use-push-preview.ts`

**Before:**
```typescript
product_ref: { supplier_sku: productId }, // TODO: resolve supplier_sku
```

**After:**
```typescript
product_ref: { product_id: productId },
```

**Why:** The `productId` from the URL is a UUID (like `70dd89af-fa28-4d49-bc79-264ae00523d7`). The code was sending this UUID in the `supplier_sku` field. The backend then searched for a product with `supplier_sku = "70dd89af..."` which obviously does not exist. The actual supplier SKU is something like `DT607`. The fix was to send it in the correct field — `product_id` — which is what it actually is.

---

### Fix 4 — `[object Object]` in DATA SOURCES
**File:** `frontend/src/app/(admin)/products/[id]/page.tsx`

**Before:**
```typescript
return Object.entries(mappings).map(([source, target]) => [
  String(target),
  ...
]);
```

**After:**
```typescript
const rows = Object.entries(mappings)
  .filter(([, target]) => typeof target === "string" || typeof target === "number")
  .map(...)
return rows.length > 0 ? rows : DEFAULT_DATA_SOURCES;
```

**Why:** The supplier's `field_mappings` in the database contained nested objects as values (not simple strings). When JavaScript tries to display an object as text, it shows `[object Object]`. The fix filters out any non-string values before displaying. If nothing is left after filtering, it falls back to the default data sources list so the section is never empty.

---

## What the preflight revealed

Once live mode was on and the fixes were applied, the preflight ran against a real product (DT607 - District Mesh Back Cap) and returned this:

| Check | Result | Meaning |
|-------|--------|---------|
| `base_price_set` | ❌ | 5 variants have no price — pricing sync has not run |
| `markup_rule_resolves` | ❌ | No markup rule for this customer — needs to be created |
| `ops_oauth2_reachable` | ❌ | OPS token URL is `http://ops.test` — fake URL, not real OPS |
| `image_urls_reachable` | ❌ | No images on this product — image sync has not run |
| `push_mappings_present` | ✅ | No options to map — fine |
| `customer_ops_creds_present` | ✅ | OPS credentials are stored |
| `required_fields` | ✅ | Product name and SKU exist |
| `decoration_attached` | ✅ | Not required |

These are not code bugs. They are missing data and configuration. A real push cannot complete until:
1. Real OPS credentials are configured (needs lead / Christian)
2. Pricing sync is run for the product
3. A markup rule is created for the customer

---

## What did NOT change

- The backend push pipeline — already existed, not rebuilt
- The OPS client — already existed
- The Integration Gateway endpoint — already existed
- The fixture file (`push-fixtures.ts`) — still there, can be removed later

---

## How can this be modified in the future?

Once the full SanMar → OPS push is stable and tested:
- `NEXT_PUBLIC_PHASE8_LIVE=true` can be permanently set
- The mock mode code path and fixture file can be deleted
- `IS_MOCK_MODE` checks throughout the codebase can be removed
- This simplifies the push hook significantly

---

## Files changed

| File | Type | Change |
|------|------|--------|
| `frontend/.env.local` | Frontend config | Uncommented live mode and admin proxy variables |
| `backend/main.py` | Backend | Added `Idempotency-Key` to CORS allowed headers |
| `frontend/src/lib/use-push-preview.ts` | Frontend | Fixed `product_ref` to send `product_id` not `supplier_sku` |
| `frontend/src/app/(admin)/products/[id]/page.tsx` | Frontend | Fixed `[object Object]` in DATA SOURCES + fallback to defaults |

---

## Manual Test Steps

### 1. Start both servers
```
Backend:  http://localhost:8000
Frontend: http://localhost:3000
```

### 2. Log in
- Email: `admin@apihub.com`
- Password: `Admin@123456`

### 3. Go to the push preview page
```
http://localhost:3000/products/70dd89af-fa28-4d49-bc79-264ae00523d7/push?customer_id=ca447265-2c0c-4c1e-8109-f6bc34379d54
```

### 4. What to check
- No "mock mode" badge on the page ✅
- Page shows a real preflight result with specific blockers ✅
- Blockers show real issues: missing price, missing markup rule, fake OPS URL ✅

### 5. Go to product page and check DATA SOURCES
```
http://localhost:3000/products/70dd89af-fa28-4d49-bc79-264ae00523d7
```
- DATA SOURCES section shows real rows — no `[object Object]` ✅

---

## What is needed to complete a real push

These are NOT code tasks — they require real credentials and configuration:

| What | Who |
|------|-----|
| Real OPS base URL and token URL | Lead / Christian |
| Real OPS client ID and client secret | Lead / Christian |
| Run pricing sync for SanMar products | Can be done once creds are in |
| Create markup rule for customer | Admin UI → Pricing Rules |

---

---

# Milestone Plan T2 — Product Preview Backend Endpoint

**Date:** 2026-05-18
**Author:** Vidhi
**Branch:** Vidhi
**Status:** Done

---

## What type of task is this?

**Backend only — new API endpoint.**

---

## How does this relate to the existing codebase?

The project already had a `GET /api/products/{id}` endpoint in `backend/modules/catalog/routes.py`. That endpoint returns everything about a product — variants, images, options, apparel details, sizes, print details, and more. It was built for the product detail page in the admin UI, which needs all of that data to render the full configuration screen.

But the preview page has a different job. It is not a configuration screen. It is a read-only summary that answers one question: "Is this product ready to be pushed to OPS?" For that job, the full `GET /api/products/{id}` response is too much — it has fields the preview does not need, and it is missing the one thing the preview does need: a `missing_fields` list.

So T2 adds a second, lighter endpoint on top of the same database table. It reuses the same `Product` model and the same `ProductVariant` and `ProductImage` models that already exist in `backend/modules/catalog/models.py`. No new database tables. No new migrations. Just a new query and a new response shape.

The new schemas (`VariantPreview`, `ProductPreview`) were added to the existing `backend/modules/catalog/schemas.py` file, which is where all catalog-related Pydantic models live. The new route was added to the existing `backend/modules/catalog/routes.py` file, which is registered in `backend/main.py` under `/api/products`.

---

## Why was it necessary to add?

Before this task, there was no way for the frontend to know which fields were missing on a product before pushing it to OPS. The push pipeline has a preflight check that also catches missing data — but that only runs when you actually try to push. By that point the admin has already clicked a button and is waiting for a result.

The preview endpoint solves this earlier in the journey. The admin opens the preview page, sees a clear list of what is missing (for example: "description is empty", "3 variants have no price"), and can fix those issues before ever touching the Push button. This avoids unnecessary push attempts that are guaranteed to fail.

There is also a practical reason. The OPS push pipeline is the most complex part of the system — it calls multiple GraphQL mutations in sequence, each depending on the result of the previous one. Running it against a product with missing data wastes time, produces confusing error messages, and can leave partial state in OPS. The preview endpoint is a cheap read-only check that acts as a first line of defence.

---

## What was the problem?

The milestone plan (T2) required a dedicated `GET /api/products/{id}/preview` endpoint that returns a clean, frontend-friendly product shape plus a `missing_fields[]` list — so the admin can see exactly what data is present or absent before pushing a product to OPS.

The existing `GET /api/products/{id}` endpoint already returns full product data but in a raw DB-mapped shape (`product_name`, `base_price`, nested relations like `apparel_details`, `options`, etc). The preview endpoint needs:
- Renamed fields (`title` instead of `product_name`, `price` instead of `base_price`)
- Only the fields relevant to a push preview (no options, no apparel_details overhead)
- A `missing_fields[]` list that tells the frontend exactly which fields are null or empty

---

## What changed and why

### New schemas — `backend/modules/catalog/schemas.py`

Two new Pydantic models added at the bottom of the file:

```python
class VariantPreview(BaseModel):
    sku: Optional[str]
    size: Optional[str]
    color: Optional[str]
    price: Optional[float]
    inventory: Optional[int]


class ProductPreview(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    brand: Optional[str]
    category: Optional[str]
    images: list[ProductImageRead]
    variants: list[VariantPreview]
    missing_fields: list[str]
```

`VariantPreview` uses clean field names (`price` not `base_price`) so the frontend does not need to know internal DB column names.

`ProductPreview` returns only what the preview page needs — no options, no apparel_details, no print_details, no sizes. Lighter and purpose-built.

---

### New route — `backend/modules/catalog/routes.py`

`GET /api/products/{product_id}/preview` added after the existing `get_product` route.

**What it does:**
1. Loads the product from DB with only `variants` and `images` eager-loaded (skips options, apparel_details — not needed for preview)
2. Checks each of the following and appends to `missing_fields[]` if null/empty:
   - `title` — product_name is null or empty
   - `description` — description is null or empty
   - `brand` — brand is null or empty
   - `category` — category is null or empty
   - `images` — no images at all
   - Per variant: `sku`, `price`, `inventory` — each checked individually with the variant identifier in the message
3. Returns a `ProductPreview` response

**Missing field messages format:**
- Top-level fields: just the field name — e.g. `"description"`, `"brand"`
- Variant-level fields: include identifier — e.g. `"price (variant DT607-S-Black)"`, `"sku (variant White XL)"`

**Example response:**
```json
{
  "id": "70dd89af-...",
  "title": "District Re-Tee",
  "description": null,
  "brand": "District",
  "category": "T-Shirts",
  "images": [...],
  "variants": [
    { "sku": "DT607-S-Red", "size": "S", "color": "Red", "price": null, "inventory": 120 }
  ],
  "missing_fields": [
    "description",
    "price (variant DT607-S-Red)"
  ]
}
```

---

## Files changed

| File | Type | Change |
|------|------|--------|
| `backend/modules/catalog/schemas.py` | Backend | Added `VariantPreview` and `ProductPreview` schemas |
| `backend/modules/catalog/routes.py` | Backend | Added `GET /{product_id}/preview` route + imported new schemas |

---

## What did NOT change

- The existing `GET /api/products/{id}` endpoint — untouched, still used by the product detail page
- The DB models — no changes
- The frontend — T3 (the preview page) is the next task

---

## How can this be modified in the future?

**Add more missing field checks.**
Right now the endpoint checks title, description, brand, category, images, and per-variant sku/price/inventory. As the OPS push pipeline grows, more fields may become required — for example a minimum number of images, or a specific image type like "front". Those checks can be added to the `missing` list in the route without changing the response shape at all.

**Add a readiness score.**
Instead of just a list of missing fields, the endpoint could also return a score like `readiness: 0.75` — meaning 75% of required fields are present. The frontend could show this as a progress bar so the admin gets a quick visual sense of how close the product is to being push-ready.

**Group missing fields by severity.**
Not all missing fields block a push equally. A missing description is a warning. A missing price is a hard blocker. The `missing_fields` list could be split into two lists — `blockers` and `warnings` — so the frontend can show them differently (red vs yellow).

**Cache the result.**
If the product catalog grows large, admins may open preview pages frequently. The preview response could be cached for a short time (30–60 seconds) using Redis or a simple in-memory cache, since product data does not change that often. This would make the preview page feel instant.

**Extend to other product types.**
Right now the missing field checks are written for apparel products (variants with size/color/price). If the system later supports print products or hard goods, the checks would need to be different — for example a print product might need `min_width` and `max_width` instead of variants. The route could branch on `product.product_type` to run the right set of checks.

---

## Manual Test Steps

### 1. Start the backend
```bash
cd /Users/Vidhi/apihub/backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

### 2. Call the endpoint
```bash
curl http://localhost:8000/api/products/{product_id}/preview | python3 -m json.tool
```
Replace `{product_id}` with a real product UUID from your DB.

### 3. What to check
- Response has `title`, `description`, `brand`, `category`, `images`, `variants`, `missing_fields`
- `missing_fields` lists any null/empty fields — e.g. `["description", "price (variant DT607-S-Red)"]`
- No `auth_config`, no `apparel_details`, no `options` in the response
- Returns 404 for a non-existent product ID

---

## What is next

**T3** — Build the frontend preview page at `/products/{id}/preview` that calls this endpoint and displays the result.
