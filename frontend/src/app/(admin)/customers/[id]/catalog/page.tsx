"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { log } from "@/lib/log";
import type { Customer } from "@/lib/types";
import { ArrowLeft, Package, AlertTriangle, CheckCircle2, Search, Send, Loader2 } from "lucide-react";

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

type PushState = "idle" | "pushing" | "pushed" | "error";

export default function CustomerCatalogPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const supplierId = searchParams.get("supplier_id");

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [pushStates, setPushStates] = useState<Record<string, PushState>>({});
  const [pushErrors, setPushErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    const candidatesUrl = `/api/push/candidates/${id}?limit=500${supplierId ? `&supplier_id=${supplierId}` : ""}`;
    
    Promise.all([
      api<Customer>(`/api/customers/${id}`),
      api<CatalogProduct[]>(candidatesUrl),
    ])
      .then(([cust, prods]) => {
        setCustomer(cust);
        setProducts(prods);
        // Pre-mark already-pushed products
        const initial: Record<string, PushState> = {};
        prods.forEach((p) => {
          if (p.ops_product_id) initial[p.product_id] = "pushed";
        });
        setPushStates(initial);
      })
      .catch((err) => {
        log.error("Failed to fetch product candidates", err);
        toast.error(err.message || "Failed to fetch products");
      })
      .finally(() => setLoading(false));
  }, [id, supplierId]);

  async function handlePush(e: React.MouseEvent, productId: string) {
    e.preventDefault();
    e.stopPropagation();
    setPushStates((s) => ({ ...s, [productId]: "pushing" }));
    setPushErrors((s) => { const n = { ...s }; delete n[productId]; return n; });
    try {
      await api(`/api/customers/${id}/push/${productId}`, { method: "POST" });
      setPushStates((s) => ({ ...s, [productId]: "pushed" }));
    } catch (err) {
      setPushStates((s) => ({ ...s, [productId]: "error" }));
      setPushErrors((s) => ({
        ...s,
        [productId]: err instanceof Error ? err.message : "Push failed",
      }));
    }
  }

  const filtered = products.filter(
    (p) =>
      p.product_name.toLowerCase().includes(search.toLowerCase()) ||
      p.supplier_sku.toLowerCase().includes(search.toLowerCase()),
  );

  const needsDecorationCount = products.filter(
    (p) => p.supplier_has_decoration_overlay && !p.decoration_ready,
  ).length;

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
          {supplierId && " (Filtered by Supplier)"}
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
            const pushState = pushStates[p.product_id] ?? "idle";
            const pushError = pushErrors[p.product_id];
            const isPushed = pushState === "pushed";
            const isPushing = pushState === "pushing";

            return (
              <div
                key={p.product_id}
                className="group flex flex-col bg-white border border-[#cfccc8] rounded-xl overflow-hidden shadow-sm hover:border-[#1e4d92] hover:shadow-md transition-all"
              >
                {/* Image — clickable link */}
                <Link href={`/storefront/vg/product/${p.product_id}`} className="block">
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
                    {isPushed && (
                      <span className="absolute top-2 right-2 rounded-full bg-[#eef4fb] border border-[#1e4d92] px-2 py-0.5 text-[10px] font-bold text-[#1e4d92]">
                        Pushed
                      </span>
                    )}
                  </div>
                </Link>

                {/* Info + Push button */}
                <div className="p-3 flex flex-col gap-1 flex-1">
                  <Link href={`/storefront/vg/product/${p.product_id}`} className="block">
                    <p className="text-[12px] font-bold text-[#1e1e24] leading-snug line-clamp-2">
                      {p.product_name}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="font-mono text-[10px] text-[#888894]">{p.supplier_sku}</span>
                      <span className="ml-auto text-[10px] font-semibold uppercase tracking-wide text-[#888894] bg-[#f2f0ed] px-1.5 py-0.5 rounded">
                        {p.product_type}
                      </span>
                    </div>
                  </Link>

                  {/* Push error */}
                  {pushError && (
                    <p className="text-[10px] text-red-600 mt-1 leading-snug">{pushError}</p>
                  )}

                  <div className="mt-2 flex items-center gap-2">
                    <Link href={`/customers/${id}/catalog/${p.product_id}/history`} className="text-[10px] font-semibold text-[#1e4d92] hover:underline shrink-0">
                      History
                    </Link>
                    <button
                      onClick={(e) => handlePush(e, p.product_id)}
                      disabled={isPushing || needsDecoration}
                      title={needsDecoration ? "Add decoration before pushing" : isPushed ? "Push again" : "Push to storefront"}
                      className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded border text-[11px] font-bold transition-colors"
                      style={{
                        background: isPushed ? "var(--paper)" : "var(--blue)",
                        color: isPushed ? "var(--blue)" : "#fff",
                        borderColor: "var(--blue)",
                        opacity: needsDecoration ? 0.4 : isPushing ? 0.7 : 1,
                        cursor: needsDecoration || isPushing ? "not-allowed" : "pointer",
                      }}
                    >
                      {isPushing ? (
                        <>
                          <Loader2 className="w-3 h-3 animate-spin" />
                          Pushing…
                        </>
                      ) : isPushed ? (
                        <>
                          <CheckCircle2 className="w-3 h-3" />
                          Pushed
                        </>
                      ) : (
                        <>
                          <Send className="w-3 h-3" />
                          Push to OPS
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
