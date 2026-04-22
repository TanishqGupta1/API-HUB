# Task 17 — RelatedProducts Scroller

**Type:** Frontend
**Status:** Done
**Branch:** Vidhi

---

## What this task does

Adds a horizontal strip of 8 related products at the bottom of the Product
Detail Page (PDP). This helps shoppers discover similar products without
having to go back to the main grid.

The component is smart about what counts as "related":

- **If the current product has a `category_id`** → it fetches other products
  in the same category and labels the section **"Related products"**.
- **If there's no `category_id`** → it falls back to fetching other products
  from the same supplier and labels it **"Other VG products"**.
- Always filters out the current product so you don't see "related to itself".
- Requests 16 items, then shows up to 8 (the buffer guards against the current
  product landing in the first 16 results).

---

## Files created / modified

### `frontend/src/components/storefront/related-products.tsx` (NEW)

Client component with three props:
- `supplierId` — string — the current product's supplier ID
- `categoryId` — `string | null` — the current product's category ID (optional)
- `excludeId` — string — the current product ID (to filter itself out)

**Behavior:**
- `useEffect` fires on prop change → fetches from `/api/products`
- URL adapts: with/without `category_id` filter
- On error: silently resets to empty list (no broken UI)
- If list is empty: returns `null` (section doesn't render at all)

**Styling:**
- Small uppercase label on top: tracking-[0.1em], text-[#484852]
- `flex gap-4 overflow-x-auto pb-2 -mx-2 px-2` → horizontal scroller with
  bottom padding so the scrollbar doesn't clip cards
- Each card pinned to `w-[180px] shrink-0` so they don't squish
- Reuses `<StorefrontProductCard>` to match grid card styling

### `frontend/src/app/storefront/vg/product/[product_id]/page.tsx` (UPDATED)

- Added `import { RelatedProducts } from "@/components/storefront/related-products";`
- Passes `<RelatedProducts>` into the `related` slot of `<PDPLayout>`:
  - `supplierId={product.supplier_id}`
  - `categoryId={product.category_id ?? null}` (type-cast because `Product`
    doesn't yet declare `category_id` — Urvashi's task will add it)
  - `excludeId={product.id}`

The `related` slot in `PDPLayout` (Task 14) renders below the description
with a dashed top border separator.

---

## How to test

1. Open a product detail page, e.g.
   `http://localhost:3000/storefront/vg/product/<any-product-id>`
2. Scroll to the bottom — you should see a section titled
   **"OTHER VG PRODUCTS"** (uppercase, gray, small) with product cards
   in a horizontal row
3. The cards should:
   - Be 180px wide
   - Scroll horizontally if they overflow
   - Exclude the current product
   - Match the style of the grid cards
4. If fewer than 2 products exist in the DB (only one matches the filter
   after excluding current), the section doesn't render at all (graceful
   empty state)
5. When categories are populated (future), visiting a product with a
   category should show **"RELATED PRODUCTS"** instead of **"OTHER VG
   PRODUCTS"**, scoped to that category

---

## Integration contract

This component depends on:
- `GET /api/products?supplier_id=...&limit=16` — existing endpoint
- `GET /api/products?supplier_id=...&category_id=...&limit=16` — existing
  endpoint (returns empty list if `category_id` doesn't match any)
- `ProductListItem` type in `frontend/src/lib/types.ts`
- `StorefrontProductCard` component

No new backend work is needed.

---

## What comes next

**Task 18 — Rewrite PDP page**
- Final cleanup of the PDP page (breadcrumb category fetch, proper loading
  states, CTA wiring)
- Confirms all Vidhi storefront components are integrated end-to-end
