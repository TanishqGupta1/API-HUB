# Task 14 — PDPLayout Wrapper

**Type:** Frontend
**Status:** Done
**Branch:** Vidhi

---

## What this task does

Creates a reusable layout wrapper for the Product Detail Page (PDP). Before
this task, the PDP page had its own hardcoded breadcrumb and grid layout
inline. Now those are extracted into a dedicated component so the page just
passes content slots and the layout handles the structure.

---

## Files created / modified

### `frontend/src/components/storefront/pdp-layout.tsx` (NEW)
Layout wrapper with these props (content slots):
- `breadcrumbCategory` — `{ id, name } | null` — shows a clickable category crumb if present
- `breadcrumbProduct` — string — always shown (supplier SKU)
- `gallery` — ReactNode — left column (ImageGallery)
- `info` — ReactNode — right column (brand, title, price, variant picker, CTAs). Sticky on desktop.
- `description?` — ReactNode — optional, renders below the grid (DescriptionHtml)
- `related?` — ReactNode — optional, renders below description with a dashed divider (RelatedProducts, Task 17)

**Grid:** `grid-cols-[6fr_4fr]` on desktop (fixed per spec), single column on mobile.
**Info pane:** `lg:sticky lg:top-[80px] lg:self-start` — stays visible while you scroll the gallery.

### `frontend/src/app/storefront/vg/product/[product_id]/page.tsx` (UPDATED)
- Replaced inline breadcrumb + grid with `<PDPLayout>` component
- `gallery` slot → `<ImageGallery />`
- `info` slot → brand, title, SKU, PriceBlock, VariantPicker, CTAs
- `description` slot → `<DescriptionHtml />` (moved out of info panel, now below the grid)

---

## How to test

1. Open any product detail page (you need a product in DB — run seed or ingest first)
2. Or navigate to `http://localhost:3000/storefront/vg/product/<any-product-id>`
3. On **desktop (>1024px)**:
   - Left column (6 parts): product gallery
   - Right column (4 parts): title, price, variant picker, CTAs
   - Right column should stay sticky as you scroll
4. On **mobile (<1024px)**:
   - Single column: gallery stacks above info
5. Breadcrumb shows: `Visual Graphics / [Category] / SKU`
   - Category is clickable if `category_id` is present on the product

---

## What comes next

**Task 17 — RelatedProducts**
- Horizontal scroller showing 8 related products
- Passed into `PDPLayout` via the `related` prop
- Renders below the description with a dashed border separator
