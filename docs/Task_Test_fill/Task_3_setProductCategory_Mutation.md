# Task 3 — `setProductCategory` OPS Node Mutation — Detail Guide

**Status:** ✅ Completed and verified on 2026-04-23  
**Branch:** `Vidhi`  
**What you can say in one sentence:** *"I added the setProductCategory mutation to our custom n8n OnPrintShop node so that when we push a product to OPS, we can assign it to the correct category (like T-Shirts, Hoodies, Bags) so it shows up in the right section of the storefront."*

---

## 1. What Got Built

| File | What Changed |
|---|---|
| `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts` | 3 insertions — dropdown entry, input field, execute logic |
| `n8n-nodes-onprintshop/dist/` | Rebuilt TypeScript → JavaScript via `npm run build` |

---

## 2. Background — What Is This Task About?

### The Big Picture

When we push a product into an OPS storefront, OPS needs to know **where to put it**. Every storefront has categories — like a filing system. Without assigning a category, the product either goes into a "catch-all" bin or doesn't appear in the storefront navigation at all.

Think of it like uploading a file to Google Drive — you can create the file, but if you don't put it in the right folder, nobody can find it.

### The Full Push Sequence

A complete product push to OPS requires 4 mutations in order:

| Step | Mutation | What It Does |
|---|---|---|
| 1 | `setProductCategory` | Create or assign the category (e.g. "T-Shirts") — **THIS TASK** |
| 2 | `setProduct` | Create the product, linked to that category |
| 3 | `setProductSize` | Add size variants (S, M, L, XL) to the product |
| 4 | `setProductPrice` | Set the price per size/qty |

Task 3 adds Step 1 — the first thing that must exist before anything else can be linked to it.

### Why Was `setProductCategory` Missing?

The n8n OnPrintShop node is a custom plugin we maintain in `n8n-nodes-onprintshop/`. Before this task, the node had `setProduct`, `setProductPrice`, and (after Task 2) `setProductSize`, but `setProductCategory` was still absent. This meant:

- We could create a product in OPS ✅
- We could set sizes ✅
- We could set prices ✅
- But we could NOT put the product into the correct storefront category ❌

This task fills that gap.

---

## 3. How the n8n Node File Is Structured

The file `OnPrintShop.node.ts` is ~8200 lines long. Every operation (mutation or query) requires exactly **3 matching insertions** in 3 different sections:

```
Section 1: Operations Dropdown (~line 635)
───────────────────────────────────────────
{ name: 'Set Product Category', value: 'setProductCategory', ... }
         ↑ The label the user sees in the n8n UI dropdown

Section 2: Input Fields (~line 768)
───────────────────────────────────────────
{ name: 'setProductCategory_input', type: 'json', ... }
         ↑ Defines the JSON input box that appears in the UI

Section 3: Execute Logic (~line 5435)
───────────────────────────────────────────
if (operation === 'setProductCategory') { ... }
         ↑ The code that actually sends the GraphQL request to OPS
```

All 3 must exist and the `value` / `operation` strings must match exactly. If any one is missing, the operation either won't appear in the UI or will crash silently when run.

---

## 4. Exact Code Added

### Insertion 1 — Operations Dropdown

**Before:**
```ts
{ name: 'Set Product Size', value: 'setProductSize', action: 'Create or update product size variant' },
{ name: 'Set Quote', value: 'setQuote', action: 'Create or update a quote' },
```

**After:**
```ts
{ name: 'Set Product Category', value: 'setProductCategory', action: 'Create or update a product category' },
{ name: 'Set Product Size', value: 'setProductSize', action: 'Create or update product size variant' },
{ name: 'Set Quote', value: 'setQuote', action: 'Create or update a quote' },
```

**What this does:** Adds "Set Product Category" to the operation dropdown in the n8n UI. The `action` text is what appears as a subtitle/description under the operation name.

---

### Insertion 2 — Input Field Definition

**Added block:**
```ts
{
  displayName: 'Input (JSON)',
  name: 'setProductCategory_input',
  type: 'json',
  required: true,
  displayOptions: { show: { resource: ['mutation'], operation: ['setProductCategory'] } },
  default: '{\n  "category_id": 0,\n  "category_name": "",\n  "parent_id": 0,\n  "visible": 1\n}',
  description: 'ProductCategoryInput JSON object. Set category_id to 0 to create new.',
},
```

**What this does:** Defines the JSON input box that appears in n8n when "Set Product Category" is selected. The `default` value is a pre-filled template:

