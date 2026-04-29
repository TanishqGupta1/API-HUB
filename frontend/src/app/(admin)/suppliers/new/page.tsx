"use client";

import React, { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Globe, ArrowLeft, Lock, Zap, ShieldCheck, Cloud, Database } from "lucide-react";

type AuthFieldType = "text" | "password" | "number";
interface AuthField {
  key: string;
  label: string;
  type?: AuthFieldType;
  placeholder?: string;
  required?: boolean;
  default?: string;
}

interface ProtocolDef {
  value: string;
  label: string;
  base_url_label: string;
  base_url_default?: string;
  fields: AuthField[];
}

const PROTOCOLS: ProtocolDef[] = [
  {
    value: "promostandards",
    label: "PromoStandards (SOAP)",
    base_url_label: "PS Directory Base URL",
    base_url_default: "https://promostandards.org/api",
    fields: [
      { key: "id", label: "Username (ID)", required: true, placeholder: "your sanmar.com username" },
      { key: "password", label: "Password", type: "password", required: true },
      { key: "customer_number", label: "Customer Number", type: "number", placeholder: "e.g. 157718" },
    ],
  },
  {
    value: "soap",
    label: "Generic SOAP",
    base_url_label: "WSDL Base URL",
    fields: [
      { key: "id", label: "Username (ID)", required: true },
      { key: "password", label: "Password", type: "password", required: true },
      { key: "customer_number", label: "Customer Number", type: "number" },
    ],
  },
  {
    value: "rest",
    label: "REST (HTTP Basic) — S&S Activewear",
    base_url_label: "API Base URL",
    base_url_default: "https://api.ssactivewear.com",
    fields: [
      { key: "username", label: "Account # / Username", required: true },
      { key: "password", label: "API Password", type: "password", required: true },
    ],
  },
  {
    value: "rest_hmac",
    label: "REST + HMAC — 4Over",
    base_url_label: "API Base URL",
    base_url_default: "https://api.4over.com",
    fields: [
      { key: "client_id", label: "Client ID", required: true },
      { key: "client_secret", label: "Client Secret", type: "password", required: true },
    ],
  },
  {
    value: "sftp",
    label: "SFTP / CSV — SanMar",
    base_url_label: "SFTP Host:Port",
    base_url_default: "ftp.sanmar.com:2200",
    fields: [
      { key: "host", label: "SFTP Host", required: true, default: "ftp.sanmar.com" },
      { key: "port", label: "Port", type: "number", required: true, default: "2200" },
      { key: "username", label: "Username", required: true },
      { key: "password", label: "Password", type: "password", required: true },
    ],
  },
  {
    value: "ops_graphql",
    label: "OnPrintShop GraphQL (OAuth2)",
    base_url_label: "OPS Base URL",
    base_url_default: "https://yourshop.onprintshop.com",
    fields: [
      { key: "client_id", label: "OAuth2 Client ID", required: true },
      { key: "client_secret", label: "OAuth2 Client Secret", type: "password", required: true },
      { key: "token_url", label: "Token URL", placeholder: "https://yourshop.onprintshop.com/oauth/token" },
      { key: "store_url", label: "Store URL", placeholder: "https://yourshop.onprintshop.com" },
    ],
  },
];

const PRESETS = [
  {
    label: "SanMar",
    sub: "PromoStandards · SOAP",
    icon: "S",
    data: {
      name: "SanMar", slug: "sanmar", protocol: "promostandards",
      promostandards_code: "SANMAR", base_url: "https://promostandards.org/api",
      auth_config: { id: "", password: "", customer_number: "" } as Record<string, string>,
    },
  },
  {
    label: "SanMar SFTP",
    sub: "SFTP / CSV",
    icon: "S",
    data: {
      name: "SanMar SFTP", slug: "sanmar-sftp", protocol: "sftp",
      promostandards_code: "", base_url: "ftp.sanmar.com:2200",
      auth_config: { host: "ftp.sanmar.com", port: "2200", username: "", password: "" } as Record<string, string>,
    },
  },
];

