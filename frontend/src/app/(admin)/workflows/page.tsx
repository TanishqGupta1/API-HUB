"use client";

import { useEffect, useState } from "react";
import PipelineView, { type PipelineNode } from "@/components/workflows/pipeline-view";
import { api } from "@/lib/api";
import type { JobType, SyncJob, SyncStatus } from "@/lib/types";

const N8N_URL = process.env.NEXT_PUBLIC_N8N_URL ?? "http://localhost:5678";

const PIPELINE_NODES: PipelineNode[] = [
  { id: "supplier",  label: "Supplier",          sublabel: "Source data",       status: "idle", icon: "supplier"  },
  { id: "fetch",     label: "Fetch Data",        sublabel: "SOAP / REST",       status: "idle", icon: "fetch"     },
  { id: "normalize", label: "Normalize",         sublabel: "Canonical schema",  status: "idle", icon: "normalize" },
  { id: "store",     label: "Store in DB",       sublabel: "PostgreSQL",        status: "idle", icon: "store"     },
  { id: "publish",   label: "Publish to Store",  sublabel: "Storefront",        status: "idle", icon: "publish"   },
];

interface WorkflowSummary {
  id: string;
  name: string;
  active: boolean;
  updatedAt: string;
  triggers: string[];
  webhook_url: string | null;
  node_count: number;
}

