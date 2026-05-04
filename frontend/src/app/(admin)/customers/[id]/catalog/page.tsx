"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Customer } from "@/lib/types";
import { ArrowLeft, Package, AlertTriangle, CheckCircle2, Search } from "lucide-react";

interface CatalogProduct {
  product_id: string;
  supplier_sku: string;
  product_name: string;
  product_type: string;
  supplier_id: string;
  image_url: string | null;
  ops_product_id: string | null;
  supplier_has_decoration_overlay: boolean;
  decoration_ready: boolean;
}

export default function CustomerCatalogPage() {
  const { id } = useParams<{ id: string }>();

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api<Customer>(`/api/customers/${id}`),
      api<CatalogProduct[]>(`/api/push/candidates/${id}?limit=500`),
    ])
      .then(([cust, prods]) => {
        setCustomer(cust);
        setProducts(prods);
      })
      .finally(() => setLoading(false));
  }, [id]);

  const filtered = products.filter(
    (p) =>
      p.product_name.toLowerCase().includes(search.toLowerCase()) ||
      p.supplier_sku.toLowerCase().includes(search.toLowerCase()),
  );

  const needsDecorationCount = products.filter(
    (p) => p.supplier_has_decoration_overlay && !p.decoration_ready,
  ).length;

  const handlePush = async (e: React.MouseEvent, productId: string) => {
    e.preventDefault();
    if (!id) return;
    try {
      await api(`/api/push/${id}/${productId}`, { method: "POST" });
      // Update local state to show pushed
      setProducts((prev) =>
        prev.map((p) =>
          p.product_id === productId ? { ...p, ops_product_id: "pending" } : p
        )
      );
    } catch (err) {
      console.error("Failed to push product", err);
      alert("Failed to push product");
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8 pb-6 border-b-2 border-[#1e1e24]">
        <Link
          href={`/customers/${id}`}
          className="flex items-center gap-1.5 text-[12px] font-semibold text-[#888894] hover:text-[#1e4d92] transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back
        </Link>
        <div className="h-4 w-px bg-[#cfccc8]" />
        <div>
          <div className="text-[28px] font-extrabold tracking-tight leading-none text-[#1e1e24]">
            Product Catalog
          </div>
          {customer && (
            <p className="text-[13px] text-[#888894] mt-1">{customer.name}</p>
          )}
        </div>

        {needsDecorationCount > 0 && (
          <div className="ml-auto flex items-center gap-2 px-4 py-2 bg-yellow-50 border border-yellow-300 rounded-lg">
            <AlertTriangle className="w-4 h-4 text-yellow-600" />
            <span className="text-[12px] font-bold text-yellow-800">
              {needsDecorationCount} product{needsDecorationCount > 1 ? "s" : ""} need decoration
            </span>
          </div>
        )}
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-4 mb-6">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#b4b4bc]" />
          <input
            type="text"
            placeholder="Search products…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 h-10 bg-white border border-[#cfccc8] rounded-lg text-[13px] text-[#1e1e24] placeholder:text-[#b4b4bc] outline-none focus:border-[#1e4d92] transition-colors"
          />
        </div>
        <div className="text-[11px] font-mono text-[#888894]">
          {filtered.length} / {products.length} products
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 animate-pulse">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="h-48 bg-white border border-[#f2f0ed] rounded-xl" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="py-20 text-center border-2 border-dashed border-[#cfccc8] rounded-2xl">
          <Package className="w-10 h-10 text-[#b4b4bc] mx-auto mb-3" />
          <div className="text-[15px] font-bold text-[#1e1e24]">No products found</div>
          <p className="text-[12px] text-[#888894] mt-1">
            {products.length === 0
              ? "No synced products available. Run a supplier sync first."
              : "No products match your search."}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((p) => {
            const needsDecoration = p.supplier_has_decoration_overlay && !p.decoration_ready;
            const isPushable = !needsDecoration;

            return (
              <div
                key={p.product_id}
                className="group flex flex-col bg-white border border-[#cfccc8] rounded-xl overflow-hidden shadow-sm hover:border-[#1e4d92] hover:shadow-md transition-all relative"
              >
                <Link href={`/storefront/vg/product/${p.product_id}`} className="block flex-1">
                  {/* Image */}
                  <div className="aspect-square bg-[#f2f0ed] relative overflow-hidden">
                    {p.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={p.image_url}
                        alt={p.product_name}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Package className="w-10 h-10 text-[#cfccc8]" />
                      </div>
                    )}

                    {/* Badges */}
                    <div className="absolute top-2 left-2 flex flex-col gap-1">
                      {needsDecoration && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-yellow-100 border border-yellow-300 px-2 py-0.5 text-[10px] font-bold text-yellow-800">
                          <AlertTriangle className="w-3 h-3" />
                          Needs Decoration
                        </span>
                      )}
                      {p.supplier_has_decoration_overlay && p.decoration_ready && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 border border-emerald-300 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                          <CheckCircle2 className="w-3 h-3" />
                          Decorated
                        </span>
                      )}
                    </div>

                    {/* Pushed badge */}
                    {p.ops_product_id && (
                      <span className="absolute top-2 right-2 rounded-full bg-[#eef4fb] border border-[#1e4d92] px-2 py-0.5 text-[10px] font-bold text-[#1e4d92]">
                        Pushed
                      </span>
                    )}
                  </div>

                  {/* Info */}
                  <div className="p-3 flex flex-col gap-1">
                    <p className="text-[12px] font-bold text-[#1e1e24] leading-snug line-clamp-2">
                      {p.product_name}
                    </p>
                    <div className="flex items-center gap-2 mt-auto pt-2">
                      <span className="font-mono text-[10px] text-[#888894]">{p.supplier_sku}</span>
                      <span className="ml-auto text-[10px] font-semibold uppercase tracking-wide text-[#888894] bg-[#f2f0ed] px-1.5 py-0.5 rounded">
                        {p.product_type}
                      </span>
                    </div>
                  </div>
                </Link>

                {/* Push Button Container */}
                <div className="p-3 pt-0 mt-auto border-t border-[#f2f0ed] flex items-center justify-between">
                  <Link href={`/customers/${id}/catalog/${p.product_id}/history`} className="text-[10px] font-semibold text-[#1e4d92] hover:underline">
                    View History
                  </Link>
                  {isPushable && (
                    <button
                      onClick={(e) => handlePush(e, p.product_id)}
                      className="text-[10px] font-bold bg-[#1e1e24] text-white px-3 py-1.5 rounded hover:bg-[#383842] transition-colors"
                    >
                      {p.ops_product_id ? "Push Update" : "Push to OPS"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
