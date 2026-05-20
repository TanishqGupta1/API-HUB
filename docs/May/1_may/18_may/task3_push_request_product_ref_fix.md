# Task 3 — Fix Real Push Body: Product ID in Wrong Field

**Date:** 2026-05-15
**Author:** Vidhi
**Branch:** Vidhi
**Status:** Done locally, pending approval

---

## What type of task is this?

**Frontend** — one file, two lines changed.

---

## What was the problem?

Task 2 fixed the **dry-run** call to send `product_ref: { product_id: productId }` instead of `supplier_sku`. But the same bug existed in a second place — the actual **real push** call (when the admin clicks "Push" to confirm).

There were two separate issues in `frontend/src/lib/use-push-preview.ts`:

1. In `usePushRequest()` — the live mode body was still sending:
   ```typescript
   product_ref: { supplier_sku: args.supplierSku },
   ```
   This would cause "product not found" the moment a real push was attempted.

2. In the legacy `usePushExecute` alias — it was passing the UUID (`productId`) as `supplierSku`:
   ```typescript
   supplierSku: args.productId,  // UUID passed as supplier SKU — wrong
   ```
   Even if the rest of the code was fixed, this would send a UUID in the `supplierSku` argument, which would then be placed into `product_ref.supplier_sku`.

---

## How does this relate to the existing codebase?

**File:** `frontend/src/lib/use-push-preview.ts`

This file has two hooks:
- `usePushDryRun` — runs automatically on page load to show the preflight result (fixed in Task 2)
- `usePushRequest` — runs when the admin clicks "Push" to confirm

Both hooks build a `PushRequestBody` and POST it to the backend. The body must have `product_ref: { product_id: "<UUID>" }` — the backend looks up the product by its internal UUID. Sending the UUID in `supplier_sku` instead causes a product lookup failure.

The legacy `usePushExecute` alias wraps `usePushRequest` and is kept for backwards compatibility with older call sites. It was incorrectly passing `productId` as `supplierSku`.

---

## What changed and why

### Fix 1 — Real push body in `usePushRequest`
**File:** `frontend/src/lib/use-push-preview.ts`

**Before:**
```typescript
product_ref: { supplier_sku: args.supplierSku },
```

**After:**
```typescript
product_ref: { product_id: args.productId },
```

**Why:** The backend `product_ref` resolver checks `product_id` first (by UUID), then `supplier_sku`. The productId from the URL is a UUID — it belongs in `product_id`.

---

### Fix 2 — Legacy alias `usePushExecute`
**File:** `frontend/src/lib/use-push-preview.ts`

**Before:**
```typescript
supplierSku: args.productId,  // UUID was being passed as supplier SKU
```

**After:**
```typescript
supplierSku: "",  // deprecated alias, productId is already passed separately
```

**Why:** `usePushExecute` is a deprecated wrapper. The `productId` field is passed correctly. The `supplierSku` field in this alias was a copy-paste error — it was receiving the UUID and forwarding it as a supplier SKU (like "DT607"). Clearing it prevents the wrong value from reaching the request body. When real supplier SKU is needed, the caller should migrate to `usePushRequest` directly.

---

## What did NOT change

- No backend changes
- No environment variable changes
- Dry-run logic (already fixed in Task 2)
- Mock mode logic

---

## How can this be modified in the future?

Once the `usePushExecute` deprecated alias is no longer used anywhere, it can be deleted. The `supplierSku` argument in `PushRequestArgs` may also be removed if the backend fully resolves products by `product_id` only.

---

## Files changed

| File | Type | Change |
|------|------|--------|
| `frontend/src/lib/use-push-preview.ts` | Frontend | Fixed `product_ref` in real push body to use `product_id`; fixed deprecated alias passing UUID as supplier SKU |

---

---

# Milestone Plan T3 — Missing Fields Banner + Pricing & Inventory Fix

**Date:** 2026-05-18
**Author:** Vidhi
**Branch:** Vidhi
**Status:** Done

---

## What type of task is this?

**Frontend + Backend** — a banner added to an existing page and the import pipeline fixed to fetch real data.

