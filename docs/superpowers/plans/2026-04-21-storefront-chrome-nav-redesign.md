# Storefront Chrome + Navigation Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **⚠ Commit policy (project rule):** User typically commits manually per existing plans, but at the end of this session the user may ask "commit" directly — honor that. Never add `Co-Authored-By` lines.

**Goal:** Reduce chrome density and add URL-driven back/breadcrumb navigation to `/storefront/vg` without touching grid/card internals.

**Architecture:** Sticky TopBar + BreadcrumbBar, slim-by-default LeftRail (60px, expands on hover/click), Filter popover with lazy chips, URL query params (`?category`/`?q`/`?stock`/`?sort`) as source of truth, independent main-grid scroll. Shell remains the data loader.

**Tech Stack:** Next.js 15 App Router client components, `next/navigation` (`useSearchParams`, `useRouter`, `usePathname`), Tailwind v3, React 19.

**Spec:** `docs/superpowers/specs/2026-04-21-storefront-chrome-nav-redesign-design.md`

---

## File Structure

**Create:**
- `frontend/src/components/storefront/breadcrumb-bar.tsx` — sticky breadcrumb + back chevron
- `frontend/src/components/storefront/filter-button.tsx` — icon button + popover (in-stock + sort)
- `frontend/src/components/storefront/active-filter-chips.tsx` — chips row (only renders when filters are active)
- `frontend/src/lib/storefront-url.ts` — query-param reader/writer helpers

**Modify:**
- `frontend/src/components/storefront/search-context.tsx` — sync state w/ URL (q, category, stock, sort)
- `frontend/src/components/storefront/storefront-shell.tsx` — sticky layout, independent main scroll, mount BreadcrumbBar
- `frontend/src/components/storefront/top-bar.tsx` — add category Select dropdown
- `frontend/src/components/storefront/left-rail.tsx` — collapsed 60px icon rail with hover/click expand overlay
- `frontend/src/app/storefront/vg/page.tsx` — consume URL-derived state (drop local useState for chips)
- `frontend/src/app/storefront/vg/category/[category_id]/page.tsx` — derive category from route; breadcrumb auto
- `frontend/src/app/storefront/vg/product/[product_id]/page.tsx` — breadcrumb segment for product name

**Retire:**
- `frontend/src/components/storefront/filter-chip-bar.tsx` — replaced by filter-button + active-filter-chips. Delete once no consumers.

---

# Phase 1 — URL state foundation

### Task 1: URL helpers

**Files:**
- Create: `frontend/src/lib/storefront-url.ts`

- [ ] **Step 1: Create file**

```ts
export type SortKey = "name" | "price_asc" | "price_desc" | "newest";
export type StockFilter = "in" | null;

export interface StorefrontFilters {
  category: string | null;
  q: string;
  stock: StockFilter;
  sort: SortKey;
}

export function readFilters(sp: URLSearchParams): StorefrontFilters {
  const rawSort = sp.get("sort");
  const sort: SortKey =
    rawSort === "price_asc" || rawSort === "price_desc" || rawSort === "newest"
      ? rawSort
      : "name";
  return {
    category: sp.get("category"),
    q: sp.get("q") ?? "",
    stock: sp.get("stock") === "in" ? "in" : null,
    sort,
  };
}

export function writeFilters(base: URLSearchParams, next: Partial<StorefrontFilters>): URLSearchParams {
  const out = new URLSearchParams(base.toString());
  if ("category" in next) next.category ? out.set("category", next.category) : out.delete("category");
  if ("q" in next) next.q ? out.set("q", next.q) : out.delete("q");
  if ("stock" in next) next.stock === "in" ? out.set("stock", "in") : out.delete("stock");
  if ("sort" in next) next.sort && next.sort !== "name" ? out.set("sort", next.sort) : out.delete("sort");
  return out;
}

export function countActive(f: StorefrontFilters): number {
  let n = 0;
  if (f.stock === "in") n++;
  if (f.sort !== "name") n++;
  return n;
}
```

- [ ] **Step 2: TSC**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 3: Stage**

```bash
git add frontend/src/lib/storefront-url.ts
# feat(storefront): URL filter helpers
```

