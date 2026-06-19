# Team Brief — OPS Push Correctness & Open PRs

**Date:** 2026-06-17
**Owner:** Tanishq (PM)
**Context:** Several open PRs built the OnPrintShop (OPS) push on guessed or stale
GraphQL field names. The live OPS schema is now vendored; this brief is the single
set of actions to get the push correct and unblock apparel onboarding.

## Ground rule (everyone)

**Verify every OPS field/mutation against the vendored live collection before
writing push code — do not invent fields.**

- Source of truth: `docs/ops/OnPrintShop_GraphQL_API_live_2026-06-17.postman_collection.json`
  (81 ops; see `docs/ops/SOURCE.md` for the facts that bit us).
- Verified apparel push sequence: `plans/2026-06-17-ops-apparel-stock-sku-workflow.md`.

## Priority 1 — Stock blocker (product 602)

Not an OPS gap. The supported sequence:

```
setProduct        product_type="15", enable_stock_management=1 (Only Size) or 2 (Size+Option), main_sku
setProductSize    per size
getProductSkuMatrix(products_id[, prod_add_opt_ids])   → valid size/option combos
setProductSku     inputs:[...], sku_type MUST match enable_stock_management (1→size_wise, 2→size_option_wise)
updateProductStock(product_sku=<a registered variant SKU>, action: Add, input:{stock_quantity, comment})
productStocks(product_id)   → stock_id for later edits
setProductPrice   per (products_id, size_id)
```

Why 602 failed: `1745Y` is the **main_sku** (product-level, `size_id=0`) — not a
variant SKU; and SKUs weren't registered through the matrix in the matching mode.

**Action (assignee TBD): run this once on staging 602 and report** — do stock rows
appear after a matching `setProductSku`? This confirms the only inferred step.

## Per-PR actions

| PR | Owner | Action |
|----|-------|--------|
| **#180** | vidhi | Drop option-level `multiplier`/`multiplier_type` (not real fields). Use `apply_multiplication` + `price_calculate_type`; per-size price via `setProductsAttributePrice` / `setQuantityBasedAttributePrice`. `setAdditionalOption` takes batch `inputs:[]`. |
| **#181** | sinchana | Stock enum is fine (`Reset` valid) — fix only the misleading test name/comment. Then: fix the customer product-type toggle save/read, **remove committed dev DB credentials + rotate**, gate the live image mutation. |
| **#182** | urvashi | `setProductSku` is real but is a batch `inputs:[ProductSkuInput!]!` with `sku_type` + matrix ids (call `getProductSkuMatrix` first). Fix the RED test suite; add `FakeOpsClient.set_product_sku` (currently hard-fails every dry-run). |
| **#183** | vidhi | Split: land the clean rename alone; separate the OPS pipeline rewrite; add the `ops_category_mappings` migration; fix the preflight/auto-category ordering (new customers are blocked before auto-category can run). |
| **#186** | urvashi | Delete `getProductBySku` (does not exist in OPS — was a PROVISIONAL guess). Dedup via `products`/`productsDetails` filtered by `main_sku`; SKU validity via `getProductSkuMatrix`. |

(#184 V2 plan and #185 migrations already merged.)

## Questions for OnPrintShop — only if staging-602 fails

1. After a matching `setProductSku`, does `updateProductStock(product_sku, Add)`
   create the first stock row, or is an admin/bulk step still required?
2. For VG apparel, which `product_type` + `price_defining_method` matches your
   production catalog? (We will mirror an existing live product via `productsDetails`.)

## Related work already landed (main)

- Variant→option collapse (turns the color×size matrix into Color/Size options):
  design + TDD impl plans on main; implementation on branch
  `feat/variant-option-collapse` (18/18 tests pass) — pending review/merge.
- This fixes the duplicate-sizes issue (Issue B in the 602 report) on the ingest side
  via match-by-key upsert.
