"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Category, ProductListItem, Supplier } from "@/lib/types";
import { CategoryNav } from "@/components/storefront/category-nav";
import { StorefrontProductCard } from "@/components/storefront/storefront-product-card";

const VG_SLUG = "vg-ops";

export default function VGCategoryPage() {
  const params = useParams<{ category_id: string }>();
  const categoryId = params?.category_id;

  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!categoryId) return;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const allSuppliers = await api<Supplier[]>("/api/suppliers");
        const vg = allSuppliers.find((s) => s.slug === VG_SLUG) ?? null;
        setSupplier(vg);

        if (!vg) {
          setError("Visual Graphics OPS supplier row not found.");
          setLoading(false);
          return;
        }

        const [cats, prods] = await Promise.all([
          api<Category[]>(`/api/categories?supplier_id=${vg.id}`),
          api<ProductListItem[]>(
            `/api/products?supplier_id=${vg.id}&category_id=${categoryId}&limit=500`
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
  }, [categoryId]);

  const current = useMemo(
    () => categories.find((c) => c.id === categoryId) ?? null,
    [categories, categoryId]
  );

  return (
    <div className="flex flex-col gap-6 pb-12">
      <div className="flex items-end justify-between pb-5 border-b-2 border-[#1e1e24]">
        <div>
          <div className="flex items-center gap-2 text-[12px] text-[#888894] mb-2">
            <Link href="/storefront/vg" className="hover:text-[#1e4d92] font-medium">
              Visual Graphics
            </Link>
            <span>/</span>
            <span className="font-mono text-[#1e1e24]">Category</span>
          </div>
          <div className="text-[32px] font-extrabold tracking-[-0.04em] leading-none text-[#1e1e24]">
            {current?.name ?? "Category"}
          </div>
          <div className="text-[13px] text-[#888894] mt-2 font-normal">
            {products.length} product{products.length === 1 ? "" : "s"}
            {supplier && !supplier.is_active && " · supplier inactive"}
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
        <CategoryNav categories={categories} activeCategoryId={categoryId} />

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
          ) : products.length === 0 ? (
            <div className="border border-dashed border-[#cfccc8] rounded-[10px] p-16 text-center bg-white">
              <div className="text-[14px] font-bold text-[#1e1e24] mb-1">
                No products in this category yet
              </div>
              <div className="text-[12px] text-[#888894]">
                {current?.name ? (
                  <>Nothing mapped to <span className="font-mono">{current.name}</span> or its sub-categories.</>
                ) : (
                  "Category not found."
                )}
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-5">
              {products.map((p) => (
                <StorefrontProductCard key={p.id} product={p} />
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
