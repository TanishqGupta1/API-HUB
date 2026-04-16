"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { SyncJob } from "@/lib/types";

// ─── constants ───────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  completed: "var(--green)",
  running:   "var(--blueprint)",
  failed:    "var(--red)",
  pending:   "var(--ink-muted)",
};

const STATUS_BG: Record<string, string> = {
  completed: "rgba(36,122,82,0.1)",
  running:   "var(--bp-pale)",
  failed:    "rgba(185,50,50,0.1)",
  pending:   "var(--paper-dark)",
};

const JOB_TYPES = ["full_sync", "inventory", "pricing", "images", "delta"];
const STATUSES  = ["completed", "running", "failed", "pending"];

// ─── helpers ─────────────────────────────────────────────────────────────────

function fmtDuration(startedAt: string, finishedAt: string | null): string {
  if (!finishedAt) return "—";
  const ms = new Date(finishedAt).getTime() - new Date(startedAt).getTime();
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) return rem > 0 ? `${m}m ${rem}s` : `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function relTime(iso: string): string {
  const diff = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function fullDate(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

// ─── sub-components ──────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <tr style={{ borderTop: "1px solid var(--border)" }}>
      {[100, 90, 80, 50, 60, 110, 70].map((w, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-3 rounded animate-pulse" style={{ width: w, background: "var(--paper-dark)" }} />
        </td>
      ))}
    </tr>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded"
      style={{
        background: STATUS_BG[status] ?? "var(--paper-dark)",
        color: STATUS_COLOR[status] ?? "var(--ink-muted)",
        fontFamily: "var(--font-mono)",
      }}
    >
      {status === "running" && (
        <span
          className="w-1.5 h-1.5 rounded-full inline-block"
          style={{ background: "var(--blueprint)", animation: "pulse-dot 1.2s ease-in-out infinite" }}
        />
      )}
      {status}
    </span>
  );
}

function FilterChip({
  label, active, color, onClick,
}: { label: string; active: boolean; color?: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="px-3 py-1 rounded-full text-xs font-semibold border transition-colors"
      style={{
        borderColor: active ? (color ?? "var(--blueprint)") : "var(--border)",
        background: active ? `${color ?? "var(--blueprint)"}18` : "white",
        color: active ? (color ?? "var(--blueprint)") : "var(--ink-muted)",
        fontFamily: "var(--font-mono)",
      }}
    >
      {label}
    </button>
  );
}

// ─── page ────────────────────────────────────────────────────────────────────

export default function SyncJobsPage() {
  const [jobs, setJobs]               = useState<SyncJob[]>([]);
  const [loading, setLoading]         = useState(true);
  const [fetchError, setFetchError]   = useState<string | null>(null);

  // filters
  const [filterStatus,   setFilterStatus]   = useState("");
  const [filterType,     setFilterType]     = useState("");
  const [filterSupplier, setFilterSupplier] = useState("");

  // row state
  const [expanded,  setExpanded]  = useState<string | null>(null);
  const [retrying,  setRetrying]  = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── fetch ─────────────────────────────────────────────────────────────────

  async function fetchJobs(quiet = false) {
    if (!quiet) setLoading(true);
    setFetchError(null);
    const params = new URLSearchParams();
    if (filterStatus)   params.set("status",      filterStatus);
    if (filterType)     params.set("job_type",    filterType);
    if (filterSupplier) params.set("supplier_id", filterSupplier);
    try {
      const data = await api<SyncJob[]>(`/api/sync-jobs${params.size ? `?${params}` : ""}`);
      setJobs(data);
    } catch (e: any) {
      setFetchError(e.message ?? "Failed to load");
    } finally {
      if (!quiet) setLoading(false);
    }
  }

  // Re-fetch when filters change
  useEffect(() => { fetchJobs(); }, [filterStatus, filterType, filterSupplier]); // eslint-disable-line

  // Poll every 5 s while any job is running
  useEffect(() => {
    const anyRunning = jobs.some((j) => j.status === "running");
    if (anyRunning && !pollRef.current) {
      pollRef.current = setInterval(() => fetchJobs(true), 5000);
    }
    if (!anyRunning && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };
  }, [jobs]); // eslint-disable-line

  // ── re-run ────────────────────────────────────────────────────────────────

  async function handleRetry(id: string) {
    setRetrying(id);
    try {
      const newJob = await api<SyncJob>(`/api/sync-jobs/${id}/retry`, { method: "POST" });
      setJobs((prev) => [newJob, ...prev]);
    } catch (e: any) {
      alert(e.message ?? "Retry failed");
    } finally {
      setRetrying(null);
    }
  }

  // ── derived values ────────────────────────────────────────────────────────

  const suppliers = Array.from(
    new Map(jobs.map((j) => [j.supplier_id, j.supplier_name])).entries()
  ).map(([id, name]) => ({ id, name }));

  const stats = {
    total:     jobs.length,
    running:   jobs.filter((j) => j.status === "running").length,
    failed:    jobs.filter((j) => j.status === "failed").length,
    completed: jobs.filter((j) => j.status === "completed").length,
  };

  const hasFilters = filterStatus || filterType || filterSupplier;

  // ── render ────────────────────────────────────────────────────────────────

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-end mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>Sync Jobs</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--ink-muted)" }}>Pipeline run history</p>
        </div>
        <button
          onClick={() => fetchJobs()}
          className="text-xs px-3 py-1.5 rounded-md border font-semibold"
          style={{ borderColor: "var(--border)", color: "var(--ink-muted)" }}
        >
          Refresh
        </button>
      </div>

      {/* Stats bar */}
      {!loading && jobs.length > 0 && (
        <div className="grid grid-cols-4 gap-3 mb-5">
          {[
            { label: "Total",     value: stats.total,     color: "var(--ink)"      },
            { label: "Running",   value: stats.running,   color: "var(--blueprint)" },
            { label: "Completed", value: stats.completed, color: "var(--green)"    },
            { label: "Failed",    value: stats.failed,    color: "var(--red)"      },
          ].map(({ label, value, color }) => (
            <div
              key={label}
              className="rounded-lg border px-4 py-3"
              style={{ borderColor: "var(--border)", background: "white" }}
            >
              <div className="text-xl font-bold" style={{ color }}>{value}</div>
              <div className="text-xs mt-0.5" style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
                {label}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col gap-2 mb-5">
        {/* Status chips */}
        <div className="flex gap-2 flex-wrap items-center">
          <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)", minWidth: 56 }}>
            Status
          </span>
          <FilterChip label="All" active={filterStatus === ""} onClick={() => setFilterStatus("")} />
          {STATUSES.map((s) => (
            <FilterChip
              key={s}
              label={s}
              active={filterStatus === s}
              color={STATUS_COLOR[s]}
              onClick={() => setFilterStatus(filterStatus === s ? "" : s)}
            />
          ))}
        </div>

        {/* Job type chips */}
        <div className="flex gap-2 flex-wrap items-center">
          <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)", minWidth: 56 }}>
            Type
          </span>
          <FilterChip label="All" active={filterType === ""} onClick={() => setFilterType("")} />
          {JOB_TYPES.map((t) => (
            <FilterChip
              key={t}
              label={t}
              active={filterType === t}
              onClick={() => setFilterType(filterType === t ? "" : t)}
            />
          ))}
        </div>

        {/* Supplier chips — built from live data */}
        {suppliers.length > 0 && (
          <div className="flex gap-2 flex-wrap items-center">
            <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)", minWidth: 56 }}>
              Supplier
            </span>
            <FilterChip label="All" active={filterSupplier === ""} onClick={() => setFilterSupplier("")} />
            {suppliers.map(({ id, name }) => (
              <FilterChip
                key={id}
                label={name}
                active={filterSupplier === id}
                onClick={() => setFilterSupplier(filterSupplier === id ? "" : id)}
              />
            ))}
          </div>
        )}

        {/* Clear all */}
        {hasFilters && (
          <button
            onClick={() => { setFilterStatus(""); setFilterType(""); setFilterSupplier(""); }}
            className="text-xs self-start"
            style={{ color: "var(--blueprint)" }}
          >
            ✕ Clear all filters
          </button>
        )}
      </div>

      {/* Error banner */}
      {fetchError && (
        <div className="rounded-lg border px-4 py-3 mb-5 text-sm"
          style={{ borderColor: "var(--red)", color: "var(--red)", background: "rgba(185,50,50,0.06)" }}>
          Failed to load sync jobs: {fetchError}
        </div>
      )}

      {/* Table */}
      <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--border)", background: "white" }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Supplier", "Type", "Status", "Records", "Duration", "Started", ""].map((h, i) => (
                <th key={i} className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide"
                  style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {/* Skeletons */}
            {loading && [1, 2, 3, 4, 5].map((i) => <SkeletonRow key={i} />)}

            {/* Rows */}
            {!loading && jobs.map((j) => (
              <>
                <tr
                  key={j.id}
                  onClick={() => setExpanded(expanded === j.id ? null : j.id)}
                  className="cursor-pointer transition-colors"
                  style={{
                    borderTop: "1px solid var(--border)",
                    background: expanded === j.id ? "var(--bp-pale)" : undefined,
                  }}
                  onMouseEnter={(e) => { if (expanded !== j.id) (e.currentTarget as HTMLElement).style.background = "var(--paper)"; }}
                  onMouseLeave={(e) => { if (expanded !== j.id) (e.currentTarget as HTMLElement).style.background = ""; }}
                >
                  <td className="px-4 py-3 font-semibold">{j.supplier_name}</td>
                  <td className="px-4 py-3">
                    <span
                      className="text-xs px-2 py-0.5 rounded"
                      style={{ background: "var(--paper-dark)", color: "var(--ink)", fontFamily: "var(--font-mono)" }}
                    >
                      {j.job_type}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={j.status} />
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">
                    {j.records_processed > 0 ? j.records_processed.toLocaleString() : "—"}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">
                    {fmtDuration(j.started_at, j.finished_at)}
                  </td>
                  <td
                    className="px-4 py-3 text-xs"
                    title={fullDate(j.started_at)}
                    style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}
                  >
                    {relTime(j.started_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-3">
                      {(j.status === "failed" || j.status === "completed") && (
                        <button
                          onClick={(e) => { e.stopPropagation(); handleRetry(j.id); }}
                          disabled={retrying === j.id}
                          className="text-xs font-semibold"
                          style={{ color: "var(--blueprint)", opacity: retrying === j.id ? 0.5 : 1 }}
                        >
                          {retrying === j.id ? "…" : "Re-run"}
                        </button>
                      )}
                      <span
                        className="text-xs"
                        style={{ color: "var(--ink-muted)", transform: expanded === j.id ? "rotate(180deg)" : "none", display: "inline-block", transition: "transform 0.2s" }}
                      >
                        ▾
                      </span>
                    </div>
                  </td>
                </tr>

                {/* Expanded error / detail row */}
                {expanded === j.id && (
                  <tr key={`${j.id}-detail`} style={{ borderTop: "1px solid var(--border)" }}>
                    <td colSpan={7} className="px-4 py-4">
                      {j.error_log ? (
                        <pre
                          className="text-xs rounded-md p-4 overflow-auto max-h-56 whitespace-pre-wrap"
                          style={{
                            background: "rgba(185,50,50,0.06)",
                            color: "var(--red)",
                            fontFamily: "var(--font-mono)",
                            border: "1px solid rgba(185,50,50,0.2)",
                          }}
                        >
                          {j.error_log}
                        </pre>
                      ) : (
                        <div className="flex gap-6 text-xs" style={{ fontFamily: "var(--font-mono)" }}>
                          <div>
                            <span style={{ color: "var(--ink-muted)" }}>Job ID  </span>
                            <span style={{ color: "var(--ink)" }}>{j.id}</span>
                          </div>
                          <div>
                            <span style={{ color: "var(--ink-muted)" }}>Started  </span>
                            <span style={{ color: "var(--ink)" }}>{fullDate(j.started_at)}</span>
                          </div>
                          {j.finished_at && (
                            <div>
                              <span style={{ color: "var(--ink-muted)" }}>Finished  </span>
                              <span style={{ color: "var(--ink)" }}>{fullDate(j.finished_at)}</span>
                            </div>
                          )}
                          <div>
                            <span style={{ color: "var(--ink-muted)" }}>Records  </span>
                            <span style={{ color: "var(--ink)" }}>{j.records_processed.toLocaleString()}</span>
                          </div>
                          {j.status !== "failed" && (
                            <span style={{ color: "var(--green)" }}>No errors</span>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </>
            ))}

            {/* Empty state */}
            {!loading && jobs.length === 0 && !fetchError && (
              <tr>
                <td colSpan={7} className="px-4 py-14 text-center">
                  <div className="text-3xl mb-3">📋</div>
                  <div className="text-sm font-semibold mb-1" style={{ color: "var(--ink)" }}>
                    {hasFilters ? "No jobs match these filters" : "No sync jobs yet"}
                  </div>
                  <div className="text-xs" style={{ color: "var(--ink-muted)" }}>
                    {hasFilters
                      ? "Try clearing the filters to see all jobs."
                      : "Jobs appear here after a pipeline run is triggered."}
                  </div>
                  {hasFilters && (
                    <button
                      onClick={() => { setFilterStatus(""); setFilterType(""); setFilterSupplier(""); }}
                      className="mt-3 text-xs font-semibold"
                      style={{ color: "var(--blueprint)" }}
                    >
                      Clear filters
                    </button>
                  )}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.4; transform: scale(1.5); }
        }
      `}</style>
    </div>
  );
}
