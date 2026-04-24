"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { ProductListItem } from "@/lib/types";
import { useSearch } from "@/components/storefront/search-context";
import { FilterButton } from "@/components/storefront/filter-button";
import { ActiveFilterChips } from "@/components/storefront/active-filter-chips";
import { StorefrontProductCard } from "@/components/storefront/storefront-product-card";


export default function VGStorefrontPage() {
  const { filters } = useSearch();
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const rows = await api<ProductListItem[]>("/api/products?limit=500");
        setProducts(rows);
      } finally {
        setLoading(false);
      }
    })();
  }, []);


  const visible = useMemo(() => {
    let rows = products;
    
    // 1. Category Filter
    if (filters.category) {
      rows = rows.filter((p) => p.category_id === filters.category);
    }
    
    // 2. Search Query
    if (filters.q) {
      const q = filters.q.toLowerCase();
      rows = rows.filter(
        (p) => p.product_name.toLowerCase().includes(q) || 
               p.supplier_sku.toLowerCase().includes(q) ||
               (p.brand ?? "").toLowerCase().includes(q),
      );
    }
    
    // 3. Stock Filter
    if (filters.stock === "in") {
      rows = rows.filter((p) => (p.total_inventory ?? 0) > 0);
    }
    
    // 4. Sorting
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
      case "variants":
        sorted.sort((a, b) => (b.variant_count ?? 0) - (a.variant_count ?? 0));
        break;
      default:
        sorted.sort((a, b) => a.product_name.localeCompare(b.product_name));
    }
    return sorted;
  }, [products, filters]);

  return (
    <div className="flex-1 flex flex-col p-5 gap-5 overflow-hidden">
      <div className="flex items-center justify-between">
        <div className="text-[13px] text-[#888894] font-mono">
          {loading ? "Loading…" : `${visible.length} / ${products.length} products`}
        </div>
        <FilterButton />
      </div>

      <ActiveFilterChips />

      {loading ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-5">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-[340px] bg-[#f9f7f4] border border-[#ebe8e3] rounded-[10px] animate-pulse" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <div className="border border-dashed border-[#cfccc8] rounded-[10px] p-16 text-center bg-white">
          <div className="text-[14px] font-bold text-[#1e1e24] mb-1">No matches</div>
          <div className="text-[12px] text-[#888894]">
            Try removing filters or clearing the search.
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-5">
          {visible.map((p) => (
            <StorefrontProductCard key={p.id} product={p} />
          ))}
        </div>
      )}
    </div>
  );
}
