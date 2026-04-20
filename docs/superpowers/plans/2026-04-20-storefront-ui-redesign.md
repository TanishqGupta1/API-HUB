# Storefront UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **⚠ Commit policy (project rule):** User runs commits manually. Tasks end with a **"Stage"** step that lists exact `git add` paths + a suggested commit message. Do NOT run `git commit` automatically.

**Goal:** Rebuild `/storefront/vg` as a real ecommerce catalog (single sidebar, top bar, full-width grid, two-pane PDP, mobile bottom-sheet filter) while leaving admin pages (`/suppliers`, `/customers`, etc.) unchanged at their current URLs.

**Architecture:** Next.js App Router route groups split the layout tree into `(admin)` and `storefront/vg`. Admin group reuses existing `SidebarNav`; storefront group gets its own `StorefrontShell` (top bar + left rail). Backend gains three aggregate fields on `ProductListRead` (`price_min`, `price_max`, `total_inventory`) and exposes `category_id` on `ProductRead`.

**Tech Stack:** Next.js 15 App Router, Tailwind v4, shadcn primitives, FastAPI + async SQLAlchemy, PostgreSQL. New npm dep: `isomorphic-dompurify`.

---

## Phases

| Phase | Scope | Tasks |
|---|---|---|
| 1 | Backend additions (aggregates, `category_id` on PDP) | 1–3 |
| 2 | Route group migration — admin + storefront layouts | 4–6 |
| 3 | Storefront shell — top bar + left rail + mobile sheet | 7–10 |
| 4 | Product grid — filter chips + card upgrades | 11–13 |
| 5 | PDP rework — gallery, sticky info, description HTML, related | 14–18 |
| 6 | Final polish — a11y, small screens | 19–20 |

---

## Phase 1 — Backend

### Task 1: Add aggregate fields to `ProductListRead`

**Files:**
- Modify: `backend/modules/catalog/schemas.py`

- [ ] **Step 1: Add fields**

Replace the existing `ProductListRead` class with:

```python
class ProductListRead(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: Optional[str] = None
    supplier_sku: str
    product_name: str
    brand: Optional[str]
    category: Optional[str]
    category_id: Optional[UUID] = None
    product_type: str
    image_url: Optional[str]
    variant_count: int = 0
    price_min: Optional[Decimal] = None
    price_max: Optional[Decimal] = None
    total_inventory: Optional[int] = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Stage**

```bash
git add backend/modules/catalog/schemas.py
# Suggested commit: feat(catalog): expose price_min/max/total_inventory on ProductListRead
```

### Task 2: Compute aggregates in `list_products`

**Files:**
- Modify: `backend/modules/catalog/routes.py`

- [ ] **Step 1: Rewrite the aggregate section of `list_products`**

Replace the existing loop at the bottom of `list_products` with a single aggregate query that pulls variant stats for every product in one go:

```python
    out = []
    for p in products:
        # (leave existing supplier_name lookup unchanged)
        data = ProductListRead.model_validate(p)
        data.supplier_name = supplier_map.get(p.supplier_id)
        out.append(data)

    if out:
        product_ids = [p.id for p in products]
        agg_rows = (
            await db.execute(
                select(
                    ProductVariant.product_id,
                    func.count(ProductVariant.id).label("variant_count"),
                    func.min(ProductVariant.base_price).label("price_min"),
                    func.max(ProductVariant.base_price).label("price_max"),
                    func.coalesce(func.sum(ProductVariant.inventory), 0).label("total_inventory"),
                )
                .where(ProductVariant.product_id.in_(product_ids))
                .group_by(ProductVariant.product_id)
            )
        ).all()
        agg_map = {r.product_id: r for r in agg_rows}
        for d in out:
            row = agg_map.get(d.id)
            if row:
                d.variant_count = int(row.variant_count or 0)
                d.price_min = row.price_min
                d.price_max = row.price_max
                d.total_inventory = int(row.total_inventory or 0)

    return out
```

Remove the previous per-product `variant_count` count query (it's now folded into the aggregate).

- [ ] **Step 2: Smoke test the endpoint**

Run:
```bash
cd backend && source .venv/bin/activate
uvicorn main:app --port 8000 --log-level warning &
sleep 3
curl -s "http://localhost:8000/api/products?supplier_id=$(curl -s http://localhost:8000/api/suppliers | python3 -c 'import sys,json; print([s[\"id\"] for s in json.load(sys.stdin) if s[\"slug\"]==\"vg-ops\"][0])')&limit=5" | python3 -m json.tool | head -30
```

Expected: each product row includes `price_min`, `price_max`, `total_inventory` fields (may be null/0 if variants lack prices).

- [ ] **Step 3: Stage**

```bash
git add backend/modules/catalog/routes.py
# Suggested commit: perf(catalog): single aggregate query for list_products (price + inventory + count)
```

### Task 3: Expose `category_id` on `ProductRead`

**Files:**
- Modify: `backend/modules/catalog/schemas.py`

- [ ] **Step 1: Add field to `ProductRead`**

Insert inside the existing `ProductRead` class, after `category`:

```python
    category_id: Optional[UUID] = None
