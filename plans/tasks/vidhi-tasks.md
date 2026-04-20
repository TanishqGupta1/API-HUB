# Vidhi — Sprint Tasks

**Sprint:** Storefront UI redesign
**Spec:** `docs/superpowers/specs/2026-04-20-storefront-ui-redesign-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-04-20-storefront-ui-redesign.md`
**Load:** 8 tasks (heavy — shell, top bar, PDP)
**Branch:** cut from `main` as `vidhi/storefront-ui-<slug>` per task. One PR per task.

> Read the spec once before starting. It defines the two-pane PDP + sticky info + breadcrumb + description + related. The plan file has full code for each step — copy verbatim.

---

## Priority order

1. **Plan Task 5 — Storefront layout skeleton** (`frontend/src/app/storefront/vg/layout.tsx`)
   - Tiny shim that wraps children with `<StorefrontShell>`.
   - Paired stub `storefront-shell.tsx` — plain min-height container for now. (Replaced in Task 9.)
   - Acceptance: `/storefront/vg` returns 200 with new shell wrapping old page content.

2. **Plan Task 7 — TopBar + SearchContext**
   - `frontend/src/components/storefront/search-context.tsx`: SearchProvider + useSearch hook. Exposes `{ query, setQuery }`.
   - `frontend/src/components/storefront/top-bar.tsx`: sticky 60px, brand left, search center (debounced via context), `← Admin` link right.
   - Acceptance: typing in search updates context; TopBar re-renders only the input value.

3. **Plan Task 9 — StorefrontShell wires data + composes TopBar + LeftRail**
   - Replaces Task 5 stub.
   - Loads `GET /api/suppliers` → finds VG → loads `/api/categories?supplier_id=<vg>` + `/api/products?...&limit=500` in parallel.
   - Tallies `category_id` counts client-side, passes to `LeftRail` (Sinchana Task 8).
   - Wraps tree in `SearchProvider`. Mobile: hide LeftRail at `< 768px`, mount MobileFilterSheet (Sinchana Task 10).
   - Acceptance: shell renders top bar, left rail with counts, sheet FAB on mobile. No data fetches in children.

4. **Plan Task 14 — PDPLayout wrapper** (`frontend/src/components/storefront/pdp-layout.tsx`)
   - Props: `breadcrumbCategory` (`{id,name} | null`), `breadcrumbProduct`, `gallery`, `info`, `description?`, `related?`.
   - Desktop: `grid-cols-[6fr_4fr] gap-10`. Info pane: `lg:sticky lg:top-[80px] lg:self-start`.
   - Mobile: single column, info stacks below gallery.
   - Acceptance: layout snaps on/off sticky correctly; description + related sections only render if provided.

5. **Plan Task 15 — ImageGallery keyboard nav**
   - Extend `frontend/src/components/storefront/image-gallery.tsx`.
   - Add `useEffect` listener on `ArrowLeft`/`ArrowRight` to cycle hero.
   - Wrap hero `<img>` in `<a href={active.url} target="_blank">` for zoom-in-new-tab (lightbox stub).
   - Acceptance: key navigation works; clicking hero opens full-size image in new tab.

6. **Plan Task 16 — DescriptionHtml component** (`frontend/src/components/storefront/description-html.tsx`)
   - `npm install isomorphic-dompurify` in `frontend/`.
   - Sanitize whitelist: `p, br, strong, em, ul, ol, li, a, span, h1–h6`; attrs: `href, target, rel`.
   - Prose styles via `.prose-storefront` CSS class in `globals.css` (add minimal rules per plan).
   - Acceptance: OPS HTML descriptions render safely; raw `<script>` or `<iframe>` stripped.

7. **Plan Task 17 — RelatedProducts component** (`frontend/src/components/storefront/related-products.tsx`)
   - Props: `supplierId`, `categoryId`, `excludeId`.
   - Fetch 16 from `?category_id=...` (or fallback to all VG products), filter out current, take 8.
   - Horizontal scroller (`overflow-x-auto`), cards at 180px width.
   - Label: "Related products" if category scoped, else "Other VG products".
   - Acceptance: scroller renders 8 cards or fewer; current product never included.

8. **Plan Task 18 — Rewrite PDP page** (`frontend/src/app/storefront/vg/product/[product_id]/page.tsx`)
   - Use `PDPLayout`, `ImageGallery`, `VariantPicker`, `PriceBlock`, `DescriptionHtml`, `RelatedProducts`.
   - Breadcrumb category: resolved via `product.category_id` → `GET /api/categories/{id}` (graceful fallback to `null` on 404).
   - CTAs: `← Back` (router.back), `Add to quote` disabled stub with title tooltip.
   - Acceptance: PDP renders at `/storefront/vg/product/<id>` with two-pane, sticky info on scroll, related scroller at bottom.

---

## Rules

- Follow plan's code blocks verbatim for Tasks 7, 14, 15, 16, 17.
- Don't tweak layout proportions — `6fr_4fr` is fixed per spec.
- Sanitize description HTML — never raw `dangerouslySetInnerHTML` without DOMPurify.
- Blueprint tokens only. No new colors.
- No Co-Authored-By lines in commits.

## Dependencies

- Task 9 blocks on Sinchana Tasks 8 (LeftRail) + 10 (MobileFilterSheet).
- Task 18 blocks on Tasks 14, 15, 16, 17 + Urvashi Task 3 (ProductRead.category_id).
- Task 7 (TopBar) blocks Sinchana Tasks 11 + 19 (they use useSearch).

## How to test locally

```bash
docker compose up -d postgres n8n
cd backend && source .venv/bin/activate && uvicorn main:app --port 8000
cd frontend && npm run dev
# /storefront/vg loads grid; click any card → PDP
```
