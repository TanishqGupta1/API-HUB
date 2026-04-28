"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { SyncJob } from "@/lib/types";

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

function timeAgo(iso: string): string {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

type HealthInfo = { color: string; bgColor: string; dot: string; label: string };

function healthFor(iso: string | null, lastStatus?: string): HealthInfo {
  if (!iso) {
    if (lastStatus === "failed")
      return { color: "#b93232", bgColor: "#b9323222", dot: "bg-[#b93232]", label: "Error" };
    return { color: "#888894", bgColor: "#88889422", dot: "bg-[#888894]", label: "Never synced" };
  }
  const hours = (Date.now() - new Date(iso).getTime()) / 1000 / 3600;
  if (hours < 1)
    return { color: "#247a52", bgColor: "#247a5222", dot: "bg-[#247a52]", label: "Fresh" };
  if (hours < 24)
    return { color: "#d4a017", bgColor: "#d4a01722", dot: "bg-[#d4a017]", label: "Stale" };
  return { color: "#b93232", bgColor: "#b9323222", dot: "bg-[#b93232]", label: "Outdated" };
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
  const statusStyles: Record<string, string> = {
    completed: "bg-[#e6f3ec] text-[#247a52]",
    running:   "bg-[#eef4fb] text-[#1e4d92]",
    failed:    "bg-[#fdeded] text-[#b93232]",
    pending:   "bg-[#f9f7f4] text-[#484852]",
  };
  const dotStyles: Record<string, string> = {
    completed: "bg-[#247a52]",
    running:   "bg-[#1e4d92]",
    failed:    "bg-[#b93232]",
    pending:   "bg-[#484852]",
  };
  const currentStyle = statusStyles[status] || statusStyles.pending;
  const currentDot = dotStyles[status] || dotStyles.pending;

  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full ${currentStyle}`}>
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${currentDot} ${status === "running" ? "animate-pulse" : ""}`} />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function SkeletonRow() {
  return (
    <tr className="border-t border-[#cfccc8]">
      {[120, 80, 100, 60, 60, 110, 90].map((w, i) => (
        <td key={i} className="px-5 py-4">
          <div className="h-3 rounded animate-pulse w-full bg-[#f2f0ed]" style={{ width: w }} />
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

  // Per-supplier health badges — derived from ALL jobs (unfiltered wouldn't matter since we load all)
  const perSupplierHealth = useMemo(() => {
    const successMap = new Map<string, SyncJob>();
    const attemptMap = new Map<string, SyncJob>();

    jobs.forEach((j) => {
      const jTime = new Date(j.finished_at ?? j.started_at).getTime();
      const prevAttempt = attemptMap.get(j.supplier_id);
      if (!prevAttempt || jTime > new Date(prevAttempt.finished_at ?? prevAttempt.started_at).getTime()) {
        attemptMap.set(j.supplier_id, j);
      }
      if (j.status !== "completed") return;
      const prevSuccess = successMap.get(j.supplier_id);
      if (!prevSuccess || jTime > new Date(prevSuccess.finished_at ?? prevSuccess.started_at).getTime()) {
        successMap.set(j.supplier_id, j);
      }
    });

    const seen = new Set<string>();
    const entries: {
      id: string;
      name: string;
      lastSuccessIso: string | null;
      lastAttempt: SyncJob | null;
      health: HealthInfo;
    }[] = [];

    jobs.forEach((j) => {
      if (seen.has(j.supplier_id)) return;
      seen.add(j.supplier_id);
      const lastSuccess = successMap.get(j.supplier_id);
      const lastAttempt = attemptMap.get(j.supplier_id) ?? null;
      const lastSuccessIso = lastSuccess?.finished_at ?? lastSuccess?.started_at ?? null;
      const health = healthFor(lastSuccessIso, lastAttempt?.status);
      entries.push({ id: j.supplier_id, name: j.supplier_name, lastSuccessIso, lastAttempt, health });
    });

    return entries.sort((a, b) => a.name.localeCompare(b.name));
  }, [jobs]);

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
          <h1 className="text-3xl font-bold text-[#1e1e24]">Data Updates</h1>
          <p className="text-sm mt-1 text-[#484852]">Execution history of your data pipelines</p>
        </div>

        {/* Dropdown filters */}
        <div className="flex gap-3 items-center">
          <select
            value={filterSupplier}
            onChange={(e) => setFilterSupplier(e.target.value)}
            className={`text-sm px-3 py-2 rounded-md border border-[#cfccc8] bg-white outline-none min-w-[160px] font-sans ${
              filterSupplier ? "text-[#1e1e24]" : "text-[#484852]"
            }`}
          >
            <option value="">All Suppliers</option>
            {supplierNames.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <select
            value={filterJobType}
            onChange={(e) => setFilterJobType(e.target.value)}
            className={`text-sm px-3 py-2 rounded-md border border-[#cfccc8] bg-white outline-none min-w-[150px] font-sans ${
              filterJobType ? "text-[#1e1e24]" : "text-[#484852]"
            }`}
          >
            <option value="">All Job Types</option>
            {JOB_TYPES.map((j) => (
              <option key={j.value} value={j.value}>{j.label}</option>
            ))}
          </select>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className={`text-sm px-3 py-2 rounded-md border border-[#cfccc8] bg-white outline-none min-w-[140px] font-sans ${
              filterStatus ? "text-[#1e1e24]" : "text-[#484852]"
            }`}
          >
            <option value="">All Statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Per-supplier health strip */}
      {perSupplierHealth.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {perSupplierHealth.map(({ id, name, lastSuccessIso, lastAttempt, health }) => {
            const displayTime = lastSuccessIso
              ? timeAgo(lastSuccessIso)
              : lastAttempt
              ? timeAgo(lastAttempt.finished_at ?? lastAttempt.started_at)
              : null;
            return (
              <div
                key={id}
                className="inline-flex items-center gap-2 px-3 py-[7px] rounded-lg border border-[#cfccc8] bg-white hover:border-[#1e4d92] transition-colors"
                title={`${name} — ${health.label}${displayTime ? ` · ${displayTime}` : ""}`}
              >
                {/* Colored status dot */}
                <span className={`w-2 h-2 rounded-full shrink-0 ${health.dot}`} />
                {/* Supplier name */}
                <span className="text-[12px] font-semibold text-[#1e1e24]">{name}</span>
                {/* Health label pill */}
                <span
                  className="text-[10px] font-bold font-mono uppercase px-[6px] py-[2px] rounded"
                  style={{ background: health.bgColor, color: health.color }}
                >
                  {health.label}
                </span>
                {/* Time ago */}
                {displayTime && (
                  <span className="text-[11px] text-[#888894] font-mono">{displayTime}</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Divider */}
      <div className="mb-5 border-b border-[#cfccc8]" />

      {/* Fetch error */}
      {fetchError && (
        <div className="rounded-lg border border-[#b93232] px-4 py-3 mb-5 text-sm text-[#b93232] bg-[#fdf2f2]">
          Failed to load sync jobs: {fetchError}
        </div>
      )}

      {/* Table */}
      <div className="rounded-xl border border-[#cfccc8] bg-white overflow-x-auto">
        <table className="w-full text-sm min-w-[720px]">
          <thead>
            <tr className="border-b border-[#cfccc8]">
              {["Supplier", "Job Type", "Status", "Records", "Duration", "Started"].map((h) => (
                <th
                  key={h}
                  className="text-left px-5 py-3 text-xs font-semibold uppercase tracking-wide text-[#484852] font-mono"
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
                <tr className="transition-colors border-t border-[#cfccc8] hover:bg-[#f9f7f4]">
                  {/* Supplier */}
                  <td className="px-5 py-4 font-semibold text-[#1e1e24]">
                    {j.supplier_name}
                  </td>

                  {/* Job Type */}
                  <td className="px-5 py-4 text-[#484852] font-mono">
                    {j.job_type === 'delta' ? 'Recent Changes' : 
                     (j.job_type as string === 'full' || j.job_type as string === 'full_sync') ? 'Full Refresh' : 
                     j.job_type}
                  </td>

                  {/* Status */}
                  <td className="px-5 py-4">
                    <StatusBadge status={j.status} />
                  </td>

                  {/* Records */}
                  <td className="px-5 py-4 font-mono text-[#1e1e24]">
                    {j.records_processed > 0 ? j.records_processed.toLocaleString() : "0"}
                  </td>

                  {/* Duration */}
                  <td className="px-5 py-4 font-mono text-[#484852]">
                    {fmtDuration(j.started_at, j.finished_at)}
                  </td>

                  {/* Started */}
                  <td className="px-5 py-4 text-xs text-[#484852] font-mono">
                    {fmtStarted(j.started_at)}
                  </td>
                </tr>
              </React.Fragment>
            ))}

            {/* Empty state */}
            {!loading && jobs.length === 0 && !fetchError && (
              <tr>
                <td colSpan={7} className="px-5 py-16 text-center">
                  <div className="text-3xl mb-3">📋</div>
                  <div className="text-sm font-semibold mb-1 text-[#1e1e24]">
                    {filterStatus || filterSupplier ? "No jobs match these filters" : "No updates yet"}
                  </div>
                  <div className="text-xs text-[#484852]">
                    {filterStatus || filterSupplier
                      ? "Try changing the filters above."
                      : "No sync history yet. Activate a supplier to see data updates here."}
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

    </div>
  );
}
