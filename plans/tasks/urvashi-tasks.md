# Urvashi — Sprint Tasks

**Sprint:** OPS Push Pipeline — Backend Orchestration  
**Spec:** `docs/superpowers/specs/2026-04-22-remaining-tasks-design.md`  
**Full code for every task:** `docs/superpowers/plans/2026-04-20-ops-push.md` Phase B  
**Branch per task:** `urvashi/<task-slug>` → one PR per task

---

## Overview

7 tasks. All backend Python except Task 1 (tiny frontend). Every task has the complete code already written in the ops-push plan — your job is to follow the steps, not invent the code. Do in order — B1 first since B2+ depend on the push_log schema.

---

## Task 1 — Dashboard Wired to Real API (V0 Task 0.6 / V1f Task 22)

**File:** `frontend/src/app/(admin)/page.tsx`  
**Effort:** XS

Replace hardcoded stats with real API calls:

```ts
// Replace hardcoded stat values with:
const [stats, setStats] = useState<{ suppliers: number; products: number; variants: number } | null>(null);
useEffect(() => {
  api<typeof stats>("/api/stats").then(setStats);
}, []);
```

Replace hardcoded activity table rows with:
```ts
api<SyncJob[]>("/api/sync-jobs?limit=5").then(setActivity);
```

Rename labels:
- "Recent Pipeline Activity" → "Recent Data Updates"
- Remove hardcoded baselines (32.4k SKUs, 187k variants, 98% uptime)

Types `SyncJob` already in `frontend/src/lib/types.ts` — check before adding.

**Acceptance:** Dashboard shows real supplier/product/variant counts. Activity table shows real sync jobs.

---

## Task 2 — push_log Pydantic Schemas + POST Endpoint (B1)

**Files:**
- `backend/modules/push_log/schemas.py` — CREATE
- `backend/modules/push_log/routes.py` — MODIFY

**Full code:** `docs/superpowers/plans/2026-04-20-ops-push.md` → Task B1

Create `schemas.py` with `ProductPushLogCreate` and `ProductPushLogRead` Pydantic models. Rewrite `routes.py` to use these schemas and add `POST /api/push-log` endpoint.

Smoke test after:
```bash
cd backend && source .venv/bin/activate && uvicorn main:app --port 8000 &
PROD=$(curl -s "http://localhost:8000/api/products?limit=1" | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["id"])')
CUST=$(curl -s "http://localhost:8000/api/customers" | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["id"])')
curl -s -X POST http://localhost:8000/api/push-log \
  -H "Content-Type: application/json" \
  -d "{\"product_id\":\"$PROD\",\"customer_id\":\"$CUST\",\"status\":\"pushed\",\"ops_product_id\":\"999\"}" \
  | python3 -m json.tool
```

Expected: 201 with the new row.

---

## Task 3 — `push_candidates` Module (B2)

**Files:**
- `backend/modules/push_candidates/__init__.py` — CREATE (empty)
- `backend/modules/push_candidates/service.py` — CREATE
- `backend/modules/push_candidates/routes.py` — CREATE
- `backend/main.py` — MODIFY (add import + `app.include_router`)

**Full code:** `docs/superpowers/plans/2026-04-20-ops-push.md` → Task B2

Service: `list_candidates(db, customer_id, supplier_id, only_never_pushed, limit)` — returns products with `last_synced` not null, excluding already-pushed ones when `only_never_pushed=True`.

Route: `GET /api/push/candidates/{customer_id}` — returns list of `{product_id, supplier_sku, product_name, ops_product_id}`.

Wire in `main.py` same pattern as other routers.

---

## Task 4 — Variant Bundle Endpoint (B4)

**Files:**
- `backend/modules/markup/schemas.py` — MODIFY (append new schemas)
- `backend/modules/markup/routes.py` — MODIFY (add endpoint)

**Full code:** `docs/superpowers/plans/2026-04-20-ops-push.md` → Task B4

