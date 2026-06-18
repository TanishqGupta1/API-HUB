# Design — api-hub → graphx Supplier Catalog Handoff

> Companion to the implementation plan `2026-06-17-supplier-catalog-handoff-impl.md`.
> This is the design/spec (the "why" + contract + decisions); the impl plan is the "how".

## Context

Two systems, split roles: **api-hub / GraphX Connect** owns PromoStandards/REST
supplier ingest + normalization; **graphx-platform-web** owns the Universal Catalog +
OPS push + portal. The deferred piece is the handoff: get normalized supplier
products from api-hub into graphx's catalog.

**Readiness verdict (explored 2026-06-17):**
- **graphx — partially ready.** It already has an inbound, shared-secret, idempotent
  upsert endpoint `POST /api/ops-sync/products`
  (`apps/admin/src/app/api/ops-sync/products/route.ts`) that creates `Product` +
  `ProductSize` + `ProductOptionBinding(+Attribute)` from JSON. BUT it is keyed on
  `(tenant_id, ops_products_id)` and expects an **OPS-shaped** payload. No supplier
  identity, no supplier GenesisSource.
- **api-hub — not ready to push out.** It has the normalized data and a full-product
  read endpoint `GET /api/products/{id}/export` (`backend/modules/catalog/routes.py:196`),
  but **zero outbound emitter** to graphx.

**Decisions (confirmed with Tanishq):**
1. Transport = **new graphx endpoint** `POST /api/ingest/supplier-products` (sibling to
   ops-sync, shared-secret), NOT overloading ops-sync.
2. Landing = **VG template tenant** (`tenant.slug = "vg"`); other tenants adopt later
   via existing `TenantCatalogProduct` membership.

## The contract — normalized supplier-product payload

```jsonc
{
  "supplier_key": "sanmar",            // api-hub Supplier.slug
  "tenant_slug": "vg",                 // landing tenant
  "products": [{
    "supplier_sku": "PC54",            // natural key with supplier_key
    "name": "Core Cotton Tee", "brand": "Port & Company", "description": "...",
    "product_type": "apparel", "category": "T-Shirts",
    "images":  [{ "url": "...", "type": "front", "color": "Red" }],
    "options": [
      { "option_key": "color", "title": "Color", "attributes": [{ "title": "Red" }] },
      { "option_key": "size",  "title": "Size",  "attributes": [{ "title": "S" }] }
    ],
    "variants": [{ "color": "Red", "size": "S", "sku": "...", "prices": [...] }]
  }]
}
```

Natural key in graphx = **(tenant_id, supplier_key, supplier_sku)**. `internal_name`
= **`"sup:{supplier_key}:{supplier_sku}"`** — the `sup:` namespace prevents collision
with vg's OPS-pulled / authored products under `@@unique([tenant_id, internal_name])`.

## Options are MASTER-level — bind, never create per-product (critical)

graphx `MasterOption` is **UNIVERSAL** (`tenant_id?`, `scope @default(UNIVERSAL)`),
bound per product via `ProductOptionBinding` + per-product `ProductOptionBindingAttribute`.
graphx's ops-sync importer already does this (`masterOption.findFirst` →
`productOptionBinding.upsert` → `productOptionBindingAttribute.upsert`). The supplier
importer **must** follow it: Color/Size are two shared master options (find-or-create
ONCE), each product **binds** them. Per-product options would corrupt the central model.

## Key risks & hardening

1. **Master-option corruption (highest)** — bind, don't create per-product. Verify:
   exactly two new `MasterOption` rows total (`color`,`size`), not N×products.
2. **Two writers on vg** — OPS-pull (key `ops_products_id`) vs supplier-import (key
   supplier_sku) stay disjoint via the `sup:` namespace + distinct genesis + the
   `ProductSupplierSource` key. Linking a supplier product to its later OPS-pulled twin
   is **deferred**.
3. **Sequencing** — exporter runs after `derive_options`; skips + logs option-less products.
4. **Idempotency** — upsert via `ProductSupplierSource`; orphan cleanup on de-list deferred.
5. **Pricing** — carry supplier wholesale as **cost/raw only**; never clobber graphx's
   computed sell price.
6. **Scale (994 suppliers)** — batch 50–100/POST; per-row results so one bad product
   doesn't fail the batch.

## Out of scope

OPS push from graphx (graphx owns it), multi-tenant adoption UI, retiring api-hub's
wrong-schema ops_client, deep cost-engine mapping beyond carrying variant prices.

## Build sequence

1. graphx schema migration (`IMPORTED_FROM_SUPPLIER` + `ProductSupplierSource`).
2. graphx `/api/ingest/supplier-products` endpoint + tests.
3. api-hub exporter + push routes + tests (after the variant→option collapse lands).
4. E2E one SanMar style → vg tenant.

See `2026-06-17-supplier-catalog-handoff-impl.md` for the task-by-task TDD plan.
