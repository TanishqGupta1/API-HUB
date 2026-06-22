# Connect → Manage Catalog Ingest — Structured Plan

**Status:** `pending approval` (planning only — no code, no execution until explicit go-ahead)
**Date:** 2026-06-22
**Spans two repos:**
- **Connect** (api-hub) — Python/FastAPI: `/Users/tanishq/Documents/project-files/api-hub/api-hub/backend`
- **Manage** (GraphX-Manage) — TS/Prisma/PG18: `/Users/tanishq/Documents/project-files/GraphX-Manage`

---

## 1. Requirements Summary

GraphX Connect ingests 994+ PromoStandards/REST suppliers, normalizes them, and (per the
variant→option collapse plan) derives Color/Size options. GraphX-Manage is the new MIS /
catalog-of-record replacing OnPrintShop. This feature builds the **D41 "Connect pushes
wholesale catalog into Manage" seam**: Connect serializes normalized supplier products as
**wholesale cost** and pushes them to a Manage HTTP ingest endpoint, which maps them into
Manage's native catalog (Product + MasterOption/Attribute + binding + cost) while preserving
a Manage-owned pricing/markup/visibility overlay across re-syncs.

### Locked design decisions (from brainstorm)
1. **Transport:** direct HTTP — Manage exposes `POST /integration/connect/ingest/products`; Connect calls it. Manage owns mapping + dependency resolution.
2. **Options:** Color/Size become **tenant-level MasterOptions** in Manage, bound per-product via `ProductOptionAssignment`, reconciled by natural key (`optionKey`/`attributeKey`).
3. **Authority:** layered — Connect owns the **base** (cost, raw color/size attributes, availability); Manage owns the **overlay** (markup, sell price, visibility, `isReadyToBuy`, binding overrides). Re-sync refreshes base, never clobbers overlay.
4. **Price basis:** Connect sends **wholesale net cost only** (no markup). Manage's `Markup(appliedOn=VENDOR_PRICE)` + D13 engine owns all sell pricing. Connect's `apply_markup` is skipped for Manage-bound products.

### Derived decisions (forced by codebase facts — see Risks for rationale)
5. **Crosswalk = new `ConnectIdMap` table on Manage.** `OpsIdMap.opsId` is `Int` (`schema.prisma:4617`); Connect refs are string/uuid (`supplier_id` + `supplier_sku`). Cannot reuse OpsIdMap. Add a parallel `ConnectIdMap` (String connectRef) + `ConnectSyncState`, mirroring `OpsIdMap`/`OpsSyncState` shape.
6. **Manage `Product.sku` is namespaced** `"{supplier_slug}:{supplier_sku}"`. `Product` is unique on `(tenantId, sku)` (`schema.prisma:554`) with no `source` column; namespacing prevents cross-supplier SKU collisions and encodes provenance in the key.
7. **Cost mapping:** single cost → `Product.vendorCost` (`schema.prisma:512`); tiered cost → `ProductPrice.vendorPrice` (`schema.prisma:776`) rows (`qtyFrom`/`qtyTo`). `ProductPrice.price` (sell, :775) left to Manage's markup engine. `Product.priceDefiningMethod` set so the cost-rollup/grid path runs (not legacy flat 0).

---

## 2. Source & Target Facts (file-cited)

### Connect emits (Python — api-hub backend)
- DTO source: `ProductIngest` family — `modules/catalog/schemas.py:259-284` (product), `:178-186` (variant), `:189-193` (variant price), `:246-256` (option), `:235-243` (attribute).
- **Cost source:** `ProductVariant.base_price` `Numeric(10,2)` — `modules/catalog/models.py:93`; tiered cost = `VariantPrice` rows `price_type="Net"` — `models.py:212-227` (unique `(variant_id, price_type, quantity_min)` :215).
- **No persisted markup** — markup applied on-the-fly via `modules/markup/engine.py:apply_markup` (`:76-123`) / `calculate_price` (`:126-196`). For the cost push, read `base_price`/`VariantPrice` directly and **skip `apply_markup`**.
- Natural key: `Product` unique `(supplier_id, supplier_sku)` — `models.py:34`; per-variant `part_id` — `models.py:92`. Supplier `slug` unique — `modules/suppliers/models.py:17`.
- Options produced by collapse: `option_key` ∈ {`color`,`size`}, slug `attribute_key`, no pricing — per `plans/2026-06-17-variant-option-collapse-impl.md`.
- Outbound HTTP pattern to mirror: `modules/ops_client/client.py` `OpsGraphQLClient` (`:53-239`, `httpx.AsyncClient`, `execute()->OpsResult`, never raises). Creds via `EncryptedJSON` (`database.py`).

