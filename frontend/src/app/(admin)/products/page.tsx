"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ChevronDown, X } from "lucide-react";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import type { ProductListItem, Supplier } from "@/lib/types";
import { ProductCard } from "@/components/products/product-card";

interface Category { id: string; name: string; }

export default function ProductsPage() {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [supplierFilter, setSupplierFilter] = useState<string>("all");
  const [supplierSearch, setSupplierSearch] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<Supplier[]>("/api/suppliers").then(setSuppliers).catch(log.error);
    api<Category[]>("/api/categories").then(setCategories).catch(log.error);
  }, []);

  useEffect(() => {
    setLoading(true);
    const timeout = setTimeout(() => {
      const params = new URLSearchParams({ limit: "50" });
      if (search) params.set("search", search);
      if (categoryId) params.set("category_id", categoryId);
      if (supplierFilter !== "all") params.set("supplier_id", supplierFilter);
      
      api<ProductListItem[]>(`/api/products?${params.toString()}`)
        .then(setProducts)
        .catch(log.error)
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(timeout);
  }, [search, categoryId, supplierFilter]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleArchive = async (p: ProductListItem) => {
    if (!confirm(`Archive ${p.product_name}?`)) return;
    try {
      await api(`/api/products/${p.id}/archive`, { method: "POST" });
      setProducts((prev) => prev.filter((x) => x.id !== p.id));
    } catch (err) {
      log.error(err);
      alert("Failed to archive product.");
    }
  };

  const filteredSuppliers = suppliers.filter((s) =>
    s.name.toLowerCase().includes(supplierSearch.toLowerCase())
  );

  const selectedSupplier = suppliers.find((s) => s.id === supplierFilter);

  const displayedProducts = products; // Backend handles filtering now

  return (
    <div id="s-products">
      {/* Page header */}
      <div className="flex items-end justify-between mb-10 pb-5 border-b-2 border-[#1e1e24]">
        <div>
          <div className="text-[32px] font-extrabold tracking-[-0.04em] leading-none text-[#1e1e24]">
            Product Catalog
          </div>
          <div className="text-[13px] text-[#888894] mt-2 font-normal">
            32.4k products indexed across 4 normalized schemas
          </div>
        </div>
        <Link
          href="/products/archived"
          className="text-[12px] font-semibold text-[#1e4d92] hover:underline"
        >
          View archived →
        </Link>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-2 mb-8">
        {/* All Products pill */}
        <button
          onClick={() => { setSupplierFilter("all"); setSupplierSearch(""); setCategoryId(""); }}
          className={`px-4 py-[6px] rounded-full border text-[12px] font-semibold cursor-pointer transition-all duration-150
            ${supplierFilter === "all" && !categoryId
              ? "bg-[#1e1e24] text-white border-[#1e1e24]"
              : "bg-white text-[#484852] border-[#cfccc8] hover:border-[#1e4d92] hover:text-[#1e4d92]"
            }`}
        >
          All Products
        </button>

        {/* Supplier dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen((o) => !o)}
            className={`flex items-center gap-2 px-4 py-[6px] rounded-full border text-[12px] font-semibold cursor-pointer transition-all duration-150
              ${supplierFilter !== "all"
                ? "bg-[#1e4d92] text-white border-[#1e4d92]"
                : "bg-white text-[#484852] border-[#cfccc8] hover:border-[#1e4d92] hover:text-[#1e4d92]"
              }`}
          >
            <span>{selectedSupplier ? selectedSupplier.name : "Suppliers"}</span>
            {supplierFilter !== "all" ? (
              <X
                className="w-3 h-3 opacity-70 hover:opacity-100"
                onClick={(e) => { e.stopPropagation(); setSupplierFilter("all"); setSupplierSearch(""); }}
              />
            ) : (
              <ChevronDown className={`w-3 h-3 transition-transform ${dropdownOpen ? "rotate-180" : ""}`} />
            )}
          </button>

          {dropdownOpen && (
            <div className="absolute top-full left-0 mt-2 w-64 bg-white border border-[#cfccc8] rounded-lg shadow-lg z-50 overflow-hidden">
              {/* Search */}
              <div className="p-2 border-b border-[#f2f0ed]">
                <input
                  autoFocus
                  type="text"
                  placeholder="Search suppliers..."
                  value={supplierSearch}
                  onChange={(e) => setSupplierSearch(e.target.value)}
                  className="w-full px-3 py-[6px] text-[12px] bg-[#f9f7f4] border border-[#cfccc8] rounded-md outline-none focus:border-[#1e4d92]"
                />
              </div>

              {/* Scrollable list — shows ~5 rows */}
              <div className="overflow-y-auto max-h-[200px]">
                {filteredSuppliers.length === 0 ? (
                  <div className="px-3 py-4 text-[11px] text-[#888894] text-center">No suppliers found</div>
                ) : (
                  filteredSuppliers.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => { setSupplierFilter(s.id); setDropdownOpen(false); setSupplierSearch(""); setCategoryId(""); }}
                      className={`w-full text-left px-3 py-[9px] text-[12px] font-medium flex items-center justify-between transition-colors
                        ${supplierFilter === s.id
                          ? "bg-[#eef4fb] text-[#1e4d92] font-bold"
                          : "text-[#1e1e24] hover:bg-[#f9f7f4]"
                        }`}
                    >
                      <span>{s.name}</span>
                      <span className="font-mono text-[10px] text-[#888894]">{s.product_count?.toLocaleString() ?? 0}</span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Search input */}
        <div className="relative flex-1 max-w-[400px] ml-2">
          <svg
            className="absolute left-4 top-1/2 -translate-y-1/2 w-[18px] h-[18px] text-[#b4b4bc] pointer-events-none"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            type="text"
            placeholder="Search products by name or SKU..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-12 pr-4 h-11 bg-white border border-[#cfccc8] rounded-full text-[13px] font-medium text-[#1e1e24] placeholder:text-[#b4b4bc] outline-none focus:border-[#1e4d92] transition-colors"
          />
        </div>
      </div>

      {loading && products.length === 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 animate-pulse">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="aspect-[4/5] bg-white border border-[#f2f0ed] rounded-2xl" />
          ))}
        </div>
      ) : displayedProducts.length === 0 ? (
        <div className="py-20 text-center border-2 border-dashed border-[#f2f0ed] rounded-3xl bg-[#fcfbf9]">
          <div className="text-[14px] font-bold text-[#1e1e24]">No products found</div>
          <p className="text-[12px] text-[#888894] mt-1">Try adjusting your filters or search terms.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {displayedProducts.map((p) => (
            <ProductCard key={p.id} product={p} onArchive={() => handleArchive(p)} />
          ))}
        </div>
      )}

      {/* Pagination (placeholder) */}
      {!loading && displayedProducts.length > 0 && (
        <div className="mt-12 flex justify-center">
          <button className="px-6 py-2.5 bg-white border border-[#cfccc8] rounded-full text-[12px] font-bold text-[#1e1e24] hover:bg-[#fcfbf9] transition-colors">
            Load More Products
          </button>
        </div>
      )}
    </div>
  );
}
