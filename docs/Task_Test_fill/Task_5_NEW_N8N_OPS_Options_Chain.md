# Task 5 (NEW Sprint) — n8n `ops-push`: Add ops-options + Stub + push-mappings — Detail Guide

**Status:** ✅ Code complete on 2026-04-24 (workflow import not executed — Docker Desktop not running)
**Branch:** `Vidhi`
**Sprint:** Demo Push Pipeline
**What you can say in one sentence:** *"I added 4 new nodes to the n8n ops-push workflow so that after setting product + price, it fetches the product-scoped options from my new `/ops-options` endpoint, stubs the OPS option apply (real mutations pending beta), builds a push_mapping payload, and records it via Sinchana's `/api/push-mappings` endpoint — all before the final push log."*

---

## 1. What Got Built

| File | What Changed |
|---|---|
| `n8n-workflows/ops-push.json` | +4 nodes, POST Push Log + Respond shifted right, connections rewired |

---

## 2. Background — What Is This Task About?

### The full push pipeline after this task

```
Webhook Trigger
    ↓
Parse Params  (customer_id, product_id, api_base)
    ↓
Get Products → Explode Products
    ↓
Get Push Payload (/api/push/<cust>/product/<prod>/payload)
    ↓
Merge + Build OPS Inputs
    ↓
OPS: Set Product Category → Attach Category ID → OPS: Set Product
    ↓ (fork)
    ├─ Build Size Inputs → OPS: Set Product Size
    └─ Build Price Input → OPS: Set Product Price
                               ↓
                         ⭐ NEW: Get /ops-options
                               ↓
                         ⭐ NEW: Stub Apply Options
                               ↓
                         ⭐ NEW: Build Push Mapping
                               ↓
                         ⭐ NEW: POST /push-mappings
                               ↓
                         POST Push Log  (existing)
                               ↓
                         Respond to Webhook
```

### Why stub the "Apply Options" for now?

The OPS GraphQL mutations for options (`setAdditionalOption`, `setAdditionalOptionAttributes`, `setProductsAttributePrice`) are **still in OPS beta** — they aren't shipped in the OnPrintShop GraphQL production API yet.