### Manage targets (TS — GraphX-Manage)
- `Product` — `schema.prisma:491-560`; unique `(tenantId, sku)` :554; cost `vendorCost` :512; `markupId` :513; `priceDefiningMethod` :499; `productClass` :526; `isReadyToBuy` default false :528; `opsId String?` :494 (OPS-only — do **not** repurpose for Connect).
- `Markup` — `:598-628`; `appliedOn` (`VENDOR_PRICE`/`BASE_PRICE`) :604; unique `(tenantId, tierSlug)` :625.
- `Category` — `:638-667` unique `(tenantId, id)` :662; `Family` — `:988-1003` unique `(tenantId, slug)` :1000.
- `MasterOption` — `:786-815` unique `(tenantId, optionKey)` :812; `MasterOptionAttribute` — `:819-848` unique `(masterOptionId, attributeKey)` :845.
- `ProductAdditionalOption` (wraps `masterOptionId`) — `:904-922`; `ProductOptionAssignment` unique `(productId, additionalOptionId)` — `:926-956`; `ProductOptionBindingAttribute` — `:1595-1619`.
- `ProductPrice` — `:764-783`; `price`=sell :775, `vendorPrice`=cost :776.
- `OpsIdMap` — `:4613-4625` (`opsId Int` :4617; two unique keys :4621-4622); `OpsSyncState` — `:4570-4583`; `PendingDependency` — `:1692-1709` (`dependencyType` String).
- **Ingest pattern to mirror:** `packages/commerce/src/ops-ingest.ts` — `reverseLocalId` (:23-26), `txCrosswalk` (:29-40), `ingestOpsCustomer` (:73-119), `ingestOpsOrder` (:148-193); tenant via `requireContext()`; `source="OPS"` loop guard.
- Route layer: `apps/api/src/server.ts` integration section `:2358-2381`; handler wrapper `apps/api/src/integration-handlers.ts` (`ingestOrderHandler` :69-74) with `requireIntegration` guard (`:23-33`, permission `integration:ops:sync`).

---

## 3. Acceptance Criteria (testable)

**Manage side**
- AC1. `ConnectIdMap` + `ConnectSyncState` models exist in `schema.prisma` with unique keys `(tenantId, entityType, localId)` and `(tenantId, entityType, connectRef)`; migration applies cleanly on fresh + existing DB (idempotent guards).
- AC2. `POST /integration/connect/ingest/products` returns 200 for a valid payload and 401/403 without the integration principal (test asserts both).
- AC3. Ingesting a SanMar product with 8 colors × 6 sizes creates exactly: 1 `Product` (`sku="sanmar:<sku>"`, `vendorCost` set, `productClass="PRINT_PRODUCT"`), 2 `MasterOption`s (`color`,`size`) reused at tenant level, attributes count = 8 and 6, 2 `ProductAdditionalOption`+`ProductOptionAssignment` bindings, binding attributes = 14 total.
- AC4. Re-ingesting the **same** payload is idempotent: product/option/attribute/binding row counts unchanged; `ConnectSyncState="SYNCED"`.
- AC5. Overlay preserved: set `Product.markupId`, `isReadyToBuy=true`, and a `ProductPrice.price` (sell) on the ingested product; re-ingest; those overlay fields are **unchanged** while `vendorCost`/`ProductPrice.vendorPrice` refresh from payload.
- AC6. Tiered cost: a payload with `Net` qty-break tiers produces matching `ProductPrice` rows with `vendorPrice` set and `price` (sell) untouched by ingest.
- AC7. Missing dependency: a product referencing a not-yet-created master option (partial payload) parks a `PendingDependency` row (`dependencyType="master_option"`) and does not 500; resolves on the dependency's later arrival.
- AC8. Color/size value removed between syncs → that attribute is pruned; an emptied axis prunes the binding (mirrors collapse prune semantics).

**Connect side**
- AC9. `modules/manage_client/` exposes a `ManageClient.push_products(payload)` that posts to `MANAGE_INGEST_URL` with bearer `MANAGE_INGEST_TOKEN`, returns a never-raising `ManageResult(ok, data, error)` (mirrors `OpsResult`).
- AC10. The push builder serializes a Connect `Product` (+variants+options+`VariantPrice` Net tiers) into `ConnectProductPush` carrying **cost only** — assert no field derives from `apply_markup` (a product with an active `MarkupRule` yields identical push cost as one without).
- AC11. `POST /api/manage-push/{supplier_id}` (auth = existing app auth) pushes all of a supplier's products; returns per-product ok/error counts.
- AC12. End-to-end (staging or mocked Manage): one SanMar style round-trips Connect→Manage and appears in Manage catalog with correct option/cost shape.

---

## 4. Implementation Steps

