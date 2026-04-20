# Storefront UI Redesign — Design Spec

**Date:** 2026-04-20
**Status:** Approved for planning
**Author:** Tanishq + pair

## Problem

`/storefront/vg` ships with two stacked sidebars:
- Main admin `SidebarNav` (api-hub app chrome)
- Category navigation rail

Result: cramped layout, unclear mode (admin vs storefront), Blueprint grid feels chopped. Categories sidebar works but stacked-sidebar pattern is visually weak and doesn't match real ecommerce UX.

## Goal

Storefront that looks and behaves like a real ecommerce catalog (Shopify / Amazon / BigCommerce pattern) while keeping the Blueprint visual language:
- One sidebar, not two
- Full-width product area
- Clear separation between admin mode and storefront mode
- Modern PDP with sticky variant picker + price
- Mobile: bottom-sheet filters

## Architecture — Next.js App Router split

Use route groups so admin routes keep their URLs but live under an admin layout:

```
app/
├── layout.tsx                    # slim: html, body, fonts, globals
├── (admin)/                      # route group — invisible in URL
│   ├── layout.tsx                # AdminSidebar + main area (current chrome)
│   ├── page.tsx                  # dashboard
│   ├── suppliers/...
│   ├── customers/...
│   ├── markup/...
│   ├── workflows/...
│   ├── sync/...
│   ├── mappings/...
│   ├── api-registry/...
│   └── products/...              # internal admin catalog
└── storefront/
    └── vg/
        ├── layout.tsx            # StorefrontShell: top bar + left rail
        ├── page.tsx              # product grid
        ├── product/[product_id]/page.tsx
        └── category/[category_id]/page.tsx
```

**Why route groups:**
- Parentheses segment (`(admin)`) is URL-invisible — `/suppliers` stays `/suppliers`.
- Admin layout and storefront layout are entirely independent trees — no conditional rendering.
- Root layout shrinks to fonts + providers + globals.css.

## Top bar

Sticky 60px bar inside storefront layout.

| Region | Content |
|---|---|
| Left (auto) | Mini `VG` brand mark (28px square, blueprint blue `#1e4d92`, white mono) + store name `Visual Graphics` |
| Center (flex-1, max 480px) | Search input (magnifier icon, debounced 200ms, client-side filter on product_name/sku/brand) |
| Right (auto) | `← Admin` text link to `/` |

Under bar (40px, not sticky): breadcrumb `Visual Graphics / <Category or Product>` + live result count.

Scroll: top bar stays pinned, breadcrumb scrolls away.

## Left rail (desktop)

260px wide, sticky below top bar, independent scroll, collapsible to 48px icon strip (persisted via `localStorage.vg-rail-collapsed`).

Row anatomy:
- Category name left, count right (mono `#888894`)
- Indent 14px per nesting level
- Hover: `bg-[#eef4fb]`, text `#1e4d92`
- Active route: blueprint blue fill, white text
- Row padding `10px 12px`, radius 6px

Data: existing `GET /api/categories?supplier_id=<vg>`. Per-category count injected via aggregate backend query (`category_id` grouped count, cache 60s).

Empty state: "No categories synced. Run OPS pull."

Mobile (< 768px): left rail replaced by floating Filter FAB → bottom sheet.

## Product grid + filter chips

### Filter chip bar (44px above grid)
```
[Vehicle Kits ×]  [In stock ×]      Sort: [Name ▼]   [Clear all]
```
- Removable chips: current category, in-stock toggle, price range (future), brand (future)
- Right: sort dropdown (Name A-Z, Name Z-A, Newest, Most variants) + Clear all link
- Clicking `×` on category chip routes to `/storefront/vg` (drops filter)

### Grid
- CSS Grid `grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-5`
- Card:
  - Image 220px, aspect-square, `#ebe8e3` bg
  - Product name bold, 15px
  - Brand · SKU (mono, muted)
  - **New price band:** `$12.95 – $19.50` from variant min/max
  - Footer row: product_type tag + variant count
  - Hover: translateY(-4px) + shadow `8px 12px 0 rgba(30,77,146,0.1)` + border blueprint blue
  - **Out-of-stock badge** top-right if `total_inventory == 0`

### Pagination
Initial load `limit=200`. Virtualization deferred until real need (>500 products).

### Empty state
"No matches. Try removing filters or [Clear all]."

## PDP (Product Detail Page)

Two-pane (60/40) at `≥ 1024px`, sticky info pane.

### Breadcrumb row (40px sticky under top bar)
Back arrow + `VG / Category / Current product`.

### Gallery (left 60%)
- Hero: aspect-square, object-contain
- Thumbnail strip: 70x70 swatches under hero
- Keyboard: ←/→ cycle hero
- Click hero: opens full-size in new tab (v1 stub; real lightbox later)

