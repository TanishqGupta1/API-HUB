# Sinchana — Sprint Tasks

**Sprint:** OPS Push Pipeline + V1f UX Overhaul  
**Spec:** `docs/superpowers/specs/2026-04-22-remaining-tasks-design.md`  
**Branch per task:** `sinchana/<task-slug>` → one PR per task

---

## Overview

4 sprint tasks + 2 SanMar tasks. Tasks 2, 3, 4 are already done — verified against codebase. Real work is Task 1 (quick type addition) and SanMar Task 1 (error handling branch in n8n workflow JSON).

---

## Task 1 — `ProductPushLogRead` TypeScript Type ⚡ FIRST

**File:** `frontend/src/lib/types.ts`  
**Effort:** XS — append at end of file (line 203)

`types.ts` currently ends at line 203 with `FieldMapping`. Append after the last interface:

```ts
/* ─── Push Log ───────────────────────────────────────────────────────────── */
export interface ProductPushLogRead {
  id: string;
  product_id: string;
  product_name: string | null;
  customer_id: string;
  customer_name: string | null;
  supplier_name: string | null;
  ops_product_id: string | null;
  status: "pushed" | "failed" | "skipped";
  error: string | null;
  pushed_at: string;
}
```

Note: backend `PushLogRead` schema has `product_name`, `customer_name`, `supplier_name` as optional joined fields — include them so the PushHistory component can display them without extra API calls.

Ship as a standalone PR. Vidhi's PushHistory component imports this type.

**Acceptance:** `import type { ProductPushLogRead } from "@/lib/types"` compiles without error in Vidhi's component.

---

## ✅ Task 2 — Sync Dashboard Health View — DONE

`frontend/src/app/(admin)/sync/page.tsx` already has:
- Filters by supplier, job type, status (lines 72–74)
- Auto-refresh every 5s while any job is running (line 103) + background refresh every 30s (line 114)
- Human-readable `JOB_TYPE_LABELS` map in `frontend/src/app/(admin)/page.tsx` (line 31)

`frontend/src/app/(admin)/page.tsx` already has per-supplier health badges with green/amber/red thresholds and expandable error messages.

No action needed.

---

## ✅ Task 3 — Terminology Overhaul — DONE

Sidebar (`SidebarNav.tsx`) already uses: "Storefronts", "Pricing Rules", "Data Configuration", "Data Updates", "Product Catalog", sections "Products" and "Configuration".

Grep across all admin pages for `_QUERYING`, `Auth_Error`, `Technical Index`, `Push to OPS`, `Sync Jobs`, `Markup Rules`, `Field Mapping` returns zero results — all already replaced.

Empty states already present on every page (products, customers/storefronts, sync, markup/pricing rules).

No action needed.

---

## ✅ Task 4 — Simplified Supplier Form — DONE

`frontend/src/components/suppliers/reveal-form.tsx` already has the full 3-step flow: Choose supplier (with popular grid + search + custom toggle) → Connect account (API username/password + test connection) → Activate (schedule dropdown + activate button).

SanMar is in the popular suppliers grid. The **only issue** is SanMar's protocol is set to `"promostandards"` instead of `"sftp"` — that's being fixed by Urvashi in her Task 8 (`reveal-form.tsx` line 14).

No action needed from Sinchana on this task.

---

## SanMar SFTP Tasks

**Spec:** `docs/superpowers/specs/2026-04-22-sanmar-sftp-integration-design.md`

---

### SanMar Task 1 — Error Handling Branch in Workflow JSON (W4)

**File:** `n8n-workflows/sanmar-sftp-pull.json`  
**Effort:** S  
**No backend changes. No blockers — can start now.**

The workflow currently has no error handling on the `POST /ingest/products` HTTP node (`http-002`). If a batch fails, the loop silently dies.

**How n8n error branches work in JSON:** Each node can have `onError: "continueErrorOutput"` set, which enables an error output pin. Connect a new Code node to that error output.

