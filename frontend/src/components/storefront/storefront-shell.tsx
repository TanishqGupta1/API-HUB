"use client";

import { useEffect, useMemo, useState, Suspense } from "react";
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
    <Suspense fallback={null}>
      <SearchProvider>
        <ShellInner data={data} trailingSegment={trailingSegment}>
          {children}
        </ShellInner>
      </SearchProvider>
    </Suspense>
  );
}