```

The SQLAlchemy `Product` model already has `category_id` — Pydantic `from_attributes` picks it up automatically.

- [ ] **Step 2: Smoke test PDP endpoint**

```bash
curl -s "http://localhost:8000/api/products/$(curl -s "http://localhost:8000/api/products?limit=1" | python3 -c 'import sys,json; print(json.load(sys.stdin)[0][\"id\"])')" | python3 -m json.tool | grep -E 'category|id' | head
```

Expected: response includes `"category_id": "<uuid or null>"`.

- [ ] **Step 3: Stage**

```bash
git add backend/modules/catalog/schemas.py
# Suggested commit: feat(catalog): expose category_id on ProductRead for PDP breadcrumb
```

---

## Phase 2 — Route group migration

### Task 4: Create `(admin)` route group + admin layout

**Files:**
- Create: `frontend/src/app/(admin)/layout.tsx`
- Move: 9 directories (below) into `(admin)/`

- [ ] **Step 1: Create admin layout**

Write `frontend/src/app/(admin)/layout.tsx`:

```tsx
import Sidebar from "@/components/Sidebar";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-[#f2f0ed] text-[#1e1e24]">
      <Sidebar />
      <main className="flex-1 px-8 py-8 ml-[260px]">
        {children}
      </main>
    </div>
  );
}
```

This mirrors whatever the current root layout was rendering. Open `frontend/src/app/layout.tsx` first — if the current layout already wraps `children` with `Sidebar`, copy that wrapper markup here verbatim.

- [ ] **Step 2: Move pages into the route group**

```bash
cd frontend/src/app
mkdir -p '(admin)'
# Move each directory; uses shell braces:
for d in page.tsx suppliers customers markup workflows sync mappings api-registry products; do
  git mv "$d" "(admin)/$d"
done
```

Verify in another terminal with `git status` — expect 9 renames.

- [ ] **Step 3: Slim root layout**

Open `frontend/src/app/layout.tsx` and strip it to:

```tsx
import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "API-HUB",
  description: "Universal supplier connector",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
```

Keep any existing `<link>` / `<script>` tags that were in the original.

- [ ] **Step 4: Smoke test admin routes**

```bash
cd frontend && npm run dev &
sleep 5
curl -sI http://localhost:3000/suppliers | head -1   # expect 200
curl -sI http://localhost:3000/workflows | head -1   # expect 200
curl -sI http://localhost:3000/ | head -1            # expect 200 (dashboard)
```

- [ ] **Step 5: Stage**

```bash
git add frontend/src/app
# Suggested commit: refactor(frontend): route group (admin) — admin pages move, admin layout extracted
```

### Task 5: Create storefront layout skeleton

**Files:**
- Create: `frontend/src/app/storefront/vg/layout.tsx`

- [ ] **Step 1: Minimal storefront layout**

```tsx
import { StorefrontShell } from "@/components/storefront/storefront-shell";

export default function StorefrontLayout({ children }: { children: React.ReactNode }) {
  return <StorefrontShell>{children}</StorefrontShell>;
}
```

- [ ] **Step 2: Temporary StorefrontShell stub (replaced in Task 7)**

Write `frontend/src/components/storefront/storefront-shell.tsx`:

```tsx
export function StorefrontShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#f2f0ed] text-[#1e1e24]">
      <main className="max-w-[1600px] mx-auto px-6 py-6">{children}</main>
    </div>
  );
}
```

Existing `/storefront/vg/page.tsx` and PDP/category pages already render their own shells — they'll be stripped in later tasks. Stub keeps them working for now.

- [ ] **Step 3: Smoke test**

```bash
curl -sI http://localhost:3000/storefront/vg | head -1   # expect 200
```

- [ ] **Step 4: Stage**

```bash
git add frontend/src/app/storefront/vg/layout.tsx frontend/src/components/storefront/storefront-shell.tsx
# Suggested commit: feat(storefront): layout skeleton + StorefrontShell stub
```

### Task 6: Strip old shells from existing storefront pages

**Files:**
- Modify: `frontend/src/app/storefront/vg/page.tsx`
- Modify: `frontend/src/app/storefront/vg/category/[category_id]/page.tsx`
- Modify: `frontend/src/app/storefront/vg/product/[product_id]/page.tsx`

Each page currently renders a full `<div>` shell with its own header. The new layout will own that. Strip each page to render **only** its main content (grid, PDP body, category grid). Wrap content in React fragment.

- [ ] **Step 1: `storefront/vg/page.tsx`** — remove outer wrapper + header, return just the search row + `<CategoryNav>` + grid. Left rail and top bar will come from layout later. Leave for now — it'll get torn down in Task 11.

- [ ] **Step 2: `storefront/vg/category/[category_id]/page.tsx`** — same treatment. Leave for now; Task 11 rewrites.

- [ ] **Step 3: `storefront/vg/product/[product_id]/page.tsx`** — leave; Task 14 rewrites.

- [ ] **Step 4: No stage yet** — these files change meaningfully in later tasks. Skip commit.

---

## Phase 3 — Storefront shell

### Task 7: TopBar component

**Files:**
- Create: `frontend/src/components/storefront/top-bar.tsx`
- Create: `frontend/src/components/storefront/search-context.tsx`

- [ ] **Step 1: Search context (lets TopBar search filter grid without prop drilling)**

`search-context.tsx`:

```tsx
"use client";
import { createContext, useContext, useState, type ReactNode } from "react";

interface SearchCtx {
  query: string;
  setQuery: (q: string) => void;
}

const Ctx = createContext<SearchCtx | null>(null);

export function SearchProvider({ children }: { children: ReactNode }) {
  const [query, setQuery] = useState("");
  return <Ctx.Provider value={{ query, setQuery }}>{children}</Ctx.Provider>;
}

export function useSearch() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSearch used outside SearchProvider");
  return ctx;
}
```

- [ ] **Step 2: TopBar**

`top-bar.tsx`:

```tsx
"use client";

import Link from "next/link";
import { useSearch } from "./search-context";

