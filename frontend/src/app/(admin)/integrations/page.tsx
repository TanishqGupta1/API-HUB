"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import { KeyRound, Plus, ShieldOff, Copy, CheckCheck, AlertTriangle, Clock } from "lucide-react";

interface IntegrationKey {
  id: string;
  name: string;
  allowed_customer_ids: string[] | null;
  allowed_supplier_slugs: string[] | null;
  rate_limit_per_minute: number;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
  revoked_at: string | null;
}

interface CreatedKey extends IntegrationKey {
  raw_key: string;
}

function StatusBadge({ is_active, revoked_at }: { is_active: boolean; revoked_at: string | null }) {
  if (revoked_at || !is_active) {
    return (
      <span className="inline-flex items-center gap-1 font-mono text-[10px] font-bold uppercase px-2 py-0.5 rounded-full"
        style={{ color: "#dc2626", background: "#dc262618", border: "1px solid #dc262640" }}>
        <ShieldOff className="w-3 h-3" /> Revoked
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 font-mono text-[10px] font-bold uppercase px-2 py-0.5 rounded-full"
      style={{ color: "#16a34a", background: "#16a34a18", border: "1px solid #16a34a40" }}>
      <KeyRound className="w-3 h-3" /> Active
    </span>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <button onClick={copy} className="ml-2 p-1 rounded hover:bg-[#f2f0ed] transition-colors text-[#888894] hover:text-[#1e4d92]">
      {copied ? <CheckCheck className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

function NewKeyBanner({ created, onDismiss }: { created: CreatedKey; onDismiss: () => void }) {
  return (
    <div className="mb-8 p-5 bg-[#fefce8] border-2 border-[#ca8a04] rounded-2xl">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-[#ca8a04] flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-[13px] font-bold text-[#78350f] mb-1">
            Save this key — it will never be shown again
          </p>
          <p className="text-[12px] text-[#92400e] mb-3">
            Copy the raw key and store it somewhere safe (e.g. your n8n credential vault).
            You cannot retrieve it after closing this banner.
          </p>
          <div className="flex items-center gap-2 bg-white border border-[#fde68a] rounded-xl px-4 py-3">
            <span className="font-mono text-[13px] text-[#1e1e24] flex-1 select-all break-all">{created.raw_key}</span>
            <CopyButton text={created.raw_key} />
          </div>
          <div className="mt-3 text-[11px] text-[#92400e]">
            Key ID: <span className="font-mono font-bold">{created.id}</span>
          </div>
        </div>
        <button onClick={onDismiss} className="text-[#ca8a04] hover:text-[#78350f] text-[18px] leading-none font-bold">×</button>
      </div>
    </div>
  );
}

function CreateKeyModal({ onClose, onCreated }: { onClose: () => void; onCreated: (k: CreatedKey) => void }) {
  const [id, setId] = useState("");
  const [name, setName] = useState("");
  const [rateLimit, setRateLimit] = useState(60);
  const [customerIds, setCustomerIds] = useState("");
  const [supplierSlugs, setSupplierSlugs] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!id.trim() || !name.trim()) {
      setError("Key ID and Name are required.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        id: id.trim(),
        name: name.trim(),
        rate_limit_per_minute: rateLimit,
      };
      if (customerIds.trim()) {
        body.allowed_customer_ids = customerIds.split(",").map(s => s.trim()).filter(Boolean);
      }
      if (supplierSlugs.trim()) {
        body.allowed_supplier_slugs = supplierSlugs.split(",").map(s => s.trim()).filter(Boolean);
      }
      const created = await api<CreatedKey>("/api/integrations/keys", { method: "POST", body: JSON.stringify(body) });
      onCreated(created);
    } catch (err: any) {
      setError(err?.body?.detail ?? "Failed to create key.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg border border-[#cfccc8]">
        <div className="flex items-center justify-between px-6 py-5 border-b border-[#f2f0ed]">
          <div className="flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-[#1e4d92]" />
            <span className="text-[16px] font-extrabold text-[#1e1e24]">Create Integration Key</span>
          </div>
          <button onClick={onClose} className="text-[#888894] hover:text-[#1e1e24] text-[20px] leading-none font-bold">×</button>
        </div>
        <form onSubmit={submit} className="px-6 py-5 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-[12px] text-red-700 font-medium">{error}</div>
          )}
          <div>
            <label className="block text-[11px] font-black uppercase tracking-widest text-[#484852] mb-1.5">Key ID *</label>
            <input
              value={id}
              onChange={e => setId(e.target.value)}
              placeholder="e.g. n8n-vidhi-staging"
              className="w-full px-4 h-10 bg-[#fafaf9] border border-[#cfccc8] rounded-xl text-[13px] font-mono text-[#1e1e24] placeholder:text-[#b4b4bc] outline-none focus:border-[#1e4d92] transition-colors"
            />
            <p className="text-[11px] text-[#888894] mt-1">Human-readable slug. Must be unique.</p>
          </div>
          <div>
            <label className="block text-[11px] font-black uppercase tracking-widest text-[#484852] mb-1.5">Display Name *</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. n8n Staging Orchestrator"
              className="w-full px-4 h-10 bg-[#fafaf9] border border-[#cfccc8] rounded-xl text-[13px] text-[#1e1e24] placeholder:text-[#b4b4bc] outline-none focus:border-[#1e4d92] transition-colors"
            />
          </div>
          <div>
            <label className="block text-[11px] font-black uppercase tracking-widest text-[#484852] mb-1.5">Rate Limit (req/min)</label>
            <input
              type="number"
              value={rateLimit}
              onChange={e => setRateLimit(Number(e.target.value))}
              min={1}
              max={1000}
              className="w-full px-4 h-10 bg-[#fafaf9] border border-[#cfccc8] rounded-xl text-[13px] text-[#1e1e24] outline-none focus:border-[#1e4d92] transition-colors"
            />
          </div>
          <div>
            <label className="block text-[11px] font-black uppercase tracking-widest text-[#484852] mb-1.5">
              Allowed Customer IDs <span className="text-[#b4b4bc] font-medium normal-case tracking-normal">(leave blank = all customers)</span>
            </label>
            <input
              value={customerIds}
              onChange={e => setCustomerIds(e.target.value)}
              placeholder="uuid1, uuid2, ..."
              className="w-full px-4 h-10 bg-[#fafaf9] border border-[#cfccc8] rounded-xl text-[12px] font-mono text-[#1e1e24] placeholder:text-[#b4b4bc] outline-none focus:border-[#1e4d92] transition-colors"
            />
          </div>
          <div>
            <label className="block text-[11px] font-black uppercase tracking-widest text-[#484852] mb-1.5">
              Allowed Supplier Slugs <span className="text-[#b4b4bc] font-medium normal-case tracking-normal">(leave blank = all suppliers)</span>
            </label>
            <input
              value={supplierSlugs}
              onChange={e => setSupplierSlugs(e.target.value)}
              placeholder="sanmar, alphabroder, ..."
              className="w-full px-4 h-10 bg-[#fafaf9] border border-[#cfccc8] rounded-xl text-[13px] font-mono text-[#1e1e24] placeholder:text-[#b4b4bc] outline-none focus:border-[#1e4d92] transition-colors"
            />
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 h-10 border border-[#cfccc8] rounded-xl text-[13px] font-bold text-[#484852] hover:bg-[#f9f7f4] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 h-10 bg-[#1e4d92] text-white rounded-xl text-[13px] font-bold shadow-[0_3px_0_#143566] hover:bg-[#173d74] active:shadow-none active:translate-y-0.5 transition-all disabled:opacity-50"
            >
              {submitting ? "Creating..." : "Create Key"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function IntegrationsPage() {
  const [keys, setKeys] = useState<IntegrationKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [newKey, setNewKey] = useState<CreatedKey | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null);

  function load() {
    setLoading(true);
    api<IntegrationKey[]>("/api/integrations/keys")
      .then(setKeys)
      .catch(log.error)
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function revoke(keyId: string) {
    if (!confirm(`Revoke key "${keyId}"? This cannot be undone.`)) return;
    setRevoking(keyId);
    try {
      await api(`/api/integrations/keys/${keyId}/revoke`, { method: "POST" });
      load();
    } catch (err) {
      log.error("revoke failed", err);
    } finally {
      setRevoking(null);
    }
  }

  function handleCreated(k: CreatedKey) {
    setShowModal(false);
    setNewKey(k);
    load();
  }

  const activeCount = keys.filter(k => k.is_active).length;

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {showModal && <CreateKeyModal onClose={() => setShowModal(false)} onCreated={handleCreated} />}

      {/* Header */}
      <div className="flex items-end justify-between mb-10 pb-6 border-b-2 border-[#1e1e24]">
        <div>
          <div className="text-[32px] font-extrabold tracking-tight leading-none text-[#1e1e24]">
            Integration Keys
          </div>
          <p className="text-[14px] text-[#888894] mt-3 max-w-xl leading-relaxed">
            Manage <code className="font-mono text-[12px] bg-[#f2f0ed] px-1.5 py-0.5 rounded">X-Orchestrator-Key</code> credentials
            for external orchestrators (n8n, cron, Lambda). Each key has its own scope and can be revoked instantly.
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-6 py-3 bg-[#1e4d92] text-white text-[13px] font-bold rounded-xl shadow-[0_4px_0_#143566] hover:bg-[#173d74] active:shadow-none active:translate-y-1 transition-all"
        >
          <Plus className="w-4 h-4" />
          Create Key
        </button>
      </div>

      {/* New key banner */}
      {newKey && <NewKeyBanner created={newKey} onDismiss={() => setNewKey(null)} />}

      {/* Stats bar */}
      <div className="flex items-center gap-6 mb-8">
        <div className="flex items-center gap-2 px-4 py-2 bg-[#f9f7f4] border border-[#cfccc8] rounded-lg">
          <KeyRound className="w-3.5 h-3.5 text-[#1e4d92]" />
          <span className="text-[11px] font-black uppercase tracking-widest text-[#484852]">
            {keys.length} Total Keys
          </span>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 bg-[#f9f7f4] border border-[#cfccc8] rounded-lg">
          <div className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="text-[11px] font-black uppercase tracking-widest text-[#484852]">
            {activeCount} Active
          </span>
        </div>
      </div>

      {/* Keys list */}
      {loading ? (
        <div className="space-y-3 animate-pulse">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-28 bg-white border border-[#f2f0ed] rounded-2xl" />
          ))}
        </div>
      ) : keys.length === 0 ? (
        <div className="text-center py-20">
          <KeyRound className="w-12 h-12 text-[#cfccc8] mx-auto mb-4" />
          <p className="text-[15px] font-bold text-[#1e1e24] mb-1">No integration keys yet</p>
          <p className="text-[13px] text-[#888894]">Create a key to allow external orchestrators to push products.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {keys.map(k => (
            <div
              key={k.id}
              className={`bg-white border rounded-2xl px-6 py-5 transition-all ${
                k.is_active ? "border-[#cfccc8] hover:border-[#1e4d92]/30" : "border-[#f2f0ed] opacity-60"
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2 flex-wrap">
                    <span className="text-[15px] font-extrabold text-[#1e1e24]">{k.name}</span>
                    <StatusBadge is_active={k.is_active} revoked_at={k.revoked_at} />
                  </div>

                  <div className="flex items-center gap-1.5 mb-3">
                    <span className="font-mono text-[12px] text-[#484852] bg-[#f2f0ed] px-2 py-0.5 rounded">{k.id}</span>
                    <CopyButton text={k.id} />
                  </div>

                  <div className="flex flex-wrap gap-4 text-[11px] text-[#888894]">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      Created {new Date(k.created_at).toLocaleDateString()}
                    </span>
                    {k.last_used_at && (
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        Last used {new Date(k.last_used_at).toLocaleDateString()}
                      </span>
                    )}
                    {!k.last_used_at && (
                      <span className="text-[#b4b4bc]">Never used</span>
                    )}
                    <span>{k.rate_limit_per_minute} req/min</span>
                  </div>

                  {/* Scope */}
                  <div className="mt-3 flex flex-wrap gap-2">
                    {k.allowed_supplier_slugs && k.allowed_supplier_slugs.length > 0 ? (
                      k.allowed_supplier_slugs.map(slug => (
                        <span key={slug} className="font-mono text-[10px] font-bold px-2 py-0.5 bg-[#eff6ff] text-[#1e4d92] border border-[#bfdbfe] rounded-full">
                          supplier: {slug}
                        </span>
                      ))
                    ) : (
                      <span className="text-[10px] font-bold px-2 py-0.5 bg-[#f9f7f4] text-[#888894] border border-[#cfccc8] rounded-full">
                        all suppliers
                      </span>
                    )}
                    {k.allowed_customer_ids && k.allowed_customer_ids.length > 0 ? (
                      <span className="text-[10px] font-bold px-2 py-0.5 bg-[#f0fdf4] text-[#16a34a] border border-[#bbf7d0] rounded-full">
                        {k.allowed_customer_ids.length} customer{k.allowed_customer_ids.length > 1 ? "s" : ""}
                      </span>
                    ) : (
                      <span className="text-[10px] font-bold px-2 py-0.5 bg-[#f9f7f4] text-[#888894] border border-[#cfccc8] rounded-full">
                        all customers
                      </span>
                    )}
                  </div>
                </div>

                {k.is_active && (
                  <button
                    onClick={() => revoke(k.id)}
                    disabled={revoking === k.id}
                    className="flex items-center gap-1.5 px-4 py-2 text-[12px] font-bold text-red-600 border border-red-200 rounded-xl hover:bg-red-50 transition-colors disabled:opacity-50 flex-shrink-0"
                  >
                    <ShieldOff className="w-3.5 h-3.5" />
                    {revoking === k.id ? "Revoking..." : "Revoke"}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