Instead of blocking on OPS-side readiness, we:
1. Fetch the product-scoped option list from the hub (Task 4's endpoint)
2. Log it + pass it through unchanged (the stub)
3. Build a `push_mapping` record with `target_ops_option_id: null` / `target_ops_attribute_id: null`
4. When beta ships, replace the Stub Code node with real OPS mutation nodes — everything downstream (mapping, push_log) already works.

This lets the team demo the full E2E pipeline today with the known limitation "option IDs will be backfilled when OPS beta ships."

---

## 3. The 4 New Nodes — Detail

### Node 1: `Get /ops-options` (HTTP GET)

- **URL:** `http://host.docker.internal:8000/api/push/{{ $('Parse Params').item.json.customer_id }}/product/{{ $('Parse Params').item.json.product_id }}/ops-options`
- **Header:** `X-Ingest-Secret: {{ $env.INGEST_SHARED_SECRET }}`
- **Output:** array of `OPSProductOptionSchema` (from my Task 4 endpoint)

Pulls `customer_id` + `product_id` from `Parse Params` — this works for **single-product pushes** (the per-row UI button provides product_id). Bulk push (no product_id in Parse Params) would need a per-item rewrite if we want options for bulk — deferred until needed.

### Node 2: `Stub Apply Options` (Code)

```js
const options = $input.all().map(i => i.json);
console.log('[STUB] ops-push options payload:', JSON.stringify(options));
return options.map(opt => ({
  json: {
    ...opt,
    _stub: true,
    target_ops_option_id: null,
    attributes: (opt.attributes || []).map(a => ({
      ...a,
      target_ops_attribute_id: null,
    })),
  }
}));
```

Pass-through + annotation. The inline comment marks exactly which nodes replace this when OPS beta ships.

### Node 3: `Build Push Mapping` (Code)

Flattens `options[].attributes[]` into a single `options` array on the `PushMappingUpsert` shape. Pulls:
- `source_product_id`, `customer_id` ← `Parse Params`
- `source_supplier_sku` ← `Get Push Payload`'s `product.supplier_sku`
- `target_ops_base_url` ← `Get Push Payload`'s `customer.ops_base_url` (if present)
- `target_ops_product_id` ← `OPS: Set Product`'s returned `products_id`

Output shape matches Sinchana's `PushMappingUpsert` schema exactly.

### Node 4: `POST /push-mappings` (HTTP POST)

- **URL:** `http://host.docker.internal:8000/api/push-mappings`
- **Headers:** `X-Ingest-Secret` + `Content-Type: application/json`
- **Body:** `{{ $json }}` (the output of Build Push Mapping)
- Calls Sinchana's Task 3 endpoint. Backend upserts the mapping + linked options.

---

## 4. Wiring Changes

Before this task, `OPS: Set Product Price` output 0 went directly to `POST Push Log`. That edge is replaced by a 5-node chain:

```
OPS: Set Product Price → Get /ops-options → Stub Apply Options
                           → Build Push Mapping → POST /push-mappings → POST Push Log
```

The error branch (`OPS: Set Product Price` output 1 → `Error Handler`) is unchanged. If any of the 4 new nodes throws, n8n default behavior (no `onError` override) will fail the execution cleanly — acceptable since these are all local HTTP / JS and failure means the push_mapping row simply won't be written.

### Position shifts

| Node | Old position | New position |
|---|---|---|
| Get /ops-options | — (new) | [3100, 300] |
| Stub Apply Options | — (new) | [3320, 300] |
| Build Push Mapping | — (new) | [3540, 300] |
| POST /push-mappings | — (new) | [3760, 300] |
| POST Push Log | [2880, 300] | [3980, 300] |
| Respond to Webhook | [3100, 300] | [4200, 300] |

---

## 5. Validation

```bash
python -c "import json; d = json.load(open('n8n-workflows/ops-push.json')); print('nodes:', len(d['nodes']))"
```

Run result: **22 nodes** (was 18), **20 connection entries**. JSON parses clean.

Import command (spec Step 4):
```bash
docker cp n8n-workflows/ops-push.json api-hub-n8n-1:/tmp/opspush.json
docker exec api-hub-n8n-1 n8n import:workflow --input=/tmp/opspush.json
```

**Current status:** Docker Desktop is not running on the dev machine. Import step needs to be run by a dev with Docker up (or in CI). JSON validity confirmed.

---

## 6. Manual Check Steps

1. Start stack: `docker compose up -d postgres n8n api` + `npm run dev`
2. Open n8n UI at `http://localhost:5678` → find `Hub → OPS Push` workflow
3. Confirm 4 new nodes visible + chained: Set Product Price → Get /ops-options → Stub Apply Options → Build Push Mapping → POST /push-mappings → POST Push Log
4. From hub UI `/products`, click "Push to OPS" on a product that has enabled master options → pick storefront → Push
5. In n8n: open last execution → expand `Stub Apply Options` → confirm console log shows the options payload with `source_master_option_id`, `source_master_attribute_id`, `source_attribute_key`
6. Query `push_mappings` table: `docker compose exec postgres psql -U vg_user -d vg_hub -c "SELECT id, source_product_id, customer_id, target_ops_product_id, array_length(ARRAY(SELECT 1 FROM push_mapping_options WHERE push_mapping_id = pm.id), 1) as option_count FROM push_mappings pm ORDER BY pushed_at DESC LIMIT 1;"` — row should exist with matching product/customer and non-zero option_count

---

## 7. Dependencies

| Depends on | Status |
|---|---|
| Task 4 — `/ops-options` endpoint | ✅ Done (this sprint) |
| Sinchana Task 3 — `POST /api/push-mappings` | ✅ On main |
| Existing `ops-push` workflow | ✅ Already deployed |

**Does NOT block** OLD Task 5 (OPS smoke test) — that's a separate manual verification dependent on Christian's credentials.

---

## 8. Known Limitations

1. **Bulk push loses options** — URL uses `Parse Params.product_id` which is null in bulk mode. Bulk push would skip this chain entirely (HTTP 422). Fine for current UI (per-row button).
2. **Options mapping is stub-only** — `target_ops_option_id` / `target_ops_attribute_id` are `null` until OPS beta ships real mutations. The `push_mapping` row exists but downstream OPS-side lookups by target ID will fail.
3. **No retry** — if `POST /push-mappings` fails, the push log is not written and the webhook returns an error. Acceptable for single-product push; add n8n retry node if bulk becomes important.

---

## 9. What Comes Next

| Task | What It Adds | Status |
|---|---|---|
| **OLD Task 5** — n8n smoke test | Manual E2E with real OPS creds | 🔴 Blocked on Christian's credentials |
| **Future** — Replace stub with OPS beta mutations | Real `setAdditionalOption*` calls | 🔴 Blocked on OPS beta release |