### Phase A — Manage: crosswalk + ingest skeleton (TS)
- **A1.** Add `ConnectIdMap` + `ConnectSyncState` models to `packages/db/prisma/schema.prisma` (mirror `OpsIdMap` :4613 / `OpsSyncState` :4570 but `connectRef String`). Generate migration. *(AC1)*
- **A2.** New `packages/commerce/src/connect-ingest.ts` mirroring `ops-ingest.ts`: `reverseConnectLocalId`, `connectCrosswalk` (tx-aware, upserts `ConnectIdMap`+`ConnectSyncState="SYNCED"`), `requireContext()` for tenant. Export from `packages/commerce/src/index.ts` (alongside :38). *(AC4)*
- **A3.** Add `ingestConnectProductsHandler` to `apps/api/src/integration-handlers.ts` mirroring `ingestOrderHandler` (:69-74): `withPrincipal(verifier, token, tx => { requireIntegration(requireContext()); return ingestConnectProducts(tx, body); })`. Decide guard: reuse `integration:ops:sync` or add `integration:connect:sync` (recommend distinct permission + principal). *(AC2)*
- **A4.** Register `POST integration/connect/ingest/products` in `apps/api/src/server.ts` integration section (~:2381); import handler at :391-394. *(AC2)*

### Phase B — Manage: catalog mapping (TS)
- **B1.** `ConnectProductPush` input type (Zod/TS) — fields in §5. Validate in `connect-ingest.ts`.
- **B2.** Product upsert on `(tenantId, sku="{supplier_slug}:{supplier_sku}")` via `tx.product.upsert`; set base fields only (`name`, `vendorCost`, `productType`, `productClass="PRINT_PRODUCT"`, `priceDefiningMethod`, category). **On update, never write overlay fields** (`markupId`, `isReadyToBuy`, sell `price`). `connectCrosswalk("Product", product.id, connectRef)`. *(AC3, AC5)*
- **B3.** MasterOption reconcile: upsert `MasterOption` by `(tenantId, optionKey)` for `color`/`size`; upsert `MasterOptionAttribute` by `(masterOptionId, attributeKey)`; prune attributes absent from payload. *(AC3, AC8)*
- **B4.** Binding: ensure `ProductAdditionalOption` (wraps masterOptionId) then `ProductOptionAssignment` upsert by `(productId, additionalOptionId)`; create `ProductOptionBindingAttribute` per attribute. *(AC3)*
- **B5.** Cost: write single `vendorCost` on Product; for tiered `Net`, upsert `ProductPrice` rows (`qtyFrom`/`qtyTo`, `vendorPrice`); leave `price` (sell) untouched. *(AC6)*
- **B6.** Dependency parking: when a referenced master option/category isn't resolvable in-tx, write `PendingDependency` and skip that product gracefully; add resolver hook. *(AC7)*

### Phase C — Connect: push client + builder (Python)
- **C1.** `modules/manage_client/client.py` — `ManageClient` mirroring `OpsGraphQLClient` (`httpx.AsyncClient`, bearer token, `push_products()->ManageResult`, never raises). Config: `MANAGE_INGEST_URL` + `MANAGE_INGEST_TOKEN` (env; single Manage target). *(AC9)*
- **C2.** `modules/manage_push/builder.py` — `build_connect_product_push(product)` reads Product+variants+options+`VariantPrice` Net tiers → `ConnectProductPush`; **cost only, no `apply_markup`**. *(AC10)*
- **C3.** `modules/manage_push/routes.py` — `POST /api/manage-push/{supplier_id}` iterates the supplier's products, builds, pushes, returns counts. Register router in `main.py`. *(AC11)*

### Phase D — End-to-end (SanMar slice)
- **D1.** Mint a Manage integration principal for the VG tenant (`create-integration-principal.ts`); store its token as `MANAGE_INGEST_TOKEN` in Connect (EncryptedJSON or env).
- **D2.** Run collapse + push for one SanMar style; verify in Manage catalog. *(AC12)*

### Test tasks (TDD per phase)
- Manage: `packages/commerce/src/connect-ingest.test.ts` (AC3–AC8) + integration-auth test in `apps/api/src/` (AC2).
- Connect: `backend/tests/test_manage_push_builder.py` (AC10), `test_manage_client.py` (AC9, mocked httpx), `test_manage_push_routes.py` (AC11).

---

## 5. The `ConnectProductPush` contract (payload)

