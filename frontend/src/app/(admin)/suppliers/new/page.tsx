"use client";

import React, { useMemo, useState } from "react";
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
  SelectValue,
} from "@/components/ui/select";
import {
  Globe,
  ArrowLeft,
  ShieldCheck,
  Zap,
  Database,
  Lock,
  Cloud,
} from "lucide-react";

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

// Cred shapes match the backend protocol adapters:
//   soap/promostandards -> modules/promostandards/client.py reads id/password/customer_number
//   sftp -> n8n SFTP credential needs host/port/username/password
//   rest -> S&S Activewear: HTTP Basic
//   rest_hmac -> 4Over: HMAC-SHA256 with client_id/client_secret
//   ops_graphql -> OnPrintShop OAuth2
const PROTOCOLS: ProtocolDef[] = [
  {
    value: "promostandards",
    label: "PromoStandards (SOAP)",
    base_url_label: "PS Directory base URL",
    base_url_default: "https://promostandards.org/api",
    fields: [
      { key: "id", label: "Username (id)", required: true, placeholder: "your sanmar.com username" },
      { key: "password", label: "Password", type: "password", required: true },
      { key: "customer_number", label: "Customer Number", type: "number", placeholder: "157718" },
    ],
  },
  {
    value: "soap",
    label: "Generic SOAP",
    base_url_label: "WSDL base URL",
    fields: [
      { key: "id", label: "Username (id)", required: true },
      { key: "password", label: "Password", type: "password", required: true },
      { key: "customer_number", label: "Customer Number", type: "number" },
    ],
  },
  {
    value: "rest",
    label: "REST (HTTP Basic) — S&S Activewear",
    base_url_label: "API base URL",
    base_url_default: "https://api.ssactivewear.com",
    fields: [
      { key: "username", label: "Account # / Username", required: true },
      { key: "password", label: "API Password", type: "password", required: true },
    ],
  },
  {
    value: "rest_hmac",
    label: "REST + HMAC — 4Over",
    base_url_label: "API base URL",
    base_url_default: "https://api.4over.com",
    fields: [
      { key: "client_id", label: "Client ID", required: true },
      { key: "client_secret", label: "Client Secret", type: "password", required: true },
    ],
  },
  {
    value: "sftp",
    label: "SFTP / CSV — SanMar",
    base_url_label: "SFTP host:port (informational)",
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
    base_url_label: "OPS base URL",
    base_url_default: "https://yourshop.onprintshop.com",
    fields: [
      { key: "client_id", label: "OAuth2 Client ID", required: true },
      { key: "client_secret", label: "OAuth2 Client Secret", type: "password", required: true },
      { key: "token_url", label: "Token URL", placeholder: "https://yourshop.onprintshop.com/oauth/token" },
      { key: "store_url", label: "Store URL", placeholder: "https://yourshop.onprintshop.com" },
    ],
  },
];

const SANMAR_PRESET = {
  name: "SanMar",
  slug: "sanmar",
  protocol: "promostandards",
  promostandards_code: "SANMAR",
  base_url: "https://promostandards.org/api",
  auth_config: {
    id: "",
    password: "",
    customer_number: "",
  } as Record<string, string>,
};

const SANMAR_SFTP_PRESET = {
  name: "SanMar SFTP",
  slug: "sanmar-sftp",
  protocol: "sftp",
  promostandards_code: "",
  base_url: "ftp.sanmar.com:2200",
  auth_config: {
    host: "ftp.sanmar.com",
    port: "2200",
    username: "",
    password: "",
  } as Record<string, string>,
};

