"use client";

import { useEffect, useRef, useState } from "react";
import PipelineView, { type NodeStatus, type PipelineNode } from "@/components/workflows/pipeline-view";
import { api } from "@/lib/api";

// ─── types ───────────────────────────────────────────────────────────────────

interface RunRecord {
  id: string;
  startedAt: string;
  duration: string;
  status: "ok" | "fail";
  recordsProcessed: number;
}

interface Pipeline {
  id: string;
  name: string;
  description: string;
  schedule: string;
  enabled: boolean;
  nodes: PipelineNode[];
  lastRun: RunRecord | null;
  recentRuns: RunRecord[];
}

// ─── static seed data ────────────────────────────────────────────────────────
// Replaced at runtime once /api/workflows is wired up.

const SEED_PIPELINES: Pipeline[] = [
  {
    id: "full-sync",
    name: "Full Catalog Sync",
    description: "ProductData + MediaContent → normalize → push to OPS",
    schedule: "Daily at 02:00",
    enabled: true,
    nodes: [
      { id: "ps-fetch",   label: "PS Fetch",   sublabel: "ProductData",     status: "done",    duration: "4m 12s" },
      { id: "ps-media",   label: "PS Media",   sublabel: "MediaContent",    status: "done",    duration: "6m 50s" },
      { id: "normalize",  label: "Normalize",  sublabel: "Canonical schema", status: "done",    duration: "2m 08s" },
      { id: "ops-push",   label: "OPS Push",   sublabel: "Storefront API",  status: "idle"    },
    ],
    lastRun: {
      id: "run-1",
      startedAt: new Date(Date.now() - 3 * 60 * 1000).toISOString(),
      duration: "—",
      status: "ok",
      recordsProcessed: 12847,
    },
    recentRuns: [
      { id: "run-0", startedAt: new Date(Date.now() - 26 * 60 * 60 * 1000).toISOString(), duration: "18m 44s", status: "ok",   recordsProcessed: 12710 },
      { id: "run-01", startedAt: new Date(Date.now() - 50 * 60 * 60 * 1000).toISOString(), duration: "19m 02s", status: "ok",  recordsProcessed: 12598 },
      { id: "run-02", startedAt: new Date(Date.now() - 74 * 60 * 60 * 1000).toISOString(), duration: "21m 31s", status: "fail", recordsProcessed: 0 },
    ],
  },
  {
    id: "inventory",
    name: "Inventory Delta",
    description: "Inventory service → compute delta → update OPS stock levels",
    schedule: "Every hour",
    enabled: true,
    nodes: [
      { id: "inv-fetch", label: "INV Fetch",   sublabel: "Inventory svc",  status: "idle" },
      { id: "delta",     label: "Delta Check", sublabel: "Compare cache",   status: "idle" },
      { id: "inv-push",  label: "OPS Update",  sublabel: "Stock levels",    status: "idle" },
    ],
    lastRun: {
      id: "run-inv-1",
      startedAt: new Date(Date.now() - 38 * 60 * 1000).toISOString(),
      duration: "1m 14s",
      status: "ok",
      recordsProcessed: 4321,
    },
    recentRuns: [
      { id: "ri-0", startedAt: new Date(Date.now() - 98 * 60 * 1000).toISOString(),  duration: "1m 09s", status: "ok",  recordsProcessed: 4290 },
      { id: "ri-1", startedAt: new Date(Date.now() - 158 * 60 * 1000).toISOString(), duration: "1m 22s", status: "ok",  recordsProcessed: 4388 },
      { id: "ri-2", startedAt: new Date(Date.now() - 218 * 60 * 1000).toISOString(), duration: "1m 07s", status: "ok",  recordsProcessed: 4300 },
    ],
  },
  {
    id: "pricing",
    name: "Pricing Update",
    description: "Fetch latest pricing from PS → apply markup rules → sync to OPS",
    schedule: "Every 6 hours",
    enabled: false,
    nodes: [
      { id: "price-fetch",  label: "PS Pricing",   sublabel: "PricingAndConfig", status: "idle" },
      { id: "markup",       label: "Markup Rules",  sublabel: "Per-customer",     status: "idle" },
      { id: "price-push",   label: "OPS Pricing",  sublabel: "Update variants",  status: "idle" },
    ],
    lastRun: null,
    recentRuns: [],
  },
];

// ─── helpers ─────────────────────────────────────────────────────────────────

