# GraphX Connect — Integration Plan

**Status:** Final draft for review
**Date:** June 2026

GraphX Connect is the supplier-integration layer of the GraphX platform. This document describes its design: what Connect exposes, how it relates to the platforms that consume it, and how the work is sequenced. Implementation-level detail (schema, intervals, tooling) is collected in Appendix A so the body stays focused on design.

---

## 1. Overview

Connect exposes a single canonical API for supplier catalog, inventory, pricing, fulfillment, order status, images, and supplier-directory services. It is platform-neutral: the same API serves any consumer — GraphX Manage, OnPrintShop, Shopify, WooCommerce, or an automation layer — and no consumer-specific assumptions live in its core.

The supplier side is normalized behind adapters, so adding a supplier is a configuration change rather than new code. New consumers connect the same way: a record plus credentials, with no per-consumer development. Manage is the first consumer, not the design centre.

---

## 2. Scope

This plan covers the Connect service and its first consumer (Manage). The wider GraphX platform — the control plane and the other modules (Pay, Ship, Grow, Studio, Flight, Store, Intelligence, Communications) — is planned separately. References to those modules here are only to show how Connect fits the larger picture.

---

## 3. Architecture

Connect sits between supply sources and consumers, translating both directions through a canonical contract.

```
   SUPPLY SOURCES                    GRAPHX CONNECT                     CONSUMERS / TENANTS
   SanMar, S&S, 4Over        canonical API + master catalog        Manage · OnPrintShop
   994+ PromoStandards  <-->  + per-tenant shadow catalogs   <-->   Shopify · WooCommerce
   GraphX tenants                + central SKU map                  (each keeps its own
                                                                      shadow catalog)

   Connect exposes:  catalog · inventory · pricing · order status · images · directory
   Connect routes:   consumer order  ->  Connect  ->  supplier (and status back)
```

Two points worth calling out:

- **Order fulfillment is bidirectional.** Connect both receives an order from a consumer and places it back with the supplier, then returns status. It is the only seam that runs in both directions.
- **A tenant can also be a supply source.** Besides external wholesalers, a GraphX tenant may expose its own catalog as supply for other tenants — for example, a tenant that stocks blank apparel can offer it to other tenants through the same canonical contract. This makes the catalog model multi-sided rather than supplier-only.

Consumers reach Connect over HTTP; consumers that require GraphQL (such as OnPrintShop) are served through the same canonical model via an adapter.

---

## 4. Integration Seams

Connect is organized around seven seams.

| Seam | Direction | Purpose |
|---|---|---|
| Catalog | Connect → consumer | Products, options, and wholesale cost in canonical form |
| Inventory | Connect → consumer | Stock levels and discontinued flags |
| Pricing | Connect → consumer | Supplier cost, refreshed on a daily schedule |
| Fulfillment | consumer → Connect → supplier | Submit a confirmed order to the supplier (bidirectional) |
| Order status | Connect → consumer | Confirmed, shipped, tracking |
| Images | Connect → consumer | Supplier images, tagged per colour |
| Directory | Connect → consumer | Connected suppliers and their capabilities |

Pricing is served from the catalog and refreshed on a schedule rather than fetched live per request, since supplier costs change slowly. Inventory is polled on a configurable interval. (Exact cadences are in Appendix A.)

---

## 5. Foundation Rules

These apply to every seam.

1. **Canonical first.** The core uses platform-neutral field names; per-target adapters map them outward. No vendor or consumer field names appear in the core. The canonical field set is to be finalized (see Open Decisions).
2. **Documented contract.** Every endpoint is published as a collection with examples, authentication, and error shapes, in both directions.
3. **Cost only.** Connect emits wholesale cost; the consumer owns sell price and markup. A tenant's negotiated cost is still a cost — it drives the purchase-order price back to the supplier, not the sell price.
4. **Master plus shadow catalogs.** Connect owns one canonical master catalog; each tenant curates its own shadow catalog with its negotiated cost (see Section 6).
5. **Connect owns the mapping.** The option-to-SKU map and a per-tenant destination-ID map live in Connect, so order routing and return calls are unambiguous.
6. **Overlay-preserving sync.** Re-sync writes base data only and never overwrites a tenant's edits. Where upstream and tenant data conflict, the tenant is asked to choose (see Section 8).
7. **Idempotent.** Every mutating call carries an idempotency key; repeated calls never duplicate records or orders.
8. **Authenticated.** Machine callers authenticate with a key exchanged for a short-lived token, not a session cookie (see Section 7).
9. **Configuration-driven onboarding.** A new consumer is a record plus credentials — no code deployment per tenant.

---

## 6. Catalog Design

A single shared catalog does not work for two reasons. Tenants buy at different costs for the same item, which one catalog cannot represent; and tenants do not want the entire supplier catalog — one tenant may want every shirt a supplier sells, another only a single brand. Forcing the full catalog on everyone is both wrong on price and impractical at scale.

The model is therefore a **master catalog** plus a **per-tenant shadow catalog**:

- The **master catalog** is the canonical product set Connect syncs from suppliers — one entry per supplier product, with options, variants, cost, and images. It holds no tenant-specific data and is refreshed on the pricing schedule.
- A **shadow catalog** is what a tenant actually lists. It pulls from the master and adds three things on top: the tenant's **curation** (which products they list), their **negotiated cost** (used for purchase-order pricing back to the supplier), and a **destination-ID map** that links each tenant product line to its identifier on the target platform and to the exact supplier item, so return calls and orders route without ambiguity.

The master is never overwritten by tenant data, and tenant overlays are never overwritten by a master refresh. Table-level detail is in Appendix A.

