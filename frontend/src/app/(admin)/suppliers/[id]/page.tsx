"use client";

import React, { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import { Supplier } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { 
  Settings2, 
  ArrowLeft, 
  Save, 
  ShieldCheck, 
  Trash2,
  Lock,
  Globe
} from "lucide-react";

export default function SupplierDetailPage() {
  const router = useRouter();
  const { id } = useParams();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [supplier, setSupplier] = useState<Supplier | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await api<Supplier>(`/api/suppliers/${id}`);
        setSupplier(data);
      } catch (e) {
        log.error("Failed to load supplier", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  const handleSave = async () => {
    if (!supplier) return;
    setSaving(true);
    const { id: _id, created_at, product_count, ...updateData } = supplier;
    try {
      await api(`/api/suppliers/${id}`, {
        method: "PATCH",
        body: JSON.stringify(updateData),
      });
      router.push("/suppliers");
    } catch (err) {
      alert("Failed to save changes.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to remove this supplier and all its product associations?")) return;
    try {
      await api(`/api/suppliers/${id}`, { method: "DELETE" });
      router.push("/suppliers");
    } catch (err) {
      alert("Failed to delete supplier.");
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-[60vh] flex-col gap-4">
      <div className="w-8 h-8 border-[3px] border-[#1e4d92] border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (!supplier) return <div className="p-20 text-center">Supplier not found.</div>;

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.back()} className="text-[#888894]">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-2xl font-black text-[#1e1e24] tracking-tight flex items-center gap-2">
              <Settings2 className="w-6 h-6 text-[#1e4d92]" />
              {supplier.name}
            </h1>
            <p className="text-sm text-[#888894] font-medium uppercase tracking-widest text-[10px]">
              Protocol: {supplier.protocol} • Slug: {supplier.slug}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button 
            variant="outline" 
            className="border-rose-200 text-rose-600 hover:bg-rose-50 font-bold text-xs uppercase tracking-wider"
            onClick={handleDelete}
          >
            <Trash2 className="w-4 h-4 mr-2" />
            Delete
          </Button>
          <Button 
            className="bg-[#1e4d92] hover:bg-[#173d74] text-white font-bold text-xs uppercase tracking-wider shadow-lg shadow-blue-900/10 px-8"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        
        <div className="md:col-span-2 space-y-6">
          <Card className="p-6 border-[#cfccc8] shadow-sm space-y-6">
            <div className="flex items-center justify-between border-b border-[#f2f0ed] pb-4">
              <div className="flex items-center gap-2 text-[11px] font-black uppercase tracking-widest text-[#1e4d92]">
                <Globe className="w-3.5 h-3.5" />
                Connection Settings
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-black uppercase text-[#888894]">Active Status</span>
                <Switch 
                  checked={supplier.is_active} 
                  onCheckedChange={(val) => setSupplier({...supplier, is_active: val})}
                />
              </div>
            </div>
            
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">Base API URL</label>
                <Input 
                  value={supplier.base_url || ""}
                  onChange={(e) => setSupplier({...supplier, base_url: e.target.value})}
                  className="h-11 border-[#cfccc8] font-mono text-[13px]"
                />
              </div>
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">PromoStandards Code</label>
                <Input 
                  value={supplier.promostandards_code || ""}
                  onChange={(e) => setSupplier({...supplier, promostandards_code: e.target.value})}
                  className="h-11 border-[#cfccc8] font-mono text-[13px]"
                />
              </div>
            </div>
          </Card>

          <Card className="p-6 border-[#cfccc8] shadow-sm space-y-6">
            <div className="flex items-center gap-2 text-[11px] font-black uppercase tracking-widest text-[#1e4d92] border-b border-[#f2f0ed] pb-4">
              <Lock className="w-3.5 h-3.5" />
              Auth Configuration
            </div>
            
            <div className="grid grid-cols-1 gap-6">
              {Object.entries(supplier.auth_config || {}).map(([key, val]) => (
                <div key={key} className="space-y-2">
                  <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">{key}</label>
                  <Input 
                    type={key.includes('password') || key.includes('key') ? 'password' : 'text'}
                    value={val as string}
                    onChange={(e) => {
                      const newAuth = { ...supplier.auth_config, [key]: e.target.value };
                      setSupplier({ ...supplier, auth_config: newAuth });
                    }}
                    className="h-11 border-[#cfccc8]"
                  />
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-6">
           <Card className="p-6 bg-[#f9f7f4] border-[#cfccc8] shadow-sm">
             <h4 className="text-[11px] font-black uppercase tracking-widest text-[#1e4d92] mb-4">Health Monitor</h4>
             <div className="space-y-4">
                <div className="flex items-center justify-between">
                   <span className="text-[11px] font-bold text-[#888894]">Inventory Count</span>
                   <span className="text-[11px] font-black text-[#1e1e24]">{supplier.product_count?.toLocaleString()}</span>
                </div>
                <div className="flex items-center justify-between">
                   <span className="text-[11px] font-bold text-[#888894]">Created At</span>
                   <span className="text-[11px] font-black text-[#1e1e24]">{new Date(supplier.created_at).toLocaleDateString()}</span>
                </div>
                <div className="pt-4 border-t border-[#cfccc8] border-dashed">
                  <div className="flex items-center gap-2 text-emerald-600">
                    <ShieldCheck className="w-4 h-4" />
                    <span className="text-[10px] font-black uppercase tracking-widest">Encrypted Auth</span>
                  </div>
                </div>
             </div>
           </Card>
        </div>

      </div>
    </div>
  );
}