**Step 1 — open `sanmar-sftp-pull.json` and find the `http-002` node:**
```json
{
  "id": "http-002",
  "name": "POST /ingest/products",
  "type": "n8n-nodes-base.httpRequest",
  ...
}
```

**Step 2 — add `"onError": "continueErrorOutput"` to the http-002 node parameters.**

**Step 3 — add the Format Error Code node** (new entry in the `nodes` array):
```json
{
  "id": "code-error-001",
  "name": "Format Error",
  "type": "n8n-nodes-base.code",
  "typeVersion": 2,
  "position": [1400, 400],
  "parameters": {
    "jsCode": "const err = $input.first().json;\nreturn [{ json: {\n  event: 'sanmar_ingest_error',\n  batch_error: err.message || JSON.stringify(err),\n  timestamp: new Date().toISOString()\n}}];"
  }
}
```

**Step 4 — add the connection** from http-002's error output to Format Error. In the `connections` object, find the `"POST /ingest/products"` key and add an error output entry:
```json
"POST /ingest/products": {
  "main": [[{ "node": "...", "type": "main", "index": 0 }]],
  "error": [[{ "node": "Format Error", "type": "main", "index": 0 }]]
}
```

**Step 5 — add a Log Error HTTP node** after Format Error, posting the error to push-log:
```json
{
  "id": "http-error-log",
  "name": "Log Error",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "position": [1600, 400],
  "parameters": {
    "method": "POST",
    "url": "http://host.docker.internal:8000/api/push-log",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "Content-Type", "value": "application/json" }
      ]
    },
    "sendBody": true,
    "bodyParameters": {
      "parameters": [
        { "name": "status", "value": "failed" },
        { "name": "error", "value": "={{ $json.batch_error }}" }
      ]
    }
  }
}
```

Connect Format Error → Log Error in the `connections` object.

**Step 6 — import and verify in n8n:**
```bash
docker cp n8n-workflows/sanmar-sftp-pull.json api-hub-n8n-1:/tmp/sanmar-sftp-pull.json
docker exec api-hub-n8n-1 n8n import:workflow --input=/tmp/sanmar-sftp-pull.json
```

Open n8n at `http://localhost:5678` → find the SanMar SFTP workflow → confirm the error branch node appears connected to the POST /ingest node.

**Acceptance:** Workflow editor shows Format Error node connected to the error output of POST /ingest/products. Workflow imports without errors.

---

### SanMar Task 2 — Frontend E2E Verify (E2)

**Requires:**
- Tanishq: P1 (SanMar DB row), P2 (SFTP cred in n8n), P3 (env var), E1 (full workflow run)
- Urvashi Task 9: ✅ already done — products API already supports no-supplier filter

**Code change required** — update storefront to show all products, not just `vg-ops` supplier:

In `frontend/src/app/storefront/vg/page.tsx`, the current fetch (lines 19–23):
```ts
const sups = await api<{ id: string; slug: string }[]>("/api/suppliers");
const vg = sups.find((s) => s.slug === "vg-ops");
if (!vg) return;
const rows = await api<ProductListItem[]>(`/api/products?supplier_id=${vg.id}&limit=500`);
```

Replace with:
```ts
const rows = await api<ProductListItem[]>(`/api/products?limit=500`);
```

Remove the `sups` and `vg` variables entirely. The products API already supports no `supplier_id` (Urvashi Task 9 confirmed done).

Then open `http://localhost:3000/storefront/vg`. Confirm:
- SanMar products visible (brand badge shows "SanMar" in blue)
- Product images load (not broken — check browser network tab)
- Variant picker shows real colors + sizes
- Price block shows pricing
- Product detail page (`/storefront/vg/product/<id>`) loads without errors

If anything is broken after the code change, create a GitHub issue with a screenshot and the product ID.

---

## Files You Own

- `frontend/src/lib/types.ts` — MODIFY (Task 1, append ProductPushLogRead)
- `n8n-workflows/sanmar-sftp-pull.json` — MODIFY (SanMar Task 1, error branch)
- `frontend/src/app/storefront/vg/page.tsx` — MODIFY (SanMar Task 2, remove supplier filter)
