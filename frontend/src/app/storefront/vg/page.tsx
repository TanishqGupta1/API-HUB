"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { ProductListItem, ProductType } from "@/lib/types";
import { useSearch } from "@/components/storefront/search-context";
import { FilterButton } from "@/components/storefront/filter-button";
import { ActiveFilterChips } from "@/components/storefront/active-filter-chips";
import { StorefrontProductCard } from "@/components/storefront/storefront-product-card";
import { ProductTypeFilter } from "@/components/storefront/product-type-filter";


// Backend caps `/api/products?limit` at 1000 (see catalog/routes.py:53).
// Use that max so the storefront shows as many products as the API allows
// in a single fetch. If the live catalog grows past 1000 we'll need real
// pagination — but the dashboard count below will surface that gap loudly
// in the meantime (the label shows fetched-vs-real and warns when capped).
const FETCH_LIMIT = 1000;

interface StatsResponse {
  products: number;       // live (non-archived) count
  variants?: number;
  suppliers?: number;
}

export default function VGStorefrontPage() {
  const { filters } = useSearch();
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [totalInDb, setTotalInDb] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [productType, setProductType] = useState<ProductType | null>(null);

  useEffect(() => {
    (async () => {
      try {
        // Fire both requests in parallel — the stats call is cheap (one COUNT)
        // and lets us show the *real* product count even when fetch is capped.
        const [rows, stats] = await Promise.all([
          api<ProductListItem[]>(`/api/products?limit=${FETCH_LIMIT}`),
          api<StatsResponse>("/api/stats").catch(() => null),
        ]);
        setProducts(rows);
        if (stats?.products != null) setTotalInDb(stats.products);
      } finally {
        setLoading(false);
      }
    })();
  }, []);


  const availableTypes = useMemo(
    () => Array.from(new Set(products.map((p) => p.product_type))) as ProductType[],
    [products],
  );

  const visible = useMemo(() => {
    let rows = products;

    // 0. Product type filter
    if (productType) {
      rows = rows.filter((p) => p.product_type === productType);
    }

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
  }, [products, productType, filters]);

  return (
    <div className="flex-1 flex flex-col p-5 gap-5 overflow-hidden">
      <div className="flex items-center justify-between">
        <div className="text-[13px] text-[#888894] font-mono">
          {loading
            ? "Loading…"
            : totalInDb != null && totalInDb > products.length
              ? // True total is larger than what we fetched (hit the cap).
                // Be honest about it so admins know more imports exist.
                `${visible.length} of ${products.length} shown · ${totalInDb} total in catalog (showing first ${FETCH_LIMIT})`
              : // Fetched everything — simple denominator.
                `${visible.length} / ${products.length} products`}
        </div>
        <FilterButton />
      </div>

      <ActiveFilterChips />

      <ProductTypeFilter
        available={availableTypes}
        value={productType}
        onChange={setProductType}
      />

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
