# OPS Apparel Push — Verified SKU + Stock Workflow

**Date:** 2026-06-17
**Status:** Authoritative. Verified against the **live** OnPrintShop GraphQL collection
(`documenter.getpostman.com/view/33263100/2sBXijHWys`, 81 operations — 41 mutations,
39 queries), pulled 2026-06-17. Supersedes the vendored 75-op v2 collection (stale subset).

**Why this exists:** the integration hit a "stock cannot be initialized" blocker
(report on product 602 / SKU `1745Y`). Root cause was a missing step + an invented
query, not an OPS gap. This documents the supported end-to-end sequence so apparel
products reach "available for sale" automatically.

---

## 1. Headline corrections (live-verified)

| Claim in current code/PRs | Reality (live collection) |
|---|---|
| `getProductBySku(products_sku)` used for dedup/verify (`ops_client/mutations.py:212`) | **Does NOT exist in OPS.** Invented in api-hub, marked "PROVISIONAL". Returns empty live. Remove it. |
| `setProductSku` is fake | **Real.** `setProductSku(inputs: [ProductSkuInput!]!)` — batch array. |
| Stock enum is `CREDIT/DEBIT/SET` (n8n gap-analysis "knowledge pack") | **Wrong.** Live enum = `Add / Remove / Reset`. |
| `main_sku` not writable | **Writable** via `setProduct.main_sku` — but it is the **product-level** SKU, *"stored with size_id=0"*. It is **NOT a stock variant SKU**. Passing it to `updateProductStock` fails ("Invalid Product SKU") — that was the team's mistake on `1745Y`. |
| Initial stock needs a create-stock mutation OPS doesn't have | **No separate create mutation.** `updateProductStock` itself *"add[s] new stock, update[s] existing, or delete[s]"* — it creates the row, given a **registered variant SKU** (from `setProductSku`) or `stock_id`. |

### Field-type corrections (live `setProduct` / `setProductSku` / `setAdditionalOption`)

- **All three take a BATCH array** `inputs: [...]!`, not a single `input`. (`setProduct(inputs:[ProductInput!]!)`, `setProductSku(inputs:[ProductSkuInput!]!)`, `setAdditionalOption(inputs:[...]!)`.) Current api-hub/PR code assuming a single `input` must wrap in an array.
- **`product_type`** = `String`, **comma-separated, required**. Legend: `1` Custom Design · `2` Upload Center · `3` Browse Design · `7` Quote · `8` Hire Designer · **`15` Add to cart**. Apparel sold from stock → `"15"` (example live value `"15,8"`).
- **`enable_stock_management`** = `Int` **enum**, NOT boolean: `0` None · `1` Only Size · `2` Size with Product Option. **Must align with `setProductSku.sku_type`:** `1`↔`size_wise`, `2`↔`size_option_wise`. A mismatch leaves SKUs unregistered for stock → "Invalid Product SKU".
- **`main_sku`** = product-level SKU at `size_id=0`; send `""` to clear. Distinct from per-size/option variant SKUs.

## 2. The missing piece: `getProductSkuMatrix`

```
query getProductSkuMatrix($products_id: Int!, $prod_add_opt_ids: String!) {
  getProductSkuMatrix(products_id, prod_add_opt_ids) {
    matrix { size_id  prod_add_opt_ids  attribute_ids }
    totalRecords
  }
}
```
Returns the **valid** size / size×option combinations for a product. OPS docs:
*"Use it to get valid size and option combinations before calling `setProductSku`."*
- No `prod_add_opt_ids` → size-wise matrix (one row per size).
- With `prod_add_opt_ids` → size × option-attribute matrix.

This is the correct replacement for the invented `getProductBySku`, and the
prerequisite for assigning SKUs that OPS will actually recognize for stock.

## 3. `setProductSku` contract (verified)

```
mutation setProductSku($inputs: [ProductSkuInput!]!) {
  setProductSku(inputs: $inputs) { index result message id }
}
```
Each `ProductSkuInput`:
| Field | Req | Notes |
|---|---|---|
| `products_id` | Yes | |
| `sku_type` | Conditional | `"size_wise"` OR `"size_option_wise"` — one method at a time. Switching methods deletes the other method's records. |
| `size_id` | Conditional | from `getProductSkuMatrix` |
| `prod_add_opt_ids` | Conditional | comma-separated option ids. Required for `size_option_wise`. |
| `attribute_ids` | Conditional | comma-separated, one per option in same order; count must match `prod_add_opt_ids`. Required for `size_option_wise`. |
| `sku` | Conditional | the SKU value (may be empty) |
| `delete` | Conditional | `1` to delete all variant SKUs (only `products_id` needed) |

