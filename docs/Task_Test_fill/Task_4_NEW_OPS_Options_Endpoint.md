# Task 4 (NEW Sprint) — `GET /ops-options` Endpoint — Detail Guide

**Status:** ✅ Code complete on 2026-04-24 (tests not executed — Docker Desktop not running)
**Branch:** `Vidhi`
**Sprint:** Demo Push Pipeline
**What you can say in one sentence:** *"I built the backend endpoint that converts the hub's master-option product config into a product-scoped shape ready for the customer's OPS — stripping the global master IDs and keeping them only as source_* fields for traceability."*

---

## 1. What Got Built

| File | What Changed |
|---|---|
| `backend/modules/markup/schemas.py` | Added `OPSProductOptionSchema` + `OPSProductAttributeSchema` |
| `backend/modules/markup/routes.py` | Added `GET /api/push/{customer_id}/product/{product_id}/ops-options` |
| `backend/tests/test_ops_options_endpoint.py` | New test file with 2 test cases (TDD) |

---

## 2. Background — What Is This Task About?

### The architectural rule (from Christian's meeting)

**Outbound to customer OPS = product options only, never master options.**

The hub stores options in two layers:
- **Master options** (global, OPS-internal) — shared catalog, has `ops_master_option_id` / `ops_attribute_id`
- **Product options** (per-product config) — points at a master, overridden per product with `enabled`, `price`, etc.

When we push to a customer's OPS storefront, their OPS has its *own* option IDs — **our master IDs are meaningless to them**. So the push payload must be "product-scoped" — just `option_key`, `title`, `attributes[]`, no hub-global IDs in the core fields.

