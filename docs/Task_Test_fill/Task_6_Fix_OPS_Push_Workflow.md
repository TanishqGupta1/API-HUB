# Task 6 — Fix ops-push.json Workflow — Detail Guide

**Status:** ✅ Completed on 2026-04-24
**Branch:** `Vidhi`
**What you can say in one sentence:** *"I fixed the n8n workflow that pushes products to OPS by adding the missing category step, a size variant loop, and an error handler so that when a product fails to push, it gets logged instead of silently crashing."*

---

## 1. What Got Built

| File | What Changed |
|---|---|
| `n8n-workflows/ops-push.json` | Added 6 new nodes, updated 3 existing nodes, fixed broken push log context |

---

## 2. Background — What Is This Task About?

### Task Type
**Workflow fix** — editing a JSON config file that defines an n8n automation workflow. No TypeScript, no Python, no builds required.

### What Is ops-push.json?

It is the n8n workflow that answers the question:
> *"How do we take a product from our database and put it into a customer's OPS storefront?"*

n8n reads this JSON file and turns it into a visual workflow with nodes connected by arrows. Each node does one job. The workflow runs when our FastAPI backend sends a trigger to n8n.

### What Was Wrong Before This Task?

The workflow existed but was **incomplete**. It could:
- ✅ Fetch products from our database
- ✅ Create a product in OPS (`setProduct`)
- ✅ Set a price for the product (`setProductPrice`)
- ✅ Log the push result

But it could NOT:
- ❌ Assign a category to the product before creating it
- ❌ Push size variants (S, M, L, XL) to OPS
- ❌ Handle errors — if any OPS call failed, the workflow crashed silently with no log entry

---

## 3. The Workflow — Before vs After

### Before (9 nodes)
```
Webhook → Parse Params → Get Products → Explode Products
  → Get Push Payload → Merge IDs + Payload → Build OPS Inputs
  → Set Product → Build Price Input → Set Product Price
  → POST Push Log → Respond to Webhook
```

### After (17 nodes)
```
Webhook → Parse Params → Get Products → Explode Products
  → Get Push Payload → Merge IDs + Payload → Build OPS Inputs
  → [NEW] Set Product Category → [NEW] Attach Category ID
  → Set Product ──┬──→ [NEW] Build Size Inputs → [NEW] Set Product Size (loop)
                  └──→ Build Price Input → Set Product Price
                           → POST Push Log → Respond to Webhook

Any OPS failure → [NEW] Error Handler → [NEW] POST Push Log Error
```

---

## 4. The 3 Things Added — Explained Simply

### Addition 1 — Set Product Category Node

**The problem it solves:**
In OPS, every product must belong to a category (like "T-Shirts" or "Hoodies"). Before this fix, the workflow was sending `category_id: 0` when creating products — meaning every product ended up in a catch-all default category.

**What we added:**
Two nodes working together:

**Node A — `OPS: Set Product Category`**
- Calls the `setProductCategory` mutation we built in Task 3
- Creates (or finds) a category in OPS for this product
- Returns a `category_id` from OPS

**Node B — `Attach Category ID`** (Code node)
- Takes the `category_id` returned by Node A
- Injects it into the `setProduct_input` JSON
- So when `setProduct` runs next, it knows which category to put the product in

**Code in Attach Category ID:**
```js
const categoryResult = $input.first().json ?? {};
const ctx = $node['Build OPS Inputs'].json;

const category_id = Number(categoryResult.category_id ?? 0);

// Take the existing product input and fill in the real category_id
const productInput = JSON.parse(ctx.setProduct_input);
productInput.category_id = category_id;

return [{
  json: {
    ...ctx,
    setProduct_input: JSON.stringify(productInput, null, 2),
  }
}];
```

**Before this fix:**
```json
{ "category_id": 0, "products_title": "Gildan T-Shirt" }
```

**After this fix:**
```json
{ "category_id": 42, "products_title": "Gildan T-Shirt" }
```

---

### Addition 2 — Set Product Size Loop

**The problem it solves:**
A t-shirt comes in S, M, L, XL, 2XL. OPS needs to know about each size variant individually. Before this fix, sizes were never sent to OPS — so products appeared with no size options for customers to choose from.

**What we added:**
Two nodes working together:

**Node A — `Build Size Inputs`** (Code node)
- Reads the list of size variants from the product payload
- Creates **one output item per size** (e.g. 5 items for S/M/L/XL/2XL)
- Falls back to a single "OS" (One Size) entry if the product has no variants

**Node B — `OPS: Set Product Size`**
- Receives N items from Build Size Inputs
- n8n automatically runs it N times — once per size
- Each run calls the `setProductSize` mutation we built in Task 2

**How the loop works in n8n:**
n8n doesn't have an explicit "loop" node. Instead, when a Code node outputs multiple items, every downstream node processes each item separately. So if Build Size Inputs outputs 5 items, OPS: Set Product Size runs 5 times — once for S, once for M, etc.

```
Build Size Inputs → [S item, M item, L item, XL item, 2XL item]
                         ↓       ↓       ↓       ↓        ↓
OPS: Set Product Size  run1   run2    run3    run4     run5
```

