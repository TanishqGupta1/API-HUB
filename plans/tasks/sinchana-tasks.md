# Sinchana — Sprint Tasks

**Sprint:** Storefront UI redesign
**Spec:** `docs/superpowers/specs/2026-04-20-storefront-ui-redesign-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-04-20-storefront-ui-redesign.md`
**Branch:** cut from `main` as `sinchana/storefront-<slug>` per task. One PR per task.

---

## Overview

You own grid, category navigation, filter UI, and final polish. **All 8 tasks run in parallel** — they touch disjoint files. Ship in any order. If a task needs code from Vidhi or Urvashi that hasn't shipped yet, write a local stub with the interface below and move on.

## Files you own (nobody else writes these)

- `frontend/src/components/storefront/left-rail.tsx` — NEW
- `frontend/src/components/storefront/mobile-filter-sheet.tsx` — NEW
- `frontend/src/components/storefront/filter-chip-bar.tsx` — NEW
- `frontend/src/components/storefront/storefront-product-card.tsx` — EDIT
- `frontend/src/app/storefront/vg/page.tsx` — REWRITE
- `frontend/src/app/storefront/vg/category/[category_id]/page.tsx` — REWRITE
- `frontend/src/lib/types.ts` — EDIT (extend `ProductListItem`)
- `frontend/.gitignore` — EDIT (add `*.tsbuildinfo`)
- `frontend/src/components/storefront/category-nav.tsx` — DELETE

## Integration contracts (other people's files you import)

If you import a file that hasn't been shipped yet, create a local stub with the signature below. Replace with their real component via rebase when their PR merges.

| Imported from | Component | Interface |
|---|---|---|
| Vidhi 7 | `useSearch()` from `@/components/storefront/search-context` | returns `{ query: string; setQuery: (q: string) => void }` |
| Urvashi 2 | backend `GET /api/products` response | new fields on `ProductListItem`: `price_min`, `price_max`, `total_inventory`, `category_id` (all optional) |
| Urvashi 4 | no direct import (route group is orthogonal) | — |

If Vidhi hasn't shipped SearchContext yet, stub at top of your page:
```ts
const useSearch = () => ({ query: "", setQuery: () => {} }); // replaced by Vidhi 7
```

---

## Tasks

1. **Plan Task 8 — LeftRail**
   - Collapsible 260px/48px tree, sticky under top bar, per-category count.
   - localStorage key: `vg-rail-collapsed`.
   - Props: `categories: Category[]`, `counts: Record<string, number>`. No data fetch inside.
   - Acceptance: active route = blueprint blue fill; nested categories indent 14px per level.

2. **Plan Task 10 — MobileFilterSheet**
   - Floating Filter FAB at `< 768px` bottom-right; opens bottom sheet wrapping `<LeftRail>`.
   - Escape + backdrop click close; `role="dialog" aria-modal="true"`.
   - Acceptance: FAB invisible on desktop (Tailwind `md:hidden`).

3. **Plan Task 12 — FilterChipBar**
   - Props: `inStockOnly`, `onInStockChange`, `sort`, `onSortChange`, `query` (display only).
   - Active chip = blueprint blue fill with `×`; inactive = white border.
   - Right side: sort select + Clear all link.

4. **Plan Task 13 — StorefrontProductCard upgrades**
   - Add price band (min–max) and OUT badge top-right when `total_inventory <= 0`.
   - Extend `ProductListItem` in `frontend/src/lib/types.ts`:
     ```ts
     price_min: number | null;
     price_max: number | null;
     total_inventory: number | null;
     category_id: string | null;
     ```
   - If Urvashi 2 not shipped, backend returns null for new fields — card handles gracefully (no band, no badge).

5. **Plan Task 11 — Rewrite `/storefront/vg/page.tsx`**
   - Page renders grid + `<FilterChipBar>` only. Chrome comes from layout (Vidhi 5/9).
   - Client-side filter: name/sku/brand via `useSearch()`; in-stock via FilterChipBar; sort name A-Z / Z-A / most variants.
   - Acceptance: empty state when filters exclude all.

6. **Plan Task 19 — Rewrite category page** (`app/storefront/vg/category/[category_id]/page.tsx`)
   - Same layout as Task 11, adds breadcrumb at top.
   - Products fetched with `?supplier_id=<vg>&category_id=<id>` (server resolves descendants).

7. **Plan Task 20 — Dead code + a11y + gitignore**
   - `git rm frontend/src/components/storefront/category-nav.tsx`.
   - Grep for leftover imports: `grep -rn "category-nav" frontend/src || true`.
   - Add `*.tsbuildinfo` to `frontend/.gitignore`.
   - Lighthouse Accessibility audit on `/storefront/vg` and any PDP URL. Fix anything below 90 (alt attrs, contrast).

8. **Housekeeping follow-up (from PR #19 review)**
   - Grep `frontend/src/app` for any inline `style={{...}}` block > 5 lines. Convert to Tailwind utilities when obvious. Flag unclear cases in PR description — do not invent.

---

## Rules

- Follow plan's code blocks verbatim for Tasks 8, 10, 12.
- Blueprint tokens only: paper `#f2f0ed`, ink `#1e1e24`, blueprint `#1e4d92`, muted `#888894`, border `#cfccc8`.
- No Co-Authored-By lines in commits.
- One PR per task. PR title = `feat(storefront): <task name>`.

## Running locally

```bash
docker compose up -d postgres n8n
cd backend && source .venv/bin/activate && uvicorn main:app --port 8000 &
cd frontend && npm run dev &
# http://localhost:3000/storefront/vg
```
