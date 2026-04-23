# Vidhi — Sprint Tasks

**Sprint:** Demo Push Pipeline (VG team demo)
**Spec:** `docs/superpowers/specs/2026-04-23-demo-push-pipeline-design.md`
**Full plan + code:** `docs/superpowers/plans/2026-04-23-demo-push-pipeline.md` (Tasks 4, 5, 6)
**Branch per task:** `vidhi/<task-slug>` → one PR per task

---

## Overview

3 tasks — 1 backend, 1 n8n, 1 frontend. Task 4 blocks Task 5 (n8n calls the endpoint you build). Task 6 parallel, no blockers after Sinchana ships.

**Depends on Sinchana:**
- Task 4 needs `OPSProductOption` / `OPSProductAttribute` schemas from her Task 2
- Task 5 needs her POST `/api/push-mappings` endpoint (Task 3)

Pre-work: same merge-conflict resolution as rest of team.

---

## Task 4 — `GET /api/push/{customer_id}/product/{product_id}/ops-options` endpoint

**Files:**
- Modify: `backend/modules/markup/schemas.py` (append schemas — OPSProductOptionSchema, OPSProductAttributeSchema)
- Modify: `backend/modules/markup/routes.py` (add endpoint to `push_router`)
- Create: `backend/tests/test_ops_options_endpoint.py` (2 tests)

Full code in plan → Task 4 → Steps 1–3.

**What this endpoint does:** Converts hub's master-option-based product config into a product-scoped shape ready for OPS push. **Strips `master_option_id`** and `ops_attribute_id` from the core output (they're OPS-internal global IDs, not valid on per-product push). Retains them ONLY as `source_master_option_id` / `source_master_attribute_id` for the push_mapping traceback.

**This is THE architectural rule from Christian's meeting:** outbound to customer OPS = product options only, never master options.

**Logic:**
1. Load `ProductOption` where `enabled=true` for this product (with selectinload attributes)
2. Filter attributes to `enabled=true` only
3. Look up `master_option_attributes.raw_json.attribute_key` via join to `MasterOption` + `MasterOptionAttribute` — populates `source_attribute_key` for traceback
4. Build `OPSProductOptionSchema` list — drops master_* from core, keeps as source_*

**Requires:** `X-Ingest-Secret` header (reuse existing dep from `modules/catalog/ingest.py:56`).

**Tests (TDD):**
1. `test_ops_options_returns_product_scoped_shape` — asserts `master_option_id` NOT in output core, `source_master_option_id` IS present; attribute price/title/sort correctly flow through
2. `test_ops_options_empty_when_nothing_enabled` — no enabled options → returns `[]` not 404

Run: `docker compose exec -T api pytest tests/test_ops_options_endpoint.py -v` — 2 PASS.

**Acceptance:** `curl -H "X-Ingest-Secret: <value>" "http://localhost:8000/api/push/<cust>/product/<prod>/ops-options"` returns list. Each item has option_key, title, options_type, attributes[]; each attribute has title, price, sort_order, source_master_attribute_id. No master_option_id / ops_attribute_id in core fields.

---

## Task 5 — n8n `ops-push` workflow: add 4 nodes

**File:** `n8n-workflows/ops-push.json` (modify)

Full code in plan → Task 5 → Step 2.

**Insertion point:** After existing `OPS: Set Product Price` node, before `POST Push Log`. New chain:

```
OPS: Set Product Price
  → Get /ops-options (HTTP GET)
  → Stub Apply Options (Code)
  → Build Push Mapping (Code)
  → POST /push-mappings (HTTP POST)
  → POST Push Log  (existing)
```

**4 new nodes to add:**

1. **Get /ops-options** — HTTP GET to `/api/push/{customer_id}/product/{product_id}/ops-options` with X-Ingest-Secret header. Pulls customer_id + product_id from `$('Parse Params').item.json`.