---

## 7. Authentication

Machine callers (Manage, the automation layer, other consumers) authenticate by presenting an integration key and exchanging it for a short-lived bearer token. Subsequent calls carry the token; on expiry the caller requests another. Tokens are scoped, and keys are revocable. Session cookies are not used for machine access. The exchange endpoint and token lifetime are in Appendix A.

---

## 8. Synchronization and Conflict Handling

Connect refreshes supplier data on a schedule and reconciles it against what each tenant has already listed. A refresh updates base product data only.

When a supplier changes something a tenant has edited or listed — a discontinued colour, a changed option — Connect flags that item rather than applying the change silently. The tenant is notified and chooses to accept the update or keep their version. Until they decide, the affected item is held back from re-publishing so a change is never pushed out from under them. Untouched items update automatically.

---

## 9. Fulfillment and Fallback

A confirmed order is submitted to the supplier asynchronously and retried on failure, so a transient outage never loses the order.

If the supplier's API is unreachable after retries, Connect does three things: it notifies the tenant that automatic submission is down (by email or messaging), it provides a structured purchase order containing everything needed to place the order manually — supplier, items, quantities, negotiated cost, and ship-to — and it offers the tenant the choice to take over. If the tenant places the order manually, Connect cancels the pending automatic attempt so the order cannot be sent twice. If they do nothing, the retry completes the order once the supplier recovers.

---

## 10. Workflow Integration

The documented API collection is the contract the automation layer builds on. A node for the workflow engine is generated from that collection and kept in step with it automatically, so a consumer can adopt Connect without hand-writing integration code, and API changes propagate without manual rework. The choice of workflow engine is a platform-level decision made outside this plan.

---

## 11. Implementation Phases

The work is sequenced so that each phase builds on a stable foundation.

1. **Foundation** — the canonical contract per seam, a consistent error model, the adapter layer, the key-to-token authentication, and the documented API collection. Establishes that any platform can consume Connect.
2. **Catalog** — the master and per-tenant shadow catalogs, the SKU map, and the destination-ID map, with idempotent, overlay-safe sync.
3. **Inventory** — scheduled stock polling; discontinued items are archived, not deleted.
4. **Pricing refresh** — the daily cost refresh into the catalog, with tenant negotiated costs layered on top.
5. **Fulfillment and status** — order submission to the supplier and status return, including the outage fallback.
6. **Images** — supplier images with per-colour tagging; consumer-uploaded images preserved.
7. **Directory** — the dynamic supplier list and capabilities.

The critical path runs Foundation → Catalog → Pricing → Fulfillment. Inventory, Images, and Directory can proceed in parallel once the Foundation is in place. Indicative sizing is in Appendix A.

---

## 12. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Designing around one consumer | Canonical model and adapters; every consumer is one adapter |
| Double markup | Connect emits cost only; markup is the consumer's |
| Re-sync overwrites tenant edits | Base-only writes plus the conflict-choice flow |
| Cross-supplier SKU collision | Namespaced SKUs and a central map |
| Unauthenticated access | Key-to-token authentication on every call |
| Supplier API down at order time | Async submit, retries, and the manual-PO fallback |
| Duplicate orders | Idempotency keys and the manual-takeover cancel |
| Building adapters before names are agreed | Canonical field names finalized first |

---

## 13. Open Decisions

| Decision | Owner | Status |
|---|---|---|
| Canonical field names | Client | Open — blocks Catalog and everything after |
| Supplier apparel modelling approach | Client | Open — to be chosen from a short comparison |
| First supplier for fulfillment | Client | Open |
| Inventory polling cadence | Team | Default set, tunable per supplier |
| Authentication method | — | Decided: key to short-lived token |

---

## 14. Out of Scope

- Real-time per-request pricing (a scheduled refresh covers current needs; a live webhook is a later option).
- Automatic onboarding of unknown supplier APIs by introspection — a strong future direction, but not part of this plan.
- The platform-level choice of workflow engine.

---

## Appendix A — Implementation Notes

*Engineering detail, kept out of the body. Subject to change during build.*

**Tech.** Connect is a Python service backed by PostgreSQL. Consumers integrate over HTTP; GraphQL consumers are served through an adapter.

**Catalog schema.** Master catalog reuses the existing `products` / `product_variants` / `product_images` tables. The per-tenant layer adds:

```
tenant_catalogs( id, tenant_id, name, target_platform, created_at )
tenant_catalog_items(
  id, tenant_catalog_id, master_product_id,
  is_listed, negotiated_cost, destination_product_id,
  destination_variant_map, sync_state, last_synced_at,
  unique(tenant_catalog_id, master_product_id) )
```
Per-tenant cost resolution: `po_cost = negotiated_cost ?? master.wholesale_cost`.

**Authentication.** Exchange endpoint `POST /api/integrations/v1/token` (present integration key, receive a bearer token). Proposed token lifetime ~15 minutes, configurable; scopes for read / write / fulfillment.

**Schedules.** Pricing refresh runs once daily, around midnight UTC. Inventory polling defaults to 30 minutes, tunable per supplier.

**Workflow node.** Distributed as an installable package generated from the API collection, version-bumped and republished when the collection changes.

**Indicative phase sizing.** Foundation 1–2 weeks; Catalog 3–4; Inventory 2; Pricing 2; Fulfillment 4–6; Images 2; Directory 1. Critical path roughly 10–15 weeks; parallel phases shorten the calendar.

**Definition of done (per change).** Tests pass in CI; authentication enforced; idempotent and overlay-safe; cost-only; the API collection updated alongside the change; no direct writes to production data; new-consumer onboarding remains configuration-only.
