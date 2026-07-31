# GraphX Connect — API Reference (Postman Collection Spec)

**Purpose:** the agnostic Connect API contract — documented so it can be imported into Postman and turned (by Christian) into an n8n node. Platform-neutral: any consumer (Manage, OPS, Shopify, n8n) uses the same endpoints. This is the **Phase-1 deliverable**.

> Status legend: ✅ exists today (use the **actual path** shown) · 🔶 planned (build per the phase plan — new canonical path is fine)

---

## Collection setup

**Variables**
| Variable | Example | Notes |
|---|---|---|
| `base_url` | `http://localhost:8000` (dev) · `https://connect.graphxcpi.com` (prod) | Connect API root |
| `orch_key` | `<integration key>` | Machine auth key (see below) |

**Auth — use the EXISTING machine auth.** Connect's Integration Gateway authenticates machine callers with the **`X-Orchestrator-Key`** header (backed by the `integration_keys` table — `backend/modules/integrations/auth.py`). So every machine request sends:
```
X-Orchestrator-Key: {{orch_key}}
```
*(A `Bearer`-token layer is **🔶 optional/future** — not built. Do not document Bearer as if it exists.)*
**Content type (POST/PATCH):** `Content-Type: application/json`

**Standard error envelope** (non-2xx)
```json
{ "error": "forbidden", "detail": "human-readable reason", "request_id": "req_..." }
```
| Status | Meaning |
|---|---|
| 401 | Missing/invalid `X-Orchestrator-Key` |
| 403 | Key lacks the required scope |
| 404 | Unknown supplier / product / order |
| 422 | Payload failed validation |
| 502/504 | Upstream supplier API error/timeout (quote/fulfillment) |

---

## ⚠️ Spec path vs. actual path today (read before importing)
The new canonical paths (🔶) are what we'll *build*. For ✅ endpoints, use the **actual** path so Postman doesn't 404.

| Spec / canonical path | Status | Actual path today |
|---|---|---|
| `GET /api/catalog/products` | 🔶 new | **`GET /api/products`** (exists) |
| `GET /api/catalog/products/{supplier_slug}/{supplier_sku}` | 🔶 new | **`GET /api/products/{product_id}`** (by UUID, exists) |
| `GET /api/suppliers/directory` | 🔶 new shape | **`GET /api/suppliers`** (exists) |
| `GET /api/inventory/{slug}/{sku}` | 🔶 new | — |
| `POST /api/pricing/quote` | 🔶 new | — |
| `POST /api/fulfillment/submit` · `GET /api/fulfillment/status/{id}` | 🔶 new | — |
| `POST /api/manage-push/{supplier_id}` | ✅ exists | same (Manage adapter) |
| Auth | ✅ exists | `X-Orchestrator-Key` header (not Bearer) |

---

## Folder 1 — Supplier Directory  *(Seam S7)*
### GET `/api/suppliers` ✅  *(canonical `/api/suppliers/directory` 🔶 adds capabilities)*
- **200 (today):** list of suppliers.
- **200 (planned shape):**
```json
[ { "slug": "sanmar", "name": "SanMar", "active": true, "categories": ["Apparel"],
    "supports_dropship": true, "supports_realtime_pricing": true } ]
```

## Folder 2 — Catalog  *(Seam S1)*
### GET `/api/products` ✅  *(canonical `/api/catalog/products` 🔶)*
Paged product list.
- **Query:** `supplier_slug`/`supplier_id`, `page`, `page_size`, `q`.

### GET `/api/products/{product_id}` ✅  *(canonical by `{supplier_slug}/{supplier_sku}` 🔶)*
One product, full **canonical** shape (options, variants, cost, images). Keyed by **UUID today**; the slug/sku lookup is planned.
- **200:** see **Canonical Product** (Appendix A).

## Folder 3 — Inventory  *(Seam S2)* 🔶
### GET `/api/inventory/{supplier_slug}/{supplier_sku}` 🔶
```json
{ "supplier_slug": "sanmar", "connect_ref": "sanmar:K420",
  "variants": [ { "part_id": "K420-Black-M", "quantity_available": 2400, "discontinued": false } ],
  "synced_at": "2026-06-24T10:00:00Z" }
```

## Folder 4 — Live Pricing Quote  *(Seam S3)* 🔶
### POST `/api/pricing/quote` 🔶
Real-time wholesale cost. **Cost only — no markup.**
- **Body:** `{ "supplier_slug": "sanmar", "supplier_sku": "K420", "part_id": "K420-Black-M", "quantity": 48 }`
- **200:** `{ "net_cost": "8.42", "currency": "USD", "valid_until": "2026-06-24T10:15:00Z", "source": "live" }`
- Falls back to stored cost on timeout (`source: "stored"`); never persisted.

## Folder 5 — Product Images  *(Seam S6)* 🔶
### GET `/api/products/{product_id}/images` 🔶  *(also embedded in canonical product `images[]`)*
```json
[ { "url": "https://cdnm.sanmar.com/.../K420_Black_front.jpg", "sort_order": 0, "color_key": "black", "type": "front" } ]
```

