# Task 18 — PDP Page Rewrite

**Type:** Frontend
**Status:** Done
**Branch:** Vidhi

---

## What this task does

Final cleanup pass on the Product Detail Page. Tasks 14–17 built all the
pieces (layout, gallery, description, related products). Task 18 stitches
them into the final, polished PDP that matches the design spec exactly.

This is NOT a new feature — it's the **integration and consistency pass**
that aligns the PDP with the design system.

---

## Changes from Task 14/17 version

### Loading skeleton — now matches PDP layout
Before: had a skeleton breadcrumb and `grid-cols-[1fr_1fr]` (50/50 split).
After: uses `grid-cols-1 lg:grid-cols-[6fr_4fr]` (matches final PDP ratio)
so the skeleton visually previews the real layout.

### Error state — Blueprint red tokens
Before: mixed red colors (`#e94b4b`, `#fef2f2`, `#b91c1c`).
After: unified Blueprint tokens (`#b93232` border + text, `#fdeded` bg).

### CTA button — cleaner label
Before: "Add to quote (coming soon)" with tooltip "Cart/checkout coming in
a future phase".
After: "Add to quote" with tooltip "Quote flow coming in future phase".
The button is still disabled — the "coming soon" is now communicated via
the native HTML `title` tooltip on hover, not cluttering the label.

### CTA row padding tightened
Before: `pt-4` (16px top padding).
After: `pt-2` (8px) — per spec, tighter vertical rhythm.

### Description always rendered via DescriptionHtml
Before: conditional render `product.description ? <DescriptionHtml /> : undefined`.
After: unconditional `<DescriptionHtml html={product.description} />`.
Reason: `DescriptionHtml` already returns `null` for empty HTML internally,
so the page doesn't need to duplicate that check. DRY.

### `info` extracted as local const
Before: info JSX was inline inside the `<PDPLayout>` call (~40 lines deep).
After: extracted as `const info = (...)` above the return. The return
reads much cleaner: just `info={info}`.

---

## Files modified

### `frontend/src/app/storefront/vg/product/[product_id]/page.tsx` (REWRITE)

All changes above applied. File is now ~130 lines (down from ~150) and
organized as:
1. Imports
2. State + useEffect for data loading
3. `selectedVariant` derived value
4. Early returns for loading + error
5. `info` JSX as a const
6. Final `<PDPLayout>` return

---

## How to test

1. Open any product PDP:
   - `http://localhost:3000/storefront/vg/product/d47ecf20-9a56-4b56-8759-9f1a147f77cc` (PC61, has related)
   - `http://localhost:3000/storefront/vg/product/6a5017a8-2788-4376-8124-a383f55be52a` (AA1070, no related)

2. Verify end-to-end integration of all Vidhi components:
   - TopBar (Task 7) at top — sticky, with search + admin link
   - Breadcrumb (Task 14) — `Visual Graphics / SKU`
   - ImageGallery (Task 15) — left column, keyboard arrows cycle images
   - Info pane (Task 14 grid) — right column, sticky on desktop scroll
     - Brand tag
     - Product title
     - SKU · type
     - PriceBlock
     - VariantPicker (colors + sizes)
     - ← Back + Add to quote buttons
   - DescriptionHtml (Task 16) — below grid, sanitized HTML
   - RelatedProducts (Task 17) — below description with dashed divider

3. Edge cases:
   - Invalid product ID → error panel with "← Back to catalog" link
   - Product with no description → description section doesn't render
   - Product with no related products (only product from that supplier) →
     related section doesn't render
   - Loading state → skeleton matches the real 6fr/4fr layout

4. Responsive:
   - Desktop (>1024px): two-column grid, sticky info pane
   - Mobile (<1024px): single column, everything stacks

---

## Vidhi Sprint — Complete

This closes out all 8 tasks in the Vidhi storefront UI redesign sprint:
- Task 5 — Storefront layout skeleton
- Task 7 — TopBar + SearchContext
- Task 14 — PDPLayout wrapper
- Task 15 — ImageGallery keyboard nav (shipped from branch)
- Task 16 — DescriptionHtml (shipped from branch)
- Task 17 — RelatedProducts scroller
- Task 18 — PDP page rewrite (this task)

Task 9 (StorefrontShell real composition) is still pending and depends on
Sinchana's LeftRail + MobileFilterSheet components.
