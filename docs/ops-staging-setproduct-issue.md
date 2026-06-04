# OPS Staging — `setProduct` returns INTERNAL_SERVER_ERROR

**Date:** 2026-06-04
**Environment:** OPS **staging** (`https://staging.visualgraphx.com/api`)
**Status:** Blocked — needs OPS server-side log. Our client side is verified working up to the OPS call.

---

## Summary

The `setProduct` GraphQL mutation on OPS staging returns a generic, masked
`INTERNAL_SERVER_ERROR` for **every** payload we send — including OnPrintShop's own
documented minimal example. The **same OAuth token** successfully creates categories
(`setProductCategory`) and runs read queries, so authentication and permissions are fine.
This points to a **server-side error in the `setProduct` resolver**, not the request.

We need the OPS staging **Express app-server log** to see the real exception (the GraphQL
layer masks it).

---

## Environment / credentials

- GraphQL endpoint: `POST https://staging.visualgraphx.com/api/graphql`
- OAuth2 token endpoint: `POST https://staging.visualgraphx.com/api/oauth/token`
  - grant type `client_credentials`, **JSON body** (form-encoded returns 401)
- OAuth Client ID: `2190fd7c-596b-11ef-9e9f-06bd824fb541`
- Server: `Express` (header `x-powered-by: Express`), fronted by Cloudflare

## What works with this token (auth/permissions are fine)

- `setProductCategory` **succeeds** → created category **id 538** ("API Hub Imports")
- Introspection + read queries succeed (e.g. `{ products { ... } }`; the schema correctly
  rejects `product` and suggests `products`)

## What fails — exact request to reproduce

```graphql
mutation SetProduct($input: ProductInput!) {
  setProduct(input: $input) { result message products_id }
}
```