2. **Stub Apply Options** — Code node. Logs payload to console, returns each option annotated with `_stub: true`, `target_ops_option_id: null`, each attribute with `target_ops_attribute_id: null`. Inline comment marks where real OPS setAdditionalOption / setAdditionalOptionAttributes / setProductsAttributePrice nodes will go once beta ships.

3. **Build Push Mapping** — Code node. Flattens options → attributes array for `push_mappings` payload. Pulls source_product_id, customer_id from Parse Params; target_ops_product_id from `$('OPS: Set Product').item.json.products_id`; target_ops_base_url from payload's customer field; supplier_sku from payload's product field.

4. **POST /push-mappings** — HTTP POST to `/api/push-mappings` with X-Ingest-Secret + Content-Type. Body is `{{ $json }}` from Build Push Mapping.

**Update `connections` object** — re-route `OPS: Set Product Price` → `Get /ops-options`, chain through new 4 nodes, land at `POST Push Log`.

**Validate + import:**
```bash
python3 -c "import json; json.load(open('n8n-workflows/ops-push.json'))"
docker cp n8n-workflows/ops-push.json api-hub-n8n-1:/tmp/opspush.json
docker exec api-hub-n8n-1 n8n import:workflow --input=/tmp/opspush.json
```

Expected: `Successfully imported 1 workflow`. Open n8n UI → verify 4 new nodes visible and connected correctly.

**Acceptance:** workflow imports without error. Manual execution chains through all new nodes without error on a test product (Stub Apply Options just logs — no OPS call).

---

## Task 6 — Frontend: per-row "Push to OPS" button on `/products` catalog

**Files:**
- Create: `frontend/src/components/products/push-row-action.tsx` (new component)
- Modify: `frontend/src/app/(admin)/products/page.tsx` (add Action column)

Full code in plan → Task 6 → Steps 1–2.

**Component `push-row-action.tsx`:**
- shadcn `Dialog` that opens on button click
- Fetches `/api/customers` on open
- Customer dropdown (only active customers enabled)
- Confirm button fires `POST /api/n8n/workflows/vg-ops-push-001/trigger?product_id=X&customer_id=Y`
- Toast-style inline message for busy/success/error states
- Auto-closes on success

Reuse pattern from `frontend/src/components/products/publish-button.tsx` (existing full-page widget — don't modify it; this is the compact per-row version).

**Products page changes:**
- Add "Action" column header
- Add `<td>` with `<PushRowAction productId={p.id} productName={p.product_name} />` per row

**Styling:** `Button size="sm" variant="outline" className="border-[#1e4d92] text-[#1e4d92]"` for the row trigger.

**Manual check:**
1. Reload `/products` — new Action column with Push to OPS button per row
2. Click → dialog opens → customer dropdown populated
3. Select + Confirm → toast "Push started" + dialog closes after 1.5s
4. n8n UI shows workflow execution triggered

**Acceptance:** per-row push button works, triggers n8n workflow with correct product_id + customer_id.

---

## Files You Own

- `backend/modules/markup/schemas.py` — MODIFY (Task 4, append OPS schemas)
- `backend/modules/markup/routes.py` — MODIFY (Task 4, add endpoint)
- `backend/tests/test_ops_options_endpoint.py` — CREATE (Task 4)
- `n8n-workflows/ops-push.json` — MODIFY (Task 5, add 4 nodes + update connections)
- `frontend/src/components/products/push-row-action.tsx` — CREATE (Task 6)
- `frontend/src/app/(admin)/products/page.tsx` — MODIFY (Task 6, add Action column)

## Reused utilities

- `require_ingest_secret` dep → `backend/modules/catalog/ingest.py:56`
- existing `push_router` in `backend/modules/markup/routes.py`
- shadcn Dialog (already installed in frontend)
- `api<T>()` helper → `frontend/src/lib/api.ts`
- Reference pattern → `frontend/src/components/products/publish-button.tsx`
