# Sinchana — Sprint Tasks

**Sprint:** Storefront UI redesign
**Spec:** `docs/superpowers/specs/2026-04-20-storefront-ui-redesign-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-04-20-storefront-ui-redesign.md`
**Load:** 8 tasks (heavy — grid, rail, mobile, polish)
**Branch:** cut from `main` as `sinchana/storefront-ui-<slug>` per task. One PR per task.

> Read the spec once before starting. It defines layout, tokens, and out-of-scope items. The plan file has full code for each step — copy verbatim. Do NOT invent shapes or component APIs.

---

## Priority order

1. **Plan Task 8 — LeftRail** (`frontend/src/components/storefront/left-rail.tsx`)
   - Collapsible 260px/48px tree, sticky under top bar, per-category count.
   - localStorage key: `vg-rail-collapsed`.
   - Acceptance: tree builds from `GET /api/categories?supplier_id=<vg>`, counts from a product tally passed via props. Active route = blueprint blue fill.

2. **Plan Task 10 — MobileFilterSheet** (`frontend/src/components/storefront/mobile-filter-sheet.tsx`)
   - Floating Filter FAB at < 768px bottom-right, opens bottom sheet with LeftRail inside.
   - Escape key + backdrop click close it. `role="dialog" aria-modal="true"`.
   - Acceptance: on mobile viewport, FAB visible, sheet slides up, trap focus, desktop unaffected.

3. **Plan Task 11 — Rewrite `/storefront/vg/page.tsx`**
   - Strip old self-contained shell. Page renders only grid + FilterChipBar.
   - Uses `useSearch()` from SearchContext (Vidhi's Task 7). Client-side filter on name/sku/brand.
   - Sort: name A-Z / Z-A / most variants. In-stock toggle via FilterChipBar.
   - Acceptance: page renders 100+ products, search in TopBar filters live, sort works, empty state shown when filters exclude all.

4. **Plan Task 12 — FilterChipBar** (`frontend/src/components/storefront/filter-chip-bar.tsx`)
   - Props: `inStockOnly`, `onInStockChange`, `sort`, `onSortChange`, `query` (read-only display).
   - Chip pattern: active filter = blueprint blue fill with `×`; inactive = white w/ border.
   - Right: Sort `<select>` + Clear all link.
   - Acceptance: clicking chips toggles state, sort reorders grid (handled in page), "Clear all" resets everything.

5. **Plan Task 13 — StorefrontProductCard upgrades** (`frontend/src/components/storefront/storefront-product-card.tsx`)
   - Add price band (min–max) rendered from `price_min`/`price_max`.
   - Add OUT badge top-right when `total_inventory <= 0`.
   - Update `ProductListItem` type in `frontend/src/lib/types.ts` to include the new fields.
   - Acceptance: cards render band and badge based on Urvashi's backend aggregates.

6. **Plan Task 19 — Rewrite category page** (`frontend/src/app/storefront/vg/category/[category_id]/page.tsx`)
   - Same pattern as Task 11: breadcrumb + FilterChipBar + grid.
   - Uses `?supplier_id=<vg>&category_id=<id>` (server filter incl. descendants).
   - Acceptance: clicking a leaf category shows its products; parent shows subtree.

7. **Plan Task 20 — Remove dead code + Lighthouse**
   - `git rm frontend/src/components/storefront/category-nav.tsx`.
   - Grep for leftover imports: `grep -rn "category-nav" frontend/src || true`.
   - Run Lighthouse Accessibility audit on `/storefront/vg` + any PDP URL. Fix anything below 90 (likely alt attrs / contrast).
   - Acceptance: a11y score ≥ 90 on both pages, no broken imports.

8. **Follow-up housekeeping** (not in plan but related to PR #19 review)
   - Add `*.tsbuildinfo` to `frontend/.gitignore`.
   - Grep whole `frontend/src/app` for any remaining inline `style={{...}}` blocks that exceed 5 lines and convert to Tailwind utilities where obvious. Skip anything requiring invention — if unclear, leave + flag in PR description.

---

## Rules

- Follow plan's code blocks verbatim for components in Tasks 8, 10, 12.
- Don't change spec — if a field or prop seems missing, ping me before adding.
- Blueprint tokens only: paper `#f2f0ed`, ink `#1e1e24`, blueprint `#1e4d92`, muted `#888894`, border `#cfccc8`. No new colors.
- No Co-Authored-By lines in commits.
- Commit at TDD boundaries (one commit per Task's green checkpoint). PR per task.

## Dependencies

- Task 11 + 19 block on Vidhi Task 7 (SearchContext) and Sinchana Task 12 (FilterChipBar).
- Task 13 blocks on Urvashi Tasks 1+2 (backend aggregates).
- Task 20 runs last.

## How to test locally

```bash
docker compose up -d postgres n8n
cd backend && source .venv/bin/activate && uvicorn main:app --port 8000
cd frontend && npm run dev
# visit http://localhost:3000/storefront/vg
```
