# Vidhi — Sprint Tasks

**Sprint:** Storefront UI redesign
**Spec:** `docs/superpowers/specs/2026-04-20-storefront-ui-redesign-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-04-20-storefront-ui-redesign.md`
**Branch:** cut from `main` as `vidhi/storefront-<slug>` per task. One PR per task.

---

## Overview

You own the layout shell (top bar + storefront shell) and the full PDP (layout, gallery keyboard nav, sanitized description, related scroller, PDP page). **All 8 tasks run in parallel** — they touch disjoint files. Ship in any order. Stub external imports when needed.

## Files you own (nobody else writes these)

- `frontend/src/app/storefront/vg/layout.tsx` — NEW
- `frontend/src/components/storefront/storefront-shell.tsx` — NEW (Task 5 stub, Task 9 real)
- `frontend/src/components/storefront/search-context.tsx` — NEW
- `frontend/src/components/storefront/top-bar.tsx` — NEW
- `frontend/src/components/storefront/pdp-layout.tsx` — NEW
- `frontend/src/components/storefront/description-html.tsx` — NEW
- `frontend/src/components/storefront/related-products.tsx` — NEW
- `frontend/src/components/storefront/image-gallery.tsx` — EDIT
- `frontend/src/app/storefront/vg/product/[product_id]/page.tsx` — REWRITE
- `frontend/src/app/globals.css` — EDIT (add `.prose-storefront` classes)
- `frontend/package.json` + `frontend/package-lock.json` — EDIT (add `isomorphic-dompurify`)

## Integration contracts (other people's files you import)

| Imported from | Component | Stub strategy if not yet shipped |
|---|---|---|
| Sinchana 8 | `<LeftRail categories={} counts={} />` | Stub that renders empty `<aside />` |
| Sinchana 10 | `<MobileFilterSheet categories={} counts={} />` | Stub that returns `null` |
| Sinchana 13 | Extended `ProductListItem` shape | Type-cast to `any` inside related-products if Sinchana hasn't extended `types.ts` yet |
| Urvashi 3 | `ProductRead.category_id: string \| null` | Cast `as Product & { category_id?: string }` (already in current code) |

If Sinchana hasn't shipped her components, add placeholder at the top of `storefront-shell.tsx`:
```ts
function LeftRail() { return null; }           // replaced by Sinchana 8
function MobileFilterSheet() { return null; }  // replaced by Sinchana 10
```
Remove the stubs when her PRs merge.

---

## Tasks

1. **Plan Task 5 — Storefront layout skeleton**
   - `app/storefront/vg/layout.tsx`: tiny shim `<StorefrontShell>{children}</StorefrontShell>`.
   - `storefront-shell.tsx`: bare container for now. Task 9 replaces it with real composition.
   - Acceptance: `/storefront/vg` returns 200 with the new shell wrapping whatever the page renders.

2. **Plan Task 7 — TopBar + SearchContext**
   - `search-context.tsx`: `SearchProvider` + `useSearch` hook returning `{ query, setQuery }`.
   - `top-bar.tsx`: sticky 60px, brand on left (VG mark + "Visual Graphics"), search center (uses `useSearch()`), `← Admin` link to `/` on right.

3. **Plan Task 9 — StorefrontShell real composition**
   - Replace Task 5 stub.
   - Loads `GET /api/suppliers` → VG → `/api/categories?supplier_id=<vg>` + `/api/products?limit=500` in parallel.
   - Tallies `category_id` counts client-side, passes to `<LeftRail counts={} />`.
   - Wraps tree in `<SearchProvider>`. Mounts `<TopBar>`, `<LeftRail>` (hidden on mobile), `<MobileFilterSheet>`.

4. **Plan Task 14 — PDPLayout wrapper**
   - Props: `breadcrumbCategory` (`{id,name} | null`), `breadcrumbProduct`, `gallery`, `info`, `description?`, `related?`.
   - Desktop grid: `grid-cols-[6fr_4fr] gap-10`. Info pane `lg:sticky lg:top-[80px] lg:self-start`.
   - Mobile: single column stacks gallery → info.

5. **Plan Task 15 — ImageGallery keyboard nav**
   - Add `useEffect` listener on `ArrowLeft`/`ArrowRight` to cycle hero.
   - Wrap hero in `<a href={active.url} target="_blank" rel="noopener noreferrer">` so click opens full-size in new tab.

6. **Plan Task 16 — DescriptionHtml**
   - `npm install isomorphic-dompurify`.
   - Sanitize whitelist: `p, br, strong, em, ul, ol, li, a, span, h1–h6`; attrs: `href, target, rel`.
   - Add `.prose-storefront` CSS rules at bottom of `globals.css` (plan has them verbatim).

7. **Plan Task 17 — RelatedProducts**
   - Props: `supplierId`, `categoryId`, `excludeId`.
   - Fetch 16 from `?category_id=...` (fallback `?supplier_id=...&limit=16`), filter out current, take 8.
   - Horizontal scroller with cards at 180px width. Label "Related products" (category scoped) or "Other VG products".

8. **Plan Task 18 — Rewrite PDP page**
   - Use `PDPLayout`, `ImageGallery`, `VariantPicker`, `PriceBlock`, `DescriptionHtml`, `RelatedProducts`.
   - Breadcrumb category via `product.category_id` → `GET /api/categories/{id}` (graceful 404).
   - CTAs: `← Back` (router.back), `Add to quote` disabled stub with tooltip.

---

## Rules

- Follow plan's code blocks verbatim for Tasks 7, 14, 15, 16, 17.
- Layout split fixed at `6fr_4fr` per spec.
- Always sanitize HTML through DOMPurify — never raw `dangerouslySetInnerHTML`.
- Blueprint tokens only.
- No Co-Authored-By lines in commits.
- One PR per task. PR title = `feat(storefront): <task name>`.

## Running locally

```bash
docker compose up -d postgres n8n
cd backend && source .venv/bin/activate && uvicorn main:app --port 8000 &
cd frontend && npm run dev &
# /storefront/vg → click card → PDP
```
