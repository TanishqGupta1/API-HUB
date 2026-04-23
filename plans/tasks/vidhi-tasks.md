# Vidhi — Sprint Tasks

**Sprint:** OPS Push Pipeline + V0 Frontend Cleanup  
**Spec:** `docs/superpowers/specs/2026-04-22-remaining-tasks-design.md`  
**Full code reference:** `docs/superpowers/plans/2026-04-20-ops-push.md`  
**Branch per task:** `vidhi/<task-slug>` → one PR per task

---

## Overview

9 tasks. Task 1 is already done. Real work starts at Task 2 (n8n node mutations). Tasks 7+8 require Sinchana's Task 1 (TypeScript type) to be merged first.

---

## ✅ Task 1 — Customers (Storefronts) Page — DONE

`frontend/src/app/(admin)/customers/page.tsx` exists and has the full add-storefront form with validation, write-only secret field, and active badge. No action needed.

---

## Task 2 — `setProductSize` OPS Node Mutation (A3)

**File:** `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts` (8197 lines)

Three precise insertions. Make all three changes in a single commit.

**Insertion 1 — Options array (after line 638):**

Find the block at line 636–638:
```ts
{ name: 'Set Product', value: 'setProduct', action: 'Create or update a product' },
{ name: 'Set Product Design', value: 'setProductDesign', action: 'Update product design links' },
{ name: 'Set Product Price', value: 'setProductPrice', action: 'Create or update product price' },
```

Add after the `setProductPrice` line:
```ts
{ name: 'Set Product Size', value: 'setProductSize', action: 'Create or update product size variant' },
```

**Insertion 2 — Parameters block (after the `setProductPrice` parameters block ~line 754):**

Find the setProductPrice block ending around line 756:
```ts
// Mutation: Set Product Price
{
  displayName: 'Input (JSON)',
  name: 'setProductPrice_input',
  type: 'json',
  required: true,
  displayOptions: { show: { resource: ['mutation'], operation: ['setProductPrice'] } },
  default: '...',
  description: 'ProductPriceInput JSON object',
},
```

Add immediately after that closing `},`:
```ts
// Mutation: Set Product Size
{
  displayName: 'Input (JSON)',
  name: 'setProductSize_input',
  type: 'json',
  required: true,
  displayOptions: { show: { resource: ['mutation'], operation: ['setProductSize'] } },
  default: '{\n  "product_size_id": 0,\n  "products_id": 0,\n  "size_name": "",\n  "color_name": "",\n  "products_sku": "",\n  "visible": 1\n}',
  description: 'ProductSizeInput JSON object. Set product_size_id to 0 to create new.',
},
```

**Insertion 3 — Execute branch (after the `setProductPrice` execute block ~line 5400–5405):**

Find lines 5400–5406:
```ts
if (operation === 'setProductPrice') {
  const input = JSON.parse(this.getNodeParameter('setProductPrice_input', i) as string);
  const mutation = `mutation setProductPrice ($input: ProductPriceInput!) { setProductPrice (input: $input) { result message product_price_id } }`;
  const responseData = await this.helpers.request({ ... });
  if (responseData && responseData.data && responseData.data.setProductPrice) returnData.push(responseData.data.setProductPrice);
  else if (responseData && responseData.errors) throw new NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
}
```

Add after that block:
```ts
if (operation === 'setProductSize') {
  const input = JSON.parse(this.getNodeParameter('setProductSize_input', i) as string);
  const mutation = `mutation setProductSize ($input: ProductSizeInput!) { setProductSize (input: $input) { result message product_size_id } }`;
  const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
  if (responseData && responseData.data && responseData.data.setProductSize) returnData.push(responseData.data.setProductSize);
  else if (responseData && responseData.errors) throw new NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
}
```

**Build + restart:**
```bash
cd n8n-nodes-onprintshop && npm run build
cd .. && docker compose restart n8n
```

**Acceptance:** n8n editor → add OnPrintShop node → resource: Mutation → operation dropdown shows "Set Product Size". Node executes without TypeScript build errors.

---

## Task 3 — `setProductCategory` OPS Node Mutation (A4)

**File:** `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts`

Same 3-insertion pattern as Task 2.

**Insertion 1 — Options array (add after the `setProduct` entry ~line 636):**
```ts
{ name: 'Set Product Category', value: 'setProductCategory', action: 'Assign a product to a category' },
```