Add `OPSProductSizeInput`, `OPSProductPriceEntry`, `OPSVariantsBundle` schemas. Add endpoint `GET /api/push/{customer_id}/product/{product_id}/ops-variants` that returns `{sizes: [...], prices: [...]}` aligned by index.

Note: `calculate_price` is already in `backend/modules/markup/engine.py` — call it, don't rewrite it.

---

## Task 5 — Category OPS Input Endpoint (B5)

**Files:**
- `backend/modules/catalog/schemas.py` — MODIFY (append)
- `backend/modules/catalog/routes.py` — MODIFY (add endpoint)

**Full code:** `docs/superpowers/plans/2026-04-20-ops-push.md` → Task B5

Add `OPSCategoryInput` schema. Add `GET /api/categories/{category_id}/ops-input` endpoint — returns `{category_name, parent_id: -1, status: 1, category_internal_name}`.

---

## Task 6 — Image Pipeline Cache Header (B6)

**File:** `backend/modules/ops_push/image_pipeline.py`  
**Effort:** XS

**Full code:** `docs/superpowers/plans/2026-04-20-ops-push.md` → Task B6

Find the `Response(...)` return in `image_pipeline.py`. Add headers:
```python
headers={
    "Cache-Control": "public, max-age=86400",
    "X-Processed-By": "api-hub/ops_push",
}
```

---

## Task 7 — Wire S&S + 4Over Protocols into Sync Dispatch (Gap G2)

**File:** `backend/modules/promostandards/routes.py`

**Gap:** `POST /api/sync/{supplier_id}/products` only handles `protocol == "promostandards"`. S&S (`protocol = "rest"`) and 4Over (`protocol = "rest_hmac"`) adapters exist in `backend/modules/rest_connector/` but are never called.

**Fix:** In the background task function inside the sync route, add branches after the existing promostandards block:

```python
from modules.rest_connector.client import RESTConnectorClient
from modules.rest_connector.ss_normalizer import ss_to_ps_products
from modules.rest_connector.fourover_client import FourOverClient
from modules.rest_connector.fourover_normalizer import fourover_to_ps_products

# Inside the background task, where protocol is checked:
if supplier.protocol == "promostandards":
    # existing SOAP path
    ...
elif supplier.protocol == "rest":
    client = RESTConnectorClient(
        base_url=supplier.base_url,
        auth_config=supplier.auth_config,
    )
    raw = await client.get_products()
    products = ss_to_ps_products(raw)
    await upsert_products(db, supplier.id, products)
elif supplier.protocol == "rest_hmac":
    client = FourOverClient(
        base_url=supplier.base_url,
        auth_config=supplier.auth_config,
    )
    raw = await client.get_products()
    products = fourover_to_ps_products(raw)
    await upsert_products(db, supplier.id, products)
```

Read the existing rest_connector files first to verify the exact class names and method signatures before writing this — they may differ slightly from the above sketch.

**Acceptance:** `POST /api/sync/{s&s_supplier_id}/products` no longer returns 500. S&S sync runs through the REST adapter.

---

## Files You Own

- `frontend/src/app/(admin)/page.tsx` — MODIFY (Task 1, stats + activity only)
- `backend/modules/push_log/schemas.py` — CREATE (Task 2)
- `backend/modules/push_log/routes.py` — MODIFY (Task 2)
- `backend/modules/push_candidates/` — CREATE all files (Task 3)
- `backend/main.py` — MODIFY (Task 3, router wire-up only)
- `backend/modules/markup/schemas.py` — MODIFY (Task 4)
- `backend/modules/markup/routes.py` — MODIFY (Tasks 4)
- `backend/modules/catalog/schemas.py` — MODIFY (Task 5)
- `backend/modules/catalog/routes.py` — MODIFY (Task 5)
- `backend/modules/ops_push/image_pipeline.py` — MODIFY (Task 6)
- `backend/modules/promostandards/routes.py` — MODIFY (Task 7)
