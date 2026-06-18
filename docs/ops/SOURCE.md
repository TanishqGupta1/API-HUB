# OnPrintShop GraphQL API — Source of Truth

**File:** `OnPrintShop_GraphQL_API_live_2026-06-17.postman_collection.json`
**Pulled:** 2026-06-17 from the live published docs
`https://documenter.getpostman.com/view/33263100/2sBXijHWys`
(backend JSON: `https://documenter.gw.postman.com/api/collections/33263100/2sBXijHWys`)

**This is the authoritative OPS schema for API-HUB.** 81 operations (41 mutations,
39 queries). Verify any OPS field/mutation name against THIS file before writing
push code. Do not invent fields.

## Why this exists

Multiple pushes were built on guessed/stale field names (`getProductBySku`,
option-level `multiplier`, `setProductSku` mis-contracted). A previously vendored
75-op collection (in the graphx repo) was a stale subset and missed `setProductSku`,
`getProductSkuMatrix`, and current field shapes. This live copy replaces guesswork.

## Facts that bit us (all verified in this file)

- **`getProductBySku` does not exist.** Use `getProductSkuMatrix(products_id[, prod_add_opt_ids])`
  for SKU validity, or `products` / `productsDetails` filtered by `main_sku` for dedup.
- **`setProductSku(inputs: [ProductSkuInput!]!)`** — batch array. `sku_type` =
  `size_wise` | `size_option_wise`; needs `size_id` / `prod_add_opt_ids` /
  `attribute_ids` from `getProductSkuMatrix`.
- **`setProduct` / `setAdditionalOption`** also take batch `inputs: [...]!`, not a single `input`.
- **`main_sku`** = product-level SKU stored at `size_id=0` (via `setProduct`); NOT a variant SKU.
- **`updateProductStock`** action enum = `Add | Remove | Reset` (NOT CREDIT/DEBIT/SET).
  Adds new stock against a registered variant SKU or `stock_id`. No separate create-stock op.
- **`enable_stock_management`** = enum `0` None / `1` Only Size / `2` Size with Product Option
  (must match `setProductSku.sku_type`).
- **`product_type`** = String, comma-separated; `15` = Add to cart (apparel sold from stock).
- **Option-level multiplier** is `apply_multiplication` + `price_calculate_type`
  (no `multiplier`/`multiplier_type` on `AdditionalOptionInput`). `multiplier` (Float)
  is attribute-level. Per-attribute price: `setProductsAttributePrice` /
  `setQuantityBasedAttributePrice`.

See `plans/2026-06-17-ops-apparel-stock-sku-workflow.md` for the full verified
apparel push sequence.

## Refresh

When OPS publishes a new collection, re-pull the backend JSON above and overwrite
this file (datestamp the filename). Never hand-edit.
