# N8N OnPrintShop Node Expansion & Refactor

**Date:** 2026-04-22
**Goal:** Modularize the 8,000+ line node monolith and implement missing P0/P1 operations identified in the Gap Analysis.
**Status:** Implementation Approved

---

## Phase 1: Monolith Refactor (Modularization)

To improve maintainability and prevent editor lag/memory issues, we will split `OnPrintShop.node.ts` into a directory-based structure.

**Target Structure:**
```
api-hub/n8n-nodes-onprintshop/nodes/OnPrintShop/
├── OnPrintShop.node.ts (Main Router)
├── GenericFunctions.ts (API/Auth Logic)
├── CustomerDescription.ts (Properties + Methods)
├── ProductDescription.ts (Properties + Methods)
├── OrderDescription.ts (Properties + Methods)
└── [OtherResources]Description.ts
```

### Steps:
1. **GenericFunctions.ts:** Extract the OAuth2 token retrieval and `helpers.request` wrapper logic.
2. **Resource Descriptions:** Move the `properties` collection and execution sub-logic for each resource into dedicated `*Description.ts` files.
3. **OnPrintShop.node.ts:** Clean up the main class to import these descriptions and delegate the `execute` method based on the selected resource.

---

## Phase 2: Fix P0 "Broken" Contracts

Correct existing operations that deviate from the official OPS GraphQL schema.

1. **Mutation > Update Order Status:** 
   - Add `type` variable (Order vs. Product).
   - Implement the `input` object payload wrapper.
   - Support `orders_products_id` for product-level updates.
2. **Mutation > updateProductStock:**
   - Remove the broken stub under the `mutation` resource.
   - Standardize on the working version under the `product` resource.
3. **Order > createShipment:**
   - Verify and fix the `shipmentinfo` array structure to ensure it matches the `setShipment` mutation contract.

---

## Phase 3: High-Priority Push Operations (Phase A)

Implement the first batch of missing mutations required for the automated sync pipeline.

| Resource | Operation | GraphQL | Priority |
|---|---|---|---|
| **Product** | Set Product | `setProduct` | High |
| **Product** | Set Product Price | `setProductPrice` | High |
| **Batch** | Get Batch | `getBatch` | High |
| **Batch** | Set Batch | `setBatch` | High |
| **Quote** | Get Quote | `get_quote` | High |
| **Quote** | Set Quote | `setQuote` | High |
| **Design** | Update Images | `setOrderProductImage` | High |
| **Design** | Add Proof | `addProofVersion` | High |
| **Design** | Set Design Link | `setProductDesign` | High |

---

## Phase 4: Verification

1. **Automated Build:** Run `npm run build` in `api-hub/n8n-nodes-onprintshop` to ensure TS compilation passes.
2. **Manual Smoke Test:** Use a manual n8n trigger to call `setProduct` with a test SKU and verify the product appears in the OnPrintShop admin panel.
3. **Docker Sync:** Restart the n8n container to ensure the new directory structure is correctly mapped and loaded by the n8n runtime.