But we still need to **trace** which master option a pushed option came from — for the `push_mappings` table (Sinchana's Task 3). So we keep the master IDs as `source_master_option_id` / `source_master_attribute_id` — side-car fields that live alongside the core shape.

### What This Endpoint Does

`GET /api/push/{customer_id}/product/{product_id}/ops-options`

1. Reads all `ProductOption` rows for the product where `enabled=True`
2. For each, reads only the attributes where `enabled=True`
3. Joins to `MasterOption` + `MasterOptionAttribute` (via `ops_master_option_id`) to pull `attribute_key` from the master's `raw_json` — populates `source_attribute_key`
4. Returns a list of `OPSProductOptionSchema` with core fields clean + source_* fields for traceback

---

## 3. How It Fits — The Pipeline

```
Customer clicks "Push to OPS" in hub UI
    ↓
n8n ops-push workflow triggered
    ↓
Existing: OPS: Set Product + Set Price
    ↓
NEW (Task 5):  GET /ops-options  ← THIS ENDPOINT
    ↓           returns product-scoped options list
    ↓
Stub Apply Options (n8n) — logs + marks _stub: true
    (real OPS setAdditionalOption calls land here once beta ships)
    ↓
Build Push Mapping (n8n) — flattens to push_mappings payload
    ↓
POST /api/push-mappings (Sinchana's Task 3)
    ↓
POST /push-log (existing)
```

---

## 4. Key Design Decisions

### Schema location — followed spec, not Sinchana's copy

Sinchana's `push_mappings/schemas.py` already has `OPSProductOption` / `OPSProductAttribute` (similar shape — she needed them for `PushMappingUpsert`). The Vidhi task spec said to add these to `markup/schemas.py`. I kept them in `markup/schemas.py` per spec to keep the endpoint's response model colocated with the route. The two definitions differ slightly:

- `markup/schemas.py`: `float` for price/numeric (JSON-friendly for OPS push)
- `push_mappings/schemas.py`: `Decimal` (DB-friendly for upsert payloads)

Each is shaped for its consumer.

### `selectinload` for attributes

`ProductOption.attributes` is a relationship. Without `selectinload`, every iteration would trigger a lazy-load query (N+1). With it, all attributes for all options load in one extra query.

### attribute_key lookup via JSON `raw_json`

`MasterOptionAttribute.title` is the display label ("Gloss"). But OPS also has an `attribute_key` ("Gloss" or "inkFinish_gloss") stored inside `raw_json` — that's what downstream `push_mapping` rows use for dedupe. So we unpack it from `raw_json` and expose it as `source_attribute_key`.

Built as a `dict[(master_option_id, ops_attribute_id), attribute_key]` lookup so the per-attribute loop is O(1).

### Enabled filter is strict AND

Both the option AND the attribute must be `enabled=True`. An enabled option with zero enabled attributes is silently dropped (the `if not enabled_attrs: continue` guard). Empty list returned instead of 404 — n8n can handle "no options" gracefully.

### Sort order override

Respects the per-product sort override: `a.overridden_sort if a.overridden_sort is not None else a.sort_order`. Customer A can reorder attributes differently from customer B.

---

## 5. Exact Response Shape

```json
[
  {
    "option_key": "inkFinish",
    "title": "Ink Finish",
    "options_type": "combo",
    "source_master_option_id": 9001,
    "attributes": [
      {
        "title": "Gloss",
        "price": 5.0,
        "sort_order": 1,
        "numeric_value": 0.0,
        "source_master_attribute_id": 9991,
        "source_attribute_key": "Gloss"
      }
    ]
  }
]
```

Notice:
- `master_option_id` is **NOT** a core field — only `source_master_option_id`
- `ops_attribute_id` is **NOT** a core field — only `source_master_attribute_id`
- `attribute_key` comes from master's `raw_json`, surfaced as `source_attribute_key`

---

## 6. Tests (`test_ops_options_endpoint.py`)

| Test | What It Asserts |
|---|---|
| `test_ops_options_returns_product_scoped_shape` | Seeds master option + enables on a product → asserts core has no `master_option_id`/`ops_attribute_id`; `source_master_option_id=9001`; `source_master_attribute_id=9991`; price flows through as 5.00 |
| `test_ops_options_empty_when_nothing_enabled` | Product with no enabled options returns `[]`, not 404 |

Cleanup fixture wipes test rows (Products with `OPO-*` sku, Customers/Suppliers with matching names, Master options id >= 9000) to keep tests idempotent across re-runs.

---

## 7. Running Tests

Docker-based (spec command):
```bash
docker compose exec -T api pytest tests/test_ops_options_endpoint.py -v
```

**Current status:** Docker Desktop is not running on the dev machine (failed to start). Syntax verified via `python -m py_compile`. Tests must be run by next dev who has Docker up, or in CI.

---

## 8. Manual Check Steps

```bash
# Pick a customer id and a product id that has enabled options
CUST=... PROD=... SECRET=$(grep INGEST_SHARED_SECRET .env | cut -d= -f2)
curl -H "X-Ingest-Secret: $SECRET" \
  "http://localhost:8000/api/push/$CUST/product/$PROD/ops-options" | jq .
```

Expect: JSON list. Each item has `option_key`, `title`, `options_type`, `attributes[]`, `source_master_option_id`. No `master_option_id` or `ops_attribute_id` in the core fields.

---

## 9. Dependencies

**Depends on:**
- Sinchana Task 2 (master_options tables + ProductOption.enabled column) — ✅ on main
- Sinchana Task 3 (PushMappingUpsert/push_mappings module) — consumers, not direct dep

**Consumed by:**
- NEW Task 5 — n8n ops-push workflow's new `Get /ops-options` node

---

## 10. What Comes Next

| Next Task | What It Adds | Status |
|---|---|---|
| **NEW Task 5** — n8n workflow: add 4 nodes | Inserts `Get /ops-options` → `Stub Apply Options` → `Build Push Mapping` → `POST /push-mappings` between existing OPS and push-log nodes | 🟢 Unblocked — ready to build next |
| **OLD Task 5** — n8n smoke test | Manual end-to-end with real OPS | 🔴 Blocked on Christian's OPS credentials |
