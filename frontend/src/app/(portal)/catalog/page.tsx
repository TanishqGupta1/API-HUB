"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Package, Loader2, CheckCircle2, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SafeImage as Image } from "@/components/common/safe-image";

interface CatalogItem {
  selection_id: string;
  product_id: string;
  supplier_sku: string;
  product_name: string;
  brand: string | null;
  image_url: string | null;
  added_at: string | null;
  push_status: { status: string; ops_product_id: string | null } | null;
}

interface CatalogResponse {
  total: number;
  skip: number;
  limit: number;
  items: CatalogItem[];
}

function PushBadge({ push_status }: { push_status: CatalogItem["push_status"] }) {
  if (!push_status) return <span className="text-[10px] text-[#888894] font-bold uppercase">Not pushed</span>;
  if (push_status.status === "pushed") {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-600">
        <CheckCircle2 className="w-3 h-3" /> Live
      </span>
    );
  }
  return <span className="text-[10px] text-amber-600 font-bold uppercase">{push_status.status}</span>;
}

export default function PortalCatalog() {
  const [page, setPage] = useState(0);
  const [data, setData] = useState<CatalogResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const limit = 24;

  useEffect(() => {
    setIsLoading(true);
    api<CatalogResponse>(`/api/portal/catalog?skip=${page * limit}&limit=${limit}`)
      .then(setData)
      .finally(() => setIsLoading(false));
  }, [page]);

  const totalPages = Math.ceil((data?.total ?? 0) / limit);

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-[#1e1e24] tracking-tight">My Catalog</h1>
          <p className="text-sm text-[#888894] font-medium mt-1">
            {data ? `${data.total.toLocaleString()} products selected for your storefront` : "Loading…"}
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-8 h-8 animate-spin text-[#1e4d92]" />
        </div>
      ) : !data?.items?.length ? (
        <div className="text-center py-20 bg-white rounded-3xl border-2 border-dashed border-[#cfccc8]">
          <div className="w-14 h-14 rounded-2xl bg-[#f9f7f4] border border-[#cfccc8] flex items-center justify-center mx-auto mb-4">
            <Package className="w-7 h-7 text-[#888894]" />
          </div>
          <h3 className="text-base font-black text-[#1e1e24] mb-1">No products yet</h3>
          <p className="text-sm text-[#888894]">Products added to your storefront will appear here.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {data.items.map((item) => (
              <div key={item.selection_id} className="bg-white rounded-2xl border border-[#ebe9e6] overflow-hidden hover:border-[#1e4d92] hover:shadow-lg hover:shadow-blue-900/5 transition-all group">
                {/* Image */}
                <div className="aspect-square bg-[#f9f7f4] relative overflow-hidden">
                  {item.image_url ? (
                    <Image
                      src={item.image_url}
                      alt={item.product_name}
                      fill
                      className="object-contain p-3 group-hover:scale-105 transition-transform duration-300"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Package className="w-10 h-10 text-[#cfccc8]" />
                    </div>
                  )}
                </div>

                {/* Info */}
                <div className="p-3">
                  <div className="text-[10px] font-mono text-[#888894] truncate">{item.supplier_sku}</div>
                  <div className="text-sm font-bold text-[#1e1e24] leading-tight truncate mt-0.5">{item.product_name}</div>
                  {item.brand && <div className="text-[10px] text-[#888894] mt-0.5">{item.brand}</div>}
                  <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#f2f0ed]">
                    <PushBadge push_status={item.push_status} />
                    {item.added_at && (
                      <span className="text-[9px] text-[#888894] flex items-center gap-1">
                        <Clock className="w-2.5 h-2.5" />
                        {new Date(item.added_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3">
              <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}
                className="border-[#cfccc8]">Previous</Button>
              <span className="text-sm text-[#888894]">Page {page + 1} of {totalPages}</span>
              <Button variant="outline" size="sm" disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}
                className="border-[#cfccc8]">Next</Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