| Field | Meaning |
|---|---|
| `category_id` | Set to `0` to CREATE a new category, or an existing ID to UPDATE |
| `category_name` | The display name, e.g. `"T-Shirts"` or `"Hoodies"` |
| `parent_id` | Set to `0` for a top-level category, or an ID for a sub-category |
| `visible` | `1` = visible in storefront navigation, `0` = hidden |

**The `displayOptions` field** tells n8n to only show this input when resource = `mutation` AND operation = `setProductCategory`. It hides itself on all other operations.

---

### Insertion 3 — Execute Logic

**Added block:**
```ts
if (operation === 'setProductCategory') {
  const input = JSON.parse(this.getNodeParameter('setProductCategory_input', i) as string);
  const mutation = `mutation setProductCategory ($input: ProductCategoryInput!) { setProductCategory (input: $input) { result message category_id } }`;
  const responseData = await this.helpers.request({
    method: 'POST',
    url: `${baseUrl}/api/`,
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    body: { query: mutation, variables: { input } },
    json: true
  });
  if (responseData && responseData.data && responseData.data.setProductCategory)
    returnData.push(responseData.data.setProductCategory);
  else if (responseData && responseData.errors)
    throw new NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
}
```

**What this does — step by step:**

1. **Reads the JSON** the user filled in the input box
2. **Builds the GraphQL mutation string** — the exact command sent to OPS
3. **Sends a POST request** to the OPS API with Bearer token auth
4. **Handles the response:**
   - On success → pushes `{ result, message, category_id }` to n8n's output
   - On GraphQL error → throws a readable error message
5. **Returns `category_id`** — the OPS ID assigned to this category, which is needed as input for `setProduct` (Step 2 in the push sequence)

---

## 5. What Is a Product Category in OPS?

In OnPrintShop, a **category** is a grouping that appears in the storefront's navigation menu. Examples:

```
Storefront navigation
├── T-Shirts          ← category
│   ├── Men's Tees
│   └── Women's Tees  ← sub-category (parent_id = T-Shirts category_id)
├── Hoodies           ← category
└── Bags              ← category
```

When we set `parent_id: 0`, we're creating a root-level category. When we use a real `parent_id`, the category becomes a sub-folder under the parent. OPS uses `category_id` as the link — every product has a `category_id` field that points to one of these categories.

---

## 6. How This Differs from Task 2

Task 2 (`setProductSize`) and Task 3 (`setProductCategory`) follow the identical 3-insertion pattern, but the **GraphQL type names differ**:

| | Task 2 — setProductSize | Task 3 — setProductCategory |
|---|---|---|
| Input type | `ProductSizeInput` | `ProductCategoryInput` |
| Return field | `product_size_id` | `category_id` |
| Default JSON fields | product_size_id, products_id, size_name, color_name, products_sku, visible | category_id, category_name, parent_id, visible |
| Used for | Adding S/M/L/XL variants | Grouping products in storefront nav |

The pattern is the same — only the type names and field names change.

---

## 7. Build + Deploy Commands

```bash
# Step 1 — Compile TypeScript → JavaScript
# Run from: D:/company/API-HUB/n8n-nodes-onprintshop/
npm run build

# Step 2 — Restart n8n to pick up the new build
# Run from: D:/company/API-HUB/
docker compose restart n8n
```

Both steps ran successfully on 2026-04-23. Build output confirmed all 3 insertions compiled correctly into `dist/nodes/OnPrintShop.node.js`.

---

## 8. Verification

**How to verify in n8n UI:**

1. Open **http://localhost:5678**
2. Click **Create workflow**
3. Add a node → search **"OnPrintShop"**
4. Set **Resource** → `Mutation`
5. Open the **Operation** dropdown
6. Look for **"Create or update a product category"**

**Verified via compiled JS grep on 2026-04-23:** ✅ `setProductCategory` found at 8 locations in `dist/nodes/OnPrintShop.node.js` — dropdown, input field, and execute block all confirmed present.

---

## 9. What Comes Next

| Next Task | What It Adds |
|---|---|
| **Task 4** — Update gap analysis doc | Marks setProduct, setProductPrice, setProductSize, setProductCategory as implemented in `OPS-NODE-GAP-ANALYSIS.md` |
| **Task 5** — n8n smoke test | Manually chains Set Product Category → Set Product → Set Product Size → Set Product Price in a test workflow and executes with real test data |
| **Task 6** — Fix ops-push.json | Adds the setProductCategory node, setProductSize loop, and error branch to the main push workflow |
