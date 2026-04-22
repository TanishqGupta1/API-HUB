# Sinchana — Sprint Tasks

**Sprint:** OPS Push Pipeline + V1f UX Overhaul  
**Spec:** `docs/superpowers/specs/2026-04-22-remaining-tasks-design.md`  
**Reference:** `plans/2026-04-16-v1-integration-pipeline.md` Tasks 20 + 21  
**Branch per task:** `sinchana/<task-slug>` → one PR per task

---

## Overview

4 tasks. Frontend-only. Tasks 1 is a quick type addition; Tasks 2–4 are larger UX work for V1f. Do in priority order.

---

## Task 1 — `ProductPushLogRead` TypeScript Type (D1) ⚡ FIRST

**File:** `frontend/src/lib/types.ts` (modify — append)

Add this interface:

```ts
export interface ProductPushLogRead {
  id: string;
  product_id: string;
  customer_id: string;
  ops_product_id: string | null;
  status: "pushed" | "failed" | "skipped";
  error: string | null;
  pushed_at: string;
}
```

That's the full task. One PR. Ship fast — Vidhi's PushHistory component (D2) imports this type.

---

## Task 2 — Sync Dashboard Health View (V1e Task 19)

**Files:**
- `frontend/src/app/(admin)/sync/page.tsx` — modify (add filters + auto-refresh)
- `frontend/src/app/(admin)/page.tsx` — modify (add health summary section)

**Dashboard additions** (in `page.tsx` stats section):
- Per-supplier last sync time: green if < 1h, amber if < 24h, red if > 24h
- Sync health badge per supplier
- Latest failed sync with error preview (click to expand full message)

**Sync jobs page additions** (in `sync/page.tsx`):
- Filter row: by supplier (dropdown), by job type (`full_sync` / `inventory` / `pricing`), by status
- Show human-readable labels: `full_sync` → "Full Refresh", `inventory` → "Inventory Update", `delta` → "Recent Changes"
- Auto-refresh every 30s while any job has `status: "running"` (`setInterval` in `useEffect`, clear on unmount)
- Empty state: "No sync history yet. Activate a supplier to see updates here."

APIs already exist: `GET /api/sync-jobs`, `GET /api/suppliers`.

**Acceptance:** Dashboard shows per-supplier health. Sync page auto-refreshes. Filters work. Human-readable labels everywhere.

---

## Task 3 — Terminology Overhaul (V1f Task 20)

**Files:** All admin pages, `layout.tsx`, sidebar component

Global find-and-replace of jargon → business language. Full replacement map:

| Current (jargon) | Replace with | Files |
|---|---|---|
| "Vendors" | "Suppliers" | dashboard `page.tsx` |
| "Technical Index" | "Product Catalog" | `products/page.tsx` |
| "Customers" | "Storefronts" | `customers/page.tsx`, sidebar |
| "Push to OPS" | "Publish to Store" | product pages |
| "Sync Jobs" | "Data Updates" | `sync/page.tsx`, sidebar |
| "Markup Rules" | "Pricing Rules" | `markup/page.tsx`, sidebar |
| "Field Mappings" | "Data Configuration" | `mappings/page.tsx`, sidebar |
| `_QUERYING_INDEX...` | "Loading products..." | all pages |
| `_QUERYING_ENDPOINT_REGISTRY...` | "Connecting..." | all pages |
| `_FETCHING_METRICS...` | "Loading dashboard..." | dashboard |
| `Auth_Error` | "Connection Failed" | status badges |
| "delta" (job type label) | "Recent Changes" | sync page |
| "full_sync" (job type label) | "Full Refresh" | sync page |

**Sidebar sections** (find the sidebar nav component):
- "Orchestration" → "Products"
- "Management" → "Configuration"
- "Catalog" → "Product Catalog"
- "Customers" → "Storefronts"
- "Markup Rules" → "Pricing Rules"
- "Sync Jobs" → "Data Updates"
- "Field Mapping" → "Data Configuration"

**Empty states** — add to every page that can show an empty list:
- Products: "No products yet. Connect a supplier to start syncing products."
- Storefronts: "No storefronts added. Add your OnPrintShop storefront to start publishing."
- Data Updates: "No sync history yet. Activate a supplier to see updates here."
- Pricing Rules: "No pricing rules set. Add a rule to control storefront pricing."

Use the existing `EmptyState` component in `components/ui/empty-state.tsx` if it exists, otherwise a simple `<div>` with the blueprint text style.

**Acceptance:** Walk every admin page — zero instances of SOAP, WSDL, HMAC, OPS, delta, `_QUERYING` visible to the user. All empty states present.

---

## Task 4 — Simplified Supplier Form (V1f Task 21)

**Files:**
- `frontend/src/components/suppliers/reveal-form.tsx` — rewrite
- `frontend/src/app/(admin)/suppliers/page.tsx` — modify if needed

**Goal:** Replace the 5-step progressive reveal form with a clean 3-step flow. Zero SOAP/WSDL/HMAC jargon.

**Step 1 — "Choose your supplier"**
- Search input: "Search 994+ suppliers..."
- Popular supplier quick-pick grid: SanMar, S&S Activewear, Alphabroder, 4Over (with logos or just name cards)
- "Can't find yours? Add a custom supplier" toggle reveals:
  - Supplier name input
  - API URL input
  - Dropdown "Connection type":
    - "Standard API" (maps to `protocol: "rest"`)
    - "Secure API (signed requests)" (maps to `protocol: "rest_hmac"`)
  - Help text: "Not sure? Choose Standard API — your supplier's documentation will specify if signed requests are required."
- PromoStandards suppliers (from directory): auto-set `protocol: "promostandards"`, hide tech fields entirely

**Step 2 — "Connect your account"**
- "API Username" + "API Password" inputs (not "Account ID" / "auth_config")
- "Test Connection" button → calls existing supplier test endpoint
- Success state: "Connected to [SanMar] — ready to sync"
- Failure state: "Could not connect. Check your username and password." + "Try Again"

**Step 3 — "Activate"**
- Summary card: name, connection status
- Single sync frequency dropdown: "Recommended (automatic)" / "Every 30 minutes" / "Every hour" / "Once a day"
- "Activate Supplier" button → `POST /api/suppliers` → redirect to suppliers list

**Acceptance:** Walk the form as a non-technical user — no SOAP/WSDL/HMAC visible. Can add SanMar in 3 steps. Can add a custom supplier with the simplified type dropdown.

---

## Files You Own

- `frontend/src/lib/types.ts` — MODIFY (Task 1)
- `frontend/src/app/(admin)/sync/page.tsx` — MODIFY (Task 2)
- `frontend/src/app/(admin)/page.tsx` — MODIFY (Task 2, health section only)
- All admin pages + sidebar — MODIFY (Task 3, terminology only)
- `frontend/src/components/suppliers/reveal-form.tsx` — REWRITE (Task 4)
