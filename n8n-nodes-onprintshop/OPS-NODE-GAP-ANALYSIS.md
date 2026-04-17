# OPS Node Gap Analysis

**Generated:** 2026-04-04
**Node file:** `nodes/OnPrintShop.node.ts` (7535 lines)
**Knowledge pack:** `VisualGraphxLLC/ops-automation-knowledge-pack` (`OPS_OPERATION_CATALOG.md` + `OPS_MASTER_REFERENCE.md`)

---

## Executive Summary

The n8n node implements **~22 distinct operations** across 10 resources. The knowledge pack catalogs **30 approved queries** and **35 approved mutations** (65 total approved operations). The node is missing the vast majority of mutations and a significant number of queries. Two implemented mutations use incorrect GraphQL contracts compared to the knowledge pack. Several node-only convenience operations (Get/Get Many splits, legacy resource stubs) have no direct knowledge pack equivalent but are not problematic.

---

## 1. MISSING OPERATIONS -- Approved in Knowledge Pack, Absent from Node

### 1.1 Missing Queries (14 operations)

| # | Knowledge Pack Operation | GraphQL Operation | Variables | Priority |
|---|------------------------|-------------------|-----------|----------|
| 1 | **Get Batch** | `getBatch` | batch_id, search, limit, offset | High -- used in production workflows |
| 2 | **Master Option Tag** | `getMasterOptionTag` | master_option_tag_id, limit, offset | Medium |
| 3 | **Option Group** | `getOptionGroup` | prod_add_opt_group_id, use_for, limit, offset | Medium |
| 4 | **Option Formulas** | `getCustomFormula` | formula_id, limit, offset | Medium |
| 5 | **Master Option Ranges** | `getMasterOptionRange` | range_id, option_id, limit, offset | Medium |
| 6 | **Countries** | `get_countries` | countries_id, status, limit, offset | Low |
| 7 | **Markup Master** | `get_store_markup` | corporate_markup_id, limit, offset | Low |
| 8 | **Get Payment Terms** | `get_payment_term_master` | term_id, limit, offset | Low |
| 9 | **Store Address** | `storeaddress` | corporate_id, corporate_address_id, limit, offset | Low |
| 10 | **Store Details** | `get_store` | corporate_id, email, status, limit, offset | Medium |
| 11 | **Department Details** | `get_departments` | department_id, corporate_id, limit, offset | Medium |
| 12 | **FAQs Category** | `get_faq_category` | faqcat_id, status, limit, offset | Low |
| 13 | **Get Quote** | `get_quote` | quote_id, user_id, limit, offset | High -- needed for quote workflows |
| 14 | **Get Quote Product** | `quoteproduct` | quote_id, quote_products_id, limit, offset | High -- needed for quote workflows |

### 1.2 Missing Mutations (33 operations)

