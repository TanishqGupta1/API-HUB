# Demo Push Pipeline — Design Spec

**Date:** 2026-04-23
**Status:** Approved via brainstorm; ready for implementation plan
**Context:** Meeting with Christian (2026-04-23) locked multi-tenant architecture direction. This spec is NOT the multi-tenant build — it's the minimum end-to-end demo for VG team to show: SanMar SOAP → hub → product selection → push to VG's staging OPS.

## Goals

Ship a working pipeline that demonstrates:

1. **Live SanMar SOAP ingestion** — 5–10 styles pulled via web services (not CSV), with current pricing + inventory.
2. **Hub product selection** — admin sees SanMar products in `/products`, picks one, clicks Push.
3. **OPS push with master→product option conversion** — hub converts any enabled master-option config into product-scoped options before push. Beta OPS mutations for per-product option assignment are stubbed (template node in n8n) until OPS ships them.
4. **Mapping/merge table** — every push writes a row linking hub source IDs → target OPS IDs for future order routing and updates.

## Non-goals (deferred)

- Multi-tenant schema (`customer_products`, `customer_product_options`) — dedicated future spec.
- Customer self-serve auth — admin-only flow for demo.
- Push to OPS for per-product options — wire real mutations when OPS beta ships. Template/stub node in place so swap is trivial.
- SanMar SFTP pipeline deprecation — leave existing SFTP for images; live pricing via SOAP only.
- 4Over, S&S push flows — this spec only covers SanMar→OPS for the demo.

## Architecture

```
SanMar SOAP creds in DB (suppliers.auth_config, encrypted)
      ↓
n8n sanmar-soap-pull (existing) — limit 10 styles for demo
      ↓
POST /api/ingest/{sanmar_sid}/products     (existing)
      ↓
Product table in hub (products + variants + pricing + inventory)
      ↓
/products admin list — NEW per-row "Push to OPS" button
      ↓ click → customer picker → confirm
POST /api/n8n/workflows/vg-ops-push-001/trigger?product_id=X&customer_id=Y
      ↓
n8n ops-push workflow:
  1. GET /api/push/{cust}/product/{pid}/payload               (existing)
  2. GET /api/push/{cust}/product/{pid}/ops-variants          (existing)
  3. [NEW] GET /api/push/{cust}/product/{pid}/ops-options     ← master→product conversion here
  4. OPS: setProductCategory, setProduct, setProductSize (loop), setProductPrice (loop)
  5. [STUB] "Apply Options" Code node — logs payload; no OPS call until beta ships
  6. [NEW] POST /api/push-mappings — persist source↔target linkage
  7. POST /api/push-log — existing audit
      ↓
customer's OPS storefront has the product (minus options, for now)
```

## Data model

### New table: `push_mappings`

One row per (source_product_id, customer_id) pair. UPSERT on re-push.

```sql
CREATE TABLE push_mappings (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_system         VARCHAR(50)  NOT NULL,          -- 'sanmar' | 'vg-ops' | 's&s' | '4over'
  source_product_id     UUID         NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  source_supplier_sku   VARCHAR(255),
  customer_id           UUID         NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  target_ops_base_url   VARCHAR(500) NOT NULL,
  target_ops_product_id INTEGER      NOT NULL,
  pushed_at             TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at            TIMESTAMP WITH TIME ZONE DEFAULT now(),
  status                VARCHAR(20)  DEFAULT 'active',  -- 'active' | 'stale' | 'deleted'
  UNIQUE(source_product_id, customer_id)
);
CREATE INDEX idx_push_mappings_customer ON push_mappings(customer_id);
CREATE INDEX idx_push_mappings_target   ON push_mappings(target_ops_product_id);
```

### New table: `push_mapping_options`

One row per attribute pushed. Stores the source↔target option-id linkage required for order routing back to VG / the supplier.

