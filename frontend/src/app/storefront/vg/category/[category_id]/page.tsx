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