export function TopBar() {
  const { query, setQuery } = useSearch();

  return (
    <header className="sticky top-0 z-30 h-[60px] bg-white border-b border-[#cfccc8] flex items-center px-6 gap-6">
      <Link href="/storefront/vg" className="flex items-center gap-3 shrink-0">
        <span className="w-7 h-7 rounded-md bg-[#1e4d92] text-white font-mono text-[12px] font-bold flex items-center justify-center">
          VG
        </span>
        <span className="text-[15px] font-extrabold text-[#1e1e24] tracking-[-0.02em]">
          Visual Graphics
        </span>
      </Link>

      <div className="flex-1 max-w-[480px]">
        <div className="relative">
          <svg
            className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#b4b4bc] pointer-events-none"
            viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search products…"
            className="w-full pl-10 pr-4 py-2 bg-[#f9f7f4] border border-[#cfccc8] rounded-md
                       text-[13px] outline-none transition-all
                       focus:border-[#1e4d92] focus:bg-white focus:shadow-[0_0_0_3px_#eef4fb]"
          />
        </div>
      </div>

      <div className="ml-auto shrink-0">
        <Link
          href="/"
          className="text-[12px] font-semibold text-[#484852] hover:text-[#1e4d92]"
        >
          ← Admin
        </Link>
      </div>
    </header>
  );
}
```

- [ ] **Step 3: Stage**

```bash
git add frontend/src/components/storefront/top-bar.tsx frontend/src/components/storefront/search-context.tsx
# Suggested commit: feat(storefront): TopBar + SearchContext
```

### Task 8: LeftRail component

**Files:**
- Create: `frontend/src/components/storefront/left-rail.tsx`

- [ ] **Step 1: Rail**

```tsx
"use client";

import Link from "next/link";
import { useState } from "react";
import { usePathname } from "next/navigation";
import type { Category } from "@/lib/types";

interface RailProps {
  categories: Category[];
  counts: Record<string, number>;
}

interface Node extends Category {
  children: Node[];
}

function buildTree(cats: Category[]): Node[] {
  const byId = new Map<string, Node>();
  cats.forEach((c) => byId.set(c.id, { ...c, children: [] }));
  const roots: Node[] = [];
  byId.forEach((n) => {
    if (n.parent_id && byId.has(n.parent_id)) byId.get(n.parent_id)!.children.push(n);
    else roots.push(n);
  });
  const sortRec = (list: Node[]) => {
    list.sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name));
    list.forEach((n) => sortRec(n.children));
  };
  sortRec(roots);
  return roots;
}

function Row({ node, depth, counts }: { node: Node; depth: number; counts: Record<string, number> }) {
  const pathname = usePathname();
  const href = `/storefront/vg/category/${node.id}`;
  const active = pathname === href;
  const count = counts[node.id];
  return (
    <>
      <Link
        href={href}
        className={`flex items-center gap-2 rounded-md text-[12.5px] font-medium transition-colors
          ${active ? "bg-[#1e4d92] text-white" : "text-[#1e1e24] hover:bg-[#eef4fb] hover:text-[#1e4d92]"}`}
        style={{ paddingLeft: `${12 + depth * 14}px`, paddingRight: 12, paddingTop: 8, paddingBottom: 8 }}
      >
        <span className="flex-1 truncate">{node.name}</span>
        {typeof count === "number" && (
          <span className={`font-mono text-[10px] ${active ? "text-white/70" : "text-[#888894]"}`}>
            {count}
          </span>
        )}
      </Link>
      {node.children.map((c) => (
        <Row key={c.id} node={c} depth={depth + 1} counts={counts} />
      ))}
    </>
  );
}

