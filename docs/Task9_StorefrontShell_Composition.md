# Task 9 — StorefrontShell Real Composition

**Type:** Frontend
**Status:** Done (shipped by Tanishq in PR #28, merged to Vidhi branch via main)
**Branch:** Vidhi

---

## What this task does

Replaces the Task 5 **stub** shell with a real, working storefront shell.

Before Task 9:
- The shell was a placeholder wrapper — just a background color, a TopBar,
  and `{children}`. No data loading. No sidebar. No mobile filter.
- `LeftRail` and `MobileFilterSheet` were stubbed as `function X() { return null; }`

After Task 9:
- Shell actually loads supplier/category/product data from the backend
- Computes category counts client-side (how many products in each category)
- Renders the LeftRail with live counts on desktop
- Renders the MobileFilterSheet (floating Filter button) on mobile
- Wraps the whole tree in SearchProvider so any child component can access
  filter state

---

## Problems this task solves

### Problem 1 — No data in the shell
Before, the shell was dumb. It didn't know about categories, products, or
anything dynamic. Each page (grid, PDP) had to fetch its own data.
Now the shell owns the shared state (supplier + categories + counts) and
pushes it down to both the TopBar dropdown and the LeftRail.

### Problem 2 — Disconnected components
Before, TopBar, LeftRail, SearchProvider, and MobileFilterSheet existed in
isolation. Nothing wired them together. The shell couldn't mount them
because their dependencies weren't satisfied (Sinchana T8 + T10 hadn't
shipped yet).
Now the shell integrates all four — one place that composes the storefront
chrome.

### Problem 3 — Mobile vs desktop filter experience
Desktop users get a persistent LeftRail on the side. Mobile users need a
collapsible filter panel triggered by a FAB (floating action button).
The shell now renders both:
- `<LeftRail>` inside `hidden md:block` — visible only on ≥768px
- `<MobileFilterSheet>` — its internal logic shows the FAB only on `<768px`

### Problem 4 — Duplicate API calls across pages
Before, every page (/storefront/vg grid, /storefront/vg/category/:id,
/storefront/vg/product/:id) would independently fetch categories to
populate its header/nav. Now the shell fetches once on mount and shares
the data via React context + prop drilling to the chrome components.

---

## Dependencies (all satisfied)

This task depended on 4 other tasks. By the time it was integrated, all
of them had shipped:

| Dependency | Owner | Provides | File |
|---|---|---|---|
| Task 5 | Vidhi | `layout.tsx` shim | `frontend/src/app/storefront/vg/layout.tsx` |
| Task 7 | Vidhi | `SearchProvider`, `TopBar` | `search-context.tsx`, `top-bar.tsx` |
| Task 8 | Sinchana | `LeftRail` component | `left-rail.tsx` |
| Task 10 | Sinchana | `MobileFilterSheet` component | `mobile-filter-sheet.tsx` |

---

## Files modified

### `frontend/src/components/storefront/storefront-shell.tsx` (REWRITE)

Replaces the stub from Task 5. Now has:
- `ShellData` interface: `{ categories, counts, loaded }`
- `ShellInner` component (child) — consumes `useSearch()` for breadcrumb
  segments, renders the chrome layout
- `StorefrontShell` component (parent) — owns data loading via useEffect:
  1. Fetches `/api/suppliers` → finds the `vg-ops` supplier
  2. In parallel via `Promise.all`:
     - `/api/categories?supplier_id=<vg>`
     - `/api/products?supplier_id=<vg>&limit=500`
  3. Tallies `category_id` counts from products
  4. Sets `{ categories, counts, loaded: true }`
- Wraps children in `<SearchProvider>` at the root

**Layout structure rendered:**
```
<div h-screen flex flex-col>
  <TopBar categories />
  <BreadcrumbBar segments />
  <div flex flex-1>
    <div hidden md:block>
      <LeftRail categories counts />
    </div>
    <main overflow-y-auto>
      {children}
    </main>
    <MobileFilterSheet categories counts />
  </div>
</div>
```

---

## How to test

1. Start the stack:
   ```bash
   docker compose up -d postgres
   cd backend && .\.venv\Scripts\Activate.ps1 && uvicorn main:app --port 8000
   cd frontend && npm run dev
   ```

2. Open `http://localhost:3000/storefront/vg`

3. **Desktop (>768px):**
   - Top bar at top (sticky, 60px): VG brand + search + category dropdown + Admin link
   - Breadcrumb bar below top bar
   - LeftRail on the left: vertical list of categories with counts
   - Main content area fills the rest

4. **Mobile (<768px):**
   - LeftRail is hidden
   - Floating "Filter" FAB at bottom-right
   - Tap FAB → opens bottom sheet with LeftRail inside
   - Tap overlay or X to close

5. **Empty state:** with demo seed (no products in `vg-ops` supplier):
   - LeftRail shows "No categories yet"
   - Main shows "No products yet — waiting on first OPS sync from n8n"

6. **Loading state:** briefly shows "Loading storefront…" before data arrives

---

## Integration contract

**Inputs:**
- `GET /api/suppliers` → finds supplier with `slug: "vg-ops"`
- `GET /api/categories?supplier_id=<vg.id>` → category list
- `GET /api/products?supplier_id=<vg.id>&limit=500` → products (used only
  for counting by category)

**Outputs (shell provides to children):**
- `<SearchProvider>` context (filters state + URL sync via Next.js router)
- Visual chrome: TopBar, BreadcrumbBar, LeftRail, MobileFilterSheet

**Consumers of the shell:**
- `app/storefront/vg/layout.tsx` wraps all `/storefront/vg/*` pages
- Grid page, category page, PDP page all receive the shell

---

## What comes next

Task 9 is the final piece of the storefront chrome sprint. With this done:
- Grid page (Sinchana Task 11) — wired to URL filters
- Category page — filters by category_id
- PDP (Vidhi Task 14-18) — wrapped by the shell but renders its own
  breadcrumb via PDPLayout

**Known cleanup** (flagged for review):
- Double breadcrumb on PDP: BreadcrumbBar (global shell) + PDPLayout's own
  breadcrumb. One should be removed — probably PDPLayout's, since the
  shell's BreadcrumbBar is now URL-driven and handles category breadcrumbs
  globally.