---

## How does this relate to the existing codebase?

The milestone plan originally described T3 as building a separate `/products/{id}/preview` page. During implementation it became clear that the existing product detail page (`/products/[id]/page.tsx`) already showed everything that page would have — title, brand, image viewer, variants table, description. Building a separate page would have been pure duplication.

Instead, T3 was adapted to add the one thing that was genuinely missing from the detail page: a **missing fields banner** that tells the admin which fields are null before they attempt a push.

The banner calls the new `GET /api/products/{id}/preview` endpoint (built in T2) on page load, reads the `missing_fields[]` list from the response, and renders it. The endpoint already does all the checking work — the frontend just displays the result.

At the same time, investigating why products had so many missing fields revealed a deeper problem in the category import pipeline: the `_run_category_import` background task was fetching product data via PromoStandards SOAP but **never calling the pricing or inventory endpoints**. Both were passed as `None` to `upsert_products`. This meant every product imported via category import had `price = null` and `inventory = null` in the database — not just one product, but all of them. That was also fixed as part of this task.

---

## Why was it necessary?

**The banner:** Without it, an admin had no way to know a product was missing data until they clicked Push and the preflight failed — often with a confusing error message deep in the push log. The banner surfaces the problem immediately on the product detail page, before any push is attempted. The admin sees "14 missing fields — push may fail" and knows exactly what to fix before touching the Push button.

**The pricing + inventory fix:** A product with no price cannot be pushed to OPS — `setProductPrice` would have nothing to send. The entire SanMar push milestone was blocked by this gap. Every SanMar product in the database had `base_price = None` and `inventory = None` because the category import was calling `upsert_products(pricing=None, inventory=None)`. The PromoStandards client already had `get_pricing()` and `get_inventory()` methods built and tested — they just were never called during import. Wiring them in was the fix.

---

## What changed and why

### Frontend — `frontend/src/app/(admin)/products/[id]/page.tsx`

Three additions to the existing product detail page:

**1. New import:**
```typescript
import { AlertTriangle, CheckCircle2, Plus } from "lucide-react";
import type { ProductPreview } from "@/lib/types";
```

**2. New state:**
```typescript
const [missingFields, setMissingFields] = useState<string[]>([]);
```

**3. Fetch preview alongside product:**
```typescript
const [p, preview] = await Promise.all([
  api<Product>(`/api/products/${id}`),
  api<ProductPreview>(`/api/products/${id}/preview`).catch(() => null),
]);
setMissingFields(preview?.missing_fields ?? []);
```
The `.catch(() => null)` means if the preview endpoint fails for any reason, the product page still loads normally — the banner is best-effort, not load-critical.

**4. Banner in JSX** — rendered right below the source badge, above the product title:
- If `missing_fields.length > 0` → amber banner listing every missing field
- If `missing_fields.length === 0` → green banner "All required fields present — ready to push"

**What the banner shows:**
- Top-level fields: just the name — e.g. `· category`, `· images`, `· description`
- Per-variant fields: with identifier — e.g. `· price (variant 158413)`, `· inventory (variant NE200-S-Black)`

---

### Frontend — `frontend/src/lib/types.ts`

Two new TypeScript interfaces added (needed to type the preview API response):

```typescript
export interface VariantPreview {
  sku: string | null;
  size: string | null;
  color: string | null;
  price: number | null;
  inventory: number | null;
}

export interface ProductPreview {
  id: string;
  title: string;
  description: string | null;
  brand: string | null;
  category: string | null;
  images: ProductImage[];
  variants: VariantPreview[];
  missing_fields: string[];
}
```

---

### Backend — `backend/modules/suppliers/category_import.py`

**The core fix.** The `import_category` endpoint and `_run_category_import` background task were updated to fetch pricing and inventory from SanMar during every category import.

**In `import_category`:** Two new WSDL URLs resolved and passed to the background task:
```python
wsdl_pricing = resolve_wsdl_url(endpoints, "ppc")       # PricingAndConfiguration
wsdl_inventory = resolve_wsdl_url(endpoints, "inventory") # InventoryLevels
```

