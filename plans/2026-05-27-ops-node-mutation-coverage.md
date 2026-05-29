# OPS n8n Node — Full Mutation Coverage Plan

**Date:** 2026-05-27
**Target:** `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts` (TypeScript custom node)
**Goal:** Every OPS GraphQL mutation available in the node — i.e. all mutation code present and correct.
**Source of truth:** OnPrintShop GraphQL Postman collection — **40 mutations**.

---

## 1. Reality Check — the node is already at 39/40

Audit of the live node against the collection's 40 mutations: **39 are implemented**, with operation dropdown entries (`OnPrintShop.node.ts:831–869`), `displayOptions`-gated property blocks, and execute branches (≈ `6582+`).

**Implemented (39):** setProduct · setProductPrice · setProductSize · setProductPages · setProductCategory · setProductDesign · setAdditionalOption · setAdditionalOptionAttributes · setProductsAttributePrice · setQuantityBasedAttributePrice · setAssignOptions · updateProductStock · setMasterOption · setMasterOptionAttributes · setMasterOptionAttributePrice · setMasterOptionRange · setMasterOptionTag · setOptionGroup · setCustomFormula · setProductOptionRules · setOrder · setOrderProduct · setBatch · setShipment · modifyOrderProduct · setOrderProductImage (exposed 3× as updateOrderProductImages / updateZiflowLinkImages / add-proof) · updateOrderStatus · setCustomer · setCustomerAddressDetail · notifyUser · setUserBasket · setStore · setStoreAddress · setDepartment · setStoreMarkup · setQuote · setFaq · setFaqCategory.

**Missing (1):** `setProductsImageGallery` — "Set Product Image Gallery".

So "all mutation code in the node" = add this one mutation correctly, then re-verify two known contract quirks. The code below is paste-ready and matches the node's exact conventions.

---

## 2. The one gap — `setProductsImageGallery` (full code)

This mutation does **not** use the simple single-`$input` pattern. Per the collection it takes three top-level args and returns a `message` object list:

```graphql
mutation setProductsImageGallery($products_id: Int!, $optimizeimg: Int, $input: ProductsImageGalleryBulkInput!) {
  setProductsImageGallery(products_id: $products_id, optimizeimg: $optimizeimg, input: $input) {
    result
    message { id status message }
  }
}
```

So it follows the multi-variable branch pattern (like `setQuote`), not the `_input`-only one.

### 2a. Operation dropdown entry
Insert in the mutation `options` array, after the `setProductPages` line (`OnPrintShop.node.ts:856`):

```ts
{ name: 'Set Product Image Gallery', value: 'setProductsImageGallery', action: 'Create or update product image gallery' },
```

### 2b. Property blocks
Add near the `setProductPages_input` block (`OnPrintShop.node.ts:1318`):

```ts
// Mutation: Set Product Image Gallery
{
  displayName: 'Products ID',
  name: 'setProductsImageGallery_products_id',
  type: 'number',
  required: true,
  displayOptions: { show: { resource: ['mutation'], operation: ['setProductsImageGallery'] } },
  default: 0,
},
{
  displayName: 'Optimize Image',
  name: 'setProductsImageGallery_optimizeimg',
  type: 'number',
  displayOptions: { show: { resource: ['mutation'], operation: ['setProductsImageGallery'] } },
  default: 0,
  description: 'Set to 1 to run OPS image optimization on upload',
},
{
  displayName: 'Input (JSON)',
  name: 'setProductsImageGallery_input',
  type: 'json',
  required: true,
  displayOptions: { show: { resource: ['mutation'], operation: ['setProductsImageGallery'] } },
  default: '{\n  "image_arr": [\n    {\n      "products_image_gallery_id": 0,\n      "delete": 0,\n      "corporate_id": 0,\n      "title": "",\n      "products_large_image_name": "",\n      "option_id": 0,\n      "attribute_id": 0,\n      "option_ids": "",\n      "attribute_ids": "",\n      "sort_order": 0,\n      "status": "1"\n    }\n  ]\n}',
  description: 'ProductsImageGalleryBulkInput JSON — image_arr list',
},
```

### 2c. Execute branch
Add in `execute()` next to the `setProductPages` branch (≈ `OnPrintShop.node.ts:6770`):

```ts
if (operation === 'setProductsImageGallery') {
  const products_id = this.getNodeParameter('setProductsImageGallery_products_id', i) as number;
  const optimizeimg = this.getNodeParameter('setProductsImageGallery_optimizeimg', i, 0) as number;
  const input = getJsonParameter('setProductsImageGallery_input', i);
  const variables: IDataObject = { products_id, input };
  if (optimizeimg !== undefined && optimizeimg !== null) variables.optimizeimg = optimizeimg;
  const mutation = `mutation setProductsImageGallery($products_id: Int!, $optimizeimg: Int, $input: ProductsImageGalleryBulkInput!) { setProductsImageGallery(products_id: $products_id, optimizeimg: $optimizeimg, input: $input) { result message { id status message } } }`;
  const responseData = await this.helpers.request({ method: 'POST', url: `${baseUrl}/api/`, headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: { query: mutation, variables }, json: true });
  if (responseData && responseData.data && responseData.data.setProductsImageGallery) returnData.push(responseData.data.setProductsImageGallery);
  else if (responseData && responseData.errors) throw new NodeOperationError(this.getNode(), `GraphQL Error: ${JSON.stringify(responseData.errors)}`);
}
```

Conventions matched: `this.helpers.request` → `${baseUrl}/api/`, `Bearer accessToken`, `getJsonParameter` helper (`:5898`), `IDataObject` variables, `NodeOperationError` on `errors`.

---

## 3. Contract re-verify (pre-existing flags — confirm before changing)

The 2026-04-04 gap doc flagged two issues at node line 7535 (node is now 9873 lines — may already be fixed). Verify against current code; only fix if still wrong:

- [ ] **`updateOrderStatus`** — collection contract is `type`, `orders_id`, `orders_products_id`, `input`. Confirm the node sends all four (old node sent only `orders_id` + `orders_status_id`, couldn't do product-level status).
- [ ] **`updateProductStock`** — confirm only one implementation remains with the canonical `stock_id` / `product_sku` / `action` / `input` contract; remove any legacy `product_id`/`quantity` duplicate.

---

## 4. Build & test

- [ ] `cd n8n-nodes-onprintshop && npm run build` — TypeScript compiles, no type errors (mirror the `setProductsImageGallery` branch types against neighbors).
- [ ] `npm run lint` if configured.
- [ ] Rebuild the n8n Docker image / reinstall the node so the editor picks up the new operation (`docker compose up -d n8n`).
- [ ] **Staging smoke:** in the n8n editor, run `Set Product Image Gallery` against an OPS staging product with one `image_arr` entry; confirm `result` + per-image `message`. Then run `Get Product image gallery` (already implemented, `productsImageGallery`) to read it back.
- [ ] Sync the copy: this node exists in two places — `api-hub/n8n-nodes-onprintshop/` (loaded by Docker) and the sibling `n8n-nodes-onprintshop/` source. Apply the change to both, or confirm which is canonical.

---

## 5. Notes / scope
- **Queries** are out of scope here (separate concern). The node already implements `productsImageGallery` (the read side), so post-write verification is available.
- This plan targets the **n8n node only**. The M1 FastAPI `ops_client` mutation set (10 product-domain wrappers) is a different surface and not covered here.
- After merge: update `OPS-NODE-GAP-ANALYSIS.md` + the CLAUDE.md "22 implemented / 33 missing" line — both are stale; node mutation coverage is 40/40 once this lands.