interface ExecutionSummary {
  id: string;
  workflowId: string;
  status: "success" | "error" | "running" | "canceled" | "waiting";
  startedAt: string;
  stoppedAt: string | null;
  finished: boolean;
  mode: string;
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function fmtDuration(a: string, b: string | null): string {
  if (!b) return "—";
  const ms = new Date(b).getTime() - new Date(a).getTime();
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function StatusBadge({ status }: { status: string }) {
  const bg: Record<string, string> = {
    success: "#e6f3ec",
    error: "#fdeded",
    running: "#eef4fb",
    canceled: "#f9f7f4",
    waiting: "#fff7e0",
  };
  const fg: Record<string, string> = {
    success: "#247a52",
    error: "#b93232",
    running: "#1e4d92",
    canceled: "#888894",
    waiting: "#c17c00",
  };
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold"
      style={{
        background: bg[status] ?? "#f9f7f4",
        color: fg[status] ?? "#484852"
      }}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${status === "running" ? "animate-pulse" : ""}`}
        style={{ background: fg[status] ?? "#888894" }}
      />
      {status}
    </span>
  );
}

// ─── Cron workflow definitions ───────────────────────────────────────────────

const CRON_WORKFLOWS: { type: JobType; title: string; description: string; schedule: string }[] = [
  { type: "inventory", title: "Inventory Sync", description: "Stock levels and warehouse availability",  schedule: "every 15 min" },
  { type: "pricing",   title: "Pricing Sync",   description: "Supplier base prices and tier breaks",    schedule: "hourly"       },
  { type: "delta",     title: "Delta Sync",     description: "Changed products since last run",         schedule: "every 2 h"    },
  { type: "full",      title: "Full Sync",      description: "Complete product catalog refresh",        schedule: "nightly"      },
  { type: "images",    title: "Image Sync",     description: "Product imagery and color swatches",      schedule: "daily"        },
];

// ─── helpers ─────────────────────────────────────────────────────────────────

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hrs = Math.floor(min / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const STATUS_STYLE: Record<SyncStatus | "never", { color: string; bg: string; label: string }> = {
  running:   { color: "var(--blue)",       bg: "var(--blue-pale)",         label: "Running"   },
  completed: { color: "var(--green)",      bg: "rgba(36,122,82,0.1)",      label: "Healthy"   },
  failed:    { color: "var(--red)",        bg: "rgba(185,50,50,0.1)",      label: "Failed"    },
  pending:   { color: "var(--ink-muted)",  bg: "var(--paper-warm)",        label: "Queued"    },
  never:     { color: "var(--ink-muted)",  bg: "var(--paper-warm)",        label: "Not run"   },
};

type LatestByType = Partial<Record<JobType, SyncJob>>;

function pickLatestByType(jobs: SyncJob[]): LatestByType {
  const out: LatestByType = {};
  for (const j of jobs) {
    const existing = out[j.job_type];
    if (!existing || j.started_at > existing.started_at) {
      out[j.job_type] = j;
    }
  }
  return out;
}

// ─── page ────────────────────────────────────────────────────────────────────

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [executions, setExecutions] = useState<Record<string, ExecutionSummary[]>>({});
  const [latest, setLatest] = useState<LatestByType>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadAll() {
    try {
      const ws = await api<WorkflowSummary[]>("/api/n8n/workflows");
      setWorkflows(ws);

      const execMap: Record<string, ExecutionSummary[]> = {};
      await Promise.all(
        ws.map(async (w) => {
          try {
            const e = await api<ExecutionSummary[]>(
              `/api/n8n/executions?workflow_id=${w.id}&limit=5`
            );
            execMap[w.id] = e;
          } catch {
            execMap[w.id] = [];
          }
        })
      );
      setExecutions(execMap);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
    const id = setInterval(loadAll, 15000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    api<SyncJob[]>("/api/sync-jobs?limit=100")
      .then((jobs) => setLatest(pickLatestByType(jobs)))
      .catch(() => setLatest({}));
  }, []);

  async function trigger(workflowId: string) {
    setTriggering(workflowId);
    setMessage(null);
    try {
      await api<{ triggered: boolean }>(
        `/api/n8n/workflows/${workflowId}/trigger`,
        { method: "POST" }
      );
      setMessage(`Triggered ${workflowId}. Reloading executions…`);
      setTimeout(loadAll, 2000);
    } catch (err) {
      setMessage(
        "Trigger failed: " + (err instanceof Error ? err.message : String(err))
      );
    } finally {
      setTriggering(null);
    }
  }

  const runningTypes = new Set(
    Object.values(latest).filter((j): j is SyncJob => !!j && j.status === "running").map((j) => j.job_type),
  );

  const liveNodes: PipelineNode[] = runningTypes.size
    ? PIPELINE_NODES.map((n, i) => (i === 1 || i === 2 ? { ...n, status: "running" } : n))
    : PIPELINE_NODES;

  return (
    <div className="flex flex-col gap-6 pb-12">
      <div className="flex items-end justify-between pb-5 border-b-2 border-[#1e1e24]">
        <div>
          <div className="text-[32px] font-extrabold tracking-[-0.04em] leading-none text-[#1e1e24]">
            Workflows
          </div>
          <div className="text-[13px] text-[#888894] mt-2 font-normal">
            Live n8n workflows · trigger · recent runs
          </div>
        </div>
        <a
          href={N8N_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 rounded-md text-[13px] font-semibold border border-[#1e4d92] text-[#1e4d92] hover:bg-[#eef4fb]"
        >
          Open n8n editor ↗
        </a>
      </div>

      {/* Pipeline diagram */}
      <div className="rounded-lg border border-[#cfccc8] bg-white">
        <PipelineView nodes={liveNodes} />
      </div>

      {/* Cron workflow cards */}
      <div>
        <div className="text-xs font-semibold uppercase tracking-widest mb-3 text-[#484852] font-mono">
          Scheduled Workflows
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {CRON_WORKFLOWS.map((wf) => {
            const job = latest[wf.type];
            const style = STATUS_STYLE[job ? job.status : "never"];
            return (
              <div
                key={wf.type}
                className="rounded-lg border px-4 py-3 border-[#cfccc8] bg-white"
              >
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div className="text-sm font-semibold text-[#1e1e24]">
                    {wf.title}
                  </div>
                  <span
                    className="inline-flex items-center gap-1.5 text-[11px] font-semibold px-2 py-0.5 rounded-full shrink-0"
                    style={{ background: style.bg, color: style.color }}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${job?.status === "running" ? "animate-pulse" : ""}`}
                      style={{ background: style.color }}
                    />
                    {style.label}
                  </span>
                </div>

                <p className="text-xs mb-2 text-[#484852]">
                  {wf.description}
                </p>

                <div className="flex items-center justify-between text-[11px] text-[#484852] font-mono">
                  <span>{wf.schedule}</span>
                  <span>
                    {loading
                      ? "…"
                      : job
                      ? `last run ${timeAgo(job.started_at)}`
                      : "—"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {message && (
        <div className="p-3 border border-[#1e4d92] rounded-md bg-[#eef4fb] text-[13px] text-[#1e4d92]">
          {message}
        </div>
      )}

      {error && (
        <div className="p-4 border border-[#b93232] rounded-md bg-[#fdeded] text-[13px] text-[#b93232]">
          <div className="font-bold mb-1">Error</div>
          <div className="font-mono">{error}</div>
        </div>
      )}

      {loading && workflows.length === 0 ? (
        <div className="space-y-4">
          {[0, 1].map((i) => (
            <div
              key={i}
              className="h-[200px] bg-[#f9f7f4] border border-[#ebe8e3] rounded-[10px] animate-pulse"
            />
          ))}
        </div>
      ) : workflows.length === 0 ? (
        <div className="border border-dashed border-[#cfccc8] rounded-[10px] p-16 text-center bg-white">
          <div className="text-[14px] font-bold text-[#1e1e24] mb-1">
            No workflows yet
          </div>
          <div className="text-[12px] text-[#888894]">
            Import one in the n8n editor, then refresh this page.
          </div>
        </div>
      ) : (
        workflows.map((w) => {
          const recent = executions[w.id] ?? [];
          const latest = recent[0];
          return (
            <div
              key={w.id}
              className="bg-white border border-[#cfccc8] rounded-[10px] overflow-hidden"
            >
              <div className="flex items-center justify-between p-5 border-b border-[#cfccc8] bg-[#f9f7f4]">
                <div>
                  <div className="flex items-center gap-3">
                    <div className="text-[17px] font-extrabold text-[#1e1e24]">
                      {w.name}
                    </div>
                    <span
                      className={`font-mono text-[10px] font-bold px-2 py-[2px] rounded ${
                        w.active ? "bg-[#e6f3ec] text-[#247a52]" : "bg-[#fdeded] text-[#b93232]"
                      }`}
                    >
                      {w.active ? "ACTIVE" : "INACTIVE"}
                    </span>
                  </div>
                  <div className="text-[12px] text-[#888894] mt-1 font-mono">
                    id: {w.id} · {w.node_count} nodes · triggers:{" "}
                    {w.triggers.join(", ") || "—"}
                  </div>
                </div>
                <div className="flex gap-2">
                  <a
                    href={`${N8N_URL}/workflow/${w.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-2 rounded-md text-[12px] font-semibold border border-[#cfccc8] text-[#1e1e24] hover:border-[#1e4d92] hover:text-[#1e4d92]"
                  >
                    Open ↗
                  </a>
                  <button
                    type="button"
                    onClick={() => trigger(w.id)}
                    disabled={triggering === w.id || !w.active || !w.webhook_url}
                    className="px-4 py-2 rounded-md text-[12px] font-semibold bg-[#1e4d92] text-white hover:bg-[#163f78] disabled:opacity-50 disabled:cursor-not-allowed"
                    title={
                      !w.active
                        ? "Workflow is inactive"
                        : !w.webhook_url
                          ? "No webhook trigger configured"
                          : "Trigger via webhook"
                    }
                  >
                    {triggering === w.id ? "Triggering…" : "Run now"}
                  </button>
                </div>
              </div>

              <div className="p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852]">
                    Recent runs
                  </div>
                  {latest && (
                    <div className="text-[11px] font-mono text-[#888894]">
                      Last: {fmtTime(latest.startedAt)}
                    </div>
                  )}
                </div>

                {recent.length === 0 ? (
                  <div className="text-[12px] text-[#888894] py-3">
                    No executions yet.
                  </div>
                ) : (
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr className="text-left text-[10px] font-bold uppercase tracking-[0.1em] text-[#888894]">
                        <th className="pb-2">ID</th>
                        <th className="pb-2">Status</th>
                        <th className="pb-2">Mode</th>
                        <th className="pb-2">Started</th>
                        <th className="pb-2">Duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recent.map((e) => (
                        <tr key={e.id} className="border-t border-[#ebe8e3]">
                          <td className="py-2 font-mono text-[#484852]">{e.id}</td>
                          <td className="py-2">
                            <StatusBadge status={e.status} />
                          </td>
                          <td className="py-2 font-mono text-[#484852]">
                            {e.mode}
                          </td>
                          <td className="py-2 font-mono text-[#484852]">
                            {fmtTime(e.startedAt)}
                          </td>
                          <td className="py-2 font-mono text-[#484852]">
                            {fmtDuration(e.startedAt, e.stoppedAt)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                {w.webhook_url && (
                  <div className="mt-4 pt-3 border-t border-dashed border-[#cfccc8] text-[11px] font-mono text-[#888894]">
                    webhook:{" "}
                    <span className="text-[#1e4d92]">{w.webhook_url}</span>
                  </div>
                )}
              </div>
            </div>
          );
        })
      )}

    </div>
  );
}