---

### Task 2: SearchContext adopts URL as source of truth

**Files:**
- Modify: `frontend/src/components/storefront/search-context.tsx`

- [ ] **Step 1: Replace file body**

```tsx
"use client";
import { createContext, useContext, useCallback, useMemo, type ReactNode } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { readFilters, writeFilters, type StorefrontFilters } from "@/lib/storefront-url";

interface SearchCtx {
  filters: StorefrontFilters;
  setFilter: <K extends keyof StorefrontFilters>(key: K, value: StorefrontFilters[K]) => void;
  clearAll: () => void;
  // legacy alias so old callers keep compiling
  query: string;
  setQuery: (q: string) => void;
}

const Ctx = createContext<SearchCtx | null>(null);

export function SearchProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const filters = useMemo(() => readFilters(sp), [sp]);

  const push = useCallback(
    (next: Partial<StorefrontFilters>) => {
      const params = writeFilters(sp, next);
      const qs = params.toString();
      router.push(qs ? `${pathname}?${qs}` : pathname);
    },
    [router, pathname, sp]
  );

  const setFilter: SearchCtx["setFilter"] = useCallback(
    (key, value) => push({ [key]: value } as Partial<StorefrontFilters>),
    [push]
  );

  const clearAll = useCallback(() => router.push(pathname), [router, pathname]);

  return (
    <Ctx.Provider
      value={{
        filters,
        setFilter,
        clearAll,
        query: filters.q,
        setQuery: (q: string) => push({ q }),
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useSearch() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSearch used outside SearchProvider");
  return ctx;
}
```

- [ ] **Step 2: TSC**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean. Legacy callers using `query` / `setQuery` keep working.

- [ ] **Step 3: Smoke**

Run: `curl -sI http://localhost:3000/storefront/vg | head -1`
Expected: `HTTP/1.1 200 OK`.

- [ ] **Step 4: Stage**

```bash
git add frontend/src/components/storefront/search-context.tsx
# feat(storefront): URL-backed SearchContext
```

---

# Phase 2 — Chrome components

### Task 3: BreadcrumbBar

**Files:**
- Create: `frontend/src/components/storefront/breadcrumb-bar.tsx`

- [ ] **Step 1: Create file**

```tsx
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Category } from "@/lib/types";

export interface BreadcrumbSegment {
  label: string;
  href?: string;
}

export function BreadcrumbBar({
  segments,
}: {
  segments: BreadcrumbSegment[];
}) {
  const router = useRouter();
  return (
    <div
      className="sticky top-[60px] z-20 h-[36px] bg-white border-b border-[#e9e7e3]
                 flex items-center px-6 gap-2 text-[12px] font-medium text-[#484852]"
    >
      <button
        aria-label="Back"
        onClick={() => router.back()}
        className="flex items-center justify-center w-6 h-6 rounded-md
                   text-[#888894] hover:bg-[#f2f0ed] hover:text-[#1e4d92]"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </button>
      <ol className="flex items-center gap-1.5">
        {segments.map((seg, i) => {
          const last = i === segments.length - 1;
          return (
            <li key={i} className="flex items-center gap-1.5">
              {i > 0 && <span className="text-[#cfccc8]">›</span>}
              {seg.href && !last ? (
                <Link href={seg.href} className="hover:text-[#1e4d92]">
                  {seg.label}
                </Link>
              ) : (
                <span className={last ? "text-[#1e1e24] font-semibold" : ""}>{seg.label}</span>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function deriveSegments(
  categories: Category[],
  activeCategoryId: string | null,
  trailing?: BreadcrumbSegment,
): BreadcrumbSegment[] {
  const root: BreadcrumbSegment = { label: "Catalog", href: "/storefront/vg" };
  if (!activeCategoryId) return trailing ? [root, trailing] : [root];

  const byId = new Map(categories.map((c) => [c.id, c]));
  const chain: Category[] = [];
  let cur = byId.get(activeCategoryId);
  while (cur) {
    chain.unshift(cur);
    cur = cur.parent_id ? byId.get(cur.parent_id) : undefined;
  }

  const segs: BreadcrumbSegment[] = [
    root,
    ...chain.map((c) => ({
      label: c.name,
      href: `/storefront/vg?category=${c.id}`,
    })),
  ];
  return trailing ? [...segs, trailing] : segs;
}
```

