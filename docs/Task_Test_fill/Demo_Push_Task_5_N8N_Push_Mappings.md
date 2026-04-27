# Task 5 (Demo Push Pipeline) — Extend `ops-push` Workflow with Push Mappings — Detail Guide

**Status:** ✅ Completed on 2026-04-27
**Branch:** `Vidhi`
**Sprint spec:** `plans/tasks/vidhi-tasks.md` (Demo Push Pipeline)
**Plan reference:** `docs/superpowers/plans/2026-04-23-demo-push-pipeline.md` → Task 5
**What you can say in one sentence:** *"I extended the n8n OPS push workflow with four new nodes that fetch product-scoped options from our hub, stub out the OPS option mutations until the beta API ships, and POST a flattened push_mappings record so we have a per-attribute audit trail of every push."*

---

## 1. What Got Built

| File | What Changed |
|---|---|
| `n8n-workflows/ops-push.json` | 4 new nodes added (~80 lines), connections rewired so `OPS: Set Product Price` now flows through the new chain into `POST Push Log` |

**Node count:** 18 → 22.

---

## 2. Background — What Is This Task About?

### Task Type
**n8n workflow definition** — a JSON file imported into the n8n container. No Python, no React.

### Why Push Mappings?

The push log already records *"product X was pushed to customer Y"* — fine for a status indicator, but it doesn't tell us **which option/attribute on the hub maps to which option/attribute on OPS** for a given customer storefront.

That mapping matters because:
1. The hub uses **master option IDs** (global). OPS (per customer) uses **product option IDs** (per-storefront).
2. Different customers may end up with different OPS IDs for the *same* hub option.
3. When we later want to update a single attribute (e.g. a price tweak on Gloss for customer Acme), we need to know which OPS attribute ID maps to which hub master attribute on Acme's storefront.

`push_mappings` is the join table that records this. Sinchana built the table + endpoint (her Tasks 1–3); Vidhi's Task 5 is the n8n workflow that **populates** it from a real push.

### Why a Stub Code Node?

OPS hasn't shipped the option mutations yet — `setAdditionalOption`, `setAdditionalOptionAttributes`, `setProductsAttributePrice` are in beta and not in the public GraphQL schema. We can't actually call them today.

Solution: stub the application step now so the rest of the pipeline (fetch → build mapping → POST) is wired and testable. When OPS ships the mutations, only that one Code node gets replaced — everything else stays.

---

## 3. The 4 New Nodes

Inserted between `OPS: Set Product Price` and `POST Push Log`:

```
OPS: Set Product Price
   ↓
Get /ops-options          ← HTTP GET to the Task 4 endpoint
   ↓
Stub Apply Options        ← Code node: logs payload, annotates with null target IDs
   ↓
Build Push Mapping        ← Code node: flattens options→attributes for push_mappings
   ↓
POST /push-mappings       ← HTTP POST to Sinchana's endpoint
   ↓
POST Push Log             (existing)
```

### Node 1 — `Get /ops-options` (HTTP Request)

```
Method: GET
URL:    http://host.docker.internal:8000/api/push/{{ $('Parse Params').item.json.customer_id }}/product/{{ $('Parse Params').item.json.product_id }}/ops-options
Header: X-Ingest-Secret: ={{ $env.INGEST_SHARED_SECRET }}
```

Calls Vidhi's Task 4 endpoint. `$('Parse Params')` references the upstream node that already extracted `customer_id` and `product_id` from the webhook query string — no need to re-parse here.

### Node 2 — `Stub Apply Options` (Code)

```javascript
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

What it does:
1. Logs the payload to the n8n console for visibility during the demo
2. Marks each item with `_stub: true` so push_mappings rows are tagged as stub-sourced
3. Sets every `target_ops_option_id` and `target_ops_attribute_id` to `null` — these would normally come back from OPS mutations

When OPS ships the real mutations, this Code node is replaced by:
1. Split In Batches over options → `OPS: setAdditionalOption` → captures `target_ops_option_id`
2. Split In Batches over attributes → `OPS: setAdditionalOptionAttributes` → captures `target_ops_attribute_id`
3. `OPS: setProductsAttributePrice` → applies price

### Node 3 — `Build Push Mapping` (Code)

Flattens the nested option→attribute tree into a single `options` array per push_mapping row:

```javascript
const params = $('Parse Params').item.json;
const payload = $('Get Push Payload').item.json;
const setProd = $('OPS: Set Product').item.json;
const opsOpts = $input.all().map(i => i.json);

