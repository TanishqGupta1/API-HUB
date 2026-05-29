"use client";

import React, { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import { Supplier } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { ArrowLeft, ShieldCheck, Trash2, Lock, Globe, Package, Calendar, Activity, Cpu, Pencil, X } from "lucide-react";

// Per-protocol credential field definitions (mirrors new/page.tsx)
const AUTH_FIELDS: Record<string, Array<{ key: string; label: string; type?: string }>> = {
  promostandards: [
    { key: "id", label: "PromoStandards ID" },
    { key: "password", label: "Password", type: "password" },
    { key: "customer_number", label: "Customer Number" },
  ],
  soap: [
    { key: "id", label: "ID" },
    { key: "password", label: "Password", type: "password" },
    { key: "customer_number", label: "Customer Number" },
  ],
  rest: [
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
  ],
  hmac: [
    { key: "client_id", label: "Client ID" },
    { key: "client_secret", label: "Client Secret", type: "password" },
  ],
  sftp: [
    { key: "host", label: "Host" },
    { key: "port", label: "Port" },
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
  ],
  ops_graphql: [
    { key: "client_id", label: "Client ID" },
    { key: "client_secret", label: "Client Secret", type: "password" },
    { key: "token_url", label: "Token URL" },
    { key: "store_url", label: "Store URL" },
  ],
};

const ADAPTER_OPTIONS = [
  { value: "", label: "— None (manual / legacy)" },
  { value: "OPSAdapter", label: "OPSAdapter — OnPrintShop GraphQL" },
  { value: "SanMarAdapter", label: "SanMarAdapter — SanMar PromoStandards SOAP" },
  { value: "AlphabroderAdapter", label: "AlphabroderAdapter — Alphabroder PromoStandards SOAP" },
  { value: "SSAdapter", label: "SSAdapter — S&S Activewear REST" },
  { value: "FourOverAdapter", label: "FourOverAdapter — 4Over REST + HMAC" },
  { value: "PromoStandardsAdapter", label: "PromoStandardsAdapter — Generic SOAP" },
];

export default function SupplierDetailPage() {
  const router = useRouter();
  const { id } = useParams();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [showCredUpdate, setShowCredUpdate] = useState(false);
  const [newCreds, setNewCreds] = useState<Record<string, string>>({});
  const [savingCreds, setSavingCreds] = useState(false);
  const [savedCreds, setSavedCreds] = useState(false);

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

  const handleToggleActive = async (val: boolean) => {
    if (!supplier) return;
    setSupplier({ ...supplier, is_active: val });
    try {
      await api(`/api/suppliers/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: val }),
      });
    } catch {
      setSupplier({ ...supplier, is_active: !val });
      alert("Failed to update active status.");
    }
  };

  const handleSave = async () => {
    if (!supplier) return;
    setSaving(true);
    try {
      await api(`/api/suppliers/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: supplier.name,
          base_url: supplier.base_url,
          promostandards_code: supplier.promostandards_code,
          adapter_class: supplier.adapter_class,
        }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      alert("Failed to save changes.");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveCreds = async () => {
    if (!supplier) return;
    const filled = Object.fromEntries(Object.entries(newCreds).filter(([, v]) => v.trim()));
    if (Object.keys(filled).length === 0) return;
    setSavingCreds(true);
    try {
      await api(`/api/suppliers/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ auth_config: filled }),
      });
      setSavedCreds(true);
      setShowCredUpdate(false);
      setNewCreds({});
      // Reload to get updated has_credentials flag
      const updated = await api<Supplier>(`/api/suppliers/${id}`);
      setSupplier(updated);
      setTimeout(() => setSavedCreds(false), 3000);
    } catch {
      alert("Failed to update credentials.");
    } finally {
      setSavingCreds(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Remove this supplier and all its products? This cannot be undone.")) return;
    try {
      await api(`/api/suppliers/${id}`, { method: "DELETE" });
      router.push("/suppliers");
    } catch {
      alert("Failed to delete supplier.");
    }
  };

  const formatKey = (key: string) =>
    key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  if (loading) return (
    <div className="flex items-center justify-center h-[60vh]">
      <div className="w-8 h-8 border-[3px] border-[#1e4d92] border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (!supplier) return <div className="p-20 text-center text-[#888894]">Supplier not found.</div>;

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">

      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 text-[13px] text-[#888894] hover:text-[#1e4d92] transition-colors mb-4 font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Suppliers
        </button>

        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-[#1e4d92] flex items-center justify-center text-white text-2xl font-black shadow-[0_4px_0_#143566]">
              {supplier.name.charAt(0)}
            </div>
            <div>
              <h1 className="text-[28px] font-extrabold text-[#1e1e24] tracking-tight leading-none">
                {supplier.name}
              </h1>
              <div className="flex items-center gap-2 mt-1.5">
                <span className="text-[11px] font-mono font-bold bg-[#eef4fb] text-[#1e4d92] px-2 py-0.5 rounded-md uppercase">
                  {supplier.protocol}
                </span>
                <span className="text-[#b4b4bc]">·</span>
                <span className="text-[12px] font-mono text-[#888894]">{supplier.slug}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleDelete}
              className="flex items-center gap-1.5 px-4 py-2.5 text-[13px] font-semibold text-rose-600 border border-rose-200 rounded-xl hover:bg-rose-50 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              Delete
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className={`flex items-center gap-1.5 px-6 py-2.5 text-[13px] font-bold text-white rounded-xl shadow-[0_3px_0_#143566] active:shadow-none active:translate-y-px transition-all disabled:opacity-50 ${saved ? "bg-emerald-600 shadow-[0_3px_0_#1a5c3e]" : "bg-[#1e4d92] hover:bg-[#173d74]"}`}
            >
              {saving ? "Saving…" : saved ? "✓ Saved" : "Save Changes"}
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left: main form */}
        <div className="lg:col-span-2 space-y-5">

          {/* Connection Settings */}
          <div className="bg-white border border-[#cfccc8] rounded-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-[#f2f0ed] flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-[#eef4fb] flex items-center justify-center">
                  <Globe className="w-3.5 h-3.5 text-[#1e4d92]" />
                </div>
                <span className="text-[13px] font-bold text-[#1e1e24]">Connection Settings</span>
              </div>
              <div className="flex items-center gap-2.5">
                <span className="text-[12px] font-bold text-[#1e1e24]">Active</span>
                <Switch checked={supplier.is_active} onCheckedChange={handleToggleActive} />
                <span className={`text-[12px] font-bold px-2.5 py-0.5 rounded-full ${supplier.is_active ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-600"}`}>
                  {supplier.is_active ? "ON" : "OFF"}
                </span>
              </div>
            </div>

            <div className="p-6 space-y-5">
              <div>
                <label className="block text-[13px] font-semibold text-[#484852] mb-1.5">Supplier Name</label>
                <Input
                  value={supplier.name || ""}
                  onChange={(e) => setSupplier({ ...supplier, name: e.target.value })}
                  className="h-11 border-[#cfccc8] text-[13px]"
                  placeholder="e.g. SanMar"
                />
              </div>

              <div>
                <label className="block text-[13px] font-semibold text-[#484852] mb-1.5">Base URL</label>
                <Input
                  value={supplier.base_url || ""}
                  onChange={(e) => setSupplier({ ...supplier, base_url: e.target.value || null })}
                  className="h-11 border-[#cfccc8] font-mono text-[13px]"
                  placeholder="e.g. https://ws.sanmar.com/promostandards/…"
                />
              </div>

              <div>
                <label className="block text-[13px] font-semibold text-[#484852] mb-1.5">PromoStandards Code</label>
                <Input
                  value={supplier.promostandards_code || ""}
                  onChange={(e) => setSupplier({ ...supplier, promostandards_code: e.target.value })}
                  className="h-11 border-[#cfccc8] font-mono text-[13px] uppercase"
                  placeholder="e.g. SANMAR"
                />
              </div>

              <div>
                <label className="block text-[13px] font-semibold text-[#484852] mb-1.5 flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-[#1e4d92]" />
                  Adapter Class
                </label>
                <select
                  value={supplier.adapter_class || ""}
                  onChange={(e) => setSupplier({ ...supplier, adapter_class: e.target.value || null })}
                  className="w-full h-11 px-3 border border-[#cfccc8] rounded-md bg-white font-mono text-[13px] text-[#1e1e24] focus:outline-none focus:ring-2 focus:ring-[#1e4d92] focus:border-transparent"
                >
                  {ADAPTER_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
                <p className="text-[11px] text-[#888894] mt-1.5">
                  Required for scheduled sync. Must match a registered adapter in the backend.
                </p>
              </div>
            </div>
          </div>

          {/* Auth Configuration */}
          <div className="bg-white border border-[#cfccc8] rounded-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-[#f2f0ed] flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-[#eef4fb] flex items-center justify-center">
                  <Lock className="w-3.5 h-3.5 text-[#1e4d92]" />
                </div>
                <span className="text-[13px] font-bold text-[#1e1e24]">Authentication Credentials</span>
              </div>
              <span className="text-[11px] font-mono text-[#b4b4bc] bg-[#f9f7f4] px-2.5 py-1 rounded-full border border-[#ebe8e3]">
                Fernet-encrypted
              </span>
            </div>

            <div className="p-6 space-y-4">
              {/* Status row */}
              {supplier.has_credentials && !showCredUpdate ? (
                <div className="flex items-center gap-3 p-4 bg-[#f0f9f4] border border-[#247a52]/30 rounded-xl">
                  <ShieldCheck className="w-5 h-5 text-[#247a52] flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-bold text-[#247a52]">
                      Credentials configured
                      {savedCreds && (
                        <span className="ml-2 text-[11px] font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
                          ✓ Updated
                        </span>
                      )}
                    </div>
                    <div className="text-[12px] text-[#247a52]/80 mt-0.5">
                      Stored encrypted — never exposed in API responses.
                    </div>
                  </div>
                  <button
                    onClick={() => { setShowCredUpdate(true); setNewCreds({}); }}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-semibold text-[#1e4d92] border border-[#1e4d92] rounded-lg hover:bg-[#eef4fb] transition-colors shrink-0"
                  >
                    <Pencil className="w-3 h-3" />
                    Update
                  </button>
                </div>
              ) : !supplier.has_credentials && !showCredUpdate ? (
                <div className="flex items-center justify-between gap-3 p-4 bg-[#fdf8f2] border border-[#e8a020]/30 rounded-xl">
                  <div className="flex items-center gap-3">
                    <Lock className="w-5 h-5 text-[#e8a020] flex-shrink-0" />
                    <div className="text-[13px] font-semibold text-[#e8a020]">No credentials set</div>
                  </div>
                  <button
                    onClick={() => { setShowCredUpdate(true); setNewCreds({}); }}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-semibold text-[#1e4d92] border border-[#1e4d92] rounded-lg hover:bg-[#eef4fb] transition-colors shrink-0"
                  >
                    <Pencil className="w-3 h-3" />
                    Add Credentials
                  </button>
                </div>
              ) : null}

              {/* Credential update form */}
              {showCredUpdate && (
                <div className="border border-[#cfccc8] rounded-xl overflow-hidden">
                  <div className="px-4 py-3 bg-[#f9f7f4] border-b border-[#f2f0ed] flex items-center justify-between">
                    <span className="text-[12px] font-bold text-[#484852]">
                      {supplier.has_credentials ? "Replace credentials" : "Enter credentials"}
                    </span>
                    <button
                      onClick={() => { setShowCredUpdate(false); setNewCreds({}); }}
                      className="text-[#888894] hover:text-[#484852] transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="p-4 space-y-3">
                    {supplier.has_credentials && (
                      <p className="text-[11px] text-[#888894]">
                        Only filled fields will be updated. Leave blank to keep the existing value.
                      </p>
                    )}
                    {(AUTH_FIELDS[supplier.protocol] ?? []).map(({ key, label, type }) => (
                      <div key={key}>
                        <label className="block text-[12px] font-semibold text-[#484852] mb-1">{label}</label>
                        <Input
                          type={type ?? "text"}
                          value={newCreds[key] ?? ""}
                          onChange={(e) => setNewCreds((prev) => ({ ...prev, [key]: e.target.value }))}
                          className="h-10 border-[#cfccc8] font-mono text-[13px]"
                          placeholder={type === "password" ? "••••••••" : `Enter ${label.toLowerCase()}`}
                          autoComplete={type === "password" ? "new-password" : "off"}
                        />
                      </div>
                    ))}
                    {(AUTH_FIELDS[supplier.protocol] ?? []).length === 0 && (
                      <p className="text-[12px] text-[#888894] italic">
                        No standard credential fields defined for protocol &quot;{supplier.protocol}&quot;.
                        Use the supplier mappings page to set protocol_config instead.
                      </p>
                    )}
                    <div className="flex gap-2 pt-2">
                      <button
                        onClick={handleSaveCreds}
                        disabled={
                          savingCreds ||
                          Object.values(newCreds).filter(Boolean).length === 0
                        }
                        className="flex-1 py-2 text-[13px] font-bold text-white bg-[#1e4d92] rounded-lg hover:bg-[#173d74] disabled:opacity-40 transition-colors shadow-[0_2px_0_#143566] active:shadow-none active:translate-y-px"
                      >
                        {savingCreds ? "Saving…" : "Save Credentials"}
                      </button>
                      <button
                        onClick={() => { setShowCredUpdate(false); setNewCreds({}); }}
                        className="px-4 py-2 text-[13px] font-semibold text-[#484852] border border-[#cfccc8] rounded-lg hover:border-[#888894] transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right: sidebar */}
        <div className="space-y-4">

          {/* Stats */}
          <div className="bg-white border border-[#cfccc8] rounded-2xl p-5 space-y-4">
            <p className="text-[11px] font-black uppercase tracking-widest text-[#888894]">Overview</p>

            <div className="flex items-center gap-3 p-3 bg-[#f9f7f4] rounded-xl">
              <div className="w-9 h-9 rounded-lg bg-[#eef4fb] flex items-center justify-center">
                <Package className="w-4 h-4 text-[#1e4d92]" />
              </div>
              <div>
                <div className="text-[11px] text-[#888894] font-medium">Products</div>
                <div className="text-[18px] font-extrabold text-[#1e1e24] leading-none mt-0.5">
                  {supplier.product_count?.toLocaleString() ?? "—"}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3 p-3 bg-[#f9f7f4] rounded-xl">
              <div className="w-9 h-9 rounded-lg bg-[#eef4fb] flex items-center justify-center">
                <Calendar className="w-4 h-4 text-[#1e4d92]" />
              </div>
              <div>
                <div className="text-[11px] text-[#888894] font-medium">Added</div>
                <div className="text-[14px] font-bold text-[#1e1e24] mt-0.5">
                  {new Date(supplier.created_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3 p-3 bg-[#f9f7f4] rounded-xl">
              <div className="w-9 h-9 rounded-lg bg-[#eef4fb] flex items-center justify-center">
                <Activity className="w-4 h-4 text-[#1e4d92]" />
              </div>
              <div>
                <div className="text-[11px] text-[#888894] font-medium">Status</div>
                <div className={`text-[13px] font-bold mt-0.5 ${supplier.is_active ? "text-emerald-600" : "text-[#888894]"}`}>
                  {supplier.is_active ? "Active" : "Inactive"}
                </div>
              </div>
            </div>
          </div>

          {/* Security note */}
          <div className="bg-[#f9f7f4] border border-dashed border-[#cfccc8] rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span className="text-[12px] font-bold text-[#484852]">Encrypted Storage</span>
            </div>
            <p className="text-[12px] text-[#888894] leading-relaxed">
              All credentials are stored with AES-128 Fernet encryption. They are never logged or exposed in API responses.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