| # | Knowledge Pack Operation | GraphQL Operation | Variables | Priority |
|---|------------------------|-------------------|-----------|----------|
| 1 | **Set Shipment** | `setShipment` | order_id, shipment_id, tracking_number, shipmentinfo | High -- node has `createShipment` but uses different contract (see Section 3) |
| 2 | **Set Customer** | `setCustomer` | customer_id, input | High -- node has create/update but uses different contract (see Section 3) |
| 3 | **Set Order Product** | `setOrderProduct` | order_product_id, width, height, input | High |
| 4 | **Set Order Product Extra info only** | `setOrderProduct` | order_product_id, width, height, input | Medium |
| 5 | **Set Batch** | `setBatch` | batch_id, input | High |
| 6 | **Set Master Option Rules** | `setProductOptionRules` | input | Medium |
| 7 | **Set Option Formulas** | `setCustomFormula` | input | Medium |
| 8 | **Set Option Group** | `setOptionGroup` | input | Medium |
| 9 | **Set Master Option Tags** | `setMasterOptionTag` | input | Medium |
| 10 | **Set Master option attributes** | `setMasterOptionAttributes` | input | Medium |
| 11 | **Set Master option Attribute price** | `setMasterOptionAttributePrice` | input | Medium |
| 12 | **Set Product** | `setProduct` | input | High |
| 13 | **Set Product Price** | `setProductPrice` | input | High |
| 14 | **Assign Options** | `setAssignOptions` | input | Medium |
| 15 | **Set Product Size** | `setProductSize` | input | Medium |
| 16 | **Set Product Pages** | `setProductPages` | input | Medium |
| 17 | **Set Store Address** | `setStoreAddress` | input | Low |
| 18 | **Set Department** | `setDepartment` | input | Medium |
| 19 | **Set Store** | `setStore` | input | Low |
| 20 | **Set Markup Master** | `setStoreMarkup` | input | Low |
| 21 | **Set Product Category** | `setProductCategory` | input | Medium |
| 22 | **Set FAQ Category** | `setFaqCategory` | input | Low |
| 23 | **Set Quote** | `setQuote` | userid, quote_id, selectedShippingType, quote_title, input | High |
| 24 | **Set Order - Staging** | `setOrder` | userid, order_id, selectedShippingType, order_title, input | Medium (staging) |
| 25 | **Modify Order Product - Beta** | `modifyOrderProduct` | orderid, input | Medium (beta) |
| 26 | **Set Product Additional Option - Beta** | `setAdditionalOption` | input | Low (beta) |
| 27 | **Set Product Additional Option Attribute - Beta** | `setAdditionalOptionAttributes` | input | Low (beta) |
| 28 | **Set Product Additional Option Attribute Price - Beta** | `setProductsAttributePrice` | input | Low (beta) |
| 29 | **Set Quantity Based Attribute Price - Beta** | `setQuantityBasedAttributePrice` | input | Low (beta) |
| 30 | **Update Order Product Images** | `setOrderProductImage` | order_product_id, input | High |
| 31 | **Update ziflow link images wise** | `setOrderProductImage` | order_product_id, update_ziflow_link_only, input | High -- Ziflow integration |
| 32 | **Add proof version** | `setOrderProductImage` | order_product_id, update_ziflow_link_only, add_version_file_only, ask_for_approval, input | High -- Ziflow integration |
| 33 | **Set Product Design** | `setProductDesign` | order_product_id, ziflow_link, ziflow_preflight_link | High -- Ziflow integration |

---

## 2. INCORRECT IMPLEMENTATIONS -- Node vs Knowledge Pack Contract Mismatch

### 2.1 `mutation > updateOrderStatus` -- Wrong GraphQL contract

**Node (line 4789-4795):**
```
Variables: orders_id (Int!), orders_status_id (Int!)
GraphQL: updateOrderStatus(orders_id, orders_status_id)
```

**Knowledge Pack:**
```
Operation: "Update Order or Order Product Status"
GraphQL: updateOrderStatus
Variables: type, orders_id, orders_products_id, input
```

**Gaps:**
- Node is MISSING the `type` variable (required to distinguish order vs order-product status updates)
- Node is MISSING the `orders_products_id` variable (required for product-level status updates)
- Node is MISSING the `input` variable (the actual status payload)
- Node sends `orders_status_id` directly as a top-level variable, but the knowledge pack contract uses `input` for the status payload
- **Impact:** Node can only update order-level status with a non-standard contract. Cannot update order-product status at all.

### 2.2 `mutation > updateProductStock` (legacy resource) -- Wrong GraphQL contract

**Node (line 4797-4805):**
```
Variables: product_id (Int!), products_sku (String!), quantity (Int!)
GraphQL: updateProductStock(product_id, products_sku, quantity)
```

**Knowledge Pack:**
```
Operation: "Update Product Stock"
GraphQL: updateProductStock
Variables: stock_id, product_sku, action, input
```

