"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Category, ProductListItem, Supplier } from "@/lib/types";
import { CategoryNav } from "@/components/storefront/category-nav";
import { StorefrontProductCard } from "@/components/storefront/storefront-product-card";

const VG_SLUG = "vg-ops";

export default function VGStorefrontPage() {
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const allSuppliers = await api<Supplier[]>("/api/suppliers");
        const vg = allSuppliers.find((s) => s.slug === VG_SLUG) ?? null;
        setSupplier(vg);

        if (!vg) {
          setError(
            "Visual Graphics OPS supplier row not found. Run `python seed_demo.py`."
          );
          setLoading(false);
          return;
        }

        const [cats, prods] = await Promise.all([
          api<Category[]>(`/api/categories?supplier_id=${vg.id}`),
          api<ProductListItem[]>(
            `/api/products?supplier_id=${vg.id}&limit=200`
          ),
        ]);
        setCategories(cats);
        setProducts(prods);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const filtered = useMemo(() => {
    if (!search) return products;
    const q = search.toLowerCase();
    return products.filter(
      (p) =>
        p.product_name.toLowerCase().includes(q) ||
        p.supplier_sku.toLowerCase().includes(q) ||
        (p.brand ?? "").toLowerCase().includes(q)
    );
  }, [products, search]);

  return (
    <div className="flex flex-col gap-6 pb-12">
      {/* Header */}
      <div className="flex items-end justify-between pb-5 border-b-2 border-[#1e1e24]">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <span className="font-mono text-[10px] font-bold uppercase tracking-[0.15em] text-[#1e4d92] bg-[#eef4fb] px-2 py-[3px] rounded">
              Storefront
            </span>
            <span className="text-[11px] font-mono text-[#888894]">
              /{VG_SLUG}
            </span>
          </div>
          <div className="text-[32px] font-extrabold tracking-[-0.04em] leading-none text-[#1e1e24]">
            Visual Graphics
          </div>
          <div className="text-[13px] text-[#888894] mt-2 font-normal">
            {supplier
              ? supplier.is_active
                ? `${products.length} products indexed · live from OnPrintShop`
                : `Supplier seeded but inactive. Flip is_active=true to begin syncing.`
              : "Loading supplier state…"}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
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
              className="w-[320px] pl-11 pr-4 py-[12px] bg-[#f9f7f4] border-2 border-[#cfccc8] rounded-md
                         text-[14px] font-sans outline-none transition-all
                         focus:border-[#1e4d92] focus:bg-white focus:shadow-[0_0_0_4px_#eef4fb]"
              placeholder="Search products…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 border border-[#e94b4b] rounded-[10px] bg-[#fef2f2] text-[13px] text-[#b91c1c]">
          <div className="font-bold mb-1">Error</div>
          <div className="font-mono">{error}</div>
        </div>
      )}

      <div className="flex gap-6">
        <CategoryNav categories={categories} />

        <main className="flex-1 min-w-0">
          {loading ? (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-5">
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="h-[340px] bg-[#f9f7f4] border border-[#ebe8e3] rounded-[10px] animate-pulse"
                />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="border border-dashed border-[#cfccc8] rounded-[10px] p-16 text-center bg-white">
              <div className="text-[14px] font-bold text-[#1e1e24] mb-1">
                No products yet
              </div>
              <div className="text-[12px] text-[#888894]">
                {products.length === 0
                  ? "Waiting on first OPS sync from n8n."
                  : `No match for "${search}".`}
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-5">
              {filtered.map((p) => (
                <StorefrontProductCard key={p.id} product={p} />
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