```sql
CREATE TABLE push_mapping_options (
  id                           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  push_mapping_id              UUID NOT NULL REFERENCES push_mappings(id) ON DELETE CASCADE,
  source_master_option_id      INTEGER,
  source_master_attribute_id   INTEGER,
  source_option_key            VARCHAR(100),
  source_attribute_key         VARCHAR(255),
  target_ops_option_id         INTEGER,             -- NULL until beta mutations ship
  target_ops_attribute_id      INTEGER,             -- NULL until beta mutations ship
  title                        VARCHAR(255),
  price                        NUMERIC(10,2),
  sort_order                   INTEGER,
  created_at                   TIMESTAMP WITH TIME ZONE DEFAULT now()
);
CREATE INDEX idx_pmo_mapping ON push_mapping_options(push_mapping_id);
CREATE INDEX idx_pmo_source  ON push_mapping_options(source_master_option_id, source_master_attribute_id);
CREATE INDEX idx_pmo_target  ON push_mapping_options(target_ops_option_id, target_ops_attribute_id);
```

### No changes to existing tables

- `products`, `product_options`, `product_option_attributes`, `master_options`, `master_option_attributes`, `customers`, `product_push_log` — untouched.
- Schema additions are strictly new tables. Safe for existing data.

## Backend endpoints (new)

### `GET /api/push/{customer_id}/product/{product_id}/ops-options`

**Purpose:** convert hub's master-option-based config into product-scoped shape for OPS push.

Input: path params (customer_id, product_id). Reads `ProductOption` + `ProductOptionAttribute` where `enabled = true` for the product.

Output (list):
```json
[
  {
    "option_key": "inkFinish",
    "title": "Ink Finish",
    "options_type": "combo",
    "attributes": [
      { "title": "Gloss", "price": 0.00, "sort_order": 1 },
      { "title": "Matte", "price": 0.00, "sort_order": 2 }
    ]
  }
]
```

**Key transformation:** strip `master_option_id`, `ops_attribute_id`, `master_attribute_id` from output. Push handler receives ONLY product-scoped shape. This is where the master→product conversion happens, per Christian's rule (outbound must be product options only).

### `POST /api/push-mappings`

**Purpose:** n8n calls this after a successful OPS push to persist the source↔target linkage.

Body:
```json
{
  "source_product_id": "uuid",
  "source_system": "sanmar",
  "source_supplier_sku": "PC61",
  "customer_id": "uuid",
  "target_ops_base_url": "https://vg-staging.onprintshop.com",
  "target_ops_product_id": 1234,
  "options": [
    {
      "source_master_option_id": 112,
      "source_master_attribute_id": 184,
      "source_option_key": "inkFinish",
      "source_attribute_key": "Gloss",
      "target_ops_option_id": null,
      "target_ops_attribute_id": null,
      "title": "Gloss",
      "price": 0.00,
      "sort_order": 1
    }
  ]
}
```

Behavior: UPSERT on `(source_product_id, customer_id)`. Deletes + reinserts `push_mapping_options` rows (replace-all pattern consistent with existing ingest code).

Requires `X-Ingest-Secret` header (reuse existing dep).

### `GET /api/push-mappings`

Query params: `customer_id`, `source_product_id`. Returns mapping with nested options array. For audit UI.

### `DELETE /api/push-mappings/{id}`

Soft-deletes (sets `status='deleted'`). Preserves audit trail.

## n8n workflow changes

Modify `n8n-workflows/ops-push.json`. Insert nodes AFTER existing setProductPrice loop and BEFORE existing POST /push-log:

1. **HTTP GET `/ops-options`** — hit new hub endpoint for product-scoped options.
2. **Split In Batches** — iterate per option group.
3. **Code: Apply Options (STUB)** — logs option payload, returns `{...opt, _stub: true, target_ops_option_id: null}` for each attribute. No OPS call.
   - Inline comment marks where real `setAdditionalOption`/`setAdditionalOptionAttributes`/`setProductsAttributePrice` nodes go when beta ships.
4. **Code: Aggregate push_mapping payload** — collects: source_product_id, customer_id, target_ops_product_id (from setProduct output), source_system (from supplier lookup), options array (flattened from splitInBatches).
5. **HTTP POST `/api/push-mappings`** — with X-Ingest-Secret.
6. Existing POST `/api/push-log` continues to fire.