export default function NewSupplierPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [protocol, setProtocol] = useState("promostandards");
  const [promostandardsCode, setPromostandardsCode] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [authConfig, setAuthConfig] = useState<Record<string, string>>({});

  const def = useMemo(() => PROTOCOLS.find((p) => p.value === protocol) ?? PROTOCOLS[0], [protocol]);

  function changeProtocol(next: string) {
    setProtocol(next);
    const nextDef = PROTOCOLS.find((p) => p.value === next);
    if (!nextDef) return;
    const fresh: Record<string, string> = {};
    for (const f of nextDef.fields) fresh[f.key] = f.default ?? "";
    setAuthConfig(fresh);
    if (nextDef.base_url_default && !baseUrl) setBaseUrl(nextDef.base_url_default);
  }

  function applyPreset(preset: typeof PRESETS[0]["data"]) {
    setName(preset.name);
    setSlug(preset.slug);
    setProtocol(preset.protocol);
    setPromostandardsCode(preset.promostandards_code);
    setBaseUrl(preset.base_url);
    setAuthConfig({ ...preset.auth_config });
  }

  function updateAuth(key: string, val: string) {
    setAuthConfig((prev) => ({ ...prev, [key]: val }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const trimmedAuth: Record<string, string | number> = {};
      for (const [k, v] of Object.entries(authConfig)) {
        if (v === undefined || v === null || v === "") continue;
        const fdef = def.fields.find((f) => f.key === k);
        trimmedAuth[k] = fdef?.type === "number" ? Number(v) : v;
      }
      await api("/api/suppliers", {
        method: "POST",
        body: JSON.stringify({
          name, slug, protocol,
          promostandards_code: promostandardsCode || null,
          base_url: baseUrl || null,
          auth_config: trimmedAuth,
        }),
      });
      router.push("/suppliers");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to create supplier.";
      alert(`${msg}\n\nMake sure the slug is unique.`);
    } finally {
      setLoading(false);
    }
  }

  const labelCls = "block text-[13px] font-semibold text-[#484852] mb-1.5";
  const hintCls = "text-[11px] text-[#888894] mt-1.5 leading-relaxed";

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
        <h1 className="text-[28px] font-extrabold text-[#1e1e24] tracking-tight">Register New Supplier</h1>
        <p className="text-[14px] text-[#888894] mt-1">Add a data source to your universal catalog.</p>
      </div>

      {/* Quick-fill presets */}
      <div className="mb-8">
        <p className="text-[11px] font-bold uppercase tracking-widest text-[#888894] mb-3">Quick Presets</p>
        <div className="flex gap-3">
          {PRESETS.map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => applyPreset(p.data)}
              className="flex items-center gap-3 px-4 py-3 bg-white border-2 border-[#cfccc8] rounded-xl hover:border-[#1e4d92] hover:bg-[#eef4fb] transition-all group"
            >
              <div className="w-8 h-8 rounded-lg bg-[#1e4d92] text-white text-[13px] font-black flex items-center justify-center">
                {p.icon}
              </div>
              <div className="text-left">
                <div className="text-[13px] font-bold text-[#1e1e24] group-hover:text-[#1e4d92]">{p.label}</div>
                <div className="text-[11px] text-[#888894]">{p.sub}</div>
              </div>
              <Zap className="w-3.5 h-3.5 text-[#cfccc8] group-hover:text-[#1e4d92] ml-1" />
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left: form */}
        <div className="lg:col-span-2 space-y-6">

          {/* Section 1: Identity */}
          <div className="bg-white border border-[#cfccc8] rounded-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-[#f2f0ed] flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-[#eef4fb] flex items-center justify-center">
                <Globe className="w-3.5 h-3.5 text-[#1e4d92]" />
              </div>
              <span className="text-[13px] font-bold text-[#1e1e24]">Supplier Identity</span>
            </div>
            <div className="p-6 space-y-5">
              <div className="grid grid-cols-2 gap-5">
                <div>
                  <label className={labelCls}>Supplier Name</label>
                  <Input
                    placeholder="e.g. SanMar"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="h-11 border-[#cfccc8] focus:ring-[#1e4d92] text-[14px]"
                    required
                  />
                </div>
                <div>
                  <label className={labelCls}>System Slug <span className="text-[#888894] font-normal">(unique)</span></label>
                  <Input
                    placeholder="e.g. sanmar"
                    value={slug}
                    onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/\s+/g, "-"))}
                    className="h-11 border-[#cfccc8] font-mono text-[13px]"
                    required
                  />
                  <p className={hintCls}>Lowercase, no spaces. Used as the internal ID.</p>
                </div>
              </div>

              <div>
                <label className={labelCls}>Protocol / Method</label>
                <Select value={protocol} onValueChange={changeProtocol}>
                  <SelectTrigger className="h-11 border-[#cfccc8] text-[14px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PROTOCOLS.map((p) => (
                      <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {(protocol === "promostandards" || protocol === "soap") && (
                <div>
                  <label className={labelCls}>PromoStandards Code</label>
                  <Input
                    placeholder="e.g. SANMAR"
                    value={promostandardsCode}
                    onChange={(e) => setPromostandardsCode(e.target.value.toUpperCase())}
                    className="h-11 border-[#cfccc8] font-mono text-[13px]"
                  />
                  <p className={hintCls}>Used to look up WSDL endpoints in the PromoStandards directory.</p>
                </div>
              )}

              <div>
                <label className={labelCls}>{def.base_url_label}</label>
                <Input
                  placeholder={def.base_url_default ?? "https://api.supplier.com/v1"}
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  className="h-11 border-[#cfccc8] font-mono text-[13px]"
                />
              </div>
            </div>
          </div>

          {/* Section 2: Auth */}
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
            <div className="p-6">
              <div className="grid grid-cols-2 gap-5">
                {def.fields.map((f) => (
                  <div key={f.key} className={f.type === "number" && def.fields.length % 2 !== 0 ? "" : ""}>
                    <label className={labelCls}>
                      {f.label}
                      {f.required && <span className="ml-1 text-[#b93232]">*</span>}
                    </label>
                    <Input
                      type={f.type === "password" ? "password" : f.type === "number" ? "number" : "text"}
                      placeholder={f.placeholder ?? ""}
                      value={authConfig[f.key] ?? ""}
                      onChange={(e) => updateAuth(f.key, e.target.value)}
                      className={`h-11 border-[#cfccc8] text-[14px] ${f.type !== "text" ? "font-mono" : ""}`}
                      required={f.required}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full h-12 bg-[#1e4d92] hover:bg-[#173d74] text-white font-bold text-[14px] rounded-xl shadow-[0_3px_0_#143566] active:shadow-none active:translate-y-[2px] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Connecting…" : "Initialize Connection"}
          </button>
        </div>

        {/* Right: guide */}
        <div className="space-y-4">
          <div className="bg-[#1e4d92] rounded-2xl p-5 text-white">
            <p className="text-[10px] font-black uppercase tracking-widest opacity-60 mb-4">Registration Guide</p>
            <div className="space-y-4">
              {[
                { icon: ShieldCheck, text: "System slugs must be unique and alphanumeric." },
                { icon: Zap, text: "Use a preset above to prefill protocol and credential fields automatically." },
                { icon: Cloud, text: "PromoStandards code drives WSDL endpoint resolution from the public directory." },
              ].map(({ icon: Icon, text }, i) => (
                <div key={i} className="flex gap-3">
                  <div className="w-6 h-6 rounded bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <p className="text-[12px] leading-relaxed opacity-90">{text}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white border border-dashed border-[#cfccc8] rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-2">
              <Database className="w-4 h-4 text-[#888894]" />
              <span className="text-[12px] font-bold text-[#484852]">After Registration</span>
            </div>
            <p className="text-[12px] text-[#888894] leading-relaxed">
              Go to the supplier detail page and use <span className="font-semibold text-[#484852]">Refresh Endpoints</span> to verify credentials and start syncing.
            </p>
          </div>
        </div>
      </form>
    </div>
  );
}