- [ ] **Step 2: TSC**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 3: Stage**

```bash
git add frontend/src/components/storefront/breadcrumb-bar.tsx
# feat(storefront): BreadcrumbBar with back chevron
```

---

### Task 4: FilterButton + ActiveFilterChips

**Files:**
- Create: `frontend/src/components/storefront/filter-button.tsx`
- Create: `frontend/src/components/storefront/active-filter-chips.tsx`

- [ ] **Step 1: Create `active-filter-chips.tsx`**

```tsx
"use client";

import { useSearch } from "./search-context";
import { countActive, type SortKey } from "@/lib/storefront-url";

const SORT_LABEL: Record<SortKey, string> = {
  name: "Name",
  price_asc: "Price ↑",
  price_desc: "Price ↓",
  newest: "Newest",
};

export function ActiveFilterChips() {
  const { filters, setFilter, clearAll } = useSearch();
  if (countActive(filters) === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 mb-3 text-[11px]">
      {filters.stock === "in" && (
        <Chip label="In stock" onClear={() => setFilter("stock", null)} />
      )}
      {filters.sort !== "name" && (
        <Chip label={`Sort: ${SORT_LABEL[filters.sort]}`} onClear={() => setFilter("sort", "name")} />
      )}
      <button
        onClick={clearAll}
        className="text-[#888894] hover:text-[#1e4d92] font-medium underline underline-offset-2"
      >
        Clear all
      </button>
    </div>
  );
}

function Chip({ label, onClear }: { label: string; onClear: () => void }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-[#eef4fb] text-[#1e4d92] font-semibold">
      {label}
      <button
        aria-label={`Clear ${label}`}
        onClick={onClear}
        className="w-3 h-3 rounded-full text-[#1e4d92] hover:bg-[#d5e2f0] flex items-center justify-center"
      >
        ×
      </button>
    </span>
  );
}
```

- [ ] **Step 2: Create `filter-button.tsx`**

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { useSearch } from "./search-context";
import { countActive, type SortKey } from "@/lib/storefront-url";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "name", label: "Name (A→Z)" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "newest", label: "Newest" },
];

