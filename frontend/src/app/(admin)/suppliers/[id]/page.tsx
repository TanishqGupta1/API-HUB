"use client";

import React, { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import { Supplier } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { ArrowLeft, ShieldCheck, Trash2, Lock, Globe, Package, Calendar, Activity } from "lucide-react";

export default function SupplierDetailPage() {
  const router = useRouter();
  const { id } = useParams();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
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
    const { id: _id, created_at, product_count, ...updateData } = supplier;
    try {
      await api(`/api/suppliers/${id}`, {
        method: "PATCH",
        body: JSON.stringify(updateData),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      alert("Failed to save changes.");
    } finally {
      setSaving(false);
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
              <div className="flex items-center rounded-lg border border-[#cfccc8] overflow-hidden text-[12px] font-semibold">
                <button
                  type="button"
                  onClick={() => handleToggleActive(false)}
                  className={`px-4 py-2 transition-colors ${!supplier.is_active ? "bg-red-600 text-white" : "bg-white text-[#888894] hover:bg-[#f2f0ed]"}`}
                >
                  Inactive
                </button>
                <button
                  type="button"
                  onClick={() => handleToggleActive(true)}
                  className={`px-4 py-2 transition-colors ${supplier.is_active ? "bg-emerald-600 text-white" : "bg-white text-[#888894] hover:bg-[#f2f0ed]"}`}
                >
                  Active
                </button>
              </div>
            </div>

            <div className="p-6 space-y-5">
              <div>
                <label className="block text-[13px] font-semibold text-[#484852] mb-1.5">Base API URL</label>
                <Input
                  value={supplier.base_url || ""}
                  onChange={(e) => setSupplier({ ...supplier, base_url: e.target.value })}
                  className="h-11 border-[#cfccc8] font-mono text-[13px]"
                  placeholder="https://api.supplier.com"
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

            <div className="p-6 grid grid-cols-2 gap-5">
              {Object.entries(supplier.auth_config || {}).map(([key, val]) => (
                <div key={key}>
                  <label className="block text-[13px] font-semibold text-[#484852] mb-1.5">
                    {formatKey(key)}
                  </label>
                  <Input
                    type={key.includes("password") || key.includes("secret") || key.includes("key") ? "password" : "text"}
                    value={val as string}
                    onChange={(e) => setSupplier({ ...supplier, auth_config: { ...supplier.auth_config, [key]: e.target.value } })}
                    className="h-11 border-[#cfccc8] font-mono text-[13px]"
                  />
                </div>
              ))}
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