**Gaps:**
- Node uses `product_id` + `products_sku` + `quantity` -- none of these match the knowledge pack contract
- Knowledge pack uses `stock_id`, `product_sku` (not `products_sku`), `action` (CREDIT/DEBIT/SET enum), and `input` object
- The node's `product > updateStock` operation (line 6426-6513) has the CORRECT contract with `stock_id`, `product_sku`, `action`, `input` -- so this legacy mutation resource is a stale duplicate
- **Impact:** The legacy `mutation > updateProductStock` will likely fail against the actual API. The `product > updateStock` implementation is correct.

### 2.3 `order > createShipment` vs Knowledge Pack `Set Shipment`

**Node (line 5698+):**
```
Variables: orderIdCreate, shipmentId, trackingNumber, packages (fixedCollection with weight/length/width/height/tracking/orderProducts)
GraphQL: setShipment (inferred from execution)
```

**Knowledge Pack:**
```
Operation: "Set Shipment"
GraphQL: setShipment
Variables: order_id, shipment_id, tracking_number, shipmentinfo
```

**Gaps:**
- Node variable `orderIdCreate` should map to `order_id` -- naming differs but may be mapped in execution
- Node variable `trackingNumber` should map to `tracking_number`
- Knowledge pack uses `shipmentinfo` as the package payload wrapper; node builds a custom `packages` structure
- **Risk:** Medium -- the node may or may not correctly transform its UI fields to the `shipmentinfo` GraphQL variable. Requires execution-level verification.

---

## 3. FIELD-LEVEL GAPS -- Node Operations Missing Fields from Knowledge Pack

### 3.1 `Order and Order Product Statuses` query

**Knowledge Pack variable:** `process_status_id`

**Node `status > getStatus` (line 4128-4141):** Has `processStatusId` field -- OK, matches.
**Node `status > orderStatus` / `orderProductStatus` (legacy, line 4774-4786):** These legacy operations under the `status` resource do NOT accept `process_status_id` as a filter variable. They appear to fetch all statuses without filtering.

### 3.2 `Product Stocks` query

**Knowledge Pack variables:** `product_id`, `limit`, `offset`

**Node `productStocks > getAll` (line 338-366):** Has `product_id` and `products_sku` and `limit`/`offset`. The `products_sku` filter is a node addition not in the knowledge pack catalog. This is additive (not a gap), but worth noting it may not be supported by the actual GraphQL schema.

### 3.3 `Customer Address Details` query

**Knowledge Pack variables:** `user_id`

**Node `customerAddress > getAll` (line 98-107):** Has `userId` mapped to `user_id` -- OK, matches.

### 3.4 `Order Shipment Details` query

**Knowledge Pack variables:** `orders_id`

**Node `orderShipment > getAll` (line 226-237):** Has `orders_id` plus `from_date`, `to_date`, `order_status`, `customer_id`, `order_type` -- these extra filters are node additions. The knowledge pack only documents `orders_id`. These additions may or may not be supported upstream.

### 3.5 `ShipTo Multiple Address` query

**Knowledge Pack variables:** `order_id`
**Knowledge Pack status:** BLOCKED

**Node `shipToMultipleAddress > getAll` (line 284-296):** Has `orders_id` (not `order_id`). The naming difference (`orders_id` vs `order_id`) is a potential mismatch. The knowledge pack notes this operation is blocked with "Data not found" errors anyway.

---

## 4. DUPLICATE / OVERLAPPING IMPLEMENTATIONS

| Node Location | Correct Version | Legacy/Duplicate Version | Issue |
|--------------|----------------|-------------------------|-------|
| `product > updateStock` (line 3194-3309, exec 6426-6513) | Uses `stock_id`/`product_sku`/`action`/`input` -- matches knowledge pack | `mutation > updateProductStock` (line 425-449, exec 4797-4805) uses `product_id`/`products_sku`/`quantity` -- wrong contract | Legacy version should be removed or redirected |
| `status > getStatus`/`getManyStatus` (line 4100-4327, exec 7372+) | Proper implementation with `process_status_id`, field selection, pagination | `status > orderStatus`/`orderProductStatus` (line 369-394, exec 4774-4786) -- minimal legacy implementation | Legacy version is redundant |
| `order > createShipment` (line 2103-2241, exec 5698+) | Full implementation with packages | No knowledge pack `setShipment` equivalent yet | Should be verified against `setShipment` contract |