export default function NewSupplierPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [protocol, setProtocol] = useState("promostandards");
  const [promostandardsCode, setPromostandardsCode] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [authConfig, setAuthConfig] = useState<Record<string, string>>({});

  const def = useMemo(
    () => PROTOCOLS.find((p) => p.value === protocol) ?? PROTOCOLS[0],
    [protocol],
  );

  // Reset auth_config when protocol changes so we don't carry stale keys.
  function changeProtocol(next: string) {
    setProtocol(next);
    const nextDef = PROTOCOLS.find((p) => p.value === next);
    if (!nextDef) return;
    const fresh: Record<string, string> = {};
    for (const f of nextDef.fields) fresh[f.key] = f.default ?? "";
    setAuthConfig(fresh);
    if (nextDef.base_url_default && !baseUrl) setBaseUrl(nextDef.base_url_default);
  }

  function applyPreset(preset: typeof SANMAR_PRESET) {
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
      // Strip empty strings so the backend stores only fields the user filled in.
      const trimmedAuth: Record<string, string | number> = {};
      for (const [k, v] of Object.entries(authConfig)) {
        if (v === undefined || v === null || v === "") continue;
        const fdef = def.fields.find((f) => f.key === k);
        trimmedAuth[k] = fdef?.type === "number" ? Number(v) : v;
      }
      const payload = {
        name,
        slug,
        protocol,
        promostandards_code: promostandardsCode || null,
        base_url: baseUrl || null,
        auth_config: trimmedAuth,
      };
      await api("/api/suppliers", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      router.push("/suppliers");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to create supplier.";
      alert(`${msg}\n\nMake sure the slug is unique.`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="flex items-center justify-between gap-4">
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
            <p className="text-sm text-[#888894] font-medium">
              Add a new data source to your universal catalog.
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            className="text-[10px] uppercase tracking-widest border-[#cfccc8]"
            onClick={() => applyPreset(SANMAR_PRESET)}
          >
            SanMar (PromoStandards)
          </Button>
          <Button
            type="button"
            variant="outline"
            className="text-[10px] uppercase tracking-widest border-[#cfccc8]"
            onClick={() => applyPreset(SANMAR_SFTP_PRESET)}
          >
            SanMar (SFTP)
          </Button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-2 space-y-6">
          <Card className="p-6 border-[#cfccc8] shadow-sm space-y-6">
            <div className="flex items-center gap-2 text-[11px] font-black uppercase tracking-widest text-[#1e4d92] border-b border-[#f2f0ed] pb-4">
              <Globe className="w-3.5 h-3.5" />
              Core Identity
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">
                  Supplier Name
                </label>
                <Input
                  placeholder="e.g. SanMar"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="h-11 border-[#cfccc8] focus:ring-[#1e4d92]"
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">
                  System Slug (Unique)
                </label>
                <Input
                  placeholder="e.g. sanmar"
                  value={slug}
                  onChange={(e) =>
                    setSlug(e.target.value.toLowerCase().replace(/\s+/g, "-"))
                  }
                  className="h-11 border-[#cfccc8] font-mono"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">
                Protocol / Method
              </label>
              <Select value={protocol} onValueChange={changeProtocol}>
                <SelectTrigger className="h-11 border-[#cfccc8]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PROTOCOLS.map((p) => (
                    <SelectItem key={p.value} value={p.value}>
                      {p.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {protocol === "promostandards" || protocol === "soap" ? (
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">
                  PromoStandards Code (lookup key)
                </label>
                <Input
                  placeholder="SANMAR"
                  value={promostandardsCode}
                  onChange={(e) => setPromostandardsCode(e.target.value.toUpperCase())}
                  className="h-11 border-[#cfccc8] font-mono"
                />
              </div>
            ) : null}

            <div className="space-y-2">
              <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">
                {def.base_url_label}
              </label>
              <Input
                placeholder={def.base_url_default ?? "https://api.supplier.com/v1"}
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                className="h-11 border-[#cfccc8] font-mono text-[13px]"
              />
            </div>
          </Card>

          <Card className="p-6 border-[#cfccc8] shadow-sm space-y-6">
            <div className="flex items-center gap-2 text-[11px] font-black uppercase tracking-widest text-[#1e4d92] border-b border-[#f2f0ed] pb-4">
              <Lock className="w-3.5 h-3.5" />
              Authentication Credentials
              <span className="ml-auto text-[10px] font-mono text-[#b4b4bc] normal-case tracking-normal">
                stored Fernet-encrypted
              </span>
            </div>

            <div className="grid grid-cols-2 gap-6">
              {def.fields.map((f) => (
                <div key={f.key} className="space-y-2">
                  <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">
                    {f.label}
                    {f.required ? <span className="ml-1 text-[#b93232]">*</span> : null}
                  </label>
                  <Input
                    type={f.type === "password" ? "password" : f.type === "number" ? "number" : "text"}
                    placeholder={f.placeholder ?? ""}
                    value={authConfig[f.key] ?? ""}
                    onChange={(e) => updateAuth(f.key, e.target.value)}
                    className={`h-11 border-[#cfccc8] ${f.type === "number" ? "font-mono" : ""}`}
                    required={f.required}
                  />
                </div>
              ))}
            </div>

            <div className="text-[10px] font-mono text-[#b4b4bc] border-t border-dashed border-[#ebe8e3] pt-3">
              Field shape inferred from protocol. SanMar PromoStandards uses{" "}
              <code className="text-[#1e4d92]">id</code> /{" "}
              <code className="text-[#1e4d92]">password</code> per their PO Integration Guide v24.3.
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="p-6 bg-[#1e4d92] text-white border-none shadow-xl shadow-blue-900/20">
            <h4 className="font-black uppercase tracking-widest text-[10px] opacity-70 mb-4">
              Registration Guide
            </h4>
            <div className="space-y-4">
              <div className="flex gap-3">
                <div className="w-6 h-6 rounded bg-white/10 flex items-center justify-center shrink-0">
                  <ShieldCheck className="w-3.5 h-3.5" />
                </div>
                <p className="text-[11px] font-medium leading-relaxed">
                  System slugs must be unique and alphanumeric.
                </p>
              </div>
              <div className="flex gap-3">
                <div className="w-6 h-6 rounded bg-white/10 flex items-center justify-center shrink-0">
                  <Zap className="w-3.5 h-3.5" />
                </div>
                <p className="text-[11px] font-medium leading-relaxed">
                  Use the SanMar preset above to prefill the protocol + cred shape from the
                  Integration Guide.
                </p>
              </div>
              <div className="flex gap-3">
                <div className="w-6 h-6 rounded bg-white/10 flex items-center justify-center shrink-0">
                  <Cloud className="w-3.5 h-3.5" />
                </div>
                <p className="text-[11px] font-medium leading-relaxed">
                  PromoStandards code drives WSDL endpoint resolution from the public directory.
                </p>
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
              <span className="text-[11px] font-black uppercase tracking-widest text-[#888894]">
                Connection Test
              </span>
            </div>
            <p className="text-[10px] font-medium text-[#888894] leading-relaxed">
              Once created, hit the supplier detail page and use the &quot;Refresh
              endpoints&quot; / sync action to verify creds.
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
      <svg
        className="w-4 h-4"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <line x1="12" y1="5" x2="12" y2="19"></line>
        <line x1="5" y1="12" x2="19" y2="12"></line>
      </svg>
    </div>
  );
}