Minimal variables (matches the OnPrintShop n8n node's own default `ProductInput` example):

```json
{ "input": { "category_id": 0, "visible": 1, "products_title": "SA-TEST FINAL", "products_internal_title": "L420FIN" } }
```

### Exact response (verbatim, masked)

```
HTTP 200   (server: Express, via Cloudflare)
{
  "errors": [
    {
      "message": "Internal error. Looks like something went wrong on our end.",
      "extensions": { "code": "INTERNAL_SERVER_ERROR" },
      "level": "error"
    }
  ],
  "data": { "setProduct": null }
}
```

GraphQL returns HTTP 200 and hides the real exception behind `INTERNAL_SERVER_ERROR`.
There is **no further detail available to the API client** — the stack trace lives only in
OPS's server log.

## Variants tried — all return the identical 500

- The minimal payload above (OPS/n8n default)
- `category_id: 538` (the real category we created) **and** `category_id: 0`
- With and without `products_id: 0`
- With and without `product_description`
- A "rich" payload adding: `product_type`, `price_defining_method`, `measurement_unit_id`,
  `product_service_type`, `size_visible`, `enable_stock_management`, `predefined_product_type`,
  `sort_order`, `external_catalogue`

No payload variation changes the result → the cause is server-side, not in the request.

---

## Important: OPS's own Postman docs don't document `setProduct`

OPS's published Postman documentation
(`https://documenter.getpostman.com/view/33263100/2sBXijHWys`) was reviewed. It documents the
**read/query** API plus order/stock writes — but it does **not** include a `setProduct` (or
`setProductSize` / `setProductCategory` / any product-create) mutation. The only two mutations
documented are:

- `updateOrderStatus`
- `updateProductStock`

(The linked anchor `#c7d204be-…` is the `productsDetails` **query**, not a create mutation.)

`setProduct` **does** exist in the live GraphQL schema (it's introspectable and accepts a
`ProductInput`), but it is undocumented here and 500s for every input. So the open question for
OPS is now sharper:

> **Is `setProduct` a supported/enabled product-creation operation on this OPS instance, and if
> so what are its required inputs / store-site context? If product creation is NOT meant to go
> through `setProduct`, what is the correct API path to create a product?**

A useful confirmation from the documented `productsDetails` query: OPS products read back with
`default_category_id` / `associated_category_ids` (category by **id**), `product_size { size_id
products_id size_title … }`, `price_defining_method`, `measurement_unit_id`, `product_type`,
`predefined_product_type`. This matches the `setProductSize` field fix we made (`size_id` /
`size_title`) and confirms category is id-based — but none of it explains the `setProduct` 500.

## Documented `updateProductStock` contract (from OPS Postman)

The one product-write OPS documents. Pulled verbatim from the collection
(`/Mutations/Products/Update Product Stock`):

```graphql
mutation updateProductStock ($stock_id: Int, $product_sku: String, $action: UpdateProductStockActionEnum!, $input: UpdateProductStockInput!) {
    updateProductStock (stock_id: $stock_id, product_sku: $product_sku, action: $action, input: $input) {
        result
        message
        stock_id
        stock_quantity
    }
}
```
```json
{
  "stock_id": 88,
  "product_sku": "",
  "action": "Remove",
  "input": { "stock_quantity": 20, "comment": "Removed." }
}
```

Notes for wiring stock back in (currently deferred behind `OPS_PUSH_INCLUDE_STOCK=1`):
- The mutation **signature matches ours** already (`stock_id, product_sku, action!, input!`).
- OPS's canonical example targets by **`stock_id`** (here 88) with `product_sku` left empty —
  i.e. you update an **existing** stock row by its id. `action` enum = `Add | Remove | Reset`.
  `input` = `{ stock_quantity, comment }` (comment optional).
- Implication: per-variant stock can't be set in the same create pass — after creating the
  product/sizes we must **read back the OPS-assigned `stock_id`s** (via the `productStocks` /
  `productsDetails` query) and then `updateProductStock(stock_id=…, action="Reset",
  input={stock_quantity})`. Targeting by `product_sku` only works if OPS knows that SKU, which
  it won't for a freshly created size (OPS `ProductSizeInput` has no SKU field).

## Steps for Christian (OPS side)

1. Open the OPS **staging Express app-server / error log** (the masked GraphQL response is not
   enough — we need the underlying exception).
2. Find the `setProduct` GraphQL operations from **2026-06-04 (UTC)** for OAuth client
   `2190fd7c-596b-11ef-9e9f-06bd824fb541`. Grep by the test identifiers we sent:
   - `products_internal_title`: `L420FIN`, `L420RAW`, `L420RICH`, `L420TA`, `L420TB`, `L420TC`
   - `products_title`: `SA-TEST FINAL`, `SA-TEST RAW`, `SA-TEST RICH`
   - Cloudflare ray id for one attempt: **`a065c8cd38bdce12-SIN`** @ `2026-06-04 09:06:56 GMT`
3. Capture the **full stack trace / exception** behind `INTERNAL_SERVER_ERROR`.
4. If easy, run the minimal `setProduct` above with a known-good API user/store and confirm
   whether it 500s for OPS too, or only for our OAuth client.

## Questions for OPS

- What is the server-side exception for these `setProduct` calls?
- Are there **required `ProductInput` fields** beyond title / internal-title / category that the
  resolver assumes (e.g. `product_type`, `price_defining_method`, `measurement_unit_id`, a
  store/site context) whose absence causes a 500 instead of a validation error?
- Does this OAuth client need to be tied to a specific **store/site** for product creation?
  (Category creation worked; product creation may need a default store.)

---

## For reference — our side is fixed and verified

These were real client-side bugs we found and corrected while reaching the OPS call (so they are
*not* the cause of the 500):

- **OAuth token request** must be a JSON body (staging 401s on form-encoded). Fixed.
- **`setProduct` field names** aligned to the live OPS `ProductInput` (introspected): removed
  `category_name` / `brand` / `products_image`; `products_description` → `product_description`.
- **`setProductSize`** aligned: `size_id` / `size_title` (OPS sizes have no color/SKU field);
  `visible` is a String.
- Preflight (auth, pricing, images, markup) passes; the push reaches OPS and fails only at the
  `setProduct` server error.