---

## 5. STAGING / CATALOG-ONLY OPERATIONS (Not Approved but Documented)

These exist in the knowledge pack with `catalog_only` coverage and are NOT in the node. They are listed here for completeness but are lower priority since they are staging/experimental.

| Operation | GraphQL | Status |
|-----------|---------|--------|
| Store Credit Summary | `storeCreditSummary` | catalog_only |
| Account Summary | `accountSummary` | catalog_only |
| Product Additional Option | `product_additional_options` | catalog_only |
| Product Additional Attribute Price | `products_attribute_price` | catalog_only |
| Quantity Based Attribute Price | `products_attribute_price` | catalog_only |

---

## 6. BLOCKED OPERATIONS (Knowledge Pack Documents as Non-Functional)

These are documented in the knowledge pack but are currently blocked/failed at the API level. The node should NOT implement them until unblocked.

| Operation | GraphQL | Blocker |
|-----------|---------|---------|
| Notify User | `notifyUser` | 503 AxiosRequest error |
| Set Master option range | `setMasterOptionRange` | "Referenceranges is not defined" |
| Set Master option | `setMasterOption` | Internal Server Error |
| Set FAQ | `setFaq` | "ReferenceisObject is not defined" |
| Set Scheduler | `setScheduler` | Field does not exist on Mutation type |
| ShipTo Multiple Address | `shipToMultipleAddress` | "Data not found" (node implements this anyway) |

---

## 7. PRIORITIZED IMPLEMENTATION ROADMAP

### P0 -- Fix Broken Contracts (Immediate)
1. **Fix `mutation > updateOrderStatus`** to use `type`, `orders_id`, `orders_products_id`, `input` variables per knowledge pack
2. **Remove or deprecate `mutation > updateProductStock`** -- the `product > updateStock` operation already has the correct contract
3. **Verify `order > createShipment`** sends correct `shipmentinfo` structure matching `setShipment` contract

### P1 -- High-Value Missing Operations
4. **Get Batch** (`getBatch`) -- used in production batch management
5. **Get Quote / Get Quote Product** (`get_quote`, `quoteproduct`) -- quote workflow enabler
6. **Set Order Product** (`setOrderProduct`) -- order product management
7. **Set Batch** (`setBatch`) -- batch management write path
8. **Set Product / Set Product Price** (`setProduct`, `setProductPrice`) -- product catalog management
9. **Update Order Product Images / Set Product Design** (`setOrderProductImage`, `setProductDesign`) -- Ziflow integration
10. **Add proof version / Update ziflow link** -- Ziflow proof management

### P2 -- Medium-Value Missing Operations
11. Store Details, Department Details, Set Department
12. Master Option Tag, Option Group, Option Formulas, Master Option Ranges
13. Set Master Option Rules/Tags/Attributes/Attribute Price
14. Assign Options, Set Product Size, Set Product Pages, Set Product Category
15. Set Quote, Modify Order Product

### P3 -- Low-Value / Staging
16. Countries, Markup Master, Get Payment Terms, Store Address
17. Set Store, Set Store Address, Set Markup Master, Set FAQ Category
18. All Beta/Staging mutations

---

## 8. COVERAGE STATISTICS

| Category | Knowledge Pack (Approved) | Node Implements | Coverage |
|----------|--------------------------|-----------------|----------|
| Queries | 30 | 16 | **53%** |
| Mutations | 35 | 4* | **11%** |
| **Total** | **65** | **20** | **31%** |

*Mutations counted: updateOrderStatus (broken contract), updateProductStock (correct via product resource, broken via mutation resource), createShipment (unverified contract), setCustomer (via customer create/update -- different contract).

**Node-only operations not in knowledge pack:** Product Get Simple/Detailed split, Customer Get by email, legacy status operations -- these are UI conveniences that map to knowledge pack queries with different parameterization.