export function LeftRail({ categories, counts }: RailProps) {
  const [collapsed, setCollapsed] = useState(
    typeof window !== "undefined" && localStorage.getItem("vg-rail-collapsed") === "1"
  );
  const tree = buildTree(categories);

  const toggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    if (typeof window !== "undefined") {
      localStorage.setItem("vg-rail-collapsed", next ? "1" : "0");
    }
  };

  if (collapsed) {
    return (
      <aside className="w-[48px] shrink-0 border-r border-[#cfccc8] bg-white flex flex-col items-center py-3">
        <button
          onClick={toggle}
          className="w-8 h-8 rounded-md border border-[#cfccc8] hover:bg-[#eef4fb] text-[#484852]"
          aria-label="Expand categories"
        >
          →
        </button>
      </aside>
    );
  }

  return (
    <aside className="w-[260px] shrink-0 border-r border-[#cfccc8] bg-white sticky top-[60px] self-start"
      style={{ maxHeight: "calc(100vh - 60px)" }}>
      <div className="flex items-center justify-between px-4 h-10 border-b border-[#cfccc8] bg-[#f9f7f4]">
        <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852]">Categories</span>
        <button onClick={toggle} className="text-[#484852] hover:text-[#1e4d92]" aria-label="Collapse categories">
          ←
        </button>
      </div>
      <nav className="overflow-y-auto p-2 flex flex-col gap-[2px]" style={{ maxHeight: "calc(100vh - 100px)" }}>
        <Link
          href="/storefront/vg"
          className="flex items-center gap-2 px-3 py-2 rounded-md text-[12.5px] font-medium
            text-[#1e1e24] hover:bg-[#eef4fb] hover:text-[#1e4d92]"
        >
          All products
        </Link>
        {tree.length === 0 ? (
          <div className="px-3 py-6 text-center text-[11px] text-[#888894]">
            No categories synced. Run OPS pull.
          </div>
        ) : (
          tree.map((n) => <Row key={n.id} node={n} depth={0} counts={counts} />)
        )}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 2: Stage**

```bash
git add frontend/src/components/storefront/left-rail.tsx
# Suggested commit: feat(storefront): LeftRail with collapsible tree + per-category counts
```

### Task 9: Wire StorefrontShell to load data + compose TopBar + LeftRail

**Files:**
- Modify: `frontend/src/components/storefront/storefront-shell.tsx`

- [ ] **Step 1: Replace stub**

```tsx
"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Category, ProductListItem, Supplier } from "@/lib/types";
import { SearchProvider } from "./search-context";
import { TopBar } from "./top-bar";
import { LeftRail } from "./left-rail";

const VG_SLUG = "vg-ops";

export function StorefrontShell({ children }: { children: React.ReactNode }) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const sups = await api<Supplier[]>("/api/suppliers");
        const vg = sups.find((s) => s.slug === VG_SLUG);
        if (!vg) return;

        const [cats, prods] = await Promise.all([
          api<Category[]>(`/api/categories?supplier_id=${vg.id}`),
          api<ProductListItem[]>(`/api/products?supplier_id=${vg.id}&limit=500`),
        ]);

        const tally: Record<string, number> = {};
        prods.forEach((p) => {
          if (p.category_id) tally[p.category_id] = (tally[p.category_id] ?? 0) + 1;
        });

        setCategories(cats);
        setCounts(tally);
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  return (
    <SearchProvider>
      <div className="min-h-screen bg-[#f2f0ed] text-[#1e1e24]">
        <TopBar />
        <div className="flex">
          <div className="hidden md:block">
            <LeftRail categories={categories} counts={counts} />
          </div>
          <main className="flex-1 min-w-0 px-6 py-5">
            {!loaded && (
              <div className="text-[11px] font-mono text-[#888894] mb-3">Loading storefront…</div>
            )}
            {children}
          </main>
        </div>
      </div>
    </SearchProvider>
  );
}
```

- [ ] **Step 2: Smoke test**

Open `http://localhost:3000/storefront/vg`. Expect: top bar with brand + search + Admin link; left rail with 95 categories + counts; main area unchanged for now (old grid renders below old header — will clean in Task 11).

- [ ] **Step 3: Stage**

```bash
git add frontend/src/components/storefront/storefront-shell.tsx
# Suggested commit: feat(storefront): shell composes TopBar + LeftRail + data loader
```

### Task 10: Mobile filter bottom sheet

**Files:**
- Create: `frontend/src/components/storefront/mobile-filter-sheet.tsx`
- Modify: `frontend/src/components/storefront/storefront-shell.tsx`

- [ ] **Step 1: Sheet component**

```tsx
"use client";

import { useEffect, useState } from "react";
import type { Category } from "@/lib/types";
import { LeftRail } from "./left-rail";

interface Props {
  categories: Category[];
  counts: Record<string, number>;
}

export function MobileFilterSheet({ categories, counts }: Props) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="md:hidden fixed bottom-5 right-5 z-40 h-14 px-5 rounded-full bg-[#1e4d92] text-white
                   text-[13px] font-semibold shadow-[4px_6px_0_rgba(30,77,146,0.2)]"
        aria-label="Open category filter"
      >
        Filter
      </button>
      {open && (
        <div
          className="md:hidden fixed inset-0 z-50 bg-black/40"
          onClick={() => setOpen(false)}
          role="dialog" aria-modal="true"
        >
          <div
            className="absolute inset-x-0 bottom-0 bg-white rounded-t-[16px] max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-4 h-12 border-b border-[#cfccc8]">
              <span className="text-[12px] font-bold uppercase tracking-[0.1em]">Filter</span>
              <button onClick={() => setOpen(false)} className="text-[#484852]" aria-label="Close">
                ✕
              </button>
            </div>
            <div className="overflow-y-auto flex-1">
              <LeftRail categories={categories} counts={counts} />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 2: Mount in shell**

In `storefront-shell.tsx`, under the main `<div className="flex">` block, add after the `<main>`:

```tsx
        <MobileFilterSheet categories={categories} counts={counts} />
```

And add the import:

```tsx
import { MobileFilterSheet } from "./mobile-filter-sheet";
```

- [ ] **Step 3: Stage**

```bash
git add frontend/src/components/storefront/mobile-filter-sheet.tsx frontend/src/components/storefront/storefront-shell.tsx
# Suggested commit: feat(storefront): mobile filter bottom sheet
```

---

## Phase 4 — Grid + filter chips

### Task 11: Rewrite `/storefront/vg/page.tsx`

**Files:**
- Rewrite: `frontend/src/app/storefront/vg/page.tsx`

- [ ] **Step 1: Page content only (shell owns chrome)**

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { ProductListItem, Supplier } from "@/lib/types";
import { StorefrontProductCard } from "@/components/storefront/storefront-product-card";
import { FilterChipBar } from "@/components/storefront/filter-chip-bar";
import { useSearch } from "@/components/storefront/search-context";

const VG_SLUG = "vg-ops";

export default function VGStorefrontPage() {
  const { query } = useSearch();
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [loading, setLoading] = useState(true);
  const [inStockOnly, setInStockOnly] = useState(false);
  const [sort, setSort] = useState<"name" | "nameDesc" | "variants">("name");

  useEffect(() => {
    (async () => {
      try {
        const sups = await api<Supplier[]>("/api/suppliers");
        const vg = sups.find((s) => s.slug === VG_SLUG) ?? null;
        setSupplier(vg);
        if (!vg) return;
        const prods = await api<ProductListItem[]>(`/api/products?supplier_id=${vg.id}&limit=500`);
        setProducts(prods);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const filtered = useMemo(() => {
    let out = products;
    if (query) {
      const q = query.toLowerCase();
      out = out.filter(
        (p) => p.product_name.toLowerCase().includes(q) ||
               p.supplier_sku.toLowerCase().includes(q) ||
               (p.brand ?? "").toLowerCase().includes(q),
      );
    }
    if (inStockOnly) {
      out = out.filter((p) => (p.total_inventory ?? 0) > 0);
    }
    out = [...out].sort((a, b) => {
      if (sort === "nameDesc") return b.product_name.localeCompare(a.product_name);
      if (sort === "variants") return (b.variant_count ?? 0) - (a.variant_count ?? 0);
      return a.product_name.localeCompare(b.product_name);
    });
    return out;
  }, [products, query, inStockOnly, sort]);

  return (
    <div className="flex flex-col gap-5 pb-12">
      <div>
        <div className="text-[13px] text-[#888894] font-mono">
          {supplier ? `${filtered.length} / ${products.length} products` : "…"}
        </div>
      </div>

      <FilterChipBar
        inStockOnly={inStockOnly}
        onInStockChange={setInStockOnly}
        sort={sort}
        onSortChange={setSort}
        query={query}
      />

      {loading ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-5">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-[340px] bg-[#f9f7f4] border border-[#ebe8e3] rounded-[10px] animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="border border-dashed border-[#cfccc8] rounded-[10px] p-16 text-center bg-white">
          <div className="text-[14px] font-bold text-[#1e1e24] mb-1">No matches</div>
          <div className="text-[12px] text-[#888894]">
            Try removing filters or clearing the search.
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-5">
          {filtered.map((p) => (
            <StorefrontProductCard key={p.id} product={p} />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Stage**

```bash
git add frontend/src/app/storefront/vg/page.tsx
# Suggested commit: refactor(storefront): page now pure grid; shell owns chrome
```

### Task 12: FilterChipBar

**Files:**
- Create: `frontend/src/components/storefront/filter-chip-bar.tsx`

- [ ] **Step 1: Component**

```tsx
"use client";

type Sort = "name" | "nameDesc" | "variants";

interface Props {
  inStockOnly: boolean;
  onInStockChange: (v: boolean) => void;
  sort: Sort;
  onSortChange: (v: Sort) => void;
  query: string;
}

export function FilterChipBar({ inStockOnly, onInStockChange, sort, onSortChange, query }: Props) {
  const hasFilters = inStockOnly || !!query;

  return (
    <div className="flex items-center flex-wrap gap-2 h-auto py-1">
      {query && (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#1e4d92] text-white text-[11px] font-semibold">
          query: {query}
        </span>
      )}
      <button
        type="button"
        onClick={() => onInStockChange(!inStockOnly)}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold transition-all
          ${inStockOnly
            ? "bg-[#1e4d92] text-white"
            : "bg-white border border-[#cfccc8] text-[#1e1e24] hover:border-[#1e4d92] hover:text-[#1e4d92]"
          }`}
      >
        In stock {inStockOnly && "×"}
      </button>

      <div className="ml-auto flex items-center gap-3">
        <label className="text-[11px] font-mono text-[#484852]">Sort</label>
        <select
          value={sort}
          onChange={(e) => onSortChange(e.target.value as Sort)}
          className="px-2 py-1 border border-[#cfccc8] rounded-md text-[12px] bg-white focus:border-[#1e4d92] outline-none"
        >
          <option value="name">Name A–Z</option>
          <option value="nameDesc">Name Z–A</option>
          <option value="variants">Most variants</option>
        </select>
        {hasFilters && (
          <button
            type="button"
            onClick={() => { onInStockChange(false); }}
            className="text-[11px] font-semibold text-[#888894] hover:text-[#1e4d92]"
          >
            Clear all
          </button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Stage**

```bash
git add frontend/src/components/storefront/filter-chip-bar.tsx
# Suggested commit: feat(storefront): FilterChipBar with in-stock + sort
```

### Task 13: StorefrontProductCard — price band + stock badge

**Files:**
- Rewrite: `frontend/src/components/storefront/storefront-product-card.tsx`

- [ ] **Step 1: Replace file**

```tsx
"use client";

import Link from "next/link";
import type { ProductListItem } from "@/lib/types";

interface Props {
  product: ProductListItem;
}

function fmtPriceBand(min: number | null, max: number | null): string | null {
  if (min === null || min === undefined) return null;
  if (max === null || max === undefined || max === min) return `$${Number(min).toFixed(2)}`;
  return `$${Number(min).toFixed(2)} – $${Number(max).toFixed(2)}`;
}

export function StorefrontProductCard({ product }: Props) {
  const band = fmtPriceBand(product.price_min ?? null, product.price_max ?? null);
  const oos = typeof product.total_inventory === "number" && product.total_inventory <= 0;

  return (
    <Link
      href={`/storefront/vg/product/${product.id}`}
      className="group bg-white border border-[#cfccc8] rounded-[10px] overflow-hidden
                 shadow-[4px_5px_0_rgba(30,77,146,0.08)]
                 transition-all duration-300
                 hover:-translate-y-1 hover:shadow-[8px_12px_0_rgba(30,77,146,0.1)]
                 hover:border-[#1e4d92]"
    >
      <div className="relative h-[220px] bg-[#ebe8e3] flex items-center justify-center border-b border-[#cfccc8]">
        {product.image_url ? (
          <img src={product.image_url} alt={product.product_name}
               className="w-full h-full object-contain p-4" />
        ) : (
          <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#b4b4bc]">No image</span>
        )}
        <div className="absolute top-3 left-3 px-[10px] py-[4px] bg-white border border-[#cfccc8] rounded
                        font-mono text-[10px] font-bold text-[#1e4d92]">VG</div>
        {oos && (
          <div className="absolute top-3 right-3 px-[8px] py-[3px] bg-[#fdeded] border border-[#b93232] rounded
                          font-mono text-[10px] font-bold text-[#b93232]">OUT</div>
        )}
      </div>

      <div className="p-5">
        <div className="text-[15px] font-extrabold leading-[1.3] mb-2 text-[#1e1e24] line-clamp-2 min-h-[40px]">
          {product.product_name}
        </div>
        <div className="flex items-center gap-2 text-[12px] text-[#888894] mb-2">
          {product.brand && (
            <>
              <span className="text-[#1e4d92] font-bold">{product.brand}</span>
              <span>·</span>
            </>
          )}
          <span className="font-mono truncate">{product.supplier_sku}</span>
        </div>
        {band && (
          <div className="font-mono text-[14px] font-semibold text-[#1e4d92]">{band}</div>
        )}
      </div>

      <div className="flex items-center justify-between px-5 py-3 bg-[#f9f7f4] border-t border-dashed border-[#cfccc8]">
        <span className="text-[10px] font-bold uppercase text-[#484852]">{product.product_type}</span>
        <span className="font-mono text-[12px] font-semibold text-[#1e4d92]">
          {product.variant_count} variant{product.variant_count === 1 ? "" : "s"}
        </span>
      </div>
    </Link>
  );
}
```

- [ ] **Step 2: Update `ProductListItem` type**

Open `frontend/src/lib/types.ts` and extend the interface:

```ts
export interface ProductListItem {
  id: string;
  supplier_id: string;
  supplier_name: string;
  supplier_sku: string;
  product_name: string;
  brand: string | null;
  category_id: string | null;
  product_type: string;
  image_url: string | null;
  variant_count: number;
  price_min: number | null;
  price_max: number | null;
  total_inventory: number | null;
}
```

- [ ] **Step 3: Smoke test**

Refresh `http://localhost:3000/storefront/vg`. Expect cards showing price band + OUT badge where applicable.

- [ ] **Step 4: Stage**

```bash
git add frontend/src/components/storefront/storefront-product-card.tsx frontend/src/lib/types.ts
# Suggested commit: feat(storefront): ProductCard price band + out-of-stock badge
```

---

## Phase 5 — PDP

### Task 14: PDPLayout wrapper

**Files:**
- Create: `frontend/src/components/storefront/pdp-layout.tsx`

- [ ] **Step 1: Component**

```tsx
"use client";

import Link from "next/link";
import type { ReactNode } from "react";

interface Props {
  breadcrumbCategory?: { id: string; name: string } | null;
  breadcrumbProduct: string;
  gallery: ReactNode;
  info: ReactNode;
  description?: ReactNode;
  related?: ReactNode;
}

export function PDPLayout({ breadcrumbCategory, breadcrumbProduct, gallery, info, description, related }: Props) {
  return (
    <div className="flex flex-col gap-6 pb-12">
      <div className="flex items-center gap-2 text-[12px] text-[#888894]">
        <Link href="/storefront/vg" className="hover:text-[#1e4d92] font-medium">Visual Graphics</Link>
        <span>/</span>
        {breadcrumbCategory ? (
          <>
            <Link href={`/storefront/vg/category/${breadcrumbCategory.id}`}
              className="hover:text-[#1e4d92] font-medium">{breadcrumbCategory.name}</Link>
            <span>/</span>
          </>
        ) : null}
        <span className="font-mono text-[#1e1e24]">{breadcrumbProduct}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[6fr_4fr] gap-10">
        <div>{gallery}</div>
        <div className="lg:sticky lg:top-[80px] lg:self-start">{info}</div>
      </div>

      {description && (
        <section className="pt-2">{description}</section>
      )}

      {related && (
        <section className="pt-6 border-t border-dashed border-[#cfccc8]">{related}</section>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Stage**

```bash
git add frontend/src/components/storefront/pdp-layout.tsx
# Suggested commit: feat(storefront): PDPLayout two-pane with sticky info
```

### Task 15: ImageGallery — keyboard nav

**Files:**
- Modify: `frontend/src/components/storefront/image-gallery.tsx`

- [ ] **Step 1: Add keyboard handler**

After the existing `useState` lines, add inside the component:

```tsx
useEffect(() => {
  if (list.length < 2) return;
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowRight") setActiveIdx((i) => (i + 1) % list.length);
    if (e.key === "ArrowLeft") setActiveIdx((i) => (i - 1 + list.length) % list.length);
  };
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}, [list.length]);
```

And add the import: `import { useState, useEffect } from "react";`.

Also wrap the main hero `<img>` so clicking it opens full-size in a new tab (v1 stub for lightbox):

Replace the main hero block with:

```tsx
<a href={active.url} target="_blank" rel="noopener noreferrer"
   className="aspect-square bg-[#ebe8e3] border border-[#cfccc8] rounded-[10px] overflow-hidden flex items-center justify-center cursor-zoom-in">
  <img src={active.url} alt={alt} className="w-full h-full object-contain p-6" />
</a>
```

- [ ] **Step 2: Stage**

```bash
git add frontend/src/components/storefront/image-gallery.tsx
# Suggested commit: feat(storefront): ImageGallery keyboard nav + zoom-in link
```

### Task 16: DescriptionHtml component

**Files:**
- Create: `frontend/src/components/storefront/description-html.tsx`
- Modify: `frontend/package.json`

- [ ] **Step 1: Install DOMPurify**

```bash
cd frontend && npm install isomorphic-dompurify
```

- [ ] **Step 2: Component**

```tsx
"use client";

import DOMPurify from "isomorphic-dompurify";

interface Props {
  html: string | null;
}

export function DescriptionHtml({ html }: Props) {
  if (!html) return null;
  const clean = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ["p", "br", "strong", "em", "ul", "ol", "li", "a", "span", "h1", "h2", "h3", "h4", "h5", "h6"],
    ALLOWED_ATTR: ["href", "target", "rel"],
  });

  return (
    <div>
      <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852] mb-3">Description</div>
      <div
        className="prose-storefront text-[14px] leading-[1.7] text-[#1e1e24]"
        dangerouslySetInnerHTML={{ __html: clean }}
      />
    </div>
  );
}
```

- [ ] **Step 3: Add prose styles to globals.css**

At the bottom of `frontend/src/app/globals.css`:

```css
.prose-storefront p { margin-bottom: 0.9em; }
.prose-storefront strong { font-weight: 700; color: #1e1e24; }
.prose-storefront a { color: #1e4d92; text-decoration: underline; }
.prose-storefront ul { padding-left: 1.25em; list-style: disc; margin-bottom: 0.9em; }
.prose-storefront ol { padding-left: 1.25em; list-style: decimal; margin-bottom: 0.9em; }
.prose-storefront li { margin-bottom: 0.3em; }
```

- [ ] **Step 4: Stage**

```bash
git add frontend/src/components/storefront/description-html.tsx frontend/package.json frontend/package-lock.json frontend/src/app/globals.css
# Suggested commit: feat(storefront): DescriptionHtml sanitized renderer + prose styles
```

### Task 17: RelatedProducts

**Files:**
- Create: `frontend/src/components/storefront/related-products.tsx`

- [ ] **Step 1: Component**

```tsx
"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ProductListItem } from "@/lib/types";
import { StorefrontProductCard } from "./storefront-product-card";

interface Props {
  supplierId: string;
  categoryId: string | null;
  excludeId: string;
}

export function RelatedProducts({ supplierId, categoryId, excludeId }: Props) {
  const [items, setItems] = useState<ProductListItem[]>([]);
  const [label, setLabel] = useState("Related products");

  useEffect(() => {
    (async () => {
      const url = categoryId
        ? `/api/products?supplier_id=${supplierId}&category_id=${categoryId}&limit=16`
        : `/api/products?supplier_id=${supplierId}&limit=16`;
      setLabel(categoryId ? "Related products" : "Other VG products");
      try {
        const list = await api<ProductListItem[]>(url);
        setItems(list.filter((p) => p.id !== excludeId).slice(0, 8));
      } catch {
        setItems([]);
      }
    })();
  }, [supplierId, categoryId, excludeId]);

  if (items.length === 0) return null;

  return (
    <div>
      <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852] mb-3">{label}</div>
      <div className="flex gap-4 overflow-x-auto pb-2 -mx-2 px-2">
        {items.map((p) => (
          <div key={p.id} className="shrink-0 w-[180px]">
            <StorefrontProductCard product={p} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Stage**

```bash
git add frontend/src/components/storefront/related-products.tsx
# Suggested commit: feat(storefront): RelatedProducts horizontal scroller
```

### Task 18: Rewrite PDP page to use PDPLayout

**Files:**
- Rewrite: `frontend/src/app/storefront/vg/product/[product_id]/page.tsx`

- [ ] **Step 1: Replace file**

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Category, Product } from "@/lib/types";
import { PDPLayout } from "@/components/storefront/pdp-layout";
import { ImageGallery } from "@/components/storefront/image-gallery";
import { VariantPicker } from "@/components/storefront/variant-picker";
import { PriceBlock } from "@/components/storefront/price-block";
import { DescriptionHtml } from "@/components/storefront/description-html";
import { RelatedProducts } from "@/components/storefront/related-products";

export default function VGProductDetailPage() {
  const params = useParams<{ product_id: string }>();
  const productId = params?.product_id;
  const router = useRouter();

  const [product, setProduct] = useState<Product | null>(null);
  const [category, setCategory] = useState<Category | null>(null);
  const [selectedVariantId, setSelectedVariantId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!productId) return;
    setLoading(true);
    setError(null);

    api<Product>(`/api/products/${productId}`)
      .then(async (p) => {
        setProduct(p);
        if (p.variants.length > 0) setSelectedVariantId(p.variants[0].id);
        const catId = (p as Product & { category_id?: string }).category_id;
        if (catId) {
          try {
            setCategory(await api<Category>(`/api/categories/${catId}`));
          } catch { /* ignore */ }
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [productId]);

  const selectedVariant = product?.variants.find((v) => v.id === selectedVariantId) ?? null;

  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-[6fr_4fr] gap-10">
        <div className="aspect-square bg-[#ebe8e3] rounded-[10px] animate-pulse" />
        <div className="flex flex-col gap-4">
          <div className="h-[40px] bg-[#ebe8e3] rounded animate-pulse" />
          <div className="h-[20px] w-[200px] bg-[#ebe8e3] rounded animate-pulse" />
          <div className="h-[80px] bg-[#ebe8e3] rounded animate-pulse mt-4" />
        </div>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="p-6 border border-[#b93232] rounded-[10px] bg-[#fdeded] text-[13px] text-[#b93232]">
        <div className="font-bold mb-1">Product not found</div>
        <div className="font-mono">{error ?? "Missing product"}</div>
        <Link href="/storefront/vg" className="inline-block mt-4 px-4 py-2 rounded-md border border-[#1e4d92] text-[#1e4d92] text-[13px] font-semibold hover:bg-[#eef4fb]">
          ← Back to catalog
        </Link>
      </div>
    );
  }

  const info = (
    <div className="flex flex-col gap-6">
      <div>
        {product.brand && (
          <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#1e4d92] mb-2">
            {product.brand}
          </div>
        )}
        <h1 className="text-[28px] font-extrabold tracking-[-0.03em] leading-tight text-[#1e1e24]">
          {product.product_name}
        </h1>
        <div className="font-mono text-[12px] text-[#888894] mt-2">
          {product.supplier_sku} · {product.product_type}
        </div>
      </div>

      <PriceBlock variant={selectedVariant} fallback={product.variants} />

      {product.variants.length > 0 && (
        <div className="py-5 border-t border-dashed border-[#cfccc8]">
          <VariantPicker
            variants={product.variants}
            selectedVariantId={selectedVariantId}
            onSelect={setSelectedVariantId}
          />
        </div>
      )}

      <div className="flex gap-3 pt-2">
        <button type="button" onClick={() => router.back()}
          className="px-5 py-3 rounded-md border border-[#cfccc8] text-[#1e1e24] text-[13px] font-semibold hover:border-[#1e4d92] hover:text-[#1e4d92]">
          ← Back
        </button>
        <button type="button" disabled
          className="flex-1 px-5 py-3 rounded-md bg-[#1e4d92] text-white text-[13px] font-semibold opacity-60 cursor-not-allowed"
          title="Quote flow coming in future phase">
          Add to quote
        </button>
      </div>
    </div>
  );

  return (
    <PDPLayout
      breadcrumbCategory={category ? { id: category.id, name: category.name } : null}
      breadcrumbProduct={product.supplier_sku}
      gallery={
        <ImageGallery images={product.images} fallbackUrl={product.image_url} alt={product.product_name} />
      }
      info={info}
      description={<DescriptionHtml html={product.description} />}
      related={
        <RelatedProducts
          supplierId={product.supplier_id}
          categoryId={(product as Product & { category_id?: string }).category_id ?? null}
          excludeId={product.id}
        />
      }
    />
  );
}
```

- [ ] **Step 2: Smoke test**

```bash
curl -sI "http://localhost:3000/storefront/vg/product/$(curl -s 'http://localhost:8000/api/products?limit=1' | python3 -c 'import sys,json;print(json.load(sys.stdin)[0][\"id\"])')" | head -1
```

Expect `200 OK`. Open in browser; confirm two-pane layout, sticky info on scroll, description renders sanitized HTML, related scroller at bottom.

- [ ] **Step 3: Stage**

```bash
git add frontend/src/app/storefront/vg/product/
# Suggested commit: feat(storefront): PDP rewrite using PDPLayout + related + description HTML
```

---

## Phase 6 — Category page + polish

### Task 19: Category page adopts chrome-less layout

**Files:**
- Rewrite: `frontend/src/app/storefront/vg/category/[category_id]/page.tsx`

- [ ] **Step 1: Replace file**

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Category, ProductListItem } from "@/lib/types";
import { StorefrontProductCard } from "@/components/storefront/storefront-product-card";
import { FilterChipBar } from "@/components/storefront/filter-chip-bar";
import { useSearch } from "@/components/storefront/search-context";

const VG_SLUG = "vg-ops";

export default function VGCategoryPage() {
  const params = useParams<{ category_id: string }>();
  const categoryId = params?.category_id;
  const { query } = useSearch();

  const [current, setCurrent] = useState<Category | null>(null);
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [inStockOnly, setInStockOnly] = useState(false);
  const [sort, setSort] = useState<"name" | "nameDesc" | "variants">("name");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!categoryId) return;
    setLoading(true);
    (async () => {
      try {
        const sups = await api<{ id: string; slug: string }[]>("/api/suppliers");
        const vg = sups.find((s) => s.slug === VG_SLUG);
        if (!vg) {
          setError("VG supplier not found");
          return;
        }
        const [cat, prods] = await Promise.all([
          api<Category>(`/api/categories/${categoryId}`),
          api<ProductListItem[]>(`/api/products?supplier_id=${vg.id}&category_id=${categoryId}&limit=500`),
        ]);
        setCurrent(cat);
        setProducts(prods);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    })();
  }, [categoryId]);

  const filtered = useMemo(() => {
    let out = products;
    if (query) {
      const q = query.toLowerCase();
      out = out.filter((p) => p.product_name.toLowerCase().includes(q));
    }
    if (inStockOnly) out = out.filter((p) => (p.total_inventory ?? 0) > 0);
    out = [...out].sort((a, b) => {
      if (sort === "nameDesc") return b.product_name.localeCompare(a.product_name);
      if (sort === "variants") return (b.variant_count ?? 0) - (a.variant_count ?? 0);
      return a.product_name.localeCompare(b.product_name);
    });
    return out;
  }, [products, query, inStockOnly, sort]);

  return (
    <div className="flex flex-col gap-5 pb-12">
      <div className="flex items-center gap-2 text-[12px] text-[#888894]">
        <Link href="/storefront/vg" className="hover:text-[#1e4d92] font-medium">Visual Graphics</Link>
        <span>/</span>
        <span className="font-mono text-[#1e1e24]">{current?.name ?? "Category"}</span>
      </div>

      <div>
        <div className="text-[24px] font-extrabold tracking-[-0.03em] leading-tight text-[#1e1e24]">
          {current?.name ?? "Category"}
        </div>
        <div className="text-[13px] text-[#888894] mt-1 font-mono">{filtered.length} products</div>
      </div>

      {error && (
        <div className="p-4 border border-[#b93232] rounded-[10px] bg-[#fdeded] text-[13px] text-[#b93232]">
          <div className="font-bold">Error</div>
          <div className="font-mono">{error}</div>
        </div>
      )}

      <FilterChipBar
        inStockOnly={inStockOnly} onInStockChange={setInStockOnly}
        sort={sort} onSortChange={setSort} query={query}
      />

      {loading ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-[340px] bg-[#f9f7f4] border border-[#ebe8e3] rounded-[10px] animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="border border-dashed border-[#cfccc8] rounded-[10px] p-16 text-center bg-white">
          <div className="text-[14px] font-bold text-[#1e1e24] mb-1">No products here</div>
          <div className="text-[12px] text-[#888894]">
            Nothing mapped to {current?.name ?? "this category"} or its sub-categories.
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-5">
          {filtered.map((p) => <StorefrontProductCard key={p.id} product={p} />)}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Stage**

```bash
git add frontend/src/app/storefront/vg/category/
# Suggested commit: refactor(storefront): category page uses shell chrome + FilterChipBar
```

### Task 20: Remove dead code + verify Lighthouse

**Files:**
- Delete: `frontend/src/components/storefront/category-nav.tsx`

- [ ] **Step 1: Remove old CategoryNav**

```bash
git rm frontend/src/components/storefront/category-nav.tsx
# if any page still imports it, grep + remove
grep -rn "category-nav" frontend/src || true
```

- [ ] **Step 2: Lighthouse accessibility check**

Open DevTools → Lighthouse → run Accessibility audit on:
- `http://localhost:3000/storefront/vg`
- `http://localhost:3000/storefront/vg/product/<any_id>`

Expected: score ≥ 90. If lower, fix whatever is flagged (likely missing alt attrs or color contrast on a badge).

- [ ] **Step 3: Stage**

```bash
git add frontend/src/components/storefront/
# Suggested commit: chore(storefront): remove dead CategoryNav
```

---

## Verification (end-to-end)

After all 20 tasks, run:

```bash
# Backend
curl -s "http://localhost:8000/api/products?supplier_id=<vg_sid>&limit=3" | python3 -m json.tool | grep -E 'price_|total_inventory'
# Expect price_min/max/total_inventory on each row

# Frontend routes
for path in / /suppliers /customers /markup /workflows /sync /mappings /api-registry /products \
            /storefront/vg "/storefront/vg/product/<any_id>" "/storefront/vg/category/<any_cat>"; do
  curl -sI "http://localhost:3000$path" | head -1 | sed "s|^|$path |"
done
# All should report 200 OK.
```

Visual checks:
- `/storefront/vg` renders with top bar + left rail + grid + filter chip bar. No admin sidebar visible.
- Click category → URL changes, grid filters, chip bar shows current filters.
- Search in top bar → grid filters live.
- Click product → PDP two-pane, sticky info, description HTML rendered, related scroller at bottom.
- Resize to < 768px → Filter FAB appears bottom-right, bottom sheet slides up on tap.
- Click `← Admin` in top bar → back to admin dashboard; sidebar restored.
