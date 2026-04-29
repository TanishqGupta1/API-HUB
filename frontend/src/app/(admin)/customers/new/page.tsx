"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Globe,
  ArrowLeft,
  ShieldCheck,
  Zap,
  Database,
  Lock,
  Cloud,
} from "lucide-react";

export default function NewStorefrontPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const [name, setName] = useState("");
  const [opsBaseUrl, setOpsBaseUrl] = useState("");
  const [opsClientId, setOpsClientId] = useState("");
  const [opsClientSecret, setOpsClientSecret] = useState("");
  const [opsTokenUrl, setOpsTokenUrl] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const payload = {
        name,
        ops_base_url: opsBaseUrl,
        ops_client_id: opsClientId,
        ops_client_secret: opsClientSecret,
        ops_token_url: opsTokenUrl,
      };
      await api("/api/customers", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      router.push("/customers");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to create storefront.";
      alert(msg);
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
              Add Storefront
            </h1>
            <p className="text-sm text-[#888894] font-medium">
              Connect a new OnPrintShop instance to your hub.
            </p>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-2 space-y-6">
          <Card className="p-6 border-[#cfccc8] shadow-sm flex flex-col gap-6">
            <div className="flex items-center gap-2 text-[11px] font-black uppercase tracking-widest text-[#1e4d92] border-b border-[#f2f0ed] pb-4">
              <Globe className="w-3.5 h-3.5" />
              General Configuration
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">
                  Storefront Name
                </label>
                <Input
                  placeholder="e.g. Acme Printing"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="h-11 border-[#cfccc8] focus:ring-[#1e4d92]"
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">
                  Base URL (OnPrintShop)
                </label>
                <Input
                  placeholder="https://yourshop.onprintshop.com"
                  value={opsBaseUrl}
                  onChange={(e) => setOpsBaseUrl(e.target.value)}
                  className="h-11 border-[#cfccc8] font-mono text-[13px]"
                  required
                />
              </div>
            </div>
          </Card>

          <Card className="p-6 border-[#cfccc8] shadow-sm space-y-6">
            <div className="flex items-center gap-2 text-[11px] font-black uppercase tracking-widest text-[#1e4d92] border-b border-[#f2f0ed] pb-4">
              <Lock className="w-3.5 h-3.5" />
              Authentication Node
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">
                  OAuth Client ID *
                </label>
                <Input
                  placeholder="Your Client ID"
                  value={opsClientId}
                  onChange={(e) => setOpsClientId(e.target.value)}
                  className="h-11 border-[#cfccc8] font-mono"
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">
                  OAuth Client Secret *
                </label>
                <Input
                  type="password"
                  placeholder="Your Client Secret"
                  value={opsClientSecret}
                  onChange={(e) => setOpsClientSecret(e.target.value)}
                  className="h-11 border-[#cfccc8] font-mono"
                  required
                />
              </div>
              <div className="space-y-2 md:col-span-2">
                <label className="text-[11px] font-bold text-[#888894] uppercase tracking-widest">
                  Token Endpoint *
                </label>
                <Input
                  placeholder="https://yourshop.onprintshop.com/oauth/token"
                  value={opsTokenUrl}
                  onChange={(e) => setOpsTokenUrl(e.target.value)}
                  className="h-11 border-[#cfccc8] font-mono"
                  required
                />
              </div>
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
                  Storefront URLs must include HTTPS.
                </p>
              </div>
              <div className="flex gap-3">
                <div className="w-6 h-6 rounded bg-white/10 flex items-center justify-center shrink-0">
                  <Zap className="w-3.5 h-3.5" />
                </div>
                <p className="text-[11px] font-medium leading-relaxed">
                  You can retrieve OAuth credentials from the OPS Admin interface.
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
