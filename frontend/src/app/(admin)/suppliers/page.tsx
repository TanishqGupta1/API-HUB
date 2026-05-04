"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import { Supplier, SyncJob } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Plus,
  Settings2,
  RefreshCcw,
  Globe,
  Database,
  ShieldCheck,
  ChevronRight,
  MoreVertical,
  Activity
} from "lucide-react";

// ── Sync badge helpers ────────────────────────────────────────────────────────

type SyncHealth = "healthy" | "stale" | "critical" | "error" | "running" | "never";

function getSyncHealth(job: SyncJob | undefined): SyncHealth {
  if (!job) return "never";
  if (job.status === "running" || job.status === "pending") return "running";
  if (job.status === "failed") return "error";
  if (!job.completed_at) return "never";
  const ageMs = Date.now() - new Date(job.completed_at).getTime();
  const ageHrs = ageMs / (1000 * 60 * 60);
  if (ageHrs < 1) return "healthy";
  if (ageHrs < 24) return "stale";
  return "critical";
}

const SYNC_BADGE: Record<SyncHealth, { color: string; bg: string; label: string }> = {
  healthy:  { color: "#247a52", bg: "rgba(36,122,82,0.1)",   label: "Synced"    },
  stale:    { color: "#c17c00", bg: "rgba(193,124,0,0.1)",   label: "Stale"     },
  critical: { color: "#b93232", bg: "rgba(185,50,50,0.1)",   label: "Outdated"  },
  error:    { color: "#b93232", bg: "rgba(185,50,50,0.1)",   label: "Error"     },
  running:  { color: "#1e4d92", bg: "rgba(30,77,146,0.1)",   label: "Syncing"   },
  never:    { color: "#888894", bg: "var(--paper-warm)",      label: "Never run" },
};

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hrs = Math.floor(min / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ─────────────────────────────────────────────────────────────────────────────

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [syncMap, setSyncMap]     = useState<Record<string, SyncJob>>({});
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [data, jobs] = await Promise.all([
          api<Supplier[]>("/api/suppliers"),
          api<SyncJob[]>("/api/sync-jobs?limit=200").catch(() => [] as SyncJob[]),
        ]);
        setSuppliers(data);

        // Build map: supplier_id → most recent completed/failed job
        const map: Record<string, SyncJob> = {};
        for (const j of jobs) {
          const existing = map[j.supplier_id];
          if (!existing || j.started_at > existing.started_at) {
            map[j.supplier_id] = j;
          }
        }
        setSyncMap(map);
      } catch (e) {
        log.error("Failed to load suppliers", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh] flex-col gap-4">
        <div className="w-10 h-10 border-[3px] border-[#1e4d92] border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-[#888894] font-medium animate-pulse">Scanning Supplier Network...</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-700">
      
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h1 className="text-3xl font-black text-[#1e1e24] tracking-tight flex items-center gap-3">
            <Globe className="w-8 h-8 text-[#1e4d92]" />
            Supplier Directory
          </h1>
          <p className="text-[#888894] mt-1 font-medium">Manage and monitor your external data sources.</p>
        </div>
        <Button className="bg-[#1e4d92] hover:bg-[#173d74] text-white font-bold text-xs uppercase tracking-wider shadow-lg shadow-blue-900/10 px-8 h-11" asChild>
          <Link href="/suppliers/new">
            <Plus className="w-4 h-4 mr-2" />
            Add New Supplier
          </Link>
        </Button>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
         <div className="bg-[#f9f7f4] border border-[#cfccc8] rounded-2xl p-5 flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-white border border-[#cfccc8] flex items-center justify-center text-[#1e4d92] shadow-sm">
               <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
               <div className="text-[10px] font-black uppercase tracking-widest text-[#888894]">Connected</div>
               <div className="text-xl font-black text-[#1e1e24] leading-tight">{suppliers.filter(s => s.is_active).length} Suppliers</div>
            </div>
         </div>
         <div className="bg-[#f9f7f4] border border-[#cfccc8] rounded-2xl p-5 flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-white border border-[#cfccc8] flex items-center justify-center text-[#1e4d92] shadow-sm">
               <Database className="w-5 h-5" />
            </div>
            <div>
               <div className="text-[10px] font-black uppercase tracking-widest text-[#888894]">Total Inventory</div>
               <div className="text-xl font-black text-[#1e1e24] leading-tight">
                 {suppliers.reduce((acc, s) => acc + (s.product_count || 0), 0).toLocaleString()} Products
               </div>
            </div>
         </div>
         <div className="bg-[#f9f7f4] border border-[#cfccc8] rounded-2xl p-5 flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-white border border-[#cfccc8] flex items-center justify-center text-[#1e4d92] shadow-sm">
               <Activity className="w-5 h-5" />
            </div>
            <div>
               <div className="text-[10px] font-black uppercase tracking-widest text-[#888894]">Active Protocols</div>
               <div className="text-xl font-black text-[#1e1e24] leading-tight">
                 {new Set(suppliers.map(s => s.protocol)).size} Methods
               </div>
            </div>
         </div>
      </div>

      {/* Supplier Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {suppliers.map((s) => {
          const latestJob = syncMap[s.id];
          const health    = getSyncHealth(latestJob);
          const badge     = SYNC_BADGE[health];
          return (
          <Card key={s.id} className="border-[#cfccc8] overflow-hidden bg-white hover:border-[#1e4d92] transition-all hover:shadow-xl hover:shadow-blue-900/5 group">
            <div className="p-6 space-y-6">

              {/* Top Row: Name & Protocol */}
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-[#f9f7f4] border border-[#cfccc8] flex items-center justify-center text-xl font-black text-[#1e4d92] group-hover:bg-[#1e4d92] group-hover:text-white group-hover:border-[#1e4d92] transition-all duration-300">
                    {s.name[0]}
                  </div>
                  <div>
                    <h3 className="text-lg font-black text-[#1e1e24] tracking-tight group-hover:text-[#1e4d92] transition-colors">{s.name}</h3>
                    <div className="flex items-center gap-2 mt-0.5">
                      <Badge variant="outline" className="bg-[#f9f7f4] border-[#cfccc8] text-[#888894] font-black text-[9px] uppercase tracking-widest h-5">
                        {s.protocol}
                      </Badge>
                      <span className="text-[10px] font-bold text-[#888894] uppercase tracking-widest">ID: {s.slug}</span>
                    </div>
                  </div>
                </div>
                {/* Sync health badge */}
                <span
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-wider shrink-0"
                  style={{ background: badge.bg, color: badge.color }}
                  title={latestJob?.completed_at ? `Last sync: ${new Date(latestJob.completed_at).toLocaleString()}` : "Never synced"}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${health === "healthy" || health === "running" ? "animate-pulse" : ""}`}
                    style={{ background: badge.color }}
                  />
                  {badge.label}
                  {latestJob?.completed_at && (
                    <span className="font-mono font-normal normal-case tracking-normal opacity-70">
                      · {timeAgo(latestJob.completed_at)}
                    </span>
                  )}
                </span>
              </div>

              {/* Stats & Info Row */}
              <div className="grid grid-cols-3 gap-4 border-y border-[#f2f0ed] py-4">
                <div>
                  <div className="text-[9px] font-black uppercase tracking-widest text-[#888894] mb-1">Products</div>
                  <div className="font-mono font-black text-[#1e1e24] text-sm">{s.product_count?.toLocaleString() || 0}</div>
                </div>
                <div>
                  <div className="text-[9px] font-black uppercase tracking-widest text-[#888894] mb-1">Status</div>
                  <div className={`text-[10px] font-black uppercase tracking-tight ${s.is_active ? 'text-emerald-600' : 'text-[#888894]'}`}>
                    {s.is_active ? 'Online' : 'Paused'}
                  </div>
                </div>
                <div>
                  <div className="text-[9px] font-black uppercase tracking-widest text-[#888894] mb-1">Last Sync</div>
                  <div className="text-[10px] font-black uppercase tracking-tight" style={{ color: badge.color }}>
                    {latestJob?.status === "running" ? "Running…" : latestJob?.completed_at ? timeAgo(latestJob.completed_at) : "—"}
                  </div>
                </div>
              </div>

              {/* Action Bar */}
              <div className="flex items-center justify-between pt-1">
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" className="h-9 px-3 border border-transparent hover:border-[#cfccc8] text-[11px] font-bold text-[#888894] uppercase tracking-wider" asChild>
                    <Link href={`/suppliers/${s.id}`}>
                      <Settings2 className="w-3.5 h-3.5 mr-2" />
                      Configure
                    </Link>
                  </Button>
                  <Button variant="ghost" size="sm" className="h-9 px-3 border border-transparent hover:border-[#cfccc8] text-[11px] font-bold text-[#888894] uppercase tracking-wider" asChild>
                    <Link href={`/mappings/${s.id}`}>
                      <RefreshCcw className="w-3.5 h-3.5 mr-2" />
                      Mappings
                    </Link>
                  </Button>
                </div>
                <Button size="sm" className="h-9 w-9 p-0 bg-[#f9f7f4] hover:bg-[#1e4d92] text-[#1e4d92] hover:text-white border border-[#cfccc8] transition-all rounded-xl" asChild>
                   <Link href={`/suppliers/${s.id}`}>
                     <ChevronRight className="w-4 h-4" />
                   </Link>
                </Button>
              </div>

            </div>
          </Card>
          );
        })}
      </div>

      {/* Empty State */}
      {!loading && suppliers.length === 0 && (
        <div className="text-center py-20 bg-[#f9f7f4] rounded-3xl border-2 border-dashed border-[#cfccc8]">
          <div className="w-16 h-16 rounded-2xl bg-white border border-[#cfccc8] flex items-center justify-center text-3xl mx-auto mb-6 shadow-sm">📡</div>
          <h3 className="text-xl font-black text-[#1e1e24] mb-2 tracking-tight">No Suppliers Connected</h3>
          <p className="text-[13px] text-[#888894] max-w-sm mx-auto font-medium leading-relaxed mb-6">
            Start building your data hub by connecting your first supplier via SOAP, REST, or SFTP.
          </p>
          <Button className="bg-[#1e4d92] hover:bg-[#173d74] text-white font-black text-xs uppercase tracking-widest px-8" asChild>
            <Link href="/suppliers/new">Register Now</Link>
          </Button>
        </div>
      )}

    </div>
  );
}