**In `_run_category_import`:** After fetching product data and before upserting, pricing and inventory are now fetched:
```python
# Before (broken)
await upsert_products(session, supplier_id, products,
    inventory=None, pricing=None, media=None, ...)

# After (fixed)
pricing_data = await pricing_client.get_pricing(product_ids)
inventory_data = await inventory_client.get_inventory(product_ids)
await upsert_products(session, supplier_id, products,
    inventory=inventory_data, pricing=pricing_data, media=None, ...)
```

Both fetches have individual `try/except` blocks — if pricing fails, inventory still runs and vice versa. The import never crashes because of a failed pricing or inventory call.

Job status messages (`job.error_log`) are updated during each phase so the UI shows progress:
- "Fetching pricing for N products..."
- "Fetching inventory for N products..."

---

### What was deleted

A standalone `/products/[id]/preview/page.tsx` was briefly created and then deleted. The decision: it duplicated the existing product detail page. The missing fields banner added to the existing page achieves the same goal without creating a second page to maintain.

---

## What did NOT change

- The existing `GET /api/products/{id}` endpoint — untouched
- The variants table, image viewer, branding section on the detail page — all untouched
- The push flow itself — no changes to gateway, ops_client, or preflight
- Products already in the DB — the fix applies to new imports. Existing products need a separate backfill run to populate their pricing and inventory

---

## How can this be modified in the future?

**Run a backfill for existing products.** All ~161 SanMar products currently in the DB were imported before this fix and still have `price = null`, `inventory = null`. A one-time backfill script can loop through all SanMar products, call `get_pricing()` + `get_inventory()` per SKU, and save the results. This would clear the missing fields banner for all existing products without re-importing them.

**Add more missing field checks.** The banner is driven entirely by `missing_fields[]` from the backend preview endpoint. Adding new checks (e.g. minimum image count, required description length) only requires changing the backend — the frontend banner automatically shows whatever the endpoint returns.

**Change the banner from warning to blocker.** Right now the banner is informational — it warns but does not prevent the admin from clicking Push. If the team wants a hard block, the "Publish to OPS" button could be disabled when `missingFields.length > 0`. This is a one-line frontend change.

**Parallel pricing + inventory fetch.** Currently pricing and inventory are fetched sequentially. For large imports (100+ products) this could be parallelised using `asyncio.gather()` to cut fetch time roughly in half.

---

## Files changed

| File | Type | Change |
|------|------|--------|
| `frontend/src/app/(admin)/products/[id]/page.tsx` | Frontend | Added `missingFields` state, parallel preview fetch, amber/green banner in JSX |
| `frontend/src/lib/types.ts` | Frontend | Added `VariantPreview` and `ProductPreview` interfaces |
| `backend/modules/suppliers/category_import.py` | Backend | Wired `get_pricing()` + `get_inventory()` into `_run_category_import`; passes real data to `upsert_products` |

---

## Manual Test Steps

### 1. Start servers
```bash
# Backend
cd /Users/Vidhi/apihub/backend && source .venv/bin/activate
uvicorn main:app --reload --port 8000

# Frontend
cd /Users/Vidhi/apihub/frontend && npm run dev
```

### 2. Open any SanMar product
```
http://localhost:3000/products/{any-product-uuid}
```

### 3. What to check on the banner
- If product has missing fields → amber banner appears below the source badge, lists each missing field
- If all fields present → green banner "All required fields present — ready to push"
- Banner does not block page load if backend is slow or returns an error

### 4. Test the pricing + inventory fix
Run a fresh category import for any SanMar category via the Data Updates page. After the import completes, open any product from that category — the variants table should show real prices and inventory values, and the banner should show fewer or zero missing fields.

### 5. Verify the banner reflects real data
```bash
curl http://127.0.0.1:8000/api/products/{product-id}/preview | python3 -m json.tool
```
Check that `missing_fields` matches what the banner shows on screen.

---

## What is next

**Backfill** — run pricing + inventory sync for all existing SanMar products already in the DB so their banners clear. Then move to T4 (wiring the real OpsClient into the push gateway).
