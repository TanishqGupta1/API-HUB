"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { ProductListItem } from "@/lib/types";
import { ProductCard } from "@/components/products/product-card";

export default function ProductsPage() {
  const router = useRouter();
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const timeout = setTimeout(() => {
      const params = new URLSearchParams({ limit: "50" });
      if (search) params.set("search", search);
      if (typeFilter) params.set("type", typeFilter);
      api<ProductListItem[]>(`/api/products?${params.toString()}`)
        .then(setProducts)
        .catch(console.error)
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(timeout);
  }, [search, typeFilter]);

  const types = ["Apparel", "Bags", "Drinkware", "Accessories"];

  return (
    <div id="s-products">
      {/* Page header */}
      <div className="flex items-end justify-between mb-10 pb-5 border-b-2 border-[#1e1e24]">
        <div>
          <div className="text-[32px] font-extrabold tracking-[-0.04em] leading-none text-[#1e1e24]">
            Technical Index
          </div>
          <div className="text-[13px] text-[#888894] mt-2 font-normal">
            32.4k products indexed across 4 normalized schemas
          </div>
        </div>
      </div>

      {/* Filters row */}
      <div className="flex items-center gap-3 mb-8">
        {/* Search input */}
        <div className="relative flex-1 max-w-[400px]">
          <svg
            className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-[#b4b4bc] pointer-events-none"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            className="w-full pl-11 pr-4 py-[14px] bg-[#f9f7f4] border-2 border-[#cfccc8] rounded-md
                       text-[15px] font-sans outline-none transition-all
                       focus:border-[#1e4d92] focus:bg-white focus:shadow-[0_0_0_4px_#eef4fb]"
            placeholder="Query index by name, SKU, or tag..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {/* Type filter tags */}
        <button
          onClick={() => setTypeFilter("")}
          className={`px-4 py-2 rounded-md border text-[12px] font-semibold cursor-pointer transition-all duration-150
            ${typeFilter === ""
              ? "bg-[#1e4d92] text-white border-[#1e4d92]"
              : "bg-white text-[#1e1e24] border-[#cfccc8] hover:border-[#1e4d92] hover:text-[#1e4d92]"
            }`}
        >
          All
        </button>
        {types.map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className={`px-4 py-2 rounded-md border text-[12px] font-semibold cursor-pointer transition-all duration-150
              ${typeFilter === t
                ? "bg-[#1e4d92] text-white border-[#1e4d92]"
                : "bg-white text-[#1e1e24] border-[#cfccc8] hover:border-[#1e4d92] hover:text-[#1e4d92]"
              }`}
          >
            {t}
          </button>
        ))}

        {/* Result count */}
        <div className="ml-auto font-mono text-[11px] text-[#888894]">
          {loading ? "_QUERYING_INDEX..." : `${products.length.toLocaleString()} results`}
        </div>
      </div>

      {/* Product grid */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-6">
        {loading ? (
          <div className="col-span-full py-10 text-center text-[#888894] text-[14px]">
            <div className="font-mono mb-2">_QUERYING_INDEX...</div>
            <span>Loading catalog from normalized data source</span>
          </div>
        ) : products.length === 0 ? (
          <div className="col-span-full py-10 text-center text-[#888894] text-[14px]">
            No products found. Adjust filters or connect a supplier.
          </div>
        ) : (
          products.map((p) => <ProductCard key={p.id} product={p} />)
        )}
      </div>
    </div>
  );
}
