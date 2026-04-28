"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { 
  BarChart3, 
  Package, 
  RefreshCcw, 
  Layers, 
  CheckCircle2, 
  AlertCircle,
  ArrowRight,
  Activity
} from "lucide-react";

type Stats = {
  suppliers: number;
  products: number;
  variants: number;
};

type SyncJob = {
  id: string;
  supplier_id: string;
  supplier_name: string;
  job_type: string;
  status: string;
  records_processed: number;
  started_at: string;
  finished_at: string | null;
  error_log: string | null;
};

type Supplier = {
  id: string;
  name: string;
  is_active: boolean;
  product_count: number;
};

const JOB_TYPE_LABELS: Record<string, string> = {
  inventory: "Inventory",
  delta: "Sync",
  full_sync: "Full Refresh",
  full: "Full Refresh",
  pricing: "Pricing",
  push_to_ops: "Published",
};

function timeAgo(iso: string): string {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<Stats>({ suppliers: 0, products: 0, variants: 0 });
  const [recentJobs, setRecentJobs] = useState<SyncJob[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [s, j, sup] = await Promise.all([
          api<Stats>("/api/stats"),
          api<SyncJob[]>("/api/sync-jobs?limit=5"),
          api<Supplier[]>("/api/suppliers"),
        ]);
        setStats(s);
        setRecentJobs(j);
        setSuppliers(sup);
      } catch (e) {
        console.error("Failed to load dashboard stats", e);
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
        <p className="text-sm text-[#888894] font-medium animate-pulse">Initializing Dashboard...</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-700">
      
      {/* Welcome Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h1 className="text-3xl font-black text-[#1e1e24] tracking-tight flex items-center gap-3">
            <BarChart3 className="w-8 h-8 text-[#1e4d92]" />
            System Overview
          </h1>
          <p className="text-[#888894] mt-1 font-medium">Monitoring the heartbeat of your supplier network.</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" className="border-[#cfccc8] bg-white hover:bg-[#f9f7f4] font-bold text-xs uppercase tracking-wider" asChild>
            <Link href="/sync">View All Jobs</Link>
          </Button>
          <Button className="bg-[#1e4d92] hover:bg-[#173d74] font-bold text-xs uppercase tracking-wider shadow-lg shadow-blue-900/10" asChild>
            <Link href="/products/setup">Setup New Product</Link>
          </Button>
        </div>
      </div>

      {/* Hero Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <StatCard 
          title="Active Suppliers" 
          value={stats.suppliers} 
          icon={<Layers className="w-5 h-5 text-blue-600" />} 
          color="blue"
          subText={`${suppliers.filter(s => s.is_active).length} online now`}
        />
        <StatCard 
          title="Total Catalog" 
          value={stats.products.toLocaleString()} 
          icon={<Package className="w-5 h-5 text-indigo-600" />} 
          color="indigo"
          subText="Synced from 4 sources"
        />
        <StatCard 
          title="Sync Health" 
          value="98.2%" 
          icon={<Activity className="w-5 h-5 text-emerald-600" />} 
          color="emerald"
          subText="Last 24 hours"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Recent Activity */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-[#1e1e24] flex items-center gap-2">
              <RefreshCcw className="w-5 h-5 text-[#1e4d92]" />
              Recent Pipeline Activity
            </h2>
          </div>
          <Card className="border-[#cfccc8] overflow-hidden bg-white/50 backdrop-blur-sm">
            <div className="divide-y divide-[#f2f0ed]">
              {recentJobs.length === 0 ? (
                <div className="p-12 text-center text-[#888894]">No recent activity found.</div>
              ) : (
                recentJobs.map((job) => (
                  <div key={job.id} className="p-5 flex items-center justify-between hover:bg-[#f9f7f4]/50 transition-colors group">
                    <div className="flex items-center gap-4">
                      <div className={`p-2.5 rounded-xl ${
                        job.status === 'completed' ? 'bg-emerald-50 text-emerald-600' : 
                        job.status === 'failed' ? 'bg-rose-50 text-rose-600' : 'bg-blue-50 text-blue-600'
                      }`}>
                        {job.status === 'completed' ? <CheckCircle2 className="w-5 h-5" /> : 
                         job.status === 'failed' ? <AlertCircle className="w-5 h-5" /> : 
                         <RefreshCcw className="w-5 h-5 animate-spin-slow" />}
                      </div>
                      <div>
                        <div className="font-bold text-[#1e1e24] text-[13px]">{job.supplier_name}</div>
                        <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-[#888894]">
                          <span>{JOB_TYPE_LABELS[job.job_type] || job.job_type}</span>
                          <span>•</span>
                          <span>{timeAgo(job.started_at)}</span>
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono font-bold text-[#1e1e24] text-[13px]">
                        {job.records_processed.toLocaleString()} <span className="text-[10px] text-[#888894] font-sans">items</span>
                      </div>
                      <div className={`text-[10px] font-black uppercase tracking-tighter ${
                        job.status === 'completed' ? 'text-emerald-600' : 
                        job.status === 'failed' ? 'text-rose-600' : 'text-blue-600'
                      }`}>
                        {job.status}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="p-4 bg-[#f9f7f4]/30 border-t border-[#f2f0ed] text-center">
               <Link href="/sync" className="text-[11px] font-black uppercase tracking-widest text-[#1e4d92] hover:underline flex items-center justify-center gap-2">
                 View Full Execution History <ArrowRight className="w-3 h-3" />
               </Link>
            </div>
          </Card>
        </div>

        {/* Supplier Health */}
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-[#1e1e24] flex items-center gap-2">
            <Layers className="w-5 h-5 text-[#1e4d92]" />
            Supplier Connectivity
          </h2>
          <Card className="border-[#cfccc8] bg-white/50 backdrop-blur-sm overflow-hidden">
            <div className="p-5 space-y-6">
              {suppliers.map((s) => (
                <div key={s.id} className="flex items-center justify-between group">
                  <div className="flex items-center gap-3">
                    <div className={`w-2.5 h-2.5 rounded-full ${s.is_active ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-[#cfccc8]'}`} />
                    <div>
                      <div className="font-bold text-[#1e1e24] text-[13px] group-hover:text-[#1e4d92] transition-colors">{s.name}</div>
                      <div className="text-[10px] font-bold text-[#888894] uppercase tracking-wider">{s.product_count.toLocaleString()} Products</div>
                    </div>
                  </div>
                  <Link href={`/suppliers`} className="opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-[#888894]">
                      <ArrowRight className="w-4 h-4" />
                    </Button>
                  </Link>
                </div>
              ))}
            </div>
            <div className="p-4 bg-[#f9f7f4]/30 border-t border-[#f2f0ed]">
               <Button variant="outline" className="w-full border-[#cfccc8] h-9 text-[11px] font-black uppercase tracking-widest" asChild>
                 <Link href="/suppliers">Manage Connections</Link>
               </Button>
            </div>
          </Card>
        </div>

      </div>

      <style jsx global>{`
        @keyframes spin-slow {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .animate-spin-slow {
          animation: spin-slow 3s linear infinite;
        }
      `}</style>
    </div>
  );
}

function StatCard({ title, value, icon, color, subText }: { title: string, value: string | number, icon: React.ReactNode, color: string, subText: string }) {
  const colorMap: Record<string, string> = {
    blue: "from-blue-50 to-white border-blue-100",
    indigo: "from-indigo-50 to-white border-indigo-100",
    emerald: "from-emerald-50 to-white border-emerald-100",
  };

  return (
    <Card className={`p-6 border bg-gradient-to-br ${colorMap[color]} shadow-sm hover:shadow-md transition-all duration-300 group overflow-hidden relative`}>
      <div className="absolute -right-4 -bottom-4 opacity-[0.03] group-hover:opacity-[0.07] transition-opacity scale-150">
        {icon}
      </div>
      <div className="flex items-center gap-3 mb-4">
        <div className={`p-2 rounded-xl bg-white shadow-sm border ${colorMap[color].split(' ')[2]}`}>
          {icon}
        </div>
        <span className="text-[11px] font-black uppercase tracking-widest text-[#888894]">{title}</span>
      </div>
      <div className="flex flex-col">
        <div className="text-3xl font-black text-[#1e1e24] tracking-tighter">{value}</div>
        <div className="text-[11px] font-bold text-[#888894] mt-1">{subText}</div>
      </div>
    </Card>
  );
}
