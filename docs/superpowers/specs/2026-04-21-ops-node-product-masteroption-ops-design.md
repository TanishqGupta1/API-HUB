# OPS Node — Product & Master Option Operations

**Date:** 2026-04-21
**Scope:** Add 18 missing OnPrintShop GraphQL operations to the `n8n-nodes-onprintshop` custom node.
**Related:** `n8n-nodes-onprintshop/OPS-NODE-GAP-ANALYSIS.md`, V1c OPS Push phase in `plans/2026-04-16-v1-integration-pipeline.md`.

---

## 1. Goal

The custom n8n node currently implements 22 operations out of the 65 approved in the OPS knowledge pack. V1c (OPS Push) cannot complete until product-write and master-option-write paths exist. This spec adds the 18 product and master-option operations needed to unblock OPS Push, with structure that avoids further growth of the 8173-line monolith.

## 2. Scope

### In scope (18 operations)

| Type | Operation | Purpose |
|------|-----------|---------|
| Query | `getMasterOptionTag` | Read master option tags |
| Query | `getOptionGroup` | Read option groups |
| Query | `getCustomFormula` | Read option formulas |
| Query | `getMasterOptionRange` | Read master option ranges |
| Query | `product_additional_options` | Read product additional options |
| Mutation | `setProduct` | Create/update product |
| Mutation | `setProductPrice` | Product pricing rules |
| Mutation | `setProductSize` | Product size catalog |
| Mutation | `setProductPages` | Multi-page product config |
| Mutation | `setProductCategory` | Product category assignment |
| Mutation | `setProductDesign` | Ziflow design links |
| Mutation | `setAssignOptions` | Assign options to product |
| Mutation | `setProductOptionRules` | Master option rules |
| Mutation | `setCustomFormula` | Option formulas |
| Mutation | `setOptionGroup` | Option groups |
| Mutation | `setMasterOptionTag` | Master option tags |
| Mutation | `setMasterOptionAttributes` | Master option attributes |
| Mutation | `setMasterOptionAttributePrice` | Master option attribute prices |

### Out of scope

- Beta mutations (`setAdditionalOption`, `setAdditionalOptionAttributes`, `setProductsAttributePrice`, `setQuantityBasedAttributePrice`)
- Blocked upstream operations (`setMasterOption`, `setMasterOptionRange`)
- P0 broken-contract fixes (`updateOrderStatus`, `updateProductStock` legacy, `createShipment`) — tracked separately in V1c
- Refactor of existing 22 operations
- Any operation outside product / master-option domain

## 3. File Structure

Extract new ops into a subdirectory. Existing `OnPrintShop.node.ts` monolith is not touched except to wire two new resource cases.

```
n8n-nodes-onprintshop/
  nodes/
    OnPrintShop.node.ts                # existing; wire two new resource cases
    OnPrintShop/
      descriptions/
        ProductMgmtDescription.ts      # resource=productMgmt: 1 query + 7 mutations
        MasterOptionDescription.ts     # resource=masterOption: 4 queries + 6 mutations
      execute/
        product.ts                     # productExecute(this, i)
        masterOption.ts                # masterOptionExecute(this, i)
      graphql/
        queries.ts                     # 5 query strings
        mutations.ts                   # 13 mutation strings
      types.ts                         # TypeScript types for GraphQL inputs
  scripts/
    sync-ops-schemas.ts                # pulls .md from knowledge pack, generates graphql/*.ts
```

**Resource naming:** `productMgmt` (not `product`) and `masterOption` are new resources, keeping the existing read-only `product` resource untouched. Avoids merge conflicts and keeps concerns separated.

**Wiring in `OnPrintShop.node.ts`:**

```ts
// description array — append two resource options
{ name: 'Product Management', value: 'productMgmt' },
{ name: 'Master Option',      value: 'masterOption' },

// execute() switch — append two cases
case 'productMgmt':  return productExecute(this, i);
case 'masterOption': return masterOptionExecute(this, i);
```

No other change to the existing file. Description imports pulled in at top.

## 4. UI Parameter Style (Hybrid)

For each mutation:

- **Common fields (3–8 per op):** exposed as typed top-level n8n parameters. Source: knowledge-pack operation docs mark which variables are required or commonly used.
- **`additionalFields` collection:** n8n `fixedCollection` holding remaining input keys. User picks which to populate.
- **Server-side merge:** `variables.input = { ...structuredFields, ...additionalFields }`.