```jsonc
{
  "supplier_slug": "sanmar",            // provenance + sku namespace
  "supplier_sku": "PC54",               // supplier natural key
  "product_name": "Core Cotton Tee",
  "brand": "Port & Company",
  "product_class": "PRINT_PRODUCT",
  "category_path": ["Apparel", "T-Shirts"],
  "options": [
    { "option_key": "color", "title": "Color", "options_type": "swatch",
      "attributes": [ { "title": "Red", "attribute_key": "red", "sort_order": 0 }, ... ] },
    { "option_key": "size", "title": "Size", "options_type": "dropdown",
      "attributes": [ { "title": "S", "attribute_key": "s", "sort_order": 0 }, ... ] }
  ],
  "cost": {
    "currency": "USD",
    "base_cost": "3.42",                // → Product.vendorCost
    "tiers": [ { "qty_from": 1, "qty_to": 71, "vendor_price": "3.42" }, ... ]  // → ProductPrice.vendorPrice
  },
  "availability": { "discontinued": false },
  "provenance": { "source": "CONNECT", "connect_ref": "sanmar:PC54", "pushed_at": "<ts>" }
}
```
Manage upserts `Product.sku = "{supplier_slug}:{supplier_sku}"`; `connect_ref` is the `ConnectIdMap` key.

---

## 6. Risks & Mitigations

| # | Risk | Mitigation |
|---|------|------------|
| R1 | `OpsIdMap.opsId Int` can't hold Connect string refs (`schema.prisma:4617`). | New `ConnectIdMap` with `connectRef String` (decision 5); do not overload OpsIdMap or `Product.opsId`. |
| R2 | Cross-supplier SKU collision on `(tenantId, sku)` (:554). | Namespace `sku="{supplier_slug}:{supplier_sku}"` (decision 6). |
| R3 | Double markup (Connect markup + Manage markup). | Connect pushes cost only; skip `apply_markup` (decision 4); AC10 asserts it. |
| R4 | Re-sync clobbers Manage overlay (markup/sell/visibility). | Base-only upsert; overlay fields never written on update (B2); AC5 guards. |
| R5 | Manage `Product` has no `source` col → provenance ambiguity. | Provenance via `ConnectIdMap` presence + namespaced sku; document; consider future `source` enum add. |
| R6 | Partial/out-of-order payloads (option before product). | Reuse `PendingDependency` (B6, AC7). |
| R7 | `apparel size` option vs Manage `ProductSize` (physical W×H) confusion. | Size is a **MasterOption** here, NOT `product_sizes` — same lesson as the collapse plan; no `ProductSize` rows written. |
| R8 | Manage ingest endpoint unauthenticated abuse. | Bearer integration principal + `requireIntegration` guard; distinct `integration:connect:sync` permission. |
| R9 | n8n / OPS path confusion. | Out of scope — this is direct Connect→Manage HTTP, not via n8n, not OPS push. |

---

## 7. Verification Steps
- Manage: `pnpm --filter @graphx/db prisma validate` + migration dry-run; `pnpm --filter @graphx/commerce test connect-ingest`; `pnpm --filter @graphx/api test` (auth).
- Connect: `cd backend && source .venv/bin/activate && pytest tests/test_manage_push_builder.py tests/test_manage_client.py tests/test_manage_push_routes.py -v`.
- E2E: push one SanMar style to a staging Manage (or `MockManageClient`); assert catalog rows via `productsDetails`-equivalent read.

---

## 8. Out of Scope
- Live-pricing/quote seam (Manage → Connect `/api/pricing/quote` for outsourced/dropship, D19) — separate plan.
- OPS push retirement / graphx-platform-web consolidation — separate strategic decision.
- The variant→option collapse build itself — already specced (`plans/2026-06-17-variant-option-collapse-impl.md`); this plan consumes its output.
- Inventory/availability sync depth, images pipeline into Manage.

---

## 9. Decisions (resolved 2026-06-22 — override any if needed)
- **OD1 → RESOLVED: distinct `integration:connect:sync` permission + principal.** Keeps Connect ingest auditable and independently revocable from OPS sync; mint via `create-integration-principal.ts` with the new permission.
- **OD2 → RESOLVED (verify-at-build): mirror an existing Manage apparel product's `priceDefiningMethod`.** Default to the cost-rollup/grid method (>0, NOT legacy flat 0) so `vendorCost`→Markup pricing runs. Build step D must read one known-good Manage apparel product and copy its exact value before bulk push; do not hardcode blind.
- **OD3 → RESOLVED: single app-level Manage target via env** (`MANAGE_INGEST_URL` + `MANAGE_INGEST_TOKEN`, token in EncryptedJSON/secret). Revisit per-customer endpoint only when Connect serves multiple Manage tenants.
- **OD4 → RESOLVED: availability/inventory NOT in this push.** Scope = catalog + options + cost only. Inventory/availability sync is a follow-up (its own contract + cadence). `availability.discontinued` flag stays in the payload as a cheap soft-archive signal, nothing more.
