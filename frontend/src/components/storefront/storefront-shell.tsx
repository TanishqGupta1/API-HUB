"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Category, ProductListItem, Supplier } from "@/lib/types";
import { SearchProvider } from "./search-context";
import { TopBar } from "./top-bar";
import { LeftRail } from "./left-rail";
import { MobileFilterSheet } from "./mobile-filter-sheet";

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
          <MobileFilterSheet categories={categories} counts={counts} />
        </div>
      </div>
    </SearchProvider>
  );
}
