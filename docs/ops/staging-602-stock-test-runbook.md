# Runbook — Verify OPS Initial-Stock Sequence (staging, product 602)

**Goal:** Confirm the one inferred link in the verified apparel workflow — that
`updateProductStock` creates the first stock row once a variant SKU is registered
via `setProductSku`. Run against **staging** OPS, product **602** (`main_sku 1745Y`).

**Prereq:** OPS staging GraphQL access (client_id/secret/oauth_url/graphql_url).
Reference schema: `docs/ops/SOURCE.md` + the vendored live collection. All three
setters take a **batch `inputs:[]`** array.

## Background (why 602 failed before)
- `1745Y` is the **main_sku** (product-level, `size_id=0`) — NOT a stock variant SKU.
- `updateProductStock` acts on a registered variant SKU or an existing `stock_id`.
- `getProductBySku` does not exist in OPS — ignore it; use `getProductSkuMatrix`.

## Steps

1. **Confirm product type/mode.** `setProduct(inputs:[{products_id:602,
   product_type:"15", enable_stock_management:1}])` — `15` = Add to cart, `1` = Only Size.
   (Mode `1` ↔ `sku_type:"size_wise"` in step 3.)

2. **Get the SKU matrix.**
   `getProductSkuMatrix(products_id:602)` → note the returned `size_id`s
   (size-wise matrix, since no `prod_add_opt_ids`).

3. **Register a variant SKU** for one size:
   ```graphql
   setProductSku(inputs:[{ products_id:602, sku_type:"size_wise",
     size_id:<from step 2>, sku:"TEST-602-S", delete:0 }])
   ```
   Expect `result:true`.

4. **Create initial stock** against that registered SKU:
   ```graphql
   updateProductStock(product_sku:"TEST-602-S", action:Add,
     input:{ stock_quantity:25, comment:"initial stock test" })
   ```
   - **PASS** → `result:true` + a `stock_id` returned. The sequence works; wire it
     into the pipeline (SKU-first, then stock).
   - **FAIL** ("Invalid Product SKU or initial stock not added!") → escalate to
     OnPrintShop with the narrowed question in `/tmp/ops-stock-escalation.md`
     (or this repo's escalation doc): "after a matching setProductSku, does
     updateProductStock(product_sku, Add) create the first row, or is an admin/bulk
     step required?"

5. **Confirm.** `productStocks(product_id:602)` → expect ≥1 row with the new
   `stock_id` + `stock_quantity:25`. Re-run step 4 with `action:Reset` → absolute set.

## Record the result
Note PASS/FAIL + the exact OPS message in the handoff/stock issue. PASS closes the
last open question in `plans/2026-06-17-ops-apparel-stock-sku-workflow.md`.