function relTime(iso: string) {
  const diff = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function isRunning(p: Pipeline) {
  return p.nodes.some((n) => n.status === "running");
}

const N8N_URL = process.env.NEXT_PUBLIC_N8N_URL ?? "http://localhost:5678";

// ─── sub-components ──────────────────────────────────────────────────────────

function RunBadge({ status }: { status: "ok" | "fail" }) {
  return (
    <span
      className="text-xs font-semibold px-1.5 py-px rounded"
      style={{
        background: status === "ok" ? "rgba(36,122,82,0.1)" : "rgba(185,50,50,0.1)",
        color: status === "ok" ? "var(--green)" : "var(--red)",
        fontFamily: "var(--font-mono)",
      }}
    >
      {status === "ok" ? "ok" : "fail"}
    </span>
  );
}

interface PipelineCardProps {
  pipeline: Pipeline;
  onTrigger: (id: string) => void;
  onToggle: (id: string) => void;
  triggering: boolean;
  toggling: boolean;
}

function PipelineCard({ pipeline: p, onTrigger, onToggle, triggering, toggling }: PipelineCardProps) {
  const [showHistory, setShowHistory] = useState(false);
  const active = isRunning(p);

  return (
    <div
      className="rounded-lg border overflow-hidden transition-shadow"
      style={{
        borderColor: active ? "var(--blue)" : "var(--border)",
        background: "white",
        boxShadow: active ? "0 0 0 1px var(--blue)20" : "none",
      }}
    >
      {/* Card header */}
      <div
        className="px-5 py-4 border-b flex justify-between items-start gap-4"
        style={{ borderColor: "var(--border)" }}
      >
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="font-semibold" style={{ color: "var(--ink)" }}>{p.name}</span>
            {active && (
              <span
                className="text-xs px-1.5 py-px rounded font-semibold animate-pulse"
                style={{ background: "var(--blue-pale)", color: "var(--blue)", fontFamily: "var(--font-mono)" }}
              >
                running
              </span>
            )}
          </div>
          <div className="text-xs truncate" style={{ color: "var(--ink-muted)" }}>{p.description}</div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {/* Schedule badge */}
          <span
            className="text-xs px-2 py-0.5 rounded font-semibold"
            style={{ background: "var(--blue-pale)", color: "var(--blue)", fontFamily: "var(--font-mono)" }}
          >
            {p.schedule}
          </span>

          {/* Enable toggle */}
          <button
            onClick={() => onToggle(p.id)}
            disabled={toggling}
            title={p.enabled ? "Disable workflow" : "Enable workflow"}
            className="relative inline-flex h-5 w-9 items-center rounded-full transition-colors"
            style={{
              background: p.enabled ? "var(--blue)" : "var(--paper-warm)",
              opacity: toggling ? 0.5 : 1,
            }}
          >
            <span
              className="inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform shadow-sm"
              style={{ transform: p.enabled ? "translateX(18px)" : "translateX(2px)" }}
            />
          </button>

          {/* Run Now */}
          <button
            onClick={() => onTrigger(p.id)}
            disabled={triggering || !p.enabled || active}
            className="text-xs px-3 py-1.5 rounded font-semibold"
            style={{
              background: p.enabled && !active ? "var(--blue)" : "var(--paper-warm)",
              color: p.enabled && !active ? "white" : "var(--ink-muted)",
              opacity: triggering ? 0.6 : 1,
              cursor: !p.enabled || active ? "not-allowed" : "pointer",
            }}
          >
            {triggering ? "Starting…" : active ? "Running" : "Run Now"}
          </button>
        </div>
      </div>

      {/* Pipeline diagram */}
      <div className="px-3">
        <PipelineView nodes={p.nodes} />
      </div>

      {/* Footer — last run + history toggle */}
      <div
        className="px-5 py-3 border-t flex items-center justify-between text-xs"
        style={{ borderColor: "var(--border)", background: "var(--paper)" }}
      >
        <div style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
          {p.lastRun ? (
            <span>
              Last run: <span style={{ color: "var(--ink)" }}>{relTime(p.lastRun.startedAt)}</span>
              {" · "}
              <RunBadge status={p.lastRun.status} />
              {p.lastRun.recordsProcessed > 0 && (
                <span> · {p.lastRun.recordsProcessed.toLocaleString()} records</span>
              )}
            </span>
          ) : (
            <span>Never run</span>
          )}
        </div>

        {p.recentRuns.length > 0 && (
          <button
            onClick={() => setShowHistory((s) => !s)}
            className="text-xs"
            style={{ color: "var(--blue)" }}
          >
            {showHistory ? "Hide history ▲" : "Run history ▼"}
          </button>
        )}
      </div>

      {/* Expandable run history */}
      {showHistory && p.recentRuns.length > 0 && (
        <div style={{ borderTop: "1px solid var(--border)" }}>
          <table className="w-full text-xs">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)", background: "var(--paper)" }}>
                {["Started", "Duration", "Records", "Result"].map((h) => (
                  <th
                    key={h}
                    className="text-left px-5 py-2 font-semibold uppercase tracking-wide"
                    style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {p.recentRuns.map((r) => (
                <tr key={r.id} style={{ borderTop: "1px solid var(--border)" }}>
                  <td className="px-5 py-2" style={{ fontFamily: "var(--font-mono)", color: "var(--ink-muted)" }}>
                    {relTime(r.startedAt)}
                  </td>
                  <td className="px-5 py-2" style={{ fontFamily: "var(--font-mono)" }}>{r.duration}</td>
                  <td className="px-5 py-2" style={{ fontFamily: "var(--font-mono)" }}>
                    {r.recordsProcessed > 0 ? r.recordsProcessed.toLocaleString() : "—"}
                  </td>
                  <td className="px-5 py-2">
                    <RunBadge status={r.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── page ────────────────────────────────────────────────────────────────────

export default function WorkflowsPage() {
  const [pipelines, setPipelines] = useState<Pipeline[]>(SEED_PIPELINES);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  const pollRef      = useRef<ReturnType<typeof setInterval> | null>(null);
  const failCountRef = useRef(0);

  // Poll /api/workflows/status every 5 s while any pipeline is running.
  // Auto-stops after 3 consecutive failures (backend not up yet).
  useEffect(() => {
    const anyRunning = pipelines.some(isRunning);
    if (anyRunning && !pollRef.current) {
      failCountRef.current = 0;
      pollRef.current = setInterval(async () => {
        try {
          const updated = await api<Pipeline[]>("/api/workflows/status");
          failCountRef.current = 0;
          setPipelines(updated);
          if (!updated.some(isRunning)) {
            clearInterval(pollRef.current!);
            pollRef.current = null;
          }
        } catch {
          failCountRef.current += 1;
          if (failCountRef.current >= 3) {
            clearInterval(pollRef.current!);
            pollRef.current = null;
          }
        }
      }, 5000);
    }
    return () => {
      if (!anyRunning && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [pipelines]); // eslint-disable-line

  async function handleTrigger(id: string) {
    setTriggering(id);
    setTriggerError(null);
    try {
      await api(`/api/workflows/${id}/trigger`, { method: "POST" });
      // Optimistically flip all nodes in this pipeline to running state
      setPipelines((prev) =>
        prev.map((p) =>
          p.id !== id
            ? p
            : {
                ...p,
                nodes: p.nodes.map((n, i) =>
                  i === 0 ? { ...n, status: "running" as NodeStatus, duration: undefined } : { ...n, status: "idle" as NodeStatus, duration: undefined }
                ),
                lastRun: {
                  id: `run-${Date.now()}`,
                  startedAt: new Date().toISOString(),
                  duration: "—",
                  status: "ok",
                  recordsProcessed: 0,
                },
              }
        )
      );
    } catch (e: any) {
      setTriggerError(`Failed to trigger "${id}": ${e.message ?? "unknown error"}`);
    } finally {
      setTriggering(null);
    }
  }

  async function handleToggle(id: string) {
    setToggling(id);
    try {
      await api(`/api/workflows/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: !pipelines.find((p) => p.id === id)?.enabled }),
      });
      setPipelines((prev) =>
        prev.map((p) => (p.id === id ? { ...p, enabled: !p.enabled } : p))
      );
    } catch (e: any) {
      alert(e.message ?? "Toggle failed");
    } finally {
      setToggling(null);
    }
  }

  const activeCount = pipelines.filter(isRunning).length;

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-end mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>Workflows</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--ink-muted)" }}>
            n8n pipeline status
            {activeCount > 0 && (
              <span
                className="ml-2 text-xs font-semibold px-1.5 py-px rounded"
                style={{ background: "var(--blue-pale)", color: "var(--blue)", fontFamily: "var(--font-mono)" }}
              >
                {activeCount} running
              </span>
            )}
          </p>
        </div>
        <a
          href={N8N_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 rounded-md text-sm font-semibold border"
          style={{ borderColor: "var(--blue)", color: "var(--blue)" }}
        >
          Open n8n Editor ↗
        </a>
      </div>

      {/* Trigger error */}
      {triggerError && (
        <div
          className="rounded-lg border px-4 py-3 mb-5 text-sm"
          style={{ borderColor: "var(--red)", color: "var(--red)", background: "rgba(185,50,50,0.06)" }}
        >
          {triggerError}
        </div>
      )}

      {/* Pipeline cards */}
      <div className="flex flex-col gap-5">
        {pipelines.map((p) => (
          <PipelineCard
            key={p.id}
            pipeline={p}
            onTrigger={handleTrigger}
            onToggle={handleToggle}
            triggering={triggering === p.id}
            toggling={toggling === p.id}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="mt-6 flex flex-wrap gap-4 px-1">
        {(["idle", "running", "done", "error"] as const).map((s) => {
          const colors: Record<string, string> = {
            idle: "var(--ink-muted)", running: "var(--blue)", done: "var(--green)", error: "var(--red)",
          };
          return (
            <div key={s} className="flex items-center gap-1.5 text-xs" style={{ color: "var(--ink-muted)" }}>
              <span className="w-2 h-2 rounded-full inline-block" style={{ background: colors[s] }} />
              {s}
            </div>
          );
        })}
      </div>
    </div>
  );
}
