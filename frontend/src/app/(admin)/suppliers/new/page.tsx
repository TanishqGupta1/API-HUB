"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import { 
  Globe, 
  ArrowLeft, 
  ShieldCheck, 
  Zap, 
  Database,
  Lock,
  Cloud
} from "lucide-react";

export default function NewSupplierPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    slug: "",
    protocol: "soap",
    base_url: "",
    promostandards_code: "",
    auth_config: {
      username: "",
      password: "",
      api_key: ""
    }
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api("/api/suppliers", {
        method: "POST",
        body: JSON.stringify(formData),
      });
      router.push("/suppliers");
    } catch (err) {
      alert("Failed to create supplier. Make sure the slug is unique.");
    } finally {
      setLoading(false);
    }
  };

  const updateAuth = (key: string, val: string) => {
    setFormData({
      ...formData,
      auth_config: { ...formData.auth_config, [key]: val }
    });
  };

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => router.back()} className="text-[#888894]">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <div>
          <h1 className="text-2xl font-black text-[#1e1e24] tracking-tight flex items-center gap-2">
            <PlusIcon />
            Register New Supplier
          </h1>
          <p className="text-sm text-[#888894] font-medium">Add a new data source to your universal catalog.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-8">
        
        {/* Basic Info */}
        <div className="md:col-span-2 space-y-6">
          <Card className="p-6 border-[#cfccc8] shadow-sm space-y-6">
            <div className="flex items-center gap-2 text-[11px] font-black uppercase tracking-widest text-[#1e4d92] border-b border-[#f2f0ed] pb-4">
              <Globe className="w-3.5 h-3.5" />
              Core Identity
            </div>
            
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">Supplier Name</label>
                <Input 
                  placeholder="e.g. SanMar" 
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="h-11 border-[#cfccc8] focus:ring-[#1e4d92]"
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">System Slug (Unique)</label>
                <Input 
                  placeholder="e.g. sanmar" 
                  value={formData.slug}
                  onChange={(e) => setFormData({...formData, slug: e.target.value.toLowerCase().replace(/\s+/g, '-')})}
                  className="h-11 border-[#cfccc8] font-mono"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">Protocol / Method</label>
              <Select value={formData.protocol} onValueChange={(val) => setFormData({...formData, protocol: val})}>
                <SelectTrigger className="h-11 border-[#cfccc8]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="soap">PromoStandards (SOAP)</SelectItem>
                  <SelectItem value="rest">REST API (JSON)</SelectItem>
                  <SelectItem value="sftp">SFTP / CSV</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">Base API URL</label>
              <Input 
                placeholder="https://api.supplier.com/v1" 
                value={formData.base_url}
                onChange={(e) => setFormData({...formData, base_url: e.target.value})}
                className="h-11 border-[#cfccc8]"
              />
            </div>
          </Card>

          <Card className="p-6 border-[#cfccc8] shadow-sm space-y-6">
            <div className="flex items-center gap-2 text-[11px] font-black uppercase tracking-widest text-[#1e4d92] border-b border-[#f2f0ed] pb-4">
              <Lock className="w-3.5 h-3.5" />
              Authentication Credentials
            </div>
            
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">Username / Client ID</label>
                <Input 
                  type="text"
                  value={formData.auth_config.username}
                  onChange={(e) => updateAuth('username', e.target.value)}
                  className="h-11 border-[#cfccc8]"
                />
              </div>
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">Password / Secret</label>
                <Input 
                  type="password"
                  value={formData.auth_config.password}
                  onChange={(e) => updateAuth('password', e.target.value)}
                  className="h-11 border-[#cfccc8]"
                />
              </div>
            </div>

            {formData.protocol === 'rest' && (
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">API Key (Header)</label>
                <Input 
                  type="text"
                  value={formData.auth_config.api_key}
                  onChange={(e) => updateAuth('api_key', e.target.value)}
                  className="h-11 border-[#cfccc8]"
                />
              </div>
            )}
          </Card>
        </div>

        {/* Sidebar Info */}
        <div className="space-y-6">
          <Card className="p-6 bg-[#1e4d92] text-white border-none shadow-xl shadow-blue-900/20">
            <h4 className="font-black uppercase tracking-widest text-[10px] opacity-70 mb-4">Registration Guide</h4>
            <div className="space-y-4">
              <div className="flex gap-3">
                <div className="w-6 h-6 rounded bg-white/10 flex items-center justify-center shrink-0">
                  <ShieldCheck className="w-3.5 h-3.5" />
                </div>
                <p className="text-[11px] font-medium leading-relaxed">System slugs must be unique and alphanumeric.</p>
              </div>
              <div className="flex gap-3">
                <div className="w-6 h-6 rounded bg-white/10 flex items-center justify-center shrink-0">
                  <Zap className="w-3.5 h-3.5" />
                </div>
                <p className="text-[11px] font-medium leading-relaxed">PromoStandards (SOAP) requires a valid company code.</p>
              </div>
              <div className="flex gap-3">
                <div className="w-6 h-6 rounded bg-white/10 flex items-center justify-center shrink-0">
                  <Cloud className="w-3.5 h-3.5" />
                </div>
                <p className="text-[11px] font-medium leading-relaxed">Base URLs should include the protocol (https://).</p>
              </div>
            </div>
            
            <Button 
              type="submit" 
              className="w-full mt-8 bg-white text-[#1e4d92] hover:bg-blue-50 font-black uppercase tracking-widest text-[11px] h-12"
              disabled={loading}
            >
              {loading ? "Connecting..." : "Initialize Connection"}
            </Button>
          </Card>

          <div className="p-6 rounded-2xl border border-dashed border-[#cfccc8] bg-[#f9f7f4]/50">
             <div className="flex items-center gap-2 mb-2">
                <Database className="w-4 h-4 text-[#888894]" />
                <span className="text-[11px] font-black uppercase tracking-widest text-[#888894]">Connection Test</span>
             </div>
             <p className="text-[10px] font-medium text-[#888894] leading-relaxed">
               Once created, the system will attempt to ping the base URL and verify credentials.
             </p>
          </div>
        </div>

      </form>
    </div>
  );
}

function PlusIcon() {
  return (
    <div className="w-8 h-8 rounded-xl bg-[#f9f7f4] border border-[#cfccc8] flex items-center justify-center text-[#1e4d92]">
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        <line x1="12" y1="5" x2="12" y2="19"></line>
        <line x1="5" y1="12" x2="19" y2="12"></line>
      </svg>
    </div>
  );
}
