"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import { Customer } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Plus, 
  Settings2, 
  Globe, 
  Layout, 
  ShieldCheck, 
  ChevronRight,
  ExternalLink,
  Activity,
  Trash2,
  Lock,
  X
} from "lucide-react";

export default function StorefrontsPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await api<Customer[]>("/api/customers");
        setCustomers(data);
      } catch (e) {
        log.error("Failed to load storefronts", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleDeactivate = async (id: string, current: boolean) => {
    try {
      await api(`/api/customers/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !current })
      });
      setCustomers(prev => prev.map(c => c.id === id ? { ...c, is_active: !current } : c));
    } catch (e) {
      alert("Failed to update status");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh] flex-col gap-4">
        <div className="w-10 h-10 border-[3px] border-[#1e4d92] border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-[#888894] font-medium animate-pulse">Initializing Storefront Controller...</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-700">
      
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h1 className="text-3xl font-black text-[#1e1e24] tracking-tight flex items-center gap-3">
            <Layout className="w-8 h-8 text-[#1e4d92]" />
            Storefront Directory
          </h1>
          <p className="text-[#888894] mt-1 font-medium">Manage and publish to your independent storefront instances.</p>
        </div>
        <Button className="bg-[#1e4d92] hover:bg-[#173d74] text-white font-bold text-xs uppercase tracking-wider shadow-lg shadow-blue-900/10 px-8 h-11" onClick={() => setShowAdd(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Add Storefront
        </Button>
      </div>

      {/* Global Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
         <div className="bg-[#f9f7f4] border border-[#cfccc8] rounded-2xl p-5 flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-white border border-[#cfccc8] flex items-center justify-center text-[#1e4d92] shadow-sm">
               <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
               <div className="text-[10px] font-black uppercase tracking-widest text-[#888894]">Active Nodes</div>
               <div className="text-xl font-black text-[#1e1e24] leading-tight">{customers.filter(c => c.is_active).length} Instances</div>
            </div>
         </div>
         <div className="bg-[#f9f7f4] border border-[#cfccc8] rounded-2xl p-5 flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-white border border-[#cfccc8] flex items-center justify-center text-[#1e4d92] shadow-sm">
               <Activity className="w-5 h-5" />
            </div>
            <div>
               <div className="text-[10px] font-black uppercase tracking-widest text-[#888894]">Total Pushed</div>
               <div className="text-xl font-black text-[#1e1e24] leading-tight">
                 {customers.reduce((acc, c) => acc + (c.products_pushed || 0), 0).toLocaleString()} SKUs
               </div>
            </div>
         </div>
         <div className="bg-[#f9f7f4] border border-[#cfccc8] rounded-2xl p-5 flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-white border border-[#cfccc8] flex items-center justify-center text-[#1e4d92] shadow-sm">
               <Lock className="w-5 h-5" />
            </div>
            <div>
               <div className="text-[10px] font-black uppercase tracking-widest text-[#888894]">Auth Method</div>
               <div className="text-xl font-black text-[#1e1e24] leading-tight">OAuth 2.0</div>
            </div>
         </div>
      </div>

      {/* Storefront Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {customers.map((c) => (
          <Card key={c.id} className="border-[#cfccc8] overflow-hidden bg-white hover:border-[#1e4d92] transition-all hover:shadow-xl hover:shadow-blue-900/5 group">
            <div className="p-6 space-y-6">
              
              {/* Header: Name & Status */}
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-[#f9f7f4] border border-[#cfccc8] flex items-center justify-center text-xl font-black text-[#1e4d92] group-hover:bg-[#1e4d92] group-hover:text-white group-hover:border-[#1e4d92] transition-all duration-300">
                    {c.name[0]}
                  </div>
                  <div>
                    <h3 className="text-lg font-black text-[#1e1e24] tracking-tight group-hover:text-[#1e4d92] transition-colors">{c.name}</h3>
                    <div className="flex items-center gap-2 mt-0.5">
                      <Badge variant="outline" className="bg-[#f9f7f4] border-[#cfccc8] text-[#888894] font-black text-[9px] uppercase tracking-widest h-5">
                        {c.ops_client_id || 'ID-REDACTED'}
                      </Badge>
                      <span className="text-[10px] font-bold text-[#888894] uppercase tracking-widest">PROD Instance</span>
                    </div>
                  </div>
                </div>
                <div className={`w-2 h-2 rounded-full mt-2 ${c.is_active ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]' : 'bg-[#cfccc8]'}`} />
              </div>

              {/* URL & API Info */}
              <div className="bg-[#f9f7f4] rounded-xl p-4 flex items-center justify-between border border-[#f2f0ed]">
                 <div className="flex items-center gap-3">
                    <Globe className="w-4 h-4 text-[#888894]" />
                    <span className="text-xs font-mono font-bold text-[#1e4d92] truncate max-w-[200px]">
                      {c.ops_base_url.replace('https://', '')}
                    </span>
                 </div>
                 <a href={c.ops_base_url} target="_blank" className="text-[#888894] hover:text-[#1e4d92]">
                    <ExternalLink className="w-3.5 h-3.5" />
                 </a>
              </div>

              {/* Metrics Row */}
              <div className="grid grid-cols-3 gap-4 border-y border-[#f2f0ed] py-4">
                <div>
                  <div className="text-[9px] font-black uppercase tracking-widest text-[#888894] mb-1">SKUs Pushed</div>
                  <div className="font-mono font-black text-[#1e1e24] text-sm">{c.products_pushed?.toLocaleString() || 0}</div>
                </div>
                <div>
                  <div className="text-[9px] font-black uppercase tracking-widest text-[#888894] mb-1">Pricing</div>
                  <div className="text-[10px] font-black uppercase tracking-tight text-[#1e4d92]">
                    {c.markup_rules_count || 0} Rules
                  </div>
                </div>
                <div>
                  <div className="text-[9px] font-black uppercase tracking-widest text-[#888894] mb-1">Security</div>
                  <div className="text-[10px] font-black uppercase tracking-tight text-emerald-600">
                    Encrypted
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center justify-between pt-1">
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" className="h-9 px-3 border border-transparent hover:border-[#cfccc8] text-[11px] font-bold text-[#888894] uppercase tracking-wider">
                    <Settings2 className="w-3.5 h-3.5 mr-2" />
                    Configure
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className={`h-9 px-3 border border-transparent hover:border-[#cfccc8] text-[11px] font-bold uppercase tracking-wider ${c.is_active ? 'text-rose-600' : 'text-emerald-600'}`}
                    onClick={() => handleDeactivate(c.id, c.is_active)}
                  >
                    {c.is_active ? 'Deactivate' : 'Activate'}
                  </Button>
                </div>
                <Button size="sm" className="h-9 w-9 p-0 bg-[#f9f7f4] hover:bg-[#1e4d92] text-[#1e4d92] hover:text-white border border-[#cfccc8] transition-all rounded-xl">
                    <ChevronRight className="w-4 h-4" />
                </Button>
              </div>

            </div>
          </Card>
        ))}
      </div>

      {/* Empty State */}
      {!loading && customers.length === 0 && (
        <div className="text-center py-20 bg-[#f9f7f4] rounded-3xl border-2 border-dashed border-[#cfccc8]">
          <div className="w-16 h-16 rounded-2xl bg-white border border-[#cfccc8] flex items-center justify-center text-3xl mx-auto mb-6 shadow-sm">🏪</div>
          <h3 className="text-xl font-black text-[#1e1e24] mb-2 tracking-tight">No Storefronts Detected</h3>
          <p className="text-[13px] text-[#888894] max-w-sm mx-auto font-medium leading-relaxed mb-6">
            Connect your OnPrintShop instances to start publishing normalized product data across your network.
          </p>
          <Button className="bg-[#1e4d92] hover:bg-[#173d74] text-white font-black text-xs uppercase tracking-widest px-8" onClick={() => setShowAdd(true)}>
            Add First Instance
          </Button>
        </div>
      )}

    </div>
  );
}