## Folder 6 — Fulfillment + Status  *(Seams S4 + S5)* 🔶
### POST `/api/fulfillment/submit` 🔶
Place a confirmed order with the supplier. **Idempotent** on `order_id`. Includes an **optional `callback_url`** so status changes can be **pushed back** (not only polled) — same pattern as the existing OPS-push intent.
- **Body:**
```json
{
  "order_id": "MGR-1042", "connect_ref": "sanmar:K420",
  "line_items": [ { "part_id": "K420-Black-M", "sku": "K420BLACKM", "quantity": 48 } ],
  "shipping_address": { "name": "...", "street1": "...", "city": "...", "state": "TX", "postcode": "75001", "country": "US" },
  "callback_url": "https://consumer.example.com/integration/connect/order-status"
}
```
- **200:** `{ "supplier_order_id": "SM-998877", "confirmed_at": "...", "status": "ACCEPTED" }`
- Async + retried — a supplier outage never loses the order.

### GET `/api/fulfillment/status/{supplier_order_id}` 🔶
- **200:** `{ "supplier_order_id": "SM-998877", "status": "SHIPPED", "tracking_number": "1Z...", "carrier": "UPS" }`
- Status flow: `SENT → ACCEPTED → IN_PRODUCTION → SHIPPED`. (If `callback_url` was given on submit, Connect also POSTs these changes there.)

## Folder 7 — Target Adapters (example)
### POST `/api/manage-push/{supplier_id}` ✅  *(Manage adapter — already built)*
Pushes a supplier's products into GraphX Manage (one consumer/adapter). Cost-only, overlay-safe, idempotent.
- **Auth:** app admin. **Query:** `sku` (optional), `limit`.
- **200:** `{ "supplier": "sanmar", "pushed": 1, "failed": 0, "results": [...] }`
> In the agnostic model these target pushes are driven by **n8n** (read canonical via Folder 2 → adapter → push to target), not per-target routes.

---

## Appendix A — Canonical Product (the shape consumers ingest)
```jsonc
{
  "supplier_slug": "sanmar",
  "supplier_sku": "K420",
  "product_name": "Port Authority Heavyweight Cotton Pique Polo",
  "brand": "Port Authority",
  "product_type": "apparel",            // see Appendix C for values
  "category_path": ["Apparel", "Polos"],
  "options": [
    { "option_key": "color", "title": "Color", "options_type": "swatch",
      "attributes": [ { "title": "Black", "attribute_key": "black", "sort_order": 0 } ] },
    { "option_key": "size",  "title": "Size",  "options_type": "dropdown",
      "attributes": [ { "title": "M", "attribute_key": "m", "sort_order": 1 } ] }
  ],
  "variants": [ { "part_id": "K420-Black-M", "color_key": "black", "size_key": "m", "sku": "K420BLACKM" } ],
  "cost": { "currency": "USD", "base_cost": "8.42",
            "tiers": [ { "qty_from": 1, "qty_to": 71, "vendor_price": "8.42" } ] },
  "images": [ { "url": "https://.../K420_Black_front.jpg", "sort_order": 0, "color_key": "black" } ],
  "availability": { "discontinued": false },
  "provenance": { "source": "CONNECT", "connect_ref": "sanmar:K420", "pushed_at": "<iso8601>" }  // 🔶 see note
}
```
> 🔶 **`connect_ref` / crosswalk note:** `connect_ref = "{supplier_slug}:{supplier_sku}"` is the **planned** crosswalk key. There is **no `ConnectIdMap`/`connect_ref` table in the Connect (Python) backend today** — the crosswalk is **consumer-side** (e.g. Manage holds a `ConnectIdMap` mapping `connect_ref` → its local IDs; built in this work). For the agnostic API, `connect_ref` is just the stable namespaced key each consumer crosswalks on its end. **To be formalized in Phase 1.**

## Appendix B — Canonical field model (platform-neutral)
| Canonical | Meaning | Maps to (Manage example) |
|---|---|---|
| `supplier_slug` + `supplier_sku` | natural key | `sku = "{slug}:{sku}"` |
| `product_name` / `brand` | identity | `name` / brand |
| `product_type` | kind of product (Appendix C) | `productType` / `productClass` |
| `option_key` / `attribute_key` | option + value natural keys | `ProductOption.key` / `ProductOptionValue.key` |
| `cost.base_cost` / `tiers[].vendor_price` | **wholesale cost** | `vendorCost` / `ProductPrice.vendorPrice` (sell price stays the consumer's) |
| `provenance.connect_ref` | crosswalk key (🔶) | `ConnectIdMap.connectRef` (consumer-side) |

> The core uses **`product_type`** — the field that already exists in the backend (`backend/modules/catalog/models.py`, values `apparel`/`print`). Adapters translate canonical → target; **no OPS/Manage field names live in the core** (Sandy's point).

## Appendix C — `product_type` values (the options-vs-product distinction)
| Value | Meaning | Pushed as | Example |
|---|---|---|---|
| `apparel` | a blank garment | **options / template target** — feeds a print product's options (NOT a standalone product) | SanMar K420 |
| `print` | a configurable print product | a standalone print product (the "print process") | DTF print, banner |
| `ready_to_buy` | finished orderable item | a standalone orderable product | 4Over brochure, B2Sign |
> Christian's rule: **SanMar apparel = options** for a print product; **4Over/B2Sign = standalone products**. The classifier in Phase 2a sets this.

## Appendix D — n8n
Once complete in Postman, **Christian builds the n8n node from the collection (~15 min)**. Suppliers + targets are **dynamic fields** on the node; workflows move data between any source and any target without code changes.