### Info (right 40%, sticky `top: 80px`)
- Brand (mono uppercase, blueprint blue)
- Title 28px extrabold
- SKU · product_type (mono, muted)
- Section divider (dashed)
- **Price block:** big mono price when variant picked, else min-max range
- Stock badge: green dot if >0, red if 0, warehouse name right
- Variant picker (reuse existing): color chips → size buttons, disables unavailable combos
- Primary CTA: `Add to quote` disabled stub w/ tooltip "Cart flow coming in future phase"
- Secondary: `← Back` using `router.back()`

### Description (full-width below panes)
- Renders `product.description` HTML sanitized via `isomorphic-dompurify`
- Prose wrapper with Blueprint typography

### Related products (horizontal scroller)
- Same `category_id`, limit 8, excluding current
- Reuses `StorefrontProductCard` at smaller width (180px)

## Mobile

| Range | Layout |
|---|---|
| `< 768px` | Compressed top bar (brand icon only, search collapses to icon), grid 2 cols, rail → bottom sheet |
| `768 - 1023px` | Rail auto-collapses to icon strip, grid 3 cols |
| `≥ 1024px` | Full desktop |

PDP mobile:
- Gallery full-width, info stacks below
- Thumbnails horizontal scroller
- Variant picker in accordion
- Sticky bottom CTA dock (price left, `Add to quote` right, 64px)

## Accessibility

- Keyboard-focusable nav, outline `2px solid #1e4d92`
- ARIA labels on nav / grid / filter regions
- Focus trap inside bottom sheet + future lightbox
- Color contrast ≥ 4.5:1 (Blueprint tokens already satisfy)

## Backend changes

| File | Change |
|---|---|
| `backend/modules/catalog/schemas.py` | `ProductListRead`: add `price_min: Decimal?`, `price_max: Decimal?`, `total_inventory: int?`; `ProductRead`: expose `category_id` |
| `backend/modules/catalog/routes.py` | Aggregate variant min/max/sum in `list_products` via subquery or joined load |

Existing `/api/categories` + `/api/products?category_id=X` filter (already shipped) reused.

## Frontend file inventory

### Moves (route-group migration)
`frontend/src/app/{page.tsx,suppliers,customers,markup,workflows,sync,mappings,api-registry,products}` → `frontend/src/app/(admin)/...`

### New
- `frontend/src/app/layout.tsx` — slim root
- `frontend/src/app/(admin)/layout.tsx` — admin shell
- `frontend/src/app/storefront/vg/layout.tsx` — StorefrontShell
- `frontend/src/components/storefront/storefront-shell.tsx`
- `frontend/src/components/storefront/top-bar.tsx`
- `frontend/src/components/storefront/left-rail.tsx`
- `frontend/src/components/storefront/filter-chip-bar.tsx`
- `frontend/src/components/storefront/pdp-layout.tsx`
- `frontend/src/components/storefront/description-html.tsx`
- `frontend/src/components/storefront/related-products.tsx`
- `frontend/src/components/storefront/mobile-filter-sheet.tsx`

### Edited
- `frontend/src/components/storefront/storefront-product-card.tsx` (price band + stock badge)
- `frontend/src/components/storefront/image-gallery.tsx` (keyboard nav)
- `frontend/src/app/storefront/vg/page.tsx`
- `frontend/src/app/storefront/vg/product/[product_id]/page.tsx`
- `frontend/src/app/storefront/vg/category/[category_id]/page.tsx`

### Removed
- `frontend/src/components/storefront/category-nav.tsx` — replaced by `left-rail.tsx`

### Deps added
- `isomorphic-dompurify` (HTML sanitizer for OPS `products_description`)

## Resolved open questions

1. **"Add to quote" CTA:** ship as disabled stub with tooltip; no functional cart yet.
2. **Related products:** category-scoped, exclude current, limit 8. Fallback to "Other VG products" if category empty.
3. **Lightbox:** v1 = click image opens full-size in new tab. Real lightbox modal is future work.

## Out of scope

- Cart / checkout / quote submission.
- User accounts on storefront.
- Multi-language.
- Pricing markup visualization per customer (reuses existing markup engine when quote flow lands).
- Real image lightbox modal.
- Infinite scroll / windowed virtualization (defer until >500 products).

## Success criteria

- Single sidebar visible on every storefront route.
- Admin routes unaffected (same URLs, same admin chrome).
- Mobile: one Filter FAB, bottom sheet with category tree.
- PDP gallery + info split renders at `≥ 1024px`, stacks at mobile.
- All OPS product HTML descriptions render safely.
- Lighthouse accessibility score ≥ 90 on `/storefront/vg` and PDP.