const flatOptions = [];
for (const opt of opsOpts) {
  for (const a of (opt.attributes || [])) {
    flatOptions.push({
      source_master_option_id: opt.source_master_option_id,
      source_master_attribute_id: a.source_master_attribute_id,
      source_option_key: opt.option_key,
      source_attribute_key: a.source_attribute_key || a.title,
      target_ops_option_id: opt.target_ops_option_id,
      target_ops_attribute_id: a.target_ops_attribute_id,
      title: a.title,
      price: a.price,
      sort_order: a.sort_order,
    });
  }
}

return [{ json: {
    source_system: payload.product?.source_system || 'sanmar',
    source_product_id: params.product_id,
    source_supplier_sku: payload.product?.supplier_sku || null,
    customer_id: params.customer_id,
    target_ops_base_url: payload.customer?.ops_base_url || '',
    target_ops_product_id: setProd.products_id,
    options: flatOptions,
}}];
```

The shape matches `push_mappings` (parent) + `push_mapping_options` (child rows) — Sinchana's endpoint expands `options[]` into the child table on insert.

### Node 4 — `POST /push-mappings` (HTTP Request)

```
Method: POST
URL:    http://host.docker.internal:8000/api/push-mappings
Headers: X-Ingest-Secret, Content-Type: application/json
Body:   {{ $json }}     (the Build Push Mapping output)
```

---

## 4. Connection Rewiring

Before:
```
OPS: Set Product Price → POST Push Log
```

After:
```
OPS: Set Product Price → Get /ops-options
Get /ops-options       → Stub Apply Options
Stub Apply Options     → Build Push Mapping
Build Push Mapping     → POST /push-mappings
POST /push-mappings    → POST Push Log
```

The `OPS: Set Product Price` error branch (index 1) still goes to `Error Handler` — error handling untouched. The success branch (index 0) now flows through the new chain before logging.

---

## 5. Validation

JSON parse check + node-count check:

```bash
python -c "import json; d=json.load(open('n8n-workflows/ops-push.json')); print(len(d['nodes']))"
# Expected: 22
```

Result: **22 nodes**, all 22 connection keys present and consistent (every named node referenced in connections also exists in `nodes[]`).

### Importing into n8n (manual step)

```bash
docker cp n8n-workflows/ops-push.json api-hub-n8n-1:/tmp/opspush.json
docker exec api-hub-n8n-1 n8n import:workflow --input=/tmp/opspush.json
```

Expected: `Successfully imported 1 workflow`.

Open `http://localhost:5678` → `Hub → OPS Push` → confirm the 4 new nodes are visible and connected as in Section 4.

---

## 6. Edge Cases Handled

| Scenario | Behavior |
|---|---|
| Product has no enabled options | `Get /ops-options` returns `[]`, Stub Apply Options passes empty array, Build Push Mapping emits `options: []` — push_mappings still gets a row, just with no children |
| Master option attribute has no `source_attribute_key` (raw_json missing it) | Build Push Mapping falls back to `a.title` so the field is never null |
| `OPS: Set Product` failed earlier in the chain | Never reaches the new chain — error branch goes straight to `Error Handler` (unchanged) |
| Hub backend (`/ops-options` or `/push-mappings`) is down | n8n's HTTP node fails the workflow execution — visible in the n8n executions list |

---

## 7. Known Limitations

| Limitation | When It Lifts |
|---|---|
| `POST /push-mappings` will 404 today | When **Sinchana's Task 3** lands her endpoint |
| All `target_ops_*` IDs are null in push_mappings rows | When OPS ships the option-mutation API, then Stub Apply Options is replaced with real OPS nodes |
| Workflow won't run end-to-end without OPS credentials configured | Pre-existing dependency — same as before this task |

These are by design — the architecture is intentionally swap-ready, not done in one go.

---

## 8. Where to Look in the JSON

`ops-push.json` is now ~430 lines. The new content:

- **Nodes** — appended to `nodes[]` after `POST Push Log Error`. Look for IDs `a1111111-0020-...` through `0023-...`.
- **Connections** — `"OPS: Set Product Price"` entry now points main[0] to `"Get /ops-options"`. New keys `"Get /ops-options"`, `"Stub Apply Options"`, `"Build Push Mapping"`, `"POST /push-mappings"` chain through to `"POST Push Log"`.

---

## 9. What Comes Next

| Next Task | What It Adds | Blocked? |
|---|---|---|
| **Task 6** — Frontend Push button | Per-row trigger that fires this workflow with `product_id` + `customer_id` | ❌ No — built next, see Demo_Push_Task_6 |
| **Sinchana Task 3** — `/api/push-mappings` endpoint | Makes the POST in this workflow actually succeed | 🔴 Owned by Sinchana, not Vidhi |
| **Replace Stub Apply Options** | When OPS ships beta option mutations | 🔴 Waiting on OPS team |
