> ⚠️ **FOLDED INTO THE FINAL PLAN (2026-06-29).** This design is now §5 of **[`2026-06-29-connect-integration-plan-final.md`](2026-06-29-connect-integration-plan-final.md)**. Kept as the detailed reference.

# Master Catalog + Per-Tenant Shadow Catalogs — Design

**Status:** design (no schema changes until approved)
**Date:** 2026-06-27
**Source:** 2026-06-26 client review — *"we need a master catalog and then each tenant has their own tenant-specific catalog that just pulls from the master and fine-tunes it."*
**Parent spec:** [`2026-06-24-connect-agnostic-api-restructure.md`](2026-06-24-connect-agnostic-api-restructure.md) (Rule 7, Phase 2)

## 1. Why
A single shared catalog can't work because:
- **Cost differs per tenant** — tenant A may pay $1.00 where tenant B pays $2.15 for the same item; one catalog can't hold both → wrong PO pricing back to the supplier.
- **Volume** — forcing every tenant to ingest the full 100k+ supplier catalog kills the consumer (OPS) and isn't what they want (tenant A wants all SanMar tees; tenant B only Gildan).

So: **one master catalog** (canonical, supplier-keyed, shared) + **a curated shadow catalog per tenant** (subset + negotiated cost + destination mapping).

## 2. The two layers

### Master catalog (already exists — reuse)
The canonical product set Connect already syncs from suppliers — the existing **`products`**, **`product_variants`**, **`product_images`** tables. One row per supplier product, keyed by `(supplier_id, supplier_sku)`. Holds wholesale cost, options, variants, images, the **option-combination ↔ supplier-SKU map**. **No per-tenant data.** Refreshed by the daily pricing cron (S3) and supplier syncs.

### Tenant shadow catalog (new)
What a tenant actually lists + sells, pulled from the master and fine-tuned. **New tables:**

```
tenant_catalogs
  id              uuid pk
  tenant_id       uuid            -- the consumer/customer
  name            varchar
  target_platform varchar         -- 'ops' | 'manage' | 'shopify' | ...
  created_at      timestamptz

tenant_catalog_items
  id                    uuid pk
  tenant_catalog_id     uuid  fk -> tenant_catalogs.id
  master_product_id     uuid  fk -> products.id      -- the master row it shadows
  is_listed             bool                         -- curation (tenant chose to list it)
  negotiated_cost       jsonb null                   -- per-variant cost override; null = use master cost
  destination_product_id varchar null                -- e.g. OPS product id 541 (filled from push return)
  destination_variant_map jsonb null                 -- { part_id -> destination variant/sku id }
  sync_state            varchar                      -- PENDING | SYNCED | STALE
  last_synced_at        timestamptz null
  unique (tenant_catalog_id, master_product_id)
```

## 3. The three things the shadow catalog adds
1. **Curation** — `is_listed`: a tenant lists only the master products they want; the rest of the master is never pushed to them.
2. **Negotiated cost** — `negotiated_cost`: per-tenant cost override used for **PO pricing back to the supplier**. Resolution: `po_cost = negotiated_cost ?? master.wholesale_cost`.
3. **Destination ID mapping** — `destination_product_id` + `destination_variant_map`: line-for-line "tenant product ↔ destination platform ID ↔ supplier item," so when a push returns IDs (or an order/status comes back), routing is unambiguous. *(This is the generalization of the existing Manage `ConnectIdMap` crosswalk — Manage is just one `target_platform`.)*

## 4. Sync semantics (overlay-safe)
- **Master refresh** (daily cron / supplier sync) updates master cost/options/images **only** — it never touches a tenant's `is_listed`, `negotiated_cost`, or destination IDs.
- **Shadow pull**: a tenant's shadow item reads current master data; the tenant overlay (curation + negotiated cost) is layered on top and **never clobbered**.
- **Destination IDs** are written from the push **return call** (e.g. OPS returns product 541 → store it on the item), then reused for status/order routing.
- **Stale flag**: if the master changes underneath a synced item, mark `STALE` and let the tenant choose *update* vs *keep my changes* (matches Christian's overlay-preservation point).

## 5. Cost & ordering flow
```
master.wholesale_cost ──┐
                        ├─► tenant_catalog_item.negotiated_cost (override) ──► PO price to supplier
consumer markup (Manage)─┘ (sell price — owned by the consumer, never by Connect)
```
Connect emits **cost only**; the consumer owns markup/sell price (Rule 6). The negotiated cost is a *cost*, not a sell price.

## 6. How it maps to today's code
| Concept | Today | Change |
|---|---|---|
| Master catalog | `products` / `product_variants` / `product_images` | none — these *are* the master |
| SKU map | per-variant `supplier_sku` | none (Phase 2 S2-3 formalizes the combination↔SKU map) |
| Tenant curation + negotiated cost | — | **new** `tenant_catalogs` + `tenant_catalog_items` |
| Destination mapping (Manage) | `ConnectIdMap` (in Manage) | generalize to `destination_*` per target; Manage = one target |

## 7. Build order (feeds sprint Phase 2)
1. `tenant_catalogs` + `tenant_catalog_items` tables + migration (idempotent, VARCHAR types per repo rule).
2. Curation API — list/add/remove master products in a tenant catalog (`is_listed`).
3. Negotiated-cost overlay + PO-cost resolver.
4. Destination ID mapping — capture from push return; expose for order/status routing.
5. Daily cron refresh writes master cost; shadow overlay preserved (S3).

## 8. Open questions for Christian
- Is `tenant_id` == OPS customer == Manage tenant (one identity), or a separate Connect-side tenant record?
- Negotiated cost granularity — per product, per variant, or per qty-tier?
- Does a tenant catalog map to exactly one `target_platform`, or can one curated catalog push to several targets?
