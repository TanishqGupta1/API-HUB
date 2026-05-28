"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Package, UploadCloud, AlertTriangle, Store, CheckCircle2, XCircle, Loader2, Clock } from "lucide-react";

interface DashboardData {
  products_selected: number;
  products_pushed: number;
  pushes_this_week: number;
  push_failures_this_week: number;
  active_suppliers: number;
  recent_pushes: {
    push_log_id: string;
    status: string;
    ops_product_id: string | null;
    supplier_sku: string | null;
    supplier_slug: string | null;
    pushed_at: string | null;
    error: string | null;
  }[];
}

interface PortalMe {
  id: string;
  name: string;
  ops_base_url: string;
  products_pushed: number;
}

function StatusIcon({ status }: { status: string }) {
  if (status === "pushed") return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
  if (status === "processing" || status === "queued" || status === "accepted")
    return <Loader2 className="w-4 h-4 animate-spin text-[#1e4d92]" />;
  return <XCircle className="w-4 h-4 text-red-400" />;
}

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hrs = Math.floor(min / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function PortalDashboard() {
  const [me, setMe] = useState<PortalMe | null>(null);
  const [data, setData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    api<PortalMe>("/api/portal/me").then(setMe).catch(() => {});
  }, []);

  useEffect(() => {
    let stopped = false;
    let timerId: ReturnType<typeof setInterval>;

    async function fetchDashboard() {
      try {
        const result = await api<DashboardData>("/api/portal/dashboard");
        setData(result);
      } catch (err: unknown) {
        // Stop polling on 401 — session has expired; further polls are useless.
        const status = (err as { status?: number })?.status;
        if (status === 401 && timerId) {
          clearInterval(timerId);
          stopped = true;
        }
      } finally {
        setIsLoading(false);
      }
    }

    fetchDashboard();
    if (!stopped) {
      timerId = setInterval(fetchDashboard, 30_000);
    }
    return () => clearInterval(timerId);
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-[#1e4d92]" />
      </div>
    );
  }

  const stats = [
    { label: "Products Selected", value: data?.products_selected ?? 0, icon: Package, color: "text-[#1e4d92]", bg: "bg-[#1e4d92]/10" },
    { label: "Products Pushed",   value: data?.products_pushed ?? 0,   icon: UploadCloud, color: "text-emerald-600", bg: "bg-emerald-50" },
    { label: "Pushes This Week",  value: data?.pushes_this_week ?? 0,  icon: Clock, color: "text-amber-600", bg: "bg-amber-50" },
    { label: "Active Suppliers",  value: data?.active_suppliers ?? 0,  icon: Store, color: "text-purple-600", bg: "bg-purple-50" },
  ];

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-black text-[#1e1e24] tracking-tight">
          Welcome back{me?.name ? `, ${me.name}` : ""}
        </h1>
        <p className="text-[#888894] text-sm font-medium mt-1">
          {me?.ops_base_url
            ? <>Your storefront: <span className="font-mono text-[#484852]">{me.ops_base_url}</span></>
            : "Your self-service storefront portal"
          }
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map(({ label, value, icon: Icon, color, bg }) => (
          <div key={label} className="bg-white rounded-2xl border border-[#ebe9e6] p-5">
            <div className={`w-9 h-9 rounded-xl ${bg} flex items-center justify-center mb-3`}>
              <Icon className={`w-5 h-5 ${color}`} />
            </div>
            <div className="text-2xl font-black text-[#1e1e24]">{value.toLocaleString()}</div>
            <div className="text-[11px] font-semibold text-[#888894] uppercase tracking-wider mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      {/* Failure alert */}
      {(data?.push_failures_this_week ?? 0) > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-2xl px-5 py-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
          <div>
            <div className="text-sm font-bold text-red-700">
              {data!.push_failures_this_week} push failure{data!.push_failures_this_week !== 1 ? "s" : ""} this week
            </div>
            <div className="text-xs text-red-500 mt-0.5">Check Push History for details.</div>
          </div>
        </div>
      )}

      {/* Recent pushes */}
      <div className="bg-white rounded-2xl border border-[#ebe9e6] overflow-hidden">
        <div className="px-6 py-4 border-b border-[#f2f0ed]">
          <h2 className="text-sm font-black text-[#1e1e24] tracking-tight uppercase">Recent Pushes</h2>
        </div>
        {!data?.recent_pushes?.length ? (
          <div className="px-6 py-10 text-center text-sm text-[#888894]">No pushes yet.</div>
        ) : (
          <div className="divide-y divide-[#f2f0ed]">
            {data.recent_pushes.map((p) => (
              <div key={p.push_log_id} className="px-6 py-4 flex items-center gap-4">
                <StatusIcon status={p.status} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-bold text-[#1e1e24] truncate">
                    {p.supplier_sku ?? "Unknown SKU"}
                    {p.supplier_slug && <span className="ml-2 text-[10px] font-normal text-[#888894] uppercase">{p.supplier_slug}</span>}
                  </div>
                  {p.ops_product_id && (
                    <div className="text-[10px] font-mono text-[#888894]">OPS: {p.ops_product_id}</div>
                  )}
                  {p.error && <div className="text-[10px] text-red-500 truncate">{p.error}</div>}
                </div>
                <div className="text-[11px] text-[#888894] shrink-0">
                  {p.pushed_at ? timeAgo(p.pushed_at) : "—"}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
}
