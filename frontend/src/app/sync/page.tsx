"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { SyncJob } from "@/lib/types";
import { EmptyState } from "@/components/ui/empty-state";

// ─── helpers ─────────────────────────────────────────────────────────────────

function fmtDuration(startedAt: string, finishedAt: string | null): string {
  if (!finishedAt) return "—";
  const s = Math.round((new Date(finishedAt).getTime() - new Date(startedAt).getTime()) / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) return rem > 0 ? `${m}m ${rem}s` : `${m}m`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

function fmtStarted(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-GB", {
    day: "numeric", month: "short",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).replace(",", "");
}

// ─── sub-components ──────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { color: string; bg: string; dot: string }> = {
    completed: { color: "var(--green)",     bg: "rgba(36,122,82,0.1)",    dot: "var(--green)"     },
    running:   { color: "var(--blue)", bg: "var(--blue-pale)",         dot: "var(--blue)" },
    failed:    { color: "var(--red)",       bg: "rgba(185,50,50,0.1)",    dot: "var(--red)"       },
    pending:   { color: "var(--ink-muted)", bg: "var(--paper-warm)",      dot: "var(--ink-muted)" },
  };
  const s = cfg[status] ?? cfg.pending;
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full"
      style={{ background: s.bg, color: s.color }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full shrink-0"
        style={{
          background: s.dot,
          animation: status === "running" ? "pulse-dot 1.2s ease-in-out infinite" : "none",
        }}
      />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function SkeletonRow() {
  return (
    <tr style={{ borderTop: "1px solid var(--border)" }}>
      {[120, 80, 100, 60, 60, 110, 90].map((w, i) => (
        <td key={i} className="px-5 py-4">
          <div className="h-3 rounded animate-pulse" style={{ width: w, background: "var(--paper-warm)" }} />
        </td>
      ))}
    </tr>
  );
}

// ─── page ────────────────────────────────────────────────────────────────────

export default function SyncJobsPage() {
  const [jobs, setJobs]               = useState<SyncJob[]>([]);
  const [loading, setLoading]         = useState(true);
  const [fetchError, setFetchError]   = useState<string | null>(null);
  const [filterSupplier, setFilterSupplier] = useState("");
  const [filterStatus,   setFilterStatus]   = useState("");
  const [filterJobType,  setFilterJobType]  = useState("");
  const [expandedError,  setExpandedError]  = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const refreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function fetchJobs(quiet = false) {
    if (!quiet) setLoading(true);
    setFetchError(null);
    const params = new URLSearchParams();
    if (filterStatus)   params.set("status",   filterStatus);
    if (filterJobType)  params.set("job_type", filterJobType);
    if (filterSupplier) params.set("supplier_name", filterSupplier);
    try {
      const data = await api<SyncJob[]>(`/api/sync-jobs${params.size ? `?${params}` : ""}`);
      setJobs(data);
    } catch (e: any) {
      setFetchError(e.message ?? "Failed to load");
    } finally {
      if (!quiet) setLoading(false);
    }
  }

  useEffect(() => { fetchJobs(); }, [filterStatus, filterJobType, filterSupplier]); // eslint-disable-line

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
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [jobs]); // eslint-disable-line

  // Background auto-refresh every 30s (independent of running-job poll)
  useEffect(() => {
    refreshRef.current = setInterval(() => fetchJobs(true), 30000);
    return () => { if (refreshRef.current) clearInterval(refreshRef.current); };
  }, [filterStatus, filterJobType, filterSupplier]); // eslint-disable-line

  // Supplier options derived from data
  const supplierNames = Array.from(new Set(jobs.map((j) => j.supplier_name))).sort();

  const STATUSES = ["completed", "running", "failed", "pending"];
  const JOB_TYPES = [
    { value: "full_sync", label: "Full Refresh" },
    { value: "full", label: "Full Refresh" },
    { value: "delta", label: "Recent Changes" },
    { value: "inventory", label: "Inventory" },
    { value: "pricing", label: "Pricing" },
    { value: "images", label: "Images" },
  ];

  return (
    <div>
      {/* Header row */}
      <div className="flex justify-between items-start mb-5">
        <div>
          <h1 className="text-3xl font-bold" style={{ color: "var(--ink)" }}>Data Updates</h1>
          <p className="text-sm mt-1" style={{ color: "var(--ink-muted)" }}>Execution history of your data pipelines</p>
        </div>

        {/* Dropdown filters */}
        <div className="flex gap-3 items-center">
          <select
            value={filterSupplier}
            onChange={(e) => setFilterSupplier(e.target.value)}
            className="text-sm px-3 py-2 rounded-md border outline-none"
            style={{
              borderColor: "var(--border)",
              background: "white",
              color: filterSupplier ? "var(--ink)" : "var(--ink-muted)",
              fontFamily: "var(--font-head)",
              minWidth: 160,
            }}
          >
            <option value="">All Suppliers</option>
            {supplierNames.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <select
            value={filterJobType}
            onChange={(e) => setFilterJobType(e.target.value)}
            className="text-sm px-3 py-2 rounded-md border outline-none"
            style={{
              borderColor: "var(--border)",
              background: "white",
              color: filterJobType ? "var(--ink)" : "var(--ink-muted)",
              fontFamily: "var(--font-head)",
              minWidth: 150,
            }}
          >
            <option value="">All Job Types</option>
            {JOB_TYPES.map((j) => (
              <option key={j.value} value={j.value}>{j.label}</option>
            ))}
          </select>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="text-sm px-3 py-2 rounded-md border outline-none"
            style={{
              borderColor: "var(--border)",
              background: "white",
              color: filterStatus ? "var(--ink)" : "var(--ink-muted)",
              fontFamily: "var(--font-head)",
              minWidth: 140,
            }}
          >
            <option value="">All Statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Divider */}
      <div className="mb-5" style={{ borderBottom: "1px solid var(--border)" }} />

      {/* Fetch error */}
      {fetchError && (
        <div className="rounded-lg border px-4 py-3 mb-5 text-sm"
          style={{ borderColor: "var(--red)", color: "var(--red)", background: "rgba(185,50,50,0.06)" }}>
          Failed to load sync jobs: {fetchError}
        </div>
      )}

      {/* Table */}
      <div className="rounded-xl border overflow-x-auto" style={{ borderColor: "var(--border)", background: "white" }}>
        <table className="w-full text-sm min-w-[720px]">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Supplier", "Job Type", "Status", "Records", "Duration", "Started", "Error"].map((h) => (
                <th
                  key={h}
                  className="text-left px-5 py-3 text-xs font-semibold uppercase tracking-wide"
                  style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {loading && [1, 2, 3, 4, 5].map((i) => <SkeletonRow key={i} />)}

            {!loading && jobs.map((j) => (
              <React.Fragment key={j.id}>
                <tr
                  className="transition-colors"
                  style={{ borderTop: "1px solid var(--border)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--paper)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "")}
                >
                  {/* Supplier */}
                  <td className="px-5 py-4 font-semibold" style={{ color: "var(--ink)" }}>
                    {j.supplier_name}
                  </td>

                  {/* Job Type */}
                  <td className="px-5 py-4" style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
                    {j.job_type === 'delta' ? 'Recent Changes' : 
                     (j.job_type as string === 'full' || j.job_type as string === 'full_sync') ? 'Full Refresh' : 
                     j.job_type}
                  </td>

                  {/* Status */}
                  <td className="px-5 py-4">
                    <StatusBadge status={j.status} />
                  </td>

                  {/* Records */}
                  <td className="px-5 py-4" style={{ fontFamily: "var(--font-mono)", color: "var(--ink)" }}>
                    {j.records_processed > 0 ? j.records_processed.toLocaleString() : "0"}
                  </td>

                  {/* Duration */}
                  <td className="px-5 py-4" style={{ fontFamily: "var(--font-mono)", color: "var(--ink-muted)" }}>
                    {fmtDuration(j.started_at, j.finished_at)}
                  </td>

                  {/* Started */}
                  <td className="px-5 py-4 text-xs" style={{ color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
                    {fmtStarted(j.started_at)}
                  </td>

                  {/* Error */}
                  <td className="px-5 py-4">
                    {j.error_log ? (
                      <button
                        onClick={() => setExpandedError(expandedError === j.id ? null : j.id)}
                        className="text-xs font-medium flex items-center gap-1"
                        style={{ color: "var(--red)", fontFamily: "var(--font-mono)" }}
                      >
                        {j.error_log.split("\n")[0].slice(0, 40)}
                        {j.error_log.length > 40 && "…"}
                        <span
                          style={{
                            display: "inline-block",
                            transition: "transform 0.15s",
                            transform: expandedError === j.id ? "rotate(180deg)" : "none",
                          }}
                        >
                          ▼
                        </span>
                      </button>
                    ) : (
                      <span style={{ color: "var(--ink-muted)" }}>—</span>
                    )}
                  </td>
                </tr>

                {/* Expanded error log */}
                {expandedError === j.id && j.error_log && (
                  <tr key={`${j.id}-err`} style={{ borderTop: "1px solid var(--border)" }}>
                    <td colSpan={7} className="px-5 py-4" style={{ background: "rgba(185,50,50,0.03)" }}>
                      <pre
                        className="text-xs rounded-md p-4 overflow-auto max-h-48 whitespace-pre-wrap"
                        style={{
                          background: "rgba(185,50,50,0.06)",
                          color: "var(--red)",
                          fontFamily: "var(--font-mono)",
                          border: "1px solid rgba(185,50,50,0.18)",
                        }}
                      >
                        {j.error_log}
                      </pre>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}

            {/* Empty state */}
            {!loading && jobs.length === 0 && !fetchError && (
              <tr>
                <td colSpan={7} className="px-5 py-16">
                  <EmptyState
                    title={filterStatus || filterSupplier ? "No match found" : "No updates yet"}
                    description={
                      filterStatus || filterSupplier
                        ? "Try adjusting your filters to see more sync activity."
                        : "No sync history detected. Connect a supplier and trigger your first data sync to see logs here."
                    }
                    icon={
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16m14-2V8a2 2 0 0 0-2-2h-4" />
                        <path d="M18 14l-4 4-2-2" />
                        <path d="M10 9l-1 0 1 0" />
                        <path d="M10 13l-1 0 1 0" />
                        <path d="M10 17l-1 0 1 0" />
                      </svg>
                    }
                  />
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

import React from "react";
