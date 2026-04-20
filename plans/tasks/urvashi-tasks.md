# Urvashi — Sprint Tasks

**Sprint:** Storefront UI redesign
**Spec:** `docs/superpowers/specs/2026-04-20-storefront-ui-redesign-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-04-20-storefront-ui-redesign.md`
**Branch:** cut from `main` as `urvashi/storefront-<slug>` per task. One PR per task.

---

## Overview

Backend aggregates + one route migration. **All 4 tasks run in parallel** — they touch disjoint files (schemas.py isn't touched by anyone else; routes.py isn't touched by anyone else; route migration only moves admin pages, not storefront). Ship in any order.

## Files you own (nobody else writes these)

- `backend/modules/catalog/schemas.py` — EDIT (extend `ProductListRead` + `ProductRead`)
- `backend/modules/catalog/routes.py` — EDIT (aggregate query rewrite)
- `frontend/src/app/(admin)/layout.tsx` — NEW (admin chrome)
- `frontend/src/app/layout.tsx` — EDIT (slim root)
- Moved directories (`git mv` under `(admin)/`):
  - `frontend/src/app/page.tsx` → `(admin)/page.tsx`
  - `frontend/src/app/suppliers/**` → `(admin)/suppliers/**`
  - `frontend/src/app/customers/**` → `(admin)/customers/**`
  - `frontend/src/app/markup/**` → `(admin)/markup/**`
  - `frontend/src/app/workflows/**` → `(admin)/workflows/**`
  - `frontend/src/app/sync/**` → `(admin)/sync/**`
  - `frontend/src/app/mappings/**` → `(admin)/mappings/**`
  - `frontend/src/app/api-registry/**` → `(admin)/api-registry/**`
  - `frontend/src/app/products/**` → `(admin)/products/**`

## Integration contracts

No imports from Sinchana or Vidhi. Your work is standalone. Sinchana + Vidhi depend on your schema fields existing, but they handle null/missing fields gracefully (their stubs). You do not need to wait for them.

---

## Tasks

1. **Plan Task 1 — Add aggregate fields to `ProductListRead` and `category_id` to both read schemas**
   - Open `backend/modules/catalog/schemas.py`.
   - In `ProductListRead` add:
     ```py
     category_id: Optional[UUID] = None
     price_min: Optional[Decimal] = None
     price_max: Optional[Decimal] = None
     total_inventory: Optional[int] = None
     ```
   - In `ProductRead` add, right after `category`:
     ```py
     category_id: Optional[UUID] = None
     ```
   - `Decimal` + `UUID` imports already present. This combines Plan Tasks 1 + 3 into one PR because both touch the same file.
   - Acceptance: `/api/products` and `/api/products/{id}` responses include the new fields (null until Task 2 computes them).

2. **Plan Task 2 — Compute aggregates in `list_products`**
   - Open `backend/modules/catalog/routes.py`.
   - Replace the per-product variant-count loop with a single aggregate query grouped by `product_id`, yielding `variant_count`, `price_min`, `price_max`, `total_inventory`.
   - Plan file has the full replacement block — copy verbatim.
   - Acceptance: one DB round trip per `/api/products` call; each response row populated with real min/max/sum.

3. **Plan Task 4 — Route group migration**
   - Create `frontend/src/app/(admin)/layout.tsx`:
     ```tsx
     import Sidebar from "@/components/Sidebar";

     export default function AdminLayout({ children }: { children: React.ReactNode }) {
       return (
         <div className="flex min-h-screen bg-[#f2f0ed] text-[#1e1e24]">
           <Sidebar />
           <main className="flex-1 px-8 py-8 ml-[260px]">{children}</main>
         </div>
       );
     }
     ```
     (Copy the actual wrapper markup from the current `app/layout.tsx` so admin chrome matches exactly.)
   - Slim `frontend/src/app/layout.tsx` to plain html/body/globals.css — admin chrome moves into `(admin)/layout.tsx`.
   - Move 9 directories with `git mv` (list in "Files you own" above).
   - Acceptance: `/`, `/suppliers`, `/workflows`, etc. return 200 with admin sidebar still rendering. `/storefront/vg` unaffected because `storefront/` is outside the `(admin)` group.

---

## Rules

- Task 2 is ONE aggregate `select()` with `func.count / min / max / sum`. No per-product subqueries.
- Task 4 uses `git mv` to preserve history — not `mv`.
- Schema changes are additive (all new fields optional with `= None`).
- No Co-Authored-By lines in commits.
- One PR per task. PR title = `feat(backend): ...` or `refactor(frontend): route group (admin)`.

## Running locally

```bash
docker compose up -d postgres
cd backend && source .venv/bin/activate && uvicorn main:app --port 8000

# Task 1/2 check:
VG_ID=$(curl -s http://localhost:8000/api/suppliers | python3 -c 'import sys,json; print([s["id"] for s in json.load(sys.stdin) if s["slug"]=="vg-ops"][0])')
curl -s "http://localhost:8000/api/products?supplier_id=$VG_ID&limit=3" | python3 -m json.tool | grep -E 'price_|inventory|category_id'

# Task 4 check:
cd frontend && npm run dev
for p in / /suppliers /workflows /storefront/vg; do curl -sI "http://localhost:3000$p" | head -1; done
# all 200
```