## Frontend changes

### `/products` admin list — per-row Push button

`frontend/src/app/(admin)/products/page.tsx`: add rightmost "Action" column. Per-row button → opens shadcn `Dialog` with a customer dropdown + Confirm. Confirm fires `POST /api/n8n/workflows/vg-ops-push-001/trigger?product_id=X&customer_id=Y`. Toast via existing patterns.

Reuse `PublishButton` logic from `frontend/src/components/products/publish-button.tsx` but extract the dropdown into a new compact component `frontend/src/components/products/push-row-action.tsx` (dialog-based) so the existing full-widget stays untouched for product detail page.

No state management beyond local dialog open/close. No global store.

## SanMar SOAP connector

**No changes — existing work stands:**
- `backend/modules/promostandards/client.py` — SanMar-compatible SOAP client (recent commits added getProduct, media v1.1.0, category parsing).
- `backend/scripts/sanmar_smoke.py` — validation script for getProduct + getConfigurationAndPricing + getInventory + getMedia.
- `n8n-workflows/sanmar-soap-pull.json` — workflow already exists from recent WIP.

**Demo operations:**
1. Ensure SanMar supplier row in `suppliers` table with `protocol: "soap"` + real creds in encrypted `auth_config`.
2. Run `sanmar-soap-pull` with hardcoded style list (10 SKUs: PC61, PC54, ST350, ...). Limit arg caps the workflow.
3. Products land in `products` table via `/api/ingest/{sid}/products`.

## Push-target OPS

VG's staging OPS. One row in `customers` table with `ops_base_url`, `ops_token_url`, `ops_client_id`, `ops_client_secret` (encrypted via existing `EncryptedJSON`). Admin creates this row through `/customers` UI (existing).

## Testing

### Unit tests (pytest)

- `test_push_mappings_ingest.py` — UPSERT on conflicting (product, customer), options replace-all.
- `test_ops_options_endpoint.py` — returns ONLY enabled product options in product-scoped shape; drops master IDs; correctly reads price/sort overrides.
- `test_ops_options_empty.py` — no enabled options → empty list (not 404).

### E2E (manual)

1. Docker stack up. SanMar supplier row with real creds.
2. Execute `sanmar-soap-pull` in n8n UI → verify 10 products in `/api/products?supplier_id=<sanmar>&limit=20`.
3. `/products` admin — scroll, click "Push to OPS" on one product, pick VG staging customer, confirm.
4. Watch n8n execution: setProduct creates OPS product, stub node logs options payload.
5. `GET /api/push-mappings?source_product_id=X` → returns mapping row + options rows (target_ops_option_id=null for now).
6. Check VG staging OPS admin → product visible (without options; manual config + yellow hub banner explains).

## Rollout

Feature branch: `fix/onprintshop-nodes` (current). Resolve open merge conflicts first (see git state). Ship as PR merged to main after demo is green.

## Risks / open items

- **Branch has unresolved merge conflicts** in ~10 files. User says "git is ok" — someone else is resolving. If not resolved by implementation start, implementation blocks on that.
- **OPS beta mutations timing** — no ETA. Stub node must be swap-ready; when beta lands, a 1-day task replaces the Code node with real OPS mutation nodes + populates `target_ops_option_id` / `target_ops_attribute_id` via push-mappings PUT.
- **SanMar staging credential availability** — user has them. If they go stale, swap via `PUT /api/suppliers/{id}`.
- **OPS push idempotency** — UPSERT on `(source_product_id, customer_id)` handles re-push. Node must check for existing mapping and call OPS `setProduct` with `products_id` of the target to update in place (OPS convention: setProduct with existing ID = update).

## Deferred follow-ups (after demo)

1. Multi-tenant schema (`customer_products`, `customer_product_options`).
2. Customer auth model.
3. Real beta-mutation wiring to replace stub.
4. Mapping-audit UI (`/mappings` page showing source↔target pairs).
5. Order routing — when customer receives order in OPS, backtrack to SanMar via mapping, create SanMar purchase order.
6. Normalization layer so different source adapters produce canonical product before hub ingest.
