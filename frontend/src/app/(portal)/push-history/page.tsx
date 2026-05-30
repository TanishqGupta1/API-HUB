"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { CheckCircle2, XCircle, Loader2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface PushHistoryItem {
  push_log_id: string;
  product_id: string;
  status: string;
  ops_product_id: string | null;
  supplier_sku: string | null;
  supplier_slug: string | null;
  dry_run: boolean;
  error: string | null;
  pushed_at: string | null;
}

interface PushHistoryResponse {
  total: number;
  skip: number;
  limit: number;
  items: PushHistoryItem[];
}

const STATUS_STYLE: Record<string, { color: string; icon: React.ReactNode }> = {
  pushed:          { color: "text-emerald-600", icon: <CheckCircle2 className="w-3.5 h-3.5" /> },
  dry_run_pushed:  { color: "text-blue-500",    icon: <CheckCircle2 className="w-3.5 h-3.5" /> },
  failed:          { color: "text-red-500",      icon: <XCircle className="w-3.5 h-3.5" /> },
  partial_failure: { color: "text-amber-500",   icon: <AlertTriangle className="w-3.5 h-3.5" /> },
  rejected:        { color: "text-red-500",      icon: <XCircle className="w-3.5 h-3.5" /> },
  processing:      { color: "text-[#1e4d92]",   icon: <Loader2 className="w-3.5 h-3.5 animate-spin" /> },
  accepted:        { color: "text-[#888894]",   icon: <Loader2 className="w-3.5 h-3.5 animate-spin" /> },
};

function fmt(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function PortalPushHistory() {
  const [page, setPage] = useState(0);
  const [data, setData] = useState<PushHistoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const limit = 20;

  useEffect(() => {
    setIsLoading(true);
    api<PushHistoryResponse>(`/api/portal/push-history?skip=${page * limit}&limit=${limit}`)
      .then(setData)
      .finally(() => setIsLoading(false));
  }, [page]);

  const totalPages = Math.ceil((data?.total ?? 0) / limit);

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div>
        <h1 className="text-2xl font-black text-[#1e1e24] tracking-tight">Push History</h1>
        <p className="text-sm text-[#888894] font-medium mt-1">All product pushes to your storefront</p>
      </div>

      <div className="bg-white rounded-2xl border border-[#ebe9e6] overflow-hidden">
        {/* Table header */}
        <div className="grid grid-cols-[1fr_120px_160px_100px] gap-4 px-6 py-3 border-b border-[#f2f0ed] bg-[#f9f7f4]">
          {["Product / SKU", "Status", "Pushed At", "OPS ID"].map((h) => (
            <div key={h} className="text-[10px] font-black uppercase tracking-widest text-[#888894]">{h}</div>
          ))}
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-[#1e4d92]" />
          </div>
        ) : !data?.items?.length ? (
          <div className="py-16 text-center text-sm text-[#888894]">No pushes found.</div>
        ) : (
          <div className="divide-y divide-[#f2f0ed]">
            {data.items.map((item) => {
              const style = STATUS_STYLE[item.status] ?? { color: "text-[#888894]", icon: null };
              return (
                <div key={item.push_log_id} className="grid grid-cols-[1fr_120px_160px_100px] gap-4 px-6 py-3.5 items-center hover:bg-[#fafaf9]">
                  <div className="min-w-0">
                    <div className="text-sm font-bold text-[#1e1e24] truncate">
                      {item.supplier_sku ?? "—"}
                      {item.dry_run && <span className="ml-2 text-[9px] font-black uppercase tracking-wider bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded">dry run</span>}
                    </div>
                    {item.supplier_slug && (
                      <div className="text-[10px] text-[#888894] uppercase tracking-wide">{item.supplier_slug}</div>
                    )}
                    {item.error && <div className="text-[10px] text-red-500 truncate mt-0.5">{item.error}</div>}
                  </div>
                  <div className={`flex items-center gap-1.5 text-[11px] font-bold ${style.color}`}>
                    {style.icon}
                    <span className="capitalize">{item.status.replace("_", " ")}</span>
                  </div>
                  <div className="text-[11px] text-[#888894]">
                    {item.pushed_at ? fmt(item.pushed_at) : "—"}
                  </div>
                  <div className="font-mono text-[10px] text-[#888894] truncate">
                    {item.ops_product_id ?? "—"}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-6 py-4 border-t border-[#f2f0ed] flex items-center justify-between">
            <span className="text-[11px] text-[#888894]">
              {data!.skip + 1}–{Math.min(data!.skip + limit, data!.total)} of {data!.total}
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}
                className="h-8 text-xs border-[#cfccc8]">Prev</Button>
              <Button variant="outline" size="sm" disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}
                className="h-8 text-xs border-[#cfccc8]">Next</Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
