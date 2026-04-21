# Storefront Chrome + Navigation Redesign — Design Spec

**Date:** 2026-04-21
**Scope:** `/storefront/vg` admin catalog tool
**Context:** Storefront UI redesign shipped (Phases 1-6), but the result is too dense and hard to navigate. Internal admin users need less chrome, sticky/scroll-aware layout, URL-driven state, and proper back navigation. Speed/pagination is out of scope for this pass.

---

## Problem

Current `/storefront/vg` pain points (ranked by user):
1. **No back / breadcrumb** — stuck on a page with no clear exit or trail
2. **Chrome too dense** — LeftRail (expanded tree) + TopBar + FilterChipBar all visible at once

Also flagged but deprioritized for later spec: grid truncation, initial-load speed, "show all products".

---

## Users

Internal admin team previewing supplier catalog before pushing products to customer storefronts. Not end consumers. Density is OK once chrome is sensible.

---

## Approach

Hybrid chrome + nav refresh. Touch shell layout, LeftRail, TopBar, breadcrumb, URL state. Leave grid / card internals alone.

**Rejected:**
- Full rework (includes grid/card) — scope creep.
- Chrome-only without URL state — back/breadcrumb cannot work reliably without URL as source of truth.

---

## Layout

Sticky zones, independent scroll:

- **TopBar** `sticky top-0 z-30` (56px): logo, search input, category dropdown (searchable Select with flat list), Admin-back link
- **BreadcrumbBar** `sticky top-[56px] z-20` (36px): breadcrumb `Catalog › <parent?> › <current>` + `←` back chevron
- **LeftRail** `sticky top-[92px]`: collapsed 60px icon-only rail by default; expands to 240px overlay (`position: absolute z-40`) on hover or click, dismiss on outside-click
- **Main grid** `overflow-y-auto` in its own column — scrolls independently from sticky chrome
- **FilterButton** floats top-right of main area; opens popover panel (280px) with in-stock toggle + sort radio group

Total chrome height above grid: 92px.

---

## URL state

Query params own state. Router push is shallow (no refetch; data is client-side).

- `?category=<uuid>` — active category (drives breadcrumb + grid filter)
- `?q=<text>` — search query (promoted from in-memory SearchContext)
- `?stock=in` — in-stock filter (absent means off)
- `?sort=name|price_asc|price_desc|newest` — sort key (absent means default `name`)

Browser back / forward works natively. URLs are shareable.

---

## LeftRail behavior

- Default: 60px icon-only column. Shows first-level category icons (~6-10 max, truncated if longer — user can expand for more).
- **Hover** or click chevron → expand to 240px overlay with full tree.
- **Outside click or blur** → collapse back.
- TopBar category dropdown is the fast path for "I know the category name" users; rail is the browse path.

---

## FilterButton + chips

- **Button** top-right of grid area: text `Filter` with numeric badge when any non-default filter is active.
- **Popover** on click: in-stock toggle + sort radio.
- **Active-filter chips** row appears above grid ONLY when at least one non-default filter is set. Each chip has an `×` to clear that filter.
- No chips visible in default state.

---

## PDP + Category page

Both reuse TopBar + BreadcrumbBar.

- **PDP:** breadcrumb ends with product name (`Catalog › Shirts › Heavy Tee`). Back chevron returns to parent category URL or `/storefront/vg` if none.
- **Category:** same shell; grid filtered by `?category=<uuid>`.

LeftRail available on both.

---

## Components affected

| Component | Change |
|-----------|--------|
| `storefront-shell.tsx` | Layout grid: sticky TopBar, BreadcrumbBar, independent-scroll main. Rail collapsed by default. |
| `top-bar.tsx` | Add category Select dropdown. Keep search + admin-back link. |
| `left-rail.tsx` | Collapsed-by-default 60px; expand on hover/click to 240px overlay. |
| `filter-chip-bar.tsx` | Split: `filter-button.tsx` (popover) + `active-filter-chips.tsx` (only render when filters active). Retire old always-visible bar. |
| `breadcrumb-bar.tsx` (new) | Sticky bar under TopBar, derives segments from URL + category tree. |
| `search-context.tsx` | Sync state with URL `?q=` + `?category=` + `?stock=` + `?sort=`. |
| `/storefront/vg/page.tsx` | Consume URL-derived state via SearchContext. |
| `/storefront/vg/category/[category_id]/page.tsx` | Same — breadcrumb auto-populates from URL. |
| `/storefront/vg/product/[product_id]/page.tsx` | PDPLayout receives breadcrumb segments via shell. |

---

## Error handling

- Unknown `?category=<uuid>` → empty grid + breadcrumb falls back to `Catalog › Unknown category`, with a banner offering reset-to-all.
- Router push failures (deep-history corner cases) are silent; reload resolves.

---

## Testing

- **Unit:** BreadcrumbBar derives correct segments from a mock category tree.
- **Integration (Playwright, later):** click category in rail → URL updates → grid filters → back button returns previous URL.
- **Smoke:** dev server, click through rail + breadcrumb + dropdown, ensure sticky positions hold and scroll area is only main grid.

---

## Out of scope (explicit)

- Grid card redesign
- Pagination / infinite scroll
- Product-fetch strategy (still 500-limit via shell load)
- Mobile bottom-sheet filter (unchanged)
- n8n / backend changes

Revisit after chrome ships.
