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
