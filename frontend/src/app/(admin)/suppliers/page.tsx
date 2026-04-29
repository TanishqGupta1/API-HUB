"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import { Supplier } from "@/lib/types";
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

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await api<Supplier[]>("/api/suppliers");
        setSuppliers(data);
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
        <Button className="bg-[#1e4d92] hover:bg-[#173d74] font-bold text-xs uppercase tracking-wider shadow-lg shadow-blue-900/10 px-8 h-11" asChild>
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
        {suppliers.map((s) => (
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
                <div className={`w-2 h-2 rounded-full mt-2 ${s.is_active ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]' : 'bg-[#cfccc8]'}`} />
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
                  <div className="text-[9px] font-black uppercase tracking-widest text-[#888894] mb-1">Auth Type</div>
                  <div className="text-[10px] font-black uppercase tracking-tight text-[#1e1e24]">
                    {s.protocol === 'soap' ? 'SOAP XML' : s.protocol === 'sftp' ? 'SSH Key' : 'REST API'}
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
        ))}
      </div>

      {/* Empty State */}
      {!loading && suppliers.length === 0 && (
        <div className="text-center py-20 bg-[#f9f7f4] rounded-3xl border-2 border-dashed border-[#cfccc8]">
          <div className="w-16 h-16 rounded-2xl bg-white border border-[#cfccc8] flex items-center justify-center text-3xl mx-auto mb-6 shadow-sm">📡</div>
          <h3 className="text-xl font-black text-[#1e1e24] mb-2 tracking-tight">No Suppliers Connected</h3>
          <p className="text-[13px] text-[#888894] max-w-sm mx-auto font-medium leading-relaxed mb-6">
            Start building your data hub by connecting your first supplier via SOAP, REST, or SFTP.
          </p>
          <Button className="bg-[#1e4d92] hover:bg-[#173d74] font-black text-xs uppercase tracking-widest px-8" asChild>
            <Link href="/suppliers/new">Register Now</Link>
          </Button>
        </div>
      )}

    </div>
  );
}