For queries, standard n8n `limit`, `offset`, filter params. Field selection is hard-coded to the knowledge-pack canonical selection set (configurable later if needed).

## 5. Data Flow

```
n8n UI params
  → description layer (validation, type coercion)
  → execute handler
  → build { query, variables } from graphql/*.ts
  → this.helpers.httpRequestWithAuthentication('onPrintShopApi', {...})
  → OPS GraphQL endpoint
  → unwrap data[opName] → return to n8n
```

Auth: existing `OnPrintShopApi.credentials.ts` OAuth2 flow reused. No credential changes.

## 6. Error Handling

| Condition | Action |
|-----------|--------|
| Response `errors[]` non-empty | Throw `NodeApiError` with concatenated messages and path |
| HTTP 4xx/5xx | Bubble to n8n default retry mechanism |
| Missing required param (e.g., `setProduct` without `title`) | Throw `NodeOperationError` pre-request |
| Auth failure (401) | Bubble; user re-auths via credential UI |
| Response shape mismatch (data[op] missing) | Throw `NodeApiError("Unexpected response shape")` with full payload attached |

## 7. Testing

### Unit (mandatory)

- Per-handler test asserts `{ query, variables }` matches expected for given input.
- Fixture pairs: input params → expected GraphQL payload. Pulled from knowledge-pack operation `.md` docs and `artifacts/live/VGX_AUTOTEST/*-passed.json`.
- Framework: existing `jest` setup in `n8n-nodes-onprintshop/` (add if absent).

### Live smoke (optional)

- `npm run test:live` — hits OPS staging endpoint with env creds (`OPS_STAGING_URL`, `OPS_CLIENT_ID`, `OPS_CLIENT_SECRET`).
- Asserts 200 + `data[op]` present. Does not assert specific IDs (staging state varies).
- Skipped in CI by default; run manually before release.

## 8. Source-of-Truth Pipeline

Schemas maintained via automated sync from the knowledge pack, not hand-maintained.

```
scripts/sync-ops-schemas.ts:
  for each op in 18:
    gh api repos/VisualGraphxLLC/ops-automation-knowledge-pack/contents/docs/operations/<type>/<op>.md
    extract first ```graphql code block (the canonical query/mutation)
    extract variables table (name → type → required)
  write to graphql/queries.ts, graphql/mutations.ts, types.ts
```

- Run: `npm run sync:ops`
- Idempotent. Commit diff when OPS changes.
- CI check: run on PR, fail if committed `graphql/*.ts` diverges from regenerated output.

## 9. Deliverables

1. 7 new source files under `nodes/OnPrintShop/` (2 descriptions, 2 execute handlers, 2 GraphQL string files, 1 types file) as listed in Section 3.
2. 1 edit to `nodes/OnPrintShop.node.ts` (wire two resource cases + imports).
3. `scripts/sync-ops-schemas.ts` + `package.json` script entry.
4. Unit tests covering all 18 ops (18 handler tests minimum).
5. Optional live smoke test script.
6. README update: new resources listed with operation tables.
7. `OPS-NODE-GAP-ANALYSIS.md` updated — 18 ops moved from "Missing" to "Implemented".

## 10. Success Criteria

- All 18 operations callable from n8n workflow editor with typed UI.
- Unit tests pass for all 18 handlers.
- At least 1 live smoke run succeeds against OPS staging (any passing op).
- `OnPrintShop.node.ts` line-count delta < +50 lines (only resource wiring added).
- Gap analysis coverage: mutation coverage rises from 11% (4/35) to ~49% (17/35 = 4 existing + 13 new). Query coverage rises from 53% (16/30) to ~70% (21/30 = 16 existing + 5 new).

## 11. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Knowledge pack schema drifts from live OPS API | Live smoke test catches drift; sync script re-pullable |
| `input` object shape under-documented for a specific op | Fall back to `product-additional-option-staging-passed.json` live fixture for that op |
| New resource names (`productMgmt`, `masterOption`) confuse users | README clearly labels them; existing `product` resource unchanged |
| Merge conflict with concurrent V1c work on `OnPrintShop.node.ts` | Resource-case wiring is additive, low-conflict surface |
| Beta/blocked ops creep into scope | Explicitly excluded in Section 2; review before adding |

## 12. Open Questions

None at time of writing. All design choices locked:
- Scope: 18 ops (user-confirmed, beta excluded)
- Structure: extract new ops only (option B)
- UI: hybrid structured + additionalFields (option C default)
- Source: knowledge pack via `gh api` (option A)