**Code in Build Size Inputs:**
```js
const setProductResult = $input.first().json ?? {};
const ctx = $node['Attach Category ID'].json;
const products_id = setProductResult.products_id;

const variants = ctx.payload?.variants ?? [];

const sizeItems = variants.length
  ? variants.map((v) => ({
      size_name: v.size ?? v.size_name ?? 'OS',
      color_name: v.color ?? v.color_name ?? '',
      products_sku: v.sku ?? ctx.product_id,
    }))
  : [{ size_name: 'OS', color_name: '', products_sku: ctx.product_id }];

return sizeItems.map((s) => ({
  json: {
    ...ctx,
    ops_product_id: String(products_id),
    setProductSize_input: JSON.stringify({
      product_size_id: 0,
      products_id: Number(products_id),
      size_name: s.size_name,
      color_name: s.color_name,
      products_sku: s.products_sku,
      visible: 1,
    }, null, 2),
  }
}));
```

**Important design decision:**
The size loop runs in **parallel** with the price step. OPS: Set Product has two output connections:
1. → Build Size Inputs (size loop, runs alongside)
2. → Build Price Input (price, runs alongside)

This is more efficient than running them one after the other.

---

### Addition 3 — Error Branch

**The problem it solves:**
Before this fix, if any OPS call failed (wrong credentials, OPS down, bad input), n8n would crash the workflow execution with a red error. The push log would never be written. Nobody would know which products failed or why.

**What we added:**
Two nodes:

**Node A — `Error Handler`** (Code node)
- Connected to the **error output** of 4 OPS nodes:
  - OPS: Set Product Category
  - OPS: Set Product
  - OPS: Set Product Size
  - OPS: Set Product Price
- Formats the error into a clean JSON with product_id, customer_id, error_message

**Node B — `POST Push Log Error`** (HTTP Request node)
- Posts to `/api/push-log` with `status: "failed"` and the error message
- This way every failed push is recorded in the database for debugging

**How error outputs work in n8n:**
Every n8n node has two outputs:
- Output `[0]` = **success** — data flows here when the node works correctly
- Output `[1]` = **error** — data flows here when the node fails

By setting `"onError": "continueErrorOutput"` on the OPS nodes, instead of crashing, failures are routed to output[1] which connects to Error Handler.

```
OPS: Set Product ──[0]──→ Build Price Input   (success path)
                └──[1]──→ Error Handler        (error path)
```

---

## 5. What Else Was Fixed (Bonus Bug Fix)

### Bug: POST Push Log was reading wrong data

The original `POST Push Log` node used `$json.product_id`, `$json.customer_id`, and `$json.ops_product_id`. But `$json` at that point in the workflow was the output of `OPS: Set Product Price` — which only returns `{ result, message, product_price_id }`. It does NOT return product_id or customer_id.

This meant the push log entries would have `undefined` for all the important fields.

**Fix:** Updated POST Push Log to use `$node['Build Price Input'].json` which carries the correct context:

```
Before: "product_id": $json.product_id          ← undefined (from OPS response)
After:  "product_id": $node['Build Price Input'].json.product_id  ← correct
```

---

## 6. Node Map — Complete Picture

| # | Node Name | Type | What It Does |
|---|---|---|---|
| 1 | Webhook Trigger | Webhook | Receives the push trigger from FastAPI |
| 2 | Parse Params | Code | Reads customer_id, supplier_id, limit from URL |
| 3 | Get Products | HTTP | Fetches product list from our database |
| 4 | Explode Products | Code | Splits product list into one item per product |
| 5 | Get Push Payload | HTTP | Fetches full product data + variants + pricing |
| 6 | Merge IDs + Payload | Merge | Combines product identity + full payload |
| 7 | Build OPS Inputs | Code | Prepares all 3 input JSONs (category, product, price) |
| 8 | OPS: Set Product Category | OPS Node | ✅ NEW — Creates category in OPS |
| 9 | Attach Category ID | Code | ✅ NEW — Injects returned category_id into product input |
| 10 | OPS: Set Product | OPS Node | Creates the product in OPS |
| 11 | Build Size Inputs | Code | ✅ NEW — Creates one item per size variant |
| 12 | OPS: Set Product Size | OPS Node | ✅ NEW — Registers each size in OPS (loops) |
| 13 | Build Price Input | Code | MODIFIED — now reads from Attach Category ID context |
| 14 | OPS: Set Product Price | OPS Node | Sets the product price |
| 15 | POST Push Log | HTTP | MODIFIED — fixed context reference |
| 16 | Respond to Webhook | Respond | Sends response back to FastAPI |
| 17 | Error Handler | Code | ✅ NEW — Formats error for logging |
| 18 | POST Push Log Error | HTTP | ✅ NEW — Logs failed pushes to database |

---

## 7. Why We Didn't Test This Yet

This workflow requires **OPS API credentials** (Client ID + Client Secret) to actually run. Those credentials are pending from Christian. The workflow structure is correct and ready — it just can't be executed until credentials are available.

The `"credentials": { "onPrintShopApi": { "id": "", "name": "OPS Storefront" } }` field in each OPS node is intentionally left blank — it will be filled in when credentials arrive.

---

## 8. What Comes Next

| Next Task | What It Adds | Blocked? |
|---|---|---|
| **Task 5** — n8n smoke test | Manually test the full chain with real OPS credentials | 🔴 Yes — needs credentials from Christian |
| **Task 7** — push-history component | Frontend component showing push history per product | ❌ No — can do now |
| **Task 8** — Wire real n8n trigger | Replace mock push button in products page with real n8n call | ❌ No — can do now |