Unprovided sizes/combinations are auto-filled with blank SKU entries.
**Main product SKU is separate:** set via `setProduct.main_sku`.

## 4. Verified end-to-end apparel push sequence

```
1. setProduct       inputs:[{ product_type:"15", enable_stock_management:1 (or 2),
                              price_defining_method, main_sku, + CREATE toggles }]
2. setProductSize   inputs per size  → size_id[]
3. (if size_option_wise) setMasterOption / setMasterOptionAttributes / setAssignOptions
4. getProductSkuMatrix(products_id[, prod_add_opt_ids])  → valid {size_id, prod_add_opt_ids, attribute_ids}
5. setProductSku    inputs:[ ... ] over the matrix; sku_type MUST match step-1 mode
                    (enable_stock_management 1→"size_wise", 2→"size_option_wise")
6. updateProductStock(product_sku:<a registered variant SKU from step 5>,
                      action: Add, input:{ stock_quantity, comment })   ← ADDS the initial row
7. productStocks(product_id)   → returns the new rows + their stock_id (for later updates)
8. setProductPrice  inputs per (products_id, size_id)   ← per-size pricing
```

**Key:** the chain is **SKU first, stock second.** `updateProductStock` "adds new
stock" — but only against a **registered variant SKU** (`setProductSku`, size_id≠0)
or an existing `stock_id`. Initial creation must use **`product_sku`** (no `stock_id`
exists yet); later edits can use `stock_id` from step 7. Enum: `Add | Remove | Reset`.

### Likely root cause of the product-602 failure (validate on staging)
1. `1745Y` is the **`main_sku`** (product-level, `size_id=0`) — never a stock variant.
2. The size SKU `3007831` either wasn't registered via `setProductSku`, or its
   `sku_type` didn't match `enable_stock_management` (mode mismatch → not stock-eligible).
3. `getProductSkuMatrix` was never called, so SKUs weren't bound to valid combos.

> **Confidence:** every field/op above is documented in the live collection.
> The end-to-end ordering (esp. that `updateProductStock(product_sku, Add)` creates
> the first row after a matching `setProductSku`) is assembled from the operation
> descriptions — **run it once on staging product 602 to confirm** before wiring it
> into the pipeline. Only if a correctly-registered variant SKU still errors do we
> escalate to OnPrintShop (`/tmp/ops-stock-escalation.md`).

## 5. Action items (integration)

- [ ] Replace `getProductBySku` (dedup/verify) with `getProductSkuMatrix` (SKU validity)
      and `productsDetails`/`products` filtered by `main_sku` (dedup). Delete the
      provisional `_GET_PRODUCT_BY_SKU` from `ops_client/mutations.py`.
- [ ] Implement `getProductSkuMatrix` → `setProductSku` (batch `inputs:[]`) before stock.
- [ ] Set `enable_stock_management` to `1`/`2` and make `setProductSku.sku_type` match
      (`1`→`size_wise`, `2`→`size_option_wise`).
- [ ] Initial stock: `updateProductStock(product_sku=<registered variant SKU>, action:Add)`;
      later edits by `stock_id` from `productStocks`. Enum `Add|Remove|Reset`.
- [ ] Never pass `main_sku` (size_id=0) to `updateProductStock` — it's product-level.
- [ ] Wrap `setProduct`/`setProductSku`/`setAdditionalOption` payloads in the `inputs:[]`
      array (live contract is batch, not single `input`).
- [ ] Fix dup-sizes (Issue B) with match-by-`size_title` upsert (ties to the
      variant→option collapse plan, 2026-06-17-variant-option-collapse-impl.md).
- [ ] Apparel `product_type="15"` (Add to cart); confirm `price_defining_method` by
      mirroring a known-good LIVE apparel product (pull-first via `productsDetails`).
- [ ] Vendor the live 81-op collection as the single source of truth (replace the
      stale 75-op copy); re-point ops mappers/n8n node at it.

## 6. PR impact (open API-HUB PRs)

- **#182** `setProductSku` — real op; verify impl sends the `inputs` **array** +
  `sku_type` + matrix ids (not a flat single SKU). Red-test + FakeOpsClient blockers stand.
- **#186** `getProductBySku` — dead query; rework onto `getProductSkuMatrix` /
  `productsDetails`-by-`main_sku`.
- **#181** stock — `action="Reset"` is valid; fix only the misleading test name/comment.
- **#180** apparel options/pricing — `multiplier`/`multiplier_type` are not
  `AdditionalOptionInput` fields; use `apply_multiplication` + `price_calculate_type`,
  per-size price via `setProductsAttributePrice` / `setQuantityBasedAttributePrice`.
