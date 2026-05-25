"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import {
  Webhook,
  Plus,
  Trash2,
  ToggleLeft,
  ToggleRight,
  Send,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  ShieldCheck,
  ShieldOff,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface WebhookEndpoint {
  id: string;
  customer_id: string | null;
  url: string;
  events: string[];
  is_active: boolean;
  failure_count: number;
  last_fired_at: string | null;
  last_failure_at: string | null;
  created_at: string;
  has_secret: boolean;
}

interface WebhookTestResult {
  success: boolean;
  status_code: number | null;
  error: string | null;
  fired_at: string;
}

const ALL_EVENTS = ["push.completed", "push.failed", "push.partial_failure"] as const;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(s: string | null) {
  if (!s) return "—";
  return new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function EventBadge({ event }: { event: string }) {
  const colour =
    event === "push.completed"
      ? { bg: "#f0fdf4", text: "#16a34a", border: "#bbf7d0" }
      : event === "push.failed"
      ? { bg: "#fef2f2", text: "#dc2626", border: "#fecaca" }
      : { bg: "#fffbeb", text: "#d97706", border: "#fde68a" };
  return (
    <span
      className="font-mono text-[10px] font-bold px-2 py-0.5 rounded-full"
      style={{ background: colour.bg, color: colour.text, border: `1px solid ${colour.border}` }}
    >
      {event}
    </span>
  );
}

// ─── Create modal ─────────────────────────────────────────────────────────────

function CreateModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState<string[]>(["push.completed", "push.failed"]);
  const [secret, setSecret] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleEvent(ev: string) {
    setEvents(prev =>
      prev.includes(ev) ? prev.filter(e => e !== ev) : [...prev, ev]
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) { setError("URL is required."); return; }
    if (events.length === 0) { setError("Select at least one event."); return; }
    setSaving(true);
    setError(null);
    try {
      await api("/api/webhooks", {
        method: "POST",
        body: JSON.stringify({ url: url.trim(), events, secret: secret.trim() || undefined }),
      });
      onCreated();
    } catch (err: any) {
      const detail = err?.body?.detail;
      setError(typeof detail === "string" ? detail : "Failed to create webhook.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg border border-[#cfccc8]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-[#f2f0ed]">
          <div className="flex items-center gap-2">
            <Webhook className="w-5 h-5 text-[#1e4d92]" />
            <span className="text-[16px] font-extrabold text-[#1e1e24]">Add Webhook Endpoint</span>
          </div>
          <button onClick={onClose} className="text-[#888894] hover:text-[#1e1e24] text-[20px] leading-none font-bold">×</button>
        </div>

        <form onSubmit={submit} className="px-6 py-5 space-y-5">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-[12px] text-red-700 font-medium">
              {error}
            </div>
          )}

          {/* URL */}
          <div>
            <label className="block text-[11px] font-black uppercase tracking-widest text-[#484852] mb-1.5">
              Endpoint URL *
            </label>
            <input
              type="url"
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://your-server.com/webhook"
              className="w-full px-4 h-10 bg-[#fafaf9] border border-[#cfccc8] rounded-xl text-[13px] font-mono text-[#1e1e24] placeholder:text-[#b4b4bc] outline-none focus:border-[#1e4d92] transition-colors"
            />
            <p className="text-[11px] text-[#888894] mt-1">
              Must be https:// for production. HTTP is allowed for local dev.
            </p>
          </div>

          {/* Events */}
          <div>
            <label className="block text-[11px] font-black uppercase tracking-widest text-[#484852] mb-2">
              Subscribe to events *
            </label>
            <div className="space-y-2">
              {ALL_EVENTS.map(ev => (
                <label key={ev} className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={events.includes(ev)}
                    onChange={() => toggleEvent(ev)}
                    className="w-4 h-4 accent-[#1e4d92] cursor-pointer"
                  />
                  <EventBadge event={ev} />
                </label>
              ))}
            </div>
          </div>

          {/* Secret */}
          <div>
            <label className="block text-[11px] font-black uppercase tracking-widest text-[#484852] mb-1.5">
              Signing Secret{" "}
              <span className="text-[#b4b4bc] font-medium normal-case tracking-normal">(optional)</span>
            </label>
            <input
              type="password"
              value={secret}
              onChange={e => setSecret(e.target.value)}
              placeholder="Leave blank to skip HMAC signing"
              className="w-full px-4 h-10 bg-[#fafaf9] border border-[#cfccc8] rounded-xl text-[13px] font-mono text-[#1e1e24] placeholder:text-[#b4b4bc] outline-none focus:border-[#1e4d92] transition-colors"
            />
            <p className="text-[11px] text-[#888894] mt-1">
              If set, each delivery includes an{" "}
              <code className="font-mono bg-[#f2f0ed] px-1 rounded">X-ApiHub-Signature</code> header
              (sha256=… HMAC).
            </p>
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 h-10 border border-[#cfccc8] rounded-xl text-[13px] font-bold text-[#484852] hover:bg-[#f9f7f4] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 h-10 bg-[#1e4d92] text-white rounded-xl text-[13px] font-bold shadow-[0_3px_0_#143566] hover:bg-[#173d74] active:shadow-none active:translate-y-0.5 transition-all disabled:opacity-50"
            >
              {saving ? "Adding..." : "Add Webhook"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Test result toast ────────────────────────────────────────────────────────

function TestToast({
  result,
  onDismiss,
}: {
  result: WebhookTestResult;
  onDismiss: () => void;
}) {
  return (
    <div
      className="fixed bottom-6 right-6 z-50 flex items-start gap-3 px-5 py-4 rounded-2xl border shadow-xl max-w-sm"
      style={{
        background: result.success ? "#f0fdf4" : "#fef2f2",
        borderColor: result.success ? "#bbf7d0" : "#fecaca",
      }}
    >
      {result.success ? (
        <CheckCircle2 className="w-5 h-5 text-[#16a34a] flex-shrink-0 mt-0.5" />
      ) : (
        <XCircle className="w-5 h-5 text-[#dc2626] flex-shrink-0 mt-0.5" />
      )}
      <div className="flex-1">
        <p
          className="text-[13px] font-bold mb-0.5"
          style={{ color: result.success ? "#15803d" : "#b91c1c" }}
        >
          {result.success ? "Test delivered" : "Test failed"}
        </p>
        {result.status_code && (
          <p className="text-[12px]" style={{ color: result.success ? "#16a34a" : "#dc2626" }}>
            HTTP {result.status_code}
          </p>
        )}
        {result.error && (
          <p className="text-[12px] text-[#dc2626] font-mono break-all">{result.error}</p>
        )}
      </div>
      <button onClick={onDismiss} className="text-[#888894] hover:text-[#1e1e24] font-bold text-[16px] leading-none">
        ×
      </button>
    </div>
  );
}

// ─── Endpoint card ────────────────────────────────────────────────────────────

function EndpointCard({
  ep,
  onRefresh,
  onTest,
}: {
  ep: WebhookEndpoint;
  onRefresh: () => void;
  onTest: (ep: WebhookEndpoint) => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const [toggling, setToggling] = useState(false);

  async function handleDelete() {
    if (!confirm("Delete this webhook? It will stop receiving events immediately.")) return;
    setDeleting(true);
    try {
      await api(`/api/webhooks/${ep.id}`, { method: "DELETE" });
      onRefresh();
    } catch (err) {
      log.error("delete webhook", err);
    } finally {
      setDeleting(false);
    }
  }

  async function handleToggle() {
    setToggling(true);
    try {
      await api(`/api/webhooks/${ep.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !ep.is_active }),
      });
      onRefresh();
    } catch (err) {
      log.error("toggle webhook", err);
    } finally {
      setToggling(false);
    }
  }

  const isDisabledByFailures = !ep.is_active && ep.failure_count >= 10;

  return (
    <div
      className={`bg-white border rounded-2xl px-6 py-5 transition-all ${
        ep.is_active
          ? "border-[#cfccc8] hover:border-[#1e4d92]/30"
          : "border-[#f2f0ed] opacity-60"
      }`}
    >
      <div className="flex items-start gap-4">
        {/* Left: info */}
        <div className="flex-1 min-w-0">
          {/* URL + status */}
          <div className="flex items-center gap-3 mb-2 flex-wrap">
            <span className="font-mono text-[13px] font-bold text-[#1e1e24] break-all">{ep.url}</span>

            {ep.is_active ? (
              <span className="inline-flex items-center gap-1 font-mono text-[10px] font-bold px-2 py-0.5 rounded-full"
                style={{ color: "#16a34a", background: "#16a34a18", border: "1px solid #16a34a40" }}>
                <div className="w-1.5 h-1.5 rounded-full bg-[#16a34a]" /> Active
              </span>
            ) : isDisabledByFailures ? (
              <span className="inline-flex items-center gap-1 font-mono text-[10px] font-bold px-2 py-0.5 rounded-full"
                style={{ color: "#dc2626", background: "#dc262618", border: "1px solid #dc262640" }}>
                <AlertTriangle className="w-3 h-3" /> Auto-disabled
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 font-mono text-[10px] font-bold px-2 py-0.5 rounded-full"
                style={{ color: "#6b7280", background: "#6b728018", border: "1px solid #6b728040" }}>
                Paused
              </span>
            )}

            {ep.has_secret && (
              <span className="inline-flex items-center gap-1 font-mono text-[10px] font-bold px-2 py-0.5 rounded-full"
                style={{ color: "#7c3aed", background: "#7c3aed12", border: "1px solid #7c3aed30" }}>
                <ShieldCheck className="w-3 h-3" /> Signed
              </span>
            )}
          </div>

          {/* Events */}
          <div className="flex flex-wrap gap-1.5 mb-3">
            {ep.events.map(ev => <EventBadge key={ev} event={ev} />)}
          </div>

          {/* Meta */}
          <div className="flex flex-wrap gap-5 text-[11px] text-[#888894]">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Added {fmtDate(ep.created_at)}
            </span>
            <span className="flex items-center gap-1">
              <Send className="w-3 h-3" />
              Last fired: {fmtDate(ep.last_fired_at)}
            </span>
            {ep.failure_count > 0 && (
              <span className="flex items-center gap-1 text-red-500 font-bold">
                <XCircle className="w-3 h-3" />
                {ep.failure_count} consecutive failure{ep.failure_count !== 1 ? "s" : ""}
              </span>
            )}
          </div>

          {isDisabledByFailures && (
            <p className="mt-2 text-[11px] text-red-600 font-medium">
              Auto-disabled after 10 consecutive failures. Re-enable once the endpoint is healthy.
            </p>
          )}
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => onTest(ep)}
            title="Send test event"
            className="flex items-center gap-1.5 px-3 py-2 text-[12px] font-bold text-[#1e4d92] border border-[#bfdbfe] rounded-xl hover:bg-[#eff6ff] transition-colors"
          >
            <Send className="w-3.5 h-3.5" />
            Test
          </button>

          <button
            onClick={handleToggle}
            disabled={toggling}
            title={ep.is_active ? "Pause webhook" : "Enable webhook"}
            className="flex items-center gap-1.5 px-3 py-2 text-[12px] font-bold text-[#484852] border border-[#cfccc8] rounded-xl hover:bg-[#f9f7f4] transition-colors disabled:opacity-50"
          >
            {ep.is_active ? (
              <><ToggleRight className="w-4 h-4 text-[#16a34a]" /> Pause</>
            ) : (
              <><ToggleLeft className="w-4 h-4 text-[#6b7280]" /> Enable</>
            )}
          </button>

          <button
            onClick={handleDelete}
            disabled={deleting}
            title="Delete webhook"
            className="flex items-center gap-1.5 px-3 py-2 text-[12px] font-bold text-red-600 border border-red-200 rounded-xl hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            <Trash2 className="w-3.5 h-3.5" />
            {deleting ? "..." : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function WebhooksPage() {
  const [endpoints, setEndpoints] = useState<WebhookEndpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [testResult, setTestResult] = useState<WebhookTestResult | null>(null);
  const [testing, setTesting] = useState<string | null>(null);

  function load() {
    setLoading(true);
    api<WebhookEndpoint[]>("/api/webhooks")
      .then(setEndpoints)
      .catch(log.error)
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function handleTest(ep: WebhookEndpoint) {
    setTesting(ep.id);
    try {
      const result = await api<WebhookTestResult>(`/api/webhooks/${ep.id}/test`, { method: "POST" });
      setTestResult(result);
    } catch (err) {
      log.error("test webhook", err);
    } finally {
      setTesting(null);
    }
  }

  const active = endpoints.filter(e => e.is_active).length;
  const disabled = endpoints.filter(e => !e.is_active).length;

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load(); }}
        />
      )}

      {testResult && (
        <TestToast result={testResult} onDismiss={() => setTestResult(null)} />
      )}

      {/* Header */}
      <div className="flex items-end justify-between mb-10 pb-6 border-b-2 border-[#1e1e24]">
        <div>
          <div className="text-[32px] font-extrabold tracking-tight leading-none text-[#1e1e24]">
            Outbound Webhooks
          </div>
          <p className="text-[14px] text-[#888894] mt-3 max-w-xl leading-relaxed">
            Register HTTPS endpoints to receive real-time push events. Each delivery is
            optionally HMAC-signed with a{" "}
            <code className="font-mono text-[12px] bg-[#f2f0ed] px-1.5 py-0.5 rounded">
              X-ApiHub-Signature
            </code>{" "}
            header. Endpoints are auto-disabled after 10 consecutive failures.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-6 py-3 bg-[#1e4d92] text-white text-[13px] font-bold rounded-xl shadow-[0_4px_0_#143566] hover:bg-[#173d74] active:shadow-none active:translate-y-1 transition-all"
        >
          <Plus className="w-4 h-4" />
          Add Endpoint
        </button>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 mb-8 flex-wrap">
        <div className="flex items-center gap-2 px-4 py-2 bg-[#f9f7f4] border border-[#cfccc8] rounded-lg">
          <Webhook className="w-3.5 h-3.5 text-[#1e4d92]" />
          <span className="text-[11px] font-black uppercase tracking-widest text-[#484852]">
            {endpoints.length} Endpoint{endpoints.length !== 1 ? "s" : ""}
          </span>
        </div>
        {active > 0 && (
          <div className="flex items-center gap-2 px-4 py-2 bg-[#f9f7f4] border border-[#cfccc8] rounded-lg">
            <div className="w-2 h-2 rounded-full bg-[#16a34a]" />
            <span className="text-[11px] font-black uppercase tracking-widest text-[#484852]">
              {active} Active
            </span>
          </div>
        )}
        {disabled > 0 && (
          <div className="flex items-center gap-2 px-4 py-2 bg-[#f9f7f4] border border-[#cfccc8] rounded-lg">
            <div className="w-2 h-2 rounded-full bg-[#6b7280]" />
            <span className="text-[11px] font-black uppercase tracking-widest text-[#484852]">
              {disabled} Paused / Disabled
            </span>
          </div>
        )}
      </div>

      {/* Event reference */}
      <div className="mb-8 p-4 bg-[#f9f7f4] border border-[#cfccc8] rounded-xl">
        <p className="text-[11px] font-black uppercase tracking-widest text-[#484852] mb-3">
          Supported Events
        </p>
        <div className="flex flex-wrap gap-3 text-[12px] text-[#484852]">
          <span><EventBadge event="push.completed" /> — product pushed successfully to OPS</span>
          <span><EventBadge event="push.failed" /> — push failed before any OPS mutation</span>
          <span><EventBadge event="push.partial_failure" /> — one or more OPS mutations failed mid-plan</span>
        </div>
      </div>

      {/* List */}
      {loading ? (
        <div className="space-y-3 animate-pulse">
          {[1, 2].map(i => (
            <div key={i} className="h-32 bg-white border border-[#f2f0ed] rounded-2xl" />
          ))}
        </div>
      ) : endpoints.length === 0 ? (
        <div className="text-center py-24">
          <Webhook className="w-12 h-12 text-[#cfccc8] mx-auto mb-4" />
          <p className="text-[15px] font-bold text-[#1e1e24] mb-1">No webhook endpoints yet</p>
          <p className="text-[13px] text-[#888894] mb-6">
            Add an endpoint to start receiving push-event notifications in real time.
          </p>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#1e4d92] text-white text-[13px] font-bold rounded-xl shadow-[0_3px_0_#143566] hover:bg-[#173d74] active:shadow-none active:translate-y-0.5 transition-all"
          >
            <Plus className="w-4 h-4" />
            Add First Endpoint
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {endpoints.map(ep => (
            <EndpointCard
              key={ep.id}
              ep={ep}
              onRefresh={load}
              onTest={handleTest}
            />
          ))}
        </div>
      )}
    </div>
  );
}
