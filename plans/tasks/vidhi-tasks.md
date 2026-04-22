# Vidhi — Sprint Tasks

**Sprint:** OPS Push Pipeline + V0 Frontend Cleanup  
**Spec:** `docs/superpowers/specs/2026-04-22-remaining-tasks-design.md`  
**Full code for every task:** `docs/superpowers/plans/2026-04-20-ops-push.md`  
**Branch per task:** `vidhi/<task-slug>` → one PR per task

---

## Overview

9 tasks. Highest load this sprint. Mix of TypeScript (n8n node), React (frontend components), and n8n workflow validation. Do in the priority order below — Task 1 is blocking the entire push pipeline.

---

## Priority Order

### Task 1 — Customers (Storefronts) Page ⚡ FIRST — blocks OPS push

**File:** `frontend/src/app/customers/page.tsx` (create)  
**Why urgent:** OPS push needs at least one customer row in the DB. Without this page, no one can add a storefront.

**What to build:**
- List all customers: name, `ops_base_url`, active/inactive toggle
- Inline add form: `name`, `ops_base_url`, `ops_token_url`, `ops_client_id`, `ops_client_secret`
- `ops_client_secret` is write-only — never display it after save
- API calls: `GET /api/customers`, `POST /api/customers`
- Use existing shadcn `Table`, `Card`, `Input`, `Button` components
- Blueprint design system: paper `#f2f0ed`, blue `#1e4d92`, same patterns as existing admin pages (see `suppliers/page.tsx` for reference)
- Label "Customers" → "Storefronts" everywhere on this page

**Acceptance:** Can add a new OPS storefront with credentials. Credentials save. Page lists all storefronts with active badge.

---

### Task 2 — `setProductSize` OPS Node Mutation (A3)

**File:** `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts`  
**Full step-by-step code:** `docs/superpowers/plans/2026-04-20-ops-push.md` → Task A3

Three steps:
1. Add option entry `setProductSize` in the product resource options array (after `setProductPrice`)
2. Add parameters block with `setProductSizeInput` JSON field (gated to `operation: ['setProductSize']`)
3. Add execute branch with mutation string `setProductSize($input: ProductSizeInput!)`

After: `cd n8n-nodes-onprintshop && npm run build` → `docker compose restart n8n`

**Acceptance:** n8n editor shows "Set Product Size" in the product resource dropdown. Node executes without TypeScript errors.

---

### Task 3 — `setProductCategory` OPS Node Mutation (A4)

**File:** `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts`  
**Full step-by-step code:** `docs/superpowers/plans/2026-04-20-ops-push.md` → Task A4

Same pattern as A3. Three steps:
1. Option entry: `setProductCategory`
2. Parameters: `setProductCategoryInput` JSON field
3. Execute branch: `setProductCategory($input: ProductCategoryInput!)`

Rebuild + restart n8n after.

**Acceptance:** "Set Product Category" appears in node. Builds clean.

---

### Task 4 — Update Gap Analysis Doc (A5)

**File:** `n8n-nodes-onprintshop/OPS-NODE-GAP-ANALYSIS.md`  
**Effort:** XS

In the "Missing Mutations" table, mark rows for `setProduct`, `setProductPrice`, `setProductSize`, `setProductCategory` as implemented. Move them to a new "Implemented" section at the bottom with the PR numbers.

---

### Task 5 — Combined n8n Smoke Test (A6)

**Requires:** Tasks 2 + 3 done and n8n running  
**No file to commit — manual test**

In n8n UI, build a throwaway workflow: Set Product Category → Set Product → Set Product Size → Set Product Price. Chain outputs (reference `products_id`, `category_id`, `product_size_id` from prior steps). Execute once. Capture the test product id and **delete it from OPS admin immediately after**. Report any schema mismatches to Tanishq.

---

### Task 6 — Verify `vg-ops-push.json` Workflow (C1)

**File:** `n8n-workflows/ops-push.json`

Open the file. Confirm it has all 9+ nodes matching the spec in `docs/superpowers/plans/2026-04-20-ops-push.md` Phase C:
- Manual trigger
- HTTP GET candidates
- Split products
- HTTP GET ops-input → setProduct
- HTTP GET ops-variants → setProductSize loop → setProductPrice loop
- POST push-log on success
- Error branch → POST push-log with `status: "failed"`

If nodes are missing or flow is wrong, fix the JSON. Import into n8n and verify it loads without errors:
```bash
docker cp n8n-workflows/ops-push.json api-hub-n8n-1:/tmp/ops-push.json
docker exec api-hub-n8n-1 n8n import:workflow --input=/tmp/ops-push.json
```

---

### Task 7 — `PushHistory` Component (D2)

**File:** `frontend/src/components/products/push-history.tsx` (create)  
**Full component code:** `docs/superpowers/plans/2026-04-20-ops-push.md` → Task D2

Table showing push history for a product. Fetches `GET /api/push-log?product_id={id}&limit=20`. Columns: When, Customer, Status (pill: green=pushed, red=failed, grey=skipped), OPS ID, Error.

Requires D1 (ProductPushLogRead type) from Sinchana — check if she's shipped it first. If not, define the interface inline and remove it when her PR lands.

---

### Task 8 — `PublishButton` + Wire into Product Detail (D3)

**Files:**
- `frontend/src/components/products/publish-button.tsx` (create)
- `frontend/src/app/(admin)/products/[id]/page.tsx` (modify)

**Full code:** `docs/superpowers/plans/2026-04-20-ops-push.md` → Task D3

Button with customer dropdown. On click: `POST /api/n8n/workflows/vg-ops-push-001/trigger?product_id=...&customer_id=...`. Shows status message. Links to n8n workflow editor.

Wire into product detail page with two new sections below existing content:
- "Push to storefront" section (PublishButton)
- "Push history" section (PushHistory from Task 7)

**Acceptance:** Product detail page shows the Publish button. Clicking it with a customer selected fires the n8n workflow. After ~15s, push history table shows a row.

---

### Task 9 — Workflows Page (V0 Task 0.5) — after Tasks 1–8

**File:** `frontend/src/app/workflows/page.tsx` (create)

Animated pipeline diagram: Supplier → Fetch → Normalize → Store → Push to OPS. Each node shows idle/running/done/error status. Link to n8n editor at `http://localhost:5678`. Mostly static for now — becomes live in V1e.

Lower priority — do after Tasks 1–8.

---

## Files You Own

- `frontend/src/app/customers/page.tsx` — NEW
- `frontend/src/app/workflows/page.tsx` — NEW
- `frontend/src/components/products/push-history.tsx` — NEW
- `frontend/src/components/products/publish-button.tsx` — NEW
- `frontend/src/app/(admin)/products/[id]/page.tsx` — MODIFY
- `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts` — MODIFY (Tasks 2+3)
- `n8n-nodes-onprintshop/OPS-NODE-GAP-ANALYSIS.md` — MODIFY (Task 4)
- `n8n-workflows/ops-push.json` — VERIFY/FIX (Task 6)