**Insertion 2 — Parameters block (add after the `setProduct_input` block ~line 745):**
```ts
// Mutation: Set Product Category
{
  displayName: 'Input (JSON)',
  name: 'setProductCategory_input',
  type: 'json',
  required: true,
  displayOptions: { show: { resource: ['mutation'], operation: ['setProductCategory'] } },
  default: '{\n  "products_id": 0,\n  "category_id": 0,\n  "categories_sort_order": 0\n}',
  description: 'ProductCategoryInput JSON object. products_id and category_id are required.',
},
```

**Insertion 3 — Execute branch (add after the `setProduct` execute block ~line 5398):**
```ts
if (operation === 'setProductCategory') {
  const input = JSON.parse(this.getNodeParameter('setProductCategory_input', i) as string);
  const mutation = `mutation setProductCategory ($input: ProductCategoryInput!) { setProductCategory (input: $input) { result message } }`;
  const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables: { input } }, json: true });
  if (responseData && responseData.data && responseData.data.setProductCategory) returnData.push(responseData.data.setProductCategory);
  else if (responseData && responseData.errors) throw new NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
}
```

Rebuild + restart n8n (same commands as Task 2).

**Acceptance:** "Set Product Category" appears in the mutation operation dropdown.

---

## Task 4 — Update Gap Analysis Doc (A5)

**File:** `n8n-nodes-onprintshop/OPS-NODE-GAP-ANALYSIS.md`  
**Effort:** XS

In the "Missing Mutations" table, find rows for `setProduct`, `setProductPrice`, `setProductSize`, `setProductCategory`. Mark each as implemented. Move them to a new section:

```markdown
## Implemented Mutations

| Mutation | PR | Notes |
|---|---|---|
| setProduct | #XX | |
| setProductPrice | #XX | |
| setProductSize | #YY (this PR) | |
| setProductCategory | #YY (this PR) | |
```

Replace `#XX` / `#YY` with actual PR numbers.

---

## Task 5 — Combined n8n Smoke Test (A6)

**Requires:** Tasks 2 + 3 done and n8n restarted  
**No file to commit — manual verification**

