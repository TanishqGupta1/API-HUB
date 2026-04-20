# Urvashi — Sprint Tasks

**Sprint:** Storefront UI redesign
**Spec:** `docs/superpowers/specs/2026-04-20-storefront-ui-redesign-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-04-20-storefront-ui-redesign.md`
**Load:** 4 tasks (mild — backend + route migration)
**Branch:** cut from `main` as `urvashi/storefront-ui-<slug>` per task. One PR per task.

> Your slice is foundational: backend aggregates + one route-group move. Sinchana/Vidhi's frontend work depends on your backend changes landing first.

---

## Priority order

1. **Plan Task 1 — Add aggregate fields to `ProductListRead`** (`backend/modules/catalog/schemas.py`)
   - Add: `category_id: Optional[UUID] = None`, `price_min: Optional[Decimal] = None`, `price_max: Optional[Decimal] = None`, `total_inventory: Optional[int] = None`.
   - `Decimal` import already present.
   - Acceptance: pydantic model instantiates without complaint; `GET /api/products` response shape includes new fields (null-valued for now).

2. **Plan Task 2 — Compute aggregates in `list_products`** (`backend/modules/catalog/routes.py`)
   - Replace per-product variant-count query with one aggregate `select()` grouping by `product_id`, summing `inventory` and min/max of `base_price`.
   - Plan file has the full replacement block verbatim — copy it.
   - Acceptance: `/api/products?supplier_id=<vg>` returns rows with real `price_min/max` and `total_inventory`. N+1 gone; single query for the batch.

3. **Plan Task 3 — Expose `category_id` on `ProductRead`**
   - `backend/modules/catalog/schemas.py` `ProductRead`: add `category_id: Optional[UUID] = None` under `category`.
   - Model already has the column; `from_attributes` picks it up.
   - Acceptance: `GET /api/products/{id}` includes `category_id`.

4. **Plan Task 4 — Route group migration** (frontend)
   - Create `frontend/src/app/(admin)/layout.tsx` that wraps children in the existing admin sidebar chrome.
   - `git mv` the 9 top-level app dirs (page.tsx, suppliers, customers, markup, workflows, sync, mappings, api-registry, products) into `(admin)/`.
   - Slim `frontend/src/app/layout.tsx` to bare html/body/globals — admin chrome moves into the group layout.
   - Acceptance: all existing URLs (`/`, `/suppliers`, `/workflows`, etc.) return 200 with the admin sidebar still rendering. `/storefront/vg` unaffected.

---

## Rules

- Task 2 is a single aggregate `select()` — don't issue one query per product. Plan shows it exactly.
- Task 4 uses `git mv` to preserve history — not `mv`.
- `ProductListRead`/`ProductRead` schema changes are additive; keep all existing fields.
- No Co-Authored-By lines in commits.

## Dependencies

- Tasks 1 → 2 → 3 in order.
- Task 13 on Sinchana (card price band/badge) blocks on your Task 2 completing.
- Task 18 on Vidhi (PDP breadcrumb) blocks on your Task 3.

## How to test locally

```bash
docker compose up -d postgres
cd backend && source .venv/bin/activate
uvicorn main:app --port 8000

# Task 1/2 check:
VG_ID=$(curl -s http://localhost:8000/api/suppliers | python3 -c 'import sys,json; print([s["id"] for s in json.load(sys.stdin) if s["slug"]=="vg-ops"][0])')
curl -s "http://localhost:8000/api/products?supplier_id=$VG_ID&limit=3" | python3 -m json.tool | grep -E 'price_|inventory|category_id'

# Task 3 check:
curl -s "http://localhost:8000/api/products/<any_id>" | python3 -m json.tool | grep category_id

# Task 4 check:
cd frontend && npm run dev
for p in / /suppliers /workflows /storefront/vg; do curl -sI "http://localhost:3000$p" | head -1; done
# All 200
```
