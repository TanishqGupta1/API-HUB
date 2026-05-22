"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import { Customer } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft,
  Settings2,
  Save,
  Globe,
  Database,
  Link as LinkIcon,
  ShieldCheck,
  ExternalLink,
  ChevronRight,
  LayoutGrid,
  KeyRound,
  Pencil,
  X,
  CheckCircle2,
  RefreshCw,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

export default function CustomerSettingsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  
  // Guard against placeholder URLs or invalid UUIDs
  const isInvalidId = !id || id.includes("[") || id.includes("{") || id.length < 32;

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(!isInvalidId);
  const [saving, setSaving] = useState(false);

  // Client Secret inline update
  const [showSecretUpdate, setShowSecretUpdate] = useState(false);
  const [newSecret, setNewSecret] = useState("");
  const [savingSecret, setSavingSecret] = useState(false);
  const [savedSecret, setSavedSecret] = useState(false);

  // Master options sync
  const [syncingOptions, setSyncingOptions] = useState(false);
  const [syncResult, setSyncResult] = useState<{ synced: number } | null>(null);

  useEffect(() => {
    if (isInvalidId) return;
    async function load() {
      try {
        const data = await api<Customer>(`/api/customers/${id}`);
        setCustomer(data);
      } catch (e) {
        log.error("Failed to load storefront details", e);
        toast.error("Failed to load storefront details");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, isInvalidId]);

  const handleSave = async () => {
    if (!customer) return;
    setSaving(true);
    try {
      await api(`/api/customers/${id}`, {
        method: "PATCH",
        body: JSON.stringify(customer)
      });
      toast.success("Settings saved successfully");
    } catch (e) {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSecret = async () => {
    if (!newSecret.trim()) return;
    setSavingSecret(true);
    try {
      await api(`/api/customers/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ ops_client_secret: newSecret.trim() }),
      });
      setSavedSecret(true);
      setShowSecretUpdate(false);
      setNewSecret("");
      toast.success("Client Secret updated");
      setTimeout(() => setSavedSecret(false), 3000);
    } catch (e) {
      toast.error("Failed to update Client Secret");
    } finally {
      setSavingSecret(false);
    }
  };

  const handleSyncOptions = async () => {
    setSyncingOptions(true);
    setSyncResult(null);
    try {
      const result = await api<{ synced: number; status: string }>(
        `/api/master-options/sync`,
        { method: "POST" }
      );
      setSyncResult({ synced: result.synced });
      toast.success(`Synced ${result.synced} master options from OPS`);
    } catch (e) {
      toast.error("Failed to sync master options — check OPS credentials");
    } finally {
      setSyncingOptions(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh] flex-col gap-4">
        <div className="w-10 h-10 border-[3px] border-[#1e4d92] border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-[#888894] font-medium">Loading Instance configuration...</p>
      </div>
    );
  }

  if (isInvalidId || !customer) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-center px-6">
        <div className="w-16 h-16 bg-[#fdf2f2] rounded-2xl flex items-center justify-center mb-6 border border-[#f5c6cb]">
          <Database className="w-8 h-8 text-[#b93232]" />
        </div>
        <h2 className="text-xl font-black text-[#1e1e24] mb-2">Invalid Customer ID</h2>
        <p className="text-sm text-[#888894] max-w-xs mb-8 leading-relaxed">
          The ID <code className="bg-[#f9f7f4] px-1.5 py-0.5 rounded font-mono text-[#b93232]">{id}</code> is not a valid identifier. Please pick a customer from the list.
        </p>
        <Button 
          onClick={() => router.push("/customers")}
          className="bg-[#1e4d92] text-white font-bold text-[10px] uppercase tracking-widest h-10 px-6"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Customers
        </Button>
      </div>
    );
  }

  // TypeScript now knows customer is non-null
  const currentCustomer = customer;

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      {/* Breadcrumbs & Actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => router.push("/customers")}
            className="w-10 h-10 rounded-xl bg-white border border-[#cfccc8] flex items-center justify-center text-[#888894] hover:text-[#1e4d92] hover:border-[#1e4d92] transition-all shadow-sm"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-[#888894]">Instance Node</span>
              <ChevronRight className="w-3 h-3 text-[#cfccc8]" />
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-[#1e4d92]">{customer.ops_client_id}</span>
            </div>
            <h1 className="text-2xl font-black text-[#1e1e24] tracking-tight">{customer.name}</h1>
          </div>
        </div>
        <Button 
          onClick={handleSave} 
          disabled={saving}
          className="bg-[#1e4d92] hover:bg-[#173d74] text-white font-bold text-xs uppercase tracking-wider h-11 px-8 shadow-lg shadow-blue-900/10"
        >
          {saving ? "Saving..." : "Save Configuration"}
          <Save className="w-4 h-4 ml-2" />
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column: Basic Info */}
        <div className="lg:col-span-2 space-y-6">
          
          <div className="bg-white rounded-2xl border border-[#cfccc8] shadow-sm overflow-hidden">
            <div className="p-6 border-b border-[#f2f0ed] flex items-center gap-3">
              <Settings2 className="w-5 h-5 text-[#1e4d92]" />
              <h2 className="text-sm font-black uppercase tracking-widest text-[#1e1e24]">General Configuration</h2>
            </div>
            <div className="p-8 space-y-8">
              
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-widest text-[#888894]">Storefront Name</label>
                  <input 
                    type="text" 
                    value={currentCustomer.name}
                    onChange={(e) => setCustomer(prev => prev ? {...prev, name: e.target.value} : null)}
                    className="w-full h-12 px-4 rounded-xl border border-[#cfccc8] text-sm font-bold focus:border-[#1e4d92] focus:ring-4 focus:ring-blue-50 outline-none transition-all"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-widest text-[#888894]">Instance Status</label>
                  <div className="flex items-center gap-3 h-12 px-4 rounded-xl border border-[#cfccc8] bg-[#f9f7f4]">
                    <div className={`w-2.5 h-2.5 rounded-full ${currentCustomer.is_active ? 'bg-emerald-500' : 'bg-[#cfccc8]'}`} />
                    <span className="text-xs font-black uppercase tracking-widest text-[#1e1e24]">
                      {currentCustomer.is_active ? 'Active' : 'Offline'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-widest text-[#888894]">Base URL (OnPrintShop)</label>
                <div className="relative">
                  <Globe className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#888894]" />
                  <input 
                    type="text" 
                    value={currentCustomer.ops_base_url}
                    onChange={(e) => setCustomer(prev => prev ? {...prev, ops_base_url: e.target.value} : null)}
                    className="w-full h-12 pl-12 pr-4 rounded-xl border border-[#cfccc8] text-sm font-bold font-mono text-[#1e4d92] focus:border-[#1e4d92] outline-none transition-all"
                  />
                </div>
              </div>

            </div>
          </div>

          <div className="bg-white rounded-2xl border border-[#cfccc8] shadow-sm overflow-hidden">
            <div className="p-6 border-b border-[#f2f0ed] flex items-center gap-3">
              <ShieldCheck className="w-5 h-5 text-[#1e4d92]" />
              <h2 className="text-sm font-black uppercase tracking-widest text-[#1e1e24]">Authentication Node</h2>
            </div>
            <div className="p-8 space-y-8">
              
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-widest text-[#888894]">OAuth Client ID</label>
                <div className="relative">
                  <Database className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#888894]" />
                  <input 
                    type="text" 
                    value={currentCustomer.ops_client_id}
                    onChange={(e) => setCustomer(prev => prev ? {...prev, ops_client_id: e.target.value} : null)}
                    className="w-full h-12 pl-12 pr-4 rounded-xl border border-[#cfccc8] text-sm font-bold font-mono focus:border-[#1e4d92] outline-none transition-all"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-widest text-[#888894]">Token Endpoint</label>
                <div className="relative">
                  <LinkIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#888894]" />
                  <input
                    type="text"
                    value={currentCustomer.ops_token_url}
                    onChange={(e) => setCustomer(prev => prev ? {...prev, ops_token_url: e.target.value} : null)}
                    className="w-full h-12 pl-12 pr-4 rounded-xl border border-[#cfccc8] text-sm font-bold font-mono focus:border-[#1e4d92] outline-none transition-all"
                  />
                </div>
              </div>

              {/* Client Secret — stored encrypted; never returned by API */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-[10px] font-black uppercase tracking-widest text-[#888894]">OAuth Client Secret</label>
                  {!showSecretUpdate && (
                    <button
                      type="button"
                      onClick={() => { setShowSecretUpdate(true); setSavedSecret(false); }}
                      className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-[#1e4d92] hover:text-[#173d74] transition-colors"
                    >
                      <Pencil className="w-3 h-3" />
                      {savedSecret ? "Updated ✓" : "Update Secret"}
                    </button>
                  )}
                </div>

                {!showSecretUpdate ? (
                  <div className="flex items-center gap-3 h-12 px-4 rounded-xl border border-[#cfccc8] bg-[#f9f7f4]">
                    <KeyRound className="w-4 h-4 text-[#888894]" />
                    {savedSecret ? (
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-[#247a52]" />
                        <span className="text-xs font-bold text-[#247a52]">Secret updated successfully</span>
                      </div>
                    ) : (
                      <span className="text-xs font-bold text-[#888894] tracking-widest">••••••••••••••••</span>
                    )}
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="relative">
                      <KeyRound className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#888894]" />
                      <input
                        type="password"
                        value={newSecret}
                        onChange={(e) => setNewSecret(e.target.value)}
                        placeholder="Enter new client secret"
                        autoFocus
                        className="w-full h-12 pl-12 pr-4 rounded-xl border border-[#1e4d92] text-sm font-mono focus:ring-4 focus:ring-blue-50 outline-none transition-all"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={handleSaveSecret}
                        disabled={savingSecret || !newSecret.trim()}
                        className="flex-1 h-10 rounded-xl bg-[#1e4d92] hover:bg-[#173d74] disabled:opacity-50 text-white font-bold text-[10px] uppercase tracking-widest transition-all"
                      >
                        {savingSecret ? "Saving…" : "Save Secret"}
                      </button>
                      <button
                        type="button"
                        onClick={() => { setShowSecretUpdate(false); setNewSecret(""); }}
                        className="w-10 h-10 rounded-xl border border-[#cfccc8] flex items-center justify-center text-[#888894] hover:text-[#b93232] hover:border-[#b93232] transition-all"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
              </div>

            </div>
          </div>

        </div>

        {/* Right Column: Actions & Quick Stats */}
        <div className="space-y-6">
          
          <div className="bg-[#1e4d92] rounded-2xl p-6 text-white shadow-xl shadow-blue-900/20">
            <h3 className="text-[10px] font-black uppercase tracking-widest opacity-60 mb-4">Node Vitality</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">SKUs Pushed</span>
                <span className="text-lg font-black">{currentCustomer.products_pushed?.toLocaleString() || 0}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Pricing Rules</span>
                <span className="text-lg font-black">{currentCustomer.markup_rules_count || 0}</span>
              </div>
              <div className="pt-4 border-t border-white/10 mt-4 space-y-2">
                <Link
                  href={`/customers/${id}/catalog`}
                  className="flex items-center justify-between p-3 rounded-xl bg-white/10 hover:bg-white/20 transition-all text-xs font-bold"
                >
                  View Product Catalog
                  <LayoutGrid className="w-4 h-4" />
                </Link>
                <a
                  href={currentCustomer.ops_base_url}
                  target="_blank"
                  className="flex items-center justify-between p-3 rounded-xl bg-white/10 hover:bg-white/20 transition-all text-xs font-bold"
                >
                  Visit Storefront
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            </div>
          </div>

          {/* Sync Master Options */}
          <div className="bg-white border border-[#cfccc8] rounded-2xl p-6 space-y-4 shadow-sm">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-[#1e4d92]" />
              <h3 className="text-[10px] font-black uppercase tracking-widest text-[#1e1e24]">Push Mappings</h3>
            </div>
            <p className="text-[11px] text-[#888894] leading-relaxed">
              Pull Color, Size and other option IDs from this OPS instance so PC61 variants can be mapped before pushing.
            </p>
            {syncResult && (
              <div className="flex items-center gap-2 px-3 py-2 bg-[#f0f9f4] border border-[#247a52] rounded-lg">
                <CheckCircle2 className="w-3.5 h-3.5 text-[#247a52] shrink-0" />
                <span className="text-[11px] font-bold text-[#247a52]">
                  {syncResult.synced} master options synced from OPS
                </span>
              </div>
            )}
            <button
              type="button"
              onClick={handleSyncOptions}
              disabled={syncingOptions}
              className="w-full h-10 rounded-xl border-2 border-[#1e4d92] text-[#1e4d92] hover:bg-[#1e4d92] hover:text-white disabled:opacity-50 font-bold text-[10px] uppercase tracking-widest transition-all flex items-center justify-center gap-2"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${syncingOptions ? "animate-spin" : ""}`} />
              {syncingOptions ? "Syncing…" : "Sync Master Options"}
            </button>
          </div>

          <div className="bg-[#fdf2f2] border border-[#f5c6cb] rounded-2xl p-6 space-y-4">
             <h3 className="text-[10px] font-black uppercase tracking-widest text-[#b93232]">Danger Zone</h3>
             <p className="text-[11px] text-[#b93232] font-medium leading-relaxed">
               Deactivating this instance will stop all product syncs immediately. Existing products on the storefront will remain but won&apos;t be updated.
             </p>
             <Button variant="outline" className="w-full border-[#f5c6cb] text-[#b93232] hover:bg-[#b93232] hover:text-white font-bold text-[10px] uppercase tracking-wider h-10 transition-all">
                Terminate Node Connection
             </Button>
          </div>

        </div>

      </div>

    </div>
  );
}