export function FilterButton() {
  const { filters, setFilter } = useSearch();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const active = countActive(filters);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div ref={ref} className="relative inline-block">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md border border-[#cfccc8]
                   bg-white text-[12px] font-semibold text-[#1e1e24] hover:border-[#1e4d92]"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
          <line x1="4" y1="6" x2="20" y2="6" />
          <line x1="7" y1="12" x2="17" y2="12" />
          <line x1="10" y1="18" x2="14" y2="18" />
        </svg>
        Filter
        {active > 0 && (
          <span className="ml-1 w-5 h-5 rounded-full bg-[#1e4d92] text-white text-[10px] font-bold flex items-center justify-center">
            {active}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-[280px] z-40 bg-white border border-[#cfccc8] rounded-md shadow-lg p-4">
          <label className="flex items-center gap-2 text-[12px] font-medium text-[#1e1e24] cursor-pointer">
            <input
              type="checkbox"
              checked={filters.stock === "in"}
              onChange={(e) => setFilter("stock", e.target.checked ? "in" : null)}
              className="w-3.5 h-3.5 accent-[#1e4d92]"
            />
            In stock only
          </label>

          <div className="mt-4 pt-3 border-t border-[#ebe8e3]">
            <div className="text-[10px] font-bold uppercase tracking-widest text-[#888894] mb-2">
              Sort
            </div>
            <div className="flex flex-col gap-1.5">
              {SORT_OPTIONS.map((o) => (
                <label key={o.value} className="flex items-center gap-2 text-[12px] cursor-pointer">
                  <input
                    type="radio"
                    name="sort"
                    checked={filters.sort === o.value}
                    onChange={() => setFilter("sort", o.value)}
                    className="w-3.5 h-3.5 accent-[#1e4d92]"
                  />
                  {o.label}
                </label>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: TSC**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 4: Stage**

```bash
git add frontend/src/components/storefront/filter-button.tsx frontend/src/components/storefront/active-filter-chips.tsx
# feat(storefront): filter popover + lazy active-filter chips
```

---

### Task 5: LeftRail slim + hover/click expand

**Files:**
- Modify: `frontend/src/components/storefront/left-rail.tsx`

- [ ] **Step 1: Replace file body**

Open current `left-rail.tsx`, preserve the tree-building logic and `Row` subcomponent, and wrap the nav in a new collapsible-overlay container. Full replacement:

```tsx
"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import type { Category } from "@/lib/types";

interface LeftRailProps {
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
    list.sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.name.localeCompare(b.name));
    list.forEach((n) => sortRec(n.children));
  };
  sortRec(roots);
  return roots;
}

function Row({ node, depth, counts }: { node: Node; depth: number; counts: Record<string, number> }) {
  return (
    <div>
      <Link
        href={`/storefront/vg?category=${node.id}`}
        className="flex items-center justify-between px-3 py-1.5 rounded-md text-[12.5px]
                   text-[#1e1e24] hover:bg-[#eef4fb] hover:text-[#1e4d92]"
        style={{ paddingLeft: 12 + depth * 14 }}
      >
        <span className="truncate">{node.name}</span>
        {counts[node.id] != null && (
          <span className="text-[10px] font-mono text-[#888894]">{counts[node.id]}</span>
        )}
      </Link>
      {node.children.map((c) => (
        <Row key={c.id} node={c} depth={depth + 1} counts={counts} />
      ))}
    </div>
  );
}

export function LeftRail({ categories, counts }: LeftRailProps) {
  const tree = useMemo(() => buildTree(categories), [categories]);
  const [open, setOpen] = useState(false);

  return (
    <aside
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      className="relative shrink-0"
      aria-label="Category rail"
    >
      {/* Collapsed rail (always in flow) */}
      <div className="w-[60px] sticky top-[96px] h-[calc(100vh-96px)] border-r border-[#e9e7e3] bg-white flex flex-col items-center py-4 gap-2">
        <button
          aria-label={open ? "Collapse categories" : "Expand categories"}
          onClick={() => setOpen((v) => !v)}
          className="w-9 h-9 rounded-md flex items-center justify-center text-[#484852]
                     hover:bg-[#f2f0ed] hover:text-[#1e4d92]"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        {tree.slice(0, 8).map((n) => {
          const initial = n.name.slice(0, 1).toUpperCase();
          return (
            <Link
              key={n.id}
              href={`/storefront/vg?category=${n.id}`}
              title={n.name}
              className="w-9 h-9 rounded-md flex items-center justify-center bg-[#f9f7f4]
                         text-[#484852] text-[11px] font-bold font-mono hover:bg-[#eef4fb] hover:text-[#1e4d92]"
            >
              {initial}
            </Link>
          );
        })}
      </div>

      {/* Expanded overlay */}
      {open && (
        <div
          className="absolute left-[60px] top-0 z-40 w-[240px] h-[calc(100vh-96px)]
                     bg-white border-r border-b border-[#cfccc8] shadow-lg overflow-y-auto"
        >
          <nav className="py-3">
            <Link
              href="/storefront/vg"
              className="flex items-center gap-2 px-3 py-2 rounded-md text-[12.5px] font-medium
                         text-[#1e1e24] hover:bg-[#eef4fb] hover:text-[#1e4d92]"
            >
              All products
            </Link>
            {tree.length === 0 ? (
              <div className="px-3 py-6 text-center text-[11px] text-[#888894]">
                No categories synced.
              </div>
            ) : (
              tree.map((n) => <Row key={n.id} node={n} depth={0} counts={counts} />)
            )}
          </nav>
        </div>
      )}
    </aside>
  );
}
```

- [ ] **Step 2: TSC**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 3: Stage**

```bash
git add frontend/src/components/storefront/left-rail.tsx
# feat(storefront): slim LeftRail with hover-expand overlay
```

---

### Task 6: TopBar category dropdown

**Files:**
- Modify: `frontend/src/components/storefront/top-bar.tsx`

- [ ] **Step 1: Replace file body**

```tsx
"use client";

import Link from "next/link";
import { useSearch } from "./search-context";
import type { Category } from "@/lib/types";

interface TopBarProps {
  categories: Category[];
}

export function TopBar({ categories }: TopBarProps) {
  const { filters, setQuery, setFilter } = useSearch();

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
            value={filters.q}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search products…"
            className="w-full pl-10 pr-4 py-2 bg-[#f9f7f4] border border-[#cfccc8] rounded-md
                       text-[13px] outline-none transition-all
                       focus:border-[#1e4d92] focus:bg-white focus:shadow-[0_0_0_3px_#eef4fb]"
          />
        </div>
      </div>

      <select
        value={filters.category ?? ""}
        onChange={(e) => setFilter("category", e.target.value || null)}
        className="h-8 px-2 border border-[#cfccc8] rounded-md bg-white text-[12px] text-[#1e1e24] max-w-[220px]"
      >
        <option value="">All categories</option>
        {categories.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>

      <div className="ml-auto shrink-0">
        <Link href="/" className="text-[12px] font-semibold text-[#484852] hover:text-[#1e4d92]">
          ← Admin
        </Link>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: TSC**

Run: `cd frontend && npx tsc --noEmit`
Expected: might fail because `StorefrontShell` still calls `<TopBar />` with no props. Task 7 fixes.

- [ ] **Step 3: Stage**

```bash
git add frontend/src/components/storefront/top-bar.tsx
# feat(storefront): TopBar category dropdown
```

---

# Phase 3 — Shell layout

### Task 7: Shell composes new chrome + independent scroll

**Files:**
- Modify: `frontend/src/components/storefront/storefront-shell.tsx`

- [ ] **Step 1: Replace file body**

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Category, ProductListItem, Supplier } from "@/lib/types";
import { SearchProvider, useSearch } from "./search-context";
import { TopBar } from "./top-bar";
import { LeftRail } from "./left-rail";
import { MobileFilterSheet } from "./mobile-filter-sheet";
import { BreadcrumbBar, deriveSegments, type BreadcrumbSegment } from "./breadcrumb-bar";

const VG_SLUG = "vg-ops";

interface ShellData {
  categories: Category[];
  counts: Record<string, number>;
  loaded: boolean;
}

function ShellInner({
  data,
  children,
  trailingSegment,
}: {
  data: ShellData;
  children: React.ReactNode;
  trailingSegment?: BreadcrumbSegment;
}) {
  const { filters } = useSearch();
  const segments = useMemo(
    () => deriveSegments(data.categories, filters.category, trailingSegment),
    [data.categories, filters.category, trailingSegment],
  );

  return (
    <div className="h-screen flex flex-col bg-[#f2f0ed] text-[#1e1e24] overflow-hidden">
      <TopBar categories={data.categories} />
      <BreadcrumbBar segments={segments} />
      <div className="flex flex-1 min-h-0">
        <div className="hidden md:block">
          <LeftRail categories={data.categories} counts={data.counts} />
        </div>
        <main className="flex-1 min-w-0 overflow-y-auto px-6 py-5">
          {!data.loaded && (
            <div className="text-[11px] font-mono text-[#888894] mb-3">Loading storefront…</div>
          )}
          {children}
        </main>
        <MobileFilterSheet categories={data.categories} counts={data.counts} />
      </div>
    </div>
  );
}

export function StorefrontShell({
  children,
  trailingSegment,
}: {
  children: React.ReactNode;
  trailingSegment?: BreadcrumbSegment;
}) {
  const [data, setData] = useState<ShellData>({ categories: [], counts: {}, loaded: false });

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
        setData({ categories: cats, counts: tally, loaded: true });
      } catch {
        setData((d) => ({ ...d, loaded: true }));
      }
    })();
  }, []);

  return (
    <SearchProvider>
      <ShellInner data={data} trailingSegment={trailingSegment}>
        {children}
      </ShellInner>
    </SearchProvider>
  );
}
```

- [ ] **Step 2: TSC**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 3: Smoke**

Run: `curl -sI http://localhost:3000/storefront/vg | head -1`
Expected: `HTTP/1.1 200 OK`. Open in browser — TopBar sticky, breadcrumb bar below, main area scrolls independently, LeftRail stays slim.

- [ ] **Step 4: Stage**

```bash
git add frontend/src/components/storefront/storefront-shell.tsx
# feat(storefront): sticky TopBar + BreadcrumbBar + independent main scroll
```

---

# Phase 4 — Pages consume URL state

### Task 8: Grid page uses URL filters

**Files:**
- Modify: `frontend/src/app/storefront/vg/page.tsx`

- [ ] **Step 1: Rewrite page**

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { ProductListItem } from "@/lib/types";
import { useSearch } from "@/components/storefront/search-context";
import { FilterButton } from "@/components/storefront/filter-button";
import { ActiveFilterChips } from "@/components/storefront/active-filter-chips";
import { StorefrontProductCard } from "@/components/storefront/storefront-product-card";

export default function StorefrontGridPage() {
  const { filters } = useSearch();
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const sups = await api<{ id: string; slug: string }[]>("/api/suppliers");
        const vg = sups.find((s) => s.slug === "vg-ops");
        if (!vg) return;
        const rows = await api<ProductListItem[]>(`/api/products?supplier_id=${vg.id}&limit=500`);
        setProducts(rows);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const visible = useMemo(() => {
    let rows = products;
    if (filters.category) rows = rows.filter((p) => p.category_id === filters.category);
    if (filters.q) {
      const q = filters.q.toLowerCase();
      rows = rows.filter(
        (p) => p.product_name.toLowerCase().includes(q) || (p.brand ?? "").toLowerCase().includes(q),
      );
    }
    if (filters.stock === "in") rows = rows.filter((p) => (p.total_inventory ?? 0) > 0);
    const sorted = [...rows];
    switch (filters.sort) {
      case "price_asc":
        sorted.sort((a, b) => (a.price_min ?? Infinity) - (b.price_min ?? Infinity));
        break;
      case "price_desc":
        sorted.sort((a, b) => (b.price_max ?? -Infinity) - (a.price_max ?? -Infinity));
        break;
      case "newest":
        sorted.reverse();
        break;
      default:
        sorted.sort((a, b) => a.product_name.localeCompare(b.product_name));
    }
    return sorted;
  }, [products, filters]);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="text-[11px] font-mono text-[#888894]">
          {loading ? "Loading…" : `${visible.length} product${visible.length === 1 ? "" : "s"}`}
        </div>
        <FilterButton />
      </div>

      <ActiveFilterChips />

      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-[220px] bg-white rounded-md border border-[#e9e7e3] animate-pulse" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <div className="text-center py-20 text-[13px] text-[#888894]">No products match.</div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {visible.map((p) => (
            <StorefrontProductCard key={p.id} product={p} />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: TSC**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 3: Smoke**

Browser: visit `/storefront/vg`, click Filter → toggle In stock → URL gains `?stock=in`, chip appears. Click category in TopBar dropdown → URL gains `?category=<uuid>`, breadcrumb updates, grid filters. Back button returns.

- [ ] **Step 4: Stage**

```bash
git add frontend/src/app/storefront/vg/page.tsx
# feat(storefront): grid page reads filters from URL
```

---

### Task 9: Category route redirects to `?category=<id>`

**Files:**
- Modify: `frontend/src/app/storefront/vg/category/[category_id]/page.tsx`

- [ ] **Step 1: Replace file body**

```tsx
import { redirect } from "next/navigation";

export default async function CategoryPage({
  params,
}: {
  params: Promise<{ category_id: string }>;
}) {
  const { category_id } = await params;
  redirect(`/storefront/vg?category=${category_id}`);
}
```

- [ ] **Step 2: TSC**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 3: Smoke**

`curl -sI "http://localhost:3000/storefront/vg/category/<uuid>" | head -3` — expect `307` or `308` to `/storefront/vg?category=<uuid>`.

- [ ] **Step 4: Stage**

```bash
git add frontend/src/app/storefront/vg/category/[category_id]/page.tsx
# refactor(storefront): category route redirects to query-param form
```

---

### Task 10: PDP breadcrumb trailing segment

**Files:**
- Modify: `frontend/src/app/storefront/vg/product/[product_id]/page.tsx`

- [ ] **Step 1: Find layout.tsx for storefront/vg**

The shell mounts via `frontend/src/app/storefront/vg/layout.tsx`. PDP is client-side and needs the product name available to the shell. Easiest route: keep PDP as-is but let shell derive trailing segment from `usePathname()` + `useProductName()` context.

Simpler approach used here: render PDPLayout with breadcrumb inside the page; the shell's BreadcrumbBar is driven by URL only (already covered in `deriveSegments`). Add product name to PDP's existing breadcrumb (PDPLayout already renders one).

If `PDPLayout` already has breadcrumb, no change needed. Otherwise add the parent category chain.

- [ ] **Step 2: Verify current PDPLayout**

Run: `grep -n "breadcrumb\|Breadcrumb" frontend/src/components/storefront/pdp-layout.tsx`
If match exists, Task 10 is a no-op on the file. Note "verified" in stage commit.

- [ ] **Step 3: Stage (noop allowed)**

```bash
# If nothing changed, skip. Otherwise:
git add frontend/src/app/storefront/vg/product/\[product_id\]/page.tsx frontend/src/components/storefront/pdp-layout.tsx
# feat(storefront): PDP trailing breadcrumb with product name
```

---

# Phase 5 — Cleanup

### Task 11: Retire old FilterChipBar

**Files:**
- Delete: `frontend/src/components/storefront/filter-chip-bar.tsx`

- [ ] **Step 1: Verify no consumers**

Run: `grep -rn "filter-chip-bar\|FilterChipBar" frontend/src 2>/dev/null`
Expected: no matches after Task 8.

- [ ] **Step 2: Delete**

```bash
rm frontend/src/components/storefront/filter-chip-bar.tsx
```

- [ ] **Step 3: TSC**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 4: Stage**

```bash
git add -A frontend/src/components/storefront/filter-chip-bar.tsx
# chore(storefront): drop old FilterChipBar (replaced by filter-button + chips)
```

---

### Task 12: End-to-end smoke + plan checkbox update

- [ ] **Step 1: TSC**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 2: Dev smokes**

```bash
curl -sI http://localhost:3000/storefront/vg | head -1
curl -sI "http://localhost:3000/storefront/vg?category=$(docker compose exec -T postgres psql -U vg_user -d vg_hub -t -c "select id from categories limit 1" | tr -d ' \n')" | head -1
```
Expected: both `200 OK`.

- [ ] **Step 3: Browser spot checks**

Visit each, verify:
- `/storefront/vg` — TopBar + BreadcrumbBar stick on scroll; LeftRail slim; Filter button top-right; no chips visible.
- Click Filter → toggle In stock → URL gains `?stock=in`; chip appears above grid; close popover by click-outside.
- Pick category in TopBar → URL updates, breadcrumb shows `Catalog › <name>`; back chevron returns.
- Hover LeftRail → overlay expands 240px with tree; move away → collapses.

- [ ] **Step 4: Tick plan checkboxes**

Open this file and mark every `- [ ]` → `- [x]` across Tasks 1-12.

- [ ] **Step 5: Stage**

```bash
git add docs/superpowers/plans/2026-04-21-storefront-chrome-nav-redesign.md
# docs(plan): tick storefront chrome redesign tasks
```

---

## Out of scope (explicit)

- Grid card design (already shipped in prior redesign)
- Product fetch strategy / pagination / infinite scroll
- Mobile filter sheet behavior (unchanged)
- Backend / n8n changes

---

## Self-review notes

- Every spec requirement maps to a task: layout (T3, T7), URL state (T1, T2), LeftRail behavior (T5), TopBar dropdown (T6), FilterButton + chips (T4, T8), PDP (T10), category (T9), cleanup (T11).
- No placeholders — every code step has complete code.
- Type consistency: `StorefrontFilters`, `SortKey`, `StockFilter`, `BreadcrumbSegment`, `countActive`, `readFilters`, `writeFilters` referenced identically across T1-T8.
- Commit policy: stage-then-commit pattern; user can batch these into their own commits if preferred.
