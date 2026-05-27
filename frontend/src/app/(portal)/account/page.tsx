"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, ShieldCheck, Globe, Save, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";

interface PortalMe {
  id: string;
  name: string;
  ops_base_url: string;
  ops_token_url: string;
  ops_client_id: string;
  is_active: boolean;
  created_at: string;
  products_pushed: number;
}

export default function PortalAccount() {
  const [me, setMe] = useState<PortalMe | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [newSecret, setNewSecret] = useState("");
  const [showSecret, setShowSecret] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadMe = useCallback(async () => {
    try {
      const data = await api<PortalMe>("/api/portal/me");
      setMe(data);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadMe(); }, [loadMe]);

  async function handleSaveSecret() {
    if (!newSecret.trim()) return;
    // Mirror the server-side min_length=16 constraint client-side so we get a
    // friendly error instead of a 422 from the backend.
    if (newSecret.trim().length < 16) {
      toast.error("Secret must be at least 16 characters");
      return;
    }
    setSaving(true);
    try {
      const data = await api<{ updated: boolean }>("/api/portal/account", {
        method: "PATCH",
        body: JSON.stringify({ ops_client_secret: newSecret }),
      });
      if (data.updated) {
        toast.success("OPS credentials updated");
        setNewSecret("");
        loadMe();
      }
      // data.updated === false means nothing changed — no toast, no side-effects.
    } catch {
      toast.error("Failed to update credentials");
    } finally {
      setSaving(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-[#1e4d92]" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div>
        <h1 className="text-2xl font-black text-[#1e1e24] tracking-tight">Account Settings</h1>
        <p className="text-sm text-[#888894] font-medium mt-1">Manage your storefront configuration</p>
      </div>

      {/* Storefront info (read-only) */}
      <div className="bg-white rounded-2xl border border-[#ebe9e6] overflow-hidden">
        <div className="px-6 py-4 border-b border-[#f2f0ed] flex items-center gap-2">
          <Globe className="w-4 h-4 text-[#1e4d92]" />
          <h2 className="text-sm font-black text-[#1e1e24] uppercase tracking-wider">Storefront Info</h2>
        </div>
        <div className="px-6 py-5 space-y-4">
          {[
            { label: "Storefront Name", value: me?.name },
            { label: "OPS Base URL",    value: me?.ops_base_url },
            { label: "Token URL",       value: me?.ops_token_url },
            { label: "Client ID",       value: me?.ops_client_id },
          ].map(({ label, value }) => (
            <div key={label}>
              <div className="text-[10px] font-black uppercase tracking-widest text-[#888894] mb-1">{label}</div>
              <div className="text-sm font-mono text-[#484852] bg-[#f9f7f4] px-3 py-2 rounded-lg border border-[#ebe9e6] break-all">
                {value ?? "—"}
              </div>
            </div>
          ))}
          <p className="text-[11px] text-[#888894]">
            Contact your administrator to update the storefront name, URLs, or Client ID.
          </p>
        </div>
      </div>

      {/* OPS client secret (self-service) */}
      <div className="bg-white rounded-2xl border border-[#ebe9e6] overflow-hidden">
        <div className="px-6 py-4 border-b border-[#f2f0ed] flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-[#1e4d92]" />
          <h2 className="text-sm font-black text-[#1e1e24] uppercase tracking-wider">OPS Client Secret</h2>
        </div>
        <div className="px-6 py-5 space-y-4">
          <p className="text-sm text-[#484852]">
            Rotate your OPS OAuth2 client secret. The current secret is never displayed.
          </p>
          <div>
            <label className="text-[10px] font-black uppercase tracking-widest text-[#888894] block mb-1.5">
              New Client Secret
            </label>
            <div className="relative">
              <input
                type={showSecret ? "text" : "password"}
                value={newSecret}
                onChange={(e) => setNewSecret(e.target.value)}
                placeholder="Paste new secret…"
                className="w-full px-3 py-2.5 pr-10 text-sm font-mono rounded-lg border border-[#cfccc8] bg-white
                           focus:outline-none focus:border-[#1e4d92] focus:ring-1 focus:ring-[#1e4d92]"
              />
              <button
                type="button"
                onClick={() => setShowSecret(!showSecret)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#888894] hover:text-[#484852]"
              >
                {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <Button
            onClick={handleSaveSecret}
            disabled={saving || newSecret.trim().length < 16}
            className="bg-[#1e4d92] hover:bg-[#173d74] text-white font-black text-xs uppercase tracking-wider"
          >
            {saving ? (
              <><Loader2 className="w-3.5 h-3.5 animate-spin mr-2" /> Saving…</>
            ) : (
              <><Save className="w-3.5 h-3.5 mr-2" /> Update Secret</>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