In n8n UI (`http://localhost:5678`):
1. Create a new workflow
2. Add Manual Trigger → Set Product Category → Set Product → Set Product Size → Set Product Price
3. Wire outputs: pass `category_id` from Category step into Product step, `products_id` from Product into Size + Price steps
4. Execute with test data (use a real OPS category_id from Tanishq's OPS creds)
5. Delete the test product from OPS admin immediately after
6. Report any `GraphQL Error` responses or missing return fields to Tanishq

---

## Task 6 — Verify + Fix `ops-push.json` Workflow (C1)

**File:** `n8n-workflows/ops-push.json`  
**Current state:** 12 nodes confirmed — Webhook Trigger, Parse Params, Get Products, Explode Products, Get Push Payload, Merge IDs + Payload, Build OPS Inputs, OPS: Set Product, Build Price Input, OPS: Set Product Price, POST Push Log, Respond to Webhook.

**Missing from spec — add these 3 nodes:**

**Missing 1 — setProductCategory before setProduct:**
After "Explode Products", add an HTTP node to call `GET /api/categories/{category_id}/ops-input` then pipe into an OPS: Set Product Category node (uses Urvashi's Task 5 endpoint).

**Missing 2 — setProductSize loop between setProduct and setProductPrice:**
After "OPS: Set Product", add:
- HTTP GET `ops-variants` endpoint (Urvashi Task 4): `/api/push/{customer_id}/product/{product_id}/ops-variants?ops_products_id={{$json.products_id}}`
- Split variants by size
- OPS: Set Product Size node (uses Task 2 mutation, loops per variant)
- Pass `product_size_id` back to Build Price Input

**Missing 3 — error branch:**
From "POST Push Log" on error: add a Code node that formats `{status: "failed", error: $json.message}` then an HTTP POST back to `/api/push-log` with `status: "failed"`.

After editing JSON, import and verify:
```bash
docker cp n8n-workflows/ops-push.json api-hub-n8n-1:/tmp/ops-push.json
docker exec api-hub-n8n-1 n8n import:workflow --input=/tmp/ops-push.json
```

Open in n8n UI — confirm all nodes visible and connected with no orphan nodes.

**Acceptance:** Workflow loads without errors. All 15+ nodes visible. Error branch present.

---

## Task 7 — `PushHistory` Component (D2)

**File:** `frontend/src/components/products/push-history.tsx` — CREATE  
**Requires:** Sinchana Task 1 (`ProductPushLogRead` type) merged first. If not yet merged, define the interface inline and remove when her PR lands.

**Note:** The product detail page already imports push statuses at the customer level via `/api/products/{id}/push-status`. This component is different — it fetches the full push log timeline for a product (all attempts, all customers, ordered by time).

```tsx
"use client";

import type { ProductPushLogRead } from "@/lib/types";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Props {
  productId: string;
}

const STATUS_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  pushed:  { bg: "#f0f9f4", text: "#247a52", dot: "#247a52" },
  failed:  { bg: "#fdf2f2", text: "#b93232", dot: "#b93232" },
  skipped: { bg: "#f9f7f4", text: "#888894", dot: "#b4b4bc" },
};

export function PushHistory({ productId }: Props) {
  const [logs, setLogs] = useState<ProductPushLogRead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<ProductPushLogRead[]>(`/api/push-log?product_id=${productId}&limit=20`)
      .then(setLogs)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [productId]);

  if (loading) return <div className="px-6 py-4 text-[13px] text-[#888894]">Loading history...</div>;
  if (!logs.length) return <div className="px-6 py-4 text-[13px] text-[#888894]">No push history yet.</div>;

  return (
    <table className="w-full border-collapse">
      <thead>
        <tr>
          {["When", "Storefront", "Status", "OPS ID", "Error"].map((h) => (
            <th key={h} className="text-left px-6 py-3 text-[10px] font-bold uppercase tracking-[0.1em] text-[#888894] border-b border-[#cfccc8]">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {logs.map((log) => {
          const style = STATUS_STYLES[log.status] ?? STATUS_STYLES.skipped;
          return (
            <tr key={log.id} className="hover:bg-[rgba(30,77,146,0.03)]">
              <td className="px-6 py-3 font-mono text-[12px] text-[#484852] border-b border-[#f9f7f4]">
                {new Date(log.pushed_at).toLocaleString()}
              </td>
              <td className="px-6 py-3 text-[13px] text-[#1e1e24] border-b border-[#f9f7f4]">
                {log.customer_name || log.customer_id.slice(0, 8)}
              </td>
              <td className="px-6 py-3 border-b border-[#f9f7f4]">
                <span className="inline-flex items-center gap-1.5 text-[12px] font-semibold px-2.5 py-0.5 rounded-full"
                      style={{ background: style.bg, color: style.text }}>
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: style.dot }} />
                  {log.status.charAt(0).toUpperCase() + log.status.slice(1)}
                </span>
              </td>
              <td className="px-6 py-3 font-mono text-[12px] text-[#484852] border-b border-[#f9f7f4]">
                {log.ops_product_id || "—"}
              </td>
              <td className="px-6 py-3 font-mono text-[11px] text-[#b93232] border-b border-[#f9f7f4] max-w-[200px] truncate">
                {log.error || "—"}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
```

**Note:** Requires Urvashi Task 2 (add `product_id` filter to `GET /api/push-log`) to be merged. Without it, the endpoint returns all logs, not this product's logs.

**Acceptance:** Component renders a table. Each row shows timestamp, storefront name, color-coded status pill, OPS ID, error message. Empty state shows "No push history yet."

---

## Task 8 — Wire `PublishButton` into Product Detail (D3)

**File:** `frontend/src/app/(admin)/products/[id]/page.tsx` — MODIFY  
**Effort:** S

**Context:** The product detail page (443 lines) already has an inline `handlePush` function (line 91) and a Storefront Publish Status section (line 369). However, `handlePush` is a **mock** — it posts a fake push log entry with `Math.random()` for `ops_product_id` (line 106) and doesn't trigger the n8n workflow.

**What needs to change — replace the mock push with real n8n trigger:**

Find `handlePush` at line 91. Replace the `api("/api/push-log", ...)` call with the n8n webhook trigger:

```ts
const handlePush = async (customerId?: string) => {
  if (!product) return;
  const targetId = customerId || (customers.length > 0 ? customers[0].id : null);
  if (!targetId) {
    alert("Please configure a storefront in the Storefronts page first.");
    return;
  }
  setPushing(targetId);
  try {
    // Trigger n8n workflow — it writes the push-log entry itself on completion
    await api(`/api/n8n/workflows/vg-ops-push-001/trigger`, {
      method: "POST",
      body: JSON.stringify({
        product_id: product.id,
        customer_id: targetId,
      }),
    });
    // Poll push status after ~5s for the result
    await new Promise((r) => setTimeout(r, 5000));
    const newStatuses = await api<ProductPushStatus[]>(`/api/products/${id}/push-status`);
    setPushStatuses(newStatuses);
  } catch (e) {
    console.error(e);
    alert("Publish failed. Check n8n logs at http://localhost:5678.");
  } finally {
    setPushing(null);
  }
};
```

**Add PushHistory section** below the existing Storefront Publish Status section (after line 439):

```tsx
import { PushHistory } from "@/components/products/push-history";

{/* ── Push History ─────────────────────────────────────── */}
<div className="bg-white border border-[#cfccc8] rounded-lg shadow-[4px_6px_0_rgba(30,77,146,0.08)] overflow-hidden">
  <div className="px-6 py-4 bg-[#ebe8e3] border-b border-[#cfccc8]">
    <div className="text-[14px] font-bold uppercase tracking-[0.05em] text-[#1e1e24]">Push History</div>
  </div>
  <PushHistory productId={id} />
</div>
```

**Acceptance:** Product detail page shows the Publish Status table (per storefront) and below it the Push History table (timeline of all push attempts). Clicking "Push Now" triggers n8n (not a mock). After workflow completes (~15s), push status updates.

---

## Task 9 — Workflows Page (V0 Task 0.5)

**File:** `frontend/src/app/workflows/page.tsx` — check if already exists  
**Priority:** Lower — do after Tasks 2–8

First check: `ls frontend/src/app/workflows/`. If the file exists, skip this task.

If not, create a static pipeline diagram page:
- Visual flow: Supplier → Fetch → Normalize → Store → Push to OPS
- Each step as a card with idle/done status badge
- Link to n8n editor: `http://localhost:5678`
- Blueprint design system styling: paper `#f2f0ed`, blue `#1e4d92`

---

## Files You Own

- `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts` — MODIFY (Tasks 2+3)
- `n8n-nodes-onprintshop/OPS-NODE-GAP-ANALYSIS.md` — MODIFY (Task 4)
- `n8n-workflows/ops-push.json` — MODIFY (Task 6, add 3 missing nodes)
- `frontend/src/components/products/push-history.tsx` — CREATE (Task 7)
- `frontend/src/app/(admin)/products/[id]/page.tsx` — MODIFY (Task 8, fix mock push + add PushHistory)
- `frontend/src/app/workflows/page.tsx` — CREATE if missing (Task 9)

---

## SanMar SFTP Tasks

**Spec:** `docs/superpowers/specs/2026-04-22-sanmar-sftp-integration-design.md`  
**Prerequisite:** Tanishq must complete P1 (DB row) + P2 (n8n SFTP credential) first.

---

### SanMar Task 1 — FTP Directory Listing (D1)

**No file to commit — discovery run only**

In n8n UI (`http://localhost:5678`), create a throwaway 2-node workflow:
1. Manual Trigger
2. SFTP: List Files
   - Credential: `SanMar SFTP` (set up by Tanishq in P2)
   - Host: `ftp.sanmar.com` — Port: `2200`
   - Path: `/`
   - Filter: *(leave empty — list everything)*

Execute. The output JSON will list all files with `name` and `size`. Document:
- Exact product CSV filename (look for something like `SanMar_All_Products.csv`)
- Whether pricing + inventory are in separate files
- File sizes (divide by ~200 bytes/row to estimate row count)

Post the file list in the PR description or paste to Tanishq.

**Acceptance:** File list captured. Product catalog filename confirmed.

---

### SanMar Task 2 — Inspect CSV Column Headers (D2)

**Requires:** D1 done  
**No file to commit**

Extend the discovery workflow:
1. Manual Trigger
2. SFTP: Download File — use exact filename from D1
3. Spreadsheet File node (type: CSV, options: `headerRow: true`) — read first 5 rows only

Look at the output. Map actual column names to these data points:

| Data Point | Guessed | Actual |
|---|---|---|
| Style / product SKU | `STYLE` | TBD |
| Product name | `PRODUCT_NAME` | TBD |
| Brand | `BRAND_NAME` | TBD |
| Description | `PRODUCT_DESCRIPTION` | TBD |
| Color name | `COLOR_NAME` | TBD |
| Size name | `SIZE_NAME` | TBD |
| Variant SKU | `UNIQUE_KEY` | TBD |
| Piece price | `PIECE_PRICE` | TBD |
| Inventory qty | `QTY` | TBD |
| Warehouse | `WAREHOUSE` | TBD |
| Image URL | `PRODUCT_IMAGE` | TBD |

Fill in the "Actual Column Name" column in the spec at `docs/superpowers/specs/2026-04-22-sanmar-sftp-integration-design.md` Task D2. Confirm with Tanishq before starting W1.

---

### SanMar Task 3 — Fix Column Mapping in Workflow (W1)

**File:** `n8n-workflows/sanmar-sftp-pull.json` — `Shape Products` node (`code-002`)  
**Requires:** D2 confirmed

Find the `// MAPPING PLACEHOLDER` comment in `code-002`. Replace with real column names from D2:

```js
return rows.map((item) => {
  const p = item.json;
  return {
    json: {
      supplier_sku:  String(p.<ACTUAL_STYLE_COL> || ''),
      product_name:  p.<ACTUAL_NAME_COL> || 'Unnamed',
      brand:         p.<ACTUAL_BRAND_COL> || 'SanMar',
      description:   p.<ACTUAL_DESC_COL> || null,
      product_type:  'apparel',
      image_url:     p.<ACTUAL_IMAGE_COL> || null,
      variants: [{
        sku:        String(p.<ACTUAL_SKU_COL> || ''),
        color:      p.<ACTUAL_COLOR_COL> || null,
        size:       p.<ACTUAL_SIZE_COL> || null,
        base_price: parseFloat(p.<ACTUAL_PRICE_COL> || 0),
        inventory:  parseInt(p.<ACTUAL_QTY_COL> || 0),
        warehouse:  p.<ACTUAL_WH_COL> || null,
      }],
      images: p.<ACTUAL_IMAGE_COL>
        ? [{ url: p.<ACTUAL_IMAGE_COL>, image_type: 'front', sort_order: 0 }]
        : [],
      options: []
    }
  };
});
```

Import and test with a small batch (set `maxItems: 5` on the SFTP download node temporarily). Verify Shape Products output shows `supplier_sku`, `product_name`, and `variants[0].base_price` populated with real values — not empty strings or 0.

---

### SanMar Task 4 — Fix SFTP File Filter (W2)

**File:** `n8n-workflows/sanmar-sftp-pull.json` — node `sftp-001` (`SFTP: List Files`)  
**Requires:** D1 done

In the `sftp-001` node, change:
```json
"filter": "*.csv"
```
to the exact product filename from D1, e.g.:
```json
"filter": "SanMar_All_Products.csv"
```

Prevents pricing/inventory CSVs from being accidentally routed to the products ingest endpoint.

---

### SanMar Task 5 — File-Type Router (W3)

**File:** `n8n-workflows/sanmar-sftp-pull.json`  
**Requires:** D1 done  
**Only needed if SanMar has separate pricing + inventory files.** Skip if one combined file.

After `SFTP: List Files`, add a Code node that tags each file by type:
```js
return $input.all().map(i => ({
  json: {
    ...i.json,
    file_type: i.json.name.toLowerCase().includes('price') ? 'pricing'
             : i.json.name.toLowerCase().includes('invent') ? 'inventory'
             : 'products'
  }
}));
```

Then a Switch node routes:
- `file_type == "products"` → existing download → shape → POST `/api/ingest/{sid}/products`
- `file_type == "pricing"` → download → POST `/api/ingest/{sid}/pricing`
- `file_type == "inventory"` → download → POST `/api/ingest/{sid}/inventory`

---

## Files You Own (SanMar additions)

- `n8n-workflows/sanmar-sftp-pull.json` — MODIFY (SanMar Tasks 3, 4, 5)
- `docs/superpowers/specs/2026-04-22-sanmar-sftp-integration-design.md` — UPDATE (SanMar Task 2, fill in actual column names)
