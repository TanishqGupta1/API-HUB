"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type Stats = {
  suppliers: number;
  products: number;
  variants: number;
};

type SyncJob = {
  id: string;
  supplier_id: string;
  supplier_name: string;
  job_type: string;
  status: string;
  records_processed: number;
  started_at: string;
  finished_at: string | null;
  error_log: string | null;
};

type Supplier = {
  id: string;
  name: string;
  is_active: boolean;
  product_count: number;
};

const JOB_TYPE_LABELS: Record<string, string> = {
  inventory: "Inventory Update",
  delta: "Product Sync",
  full_sync: "Full Refresh",
  full: "Full Refresh",
  pricing: "Pricing Update",
  push_to_ops: "Published to Store",
};

function timeAgo(iso: string): string {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function healthFor(iso: string | null): { color: string; label: string } {
  if (!iso) return { color: "var(--ink-muted)", label: "Never synced" };
  const hours = (Date.now() - new Date(iso).getTime()) / 1000 / 3600;
  if (hours < 1) return { color: "var(--green)", label: "Fresh" };
  if (hours < 24) return { color: "#d4a017", label: "Stale" };
  return { color: "var(--red)", label: "Outdated" };
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats>({ suppliers: 0, products: 0, variants: 0 });
  const [jobs, setJobs] = useState<SyncJob[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [expandedErr, setExpandedErr] = useState<string | null>(null);

  useEffect(() => {
    const load = () => {
      api<Stats>("/api/stats").then(setStats).catch(console.error);
      api<SyncJob[]>("/api/sync-jobs?limit=50").then(setJobs).catch(console.error);
      api<Supplier[]>("/api/suppliers").then(setSuppliers).catch(console.error);
    };
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  const supplierLastSync = new Map<string, SyncJob>();
  jobs.forEach((j) => {
    if (j.status !== "completed") return;
    const prev = supplierLastSync.get(j.supplier_id);
    const jTime = new Date(j.finished_at ?? j.started_at).getTime();
    if (!prev || jTime > new Date(prev.finished_at ?? prev.started_at).getTime()) {
      supplierLastSync.set(j.supplier_id, j);
    }
  });

  const latestInventorySync = jobs
    .filter((j) => j.status === "completed" && j.job_type === "inventory")
    .sort(
      (a, b) =>
        new Date(b.finished_at ?? b.started_at).getTime() -
        new Date(a.finished_at ?? a.started_at).getTime()
    )[0];

  const latestFailed = jobs
    .filter((j) => j.status === "failed")
    .sort(
      (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
    )[0];

  const recentJobs = jobs.slice(0, 5);
  const invFreshIso = latestInventorySync?.finished_at ?? latestInventorySync?.started_at ?? null;
  const invHealth = healthFor(invFreshIso);

  return (
    <div className="screen active" id="s-dashboard">
      <div className="page-header">
        <div>
          <div className="page-title">Operational Overview</div>
          <div className="page-subtitle">Live sync metrics from active suppliers</div>
        </div>
        <button className="btn btn-ghost">Export Report</button>
      </div>

      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-label">Suppliers</div>
          <div className="stat-value">{stats.suppliers.toString().padStart(2, "0")}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">SKUs Indexed</div>
          <div className="stat-value">
            {stats.products >= 1000
              ? `${(stats.products / 1000).toFixed(1)}k`
              : stats.products}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Variants</div>
          <div className="stat-value">
            {stats.variants >= 1000
              ? `${(stats.variants / 1000).toFixed(0)}k`
              : stats.variants}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Inventory Freshness</div>
          <div className={`stat-value text-[22px]`} style={{ color: invHealth.color }}>
            {invFreshIso ? timeAgo(invFreshIso) : "—"}
          </div>
          <div className="stat-note">{invHealth.label}</div>
        </div>
      </div>

      <div className="panel mb-5">
        <div className="panel-header">
          <div className="panel-title">Supplier Health</div>
          <div className="font-mono text-[11px] text-[#888894]">
            AUTO_REFRESH_30S
          </div>
        </div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3 p-4">
          {suppliers.length === 0 ? (
            <div className="col-span-full p-5 text-center text-[#888894] text-[14px]">
              No suppliers configured yet.
            </div>
          ) : (
            suppliers.map((s) => {
              const last = supplierLastSync.get(s.id);
              const lastIso = last?.finished_at ?? last?.started_at ?? null;
              const h = healthFor(lastIso);
              return (
                <Link
                  key={s.id}
                  href={`/mappings/${s.id}`}
                  className="border border-[#cfccc8] rounded-lg p-3 bg-white hover:border-[var(--blue)] hover:shadow-sm transition-all block group"
                >
                  <div className="flex justify-between items-start mb-2 gap-2">
                    <div className="font-semibold text-[13px] text-[#1e1e24] group-hover:text-[var(--blue)] transition-colors">
                      {s.name}
                    </div>
                    <span
                      className="text-[10px] font-semibold px-2 py-0.5 rounded-[10px] whitespace-nowrap"
                      style={{
                        background: h.color + "22",
                        color: h.color,
                      }}
                    >
                      {h.label}
                    </span>
                  </div>
                  <div className="text-[11px] text-[#888894] font-mono">
                    Last sync: {lastIso ? timeAgo(lastIso) : "—"}
                  </div>
                  <div className="text-[11px] text-[#888894] font-mono">
                    Products: {s.product_count}
                  </div>
                </Link>
              );
            })
          )}
        </div>
      </div>

      {latestFailed && (
        <div className="panel mb-5 border-[#b93232]">
          <div className="panel-header">
            <div className="panel-title text-[#b93232]">
              Latest Failed Sync
            </div>
            <span className="text-[11px] text-[#888894] font-mono">
              {timeAgo(latestFailed.started_at)}
            </span>
          </div>
          <div className="p-3 px-4">
            <div className="text-[13px] mb-2">
              <strong>{latestFailed.supplier_name}</strong> —{" "}
              {JOB_TYPE_LABELS[latestFailed.job_type] ?? latestFailed.job_type}
            </div>
            {latestFailed.error_log && (
              <>
                <button
                  onClick={() =>
                    setExpandedErr(expandedErr === latestFailed.id ? null : latestFailed.id)
                  }
                  className="text-[12px] text-[#b93232] bg-none border-none cursor-pointer p-0 font-mono text-left"
                >
                  {latestFailed.error_log.split("\n")[0].slice(0, 80)}
                  {latestFailed.error_log.length > 80 && "…"}{" "}
                  {expandedErr === latestFailed.id ? "▲" : "▼"}
                </button>
                {expandedErr === latestFailed.id && (
                  <pre
                    className="mt-2 p-3 bg-[#b93232]/[0.06] text-[#b93232] text-[11px] font-mono rounded-md overflow-auto max-h-[200px] whitespace-pre-wrap"
                  >
                    {latestFailed.error_log}
                  </pre>
                )}
              </>
            )}
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-header">
          <div className="panel-title">Recent Data Updates</div>
          <div className="font-mono text-[11px] text-[#1e4d92]">
            LIVE_STREAMING
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Supplier</th>
              <th>Operation</th>
              <th>Records</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {recentJobs.map((job) => (
              <tr key={job.id}>
                <td className="cell-primary">{job.supplier_name}</td>
                <td className="cell-mono">
                  {JOB_TYPE_LABELS[job.job_type] ?? job.job_type}
                </td>
                <td className="cell-mono">{job.records_processed}</td>
                <td>
                  <span
                    className={`badge ${
                      job.status === "failed"
                        ? "badge-err"
                        : job.status === "running"
                        ? "badge-warn"
                        : "badge-ok"
                    }`}
                  >
                    <span className="badge-dot"></span>{" "}
                    {job.status === "failed"
                      ? "Connection Failed"
                      : job.status === "running"
                      ? "Running"
                      : "Complete"}
                  </span>
                </td>
              </tr>
            ))}

            {recentJobs.length === 0 && (
              <tr>
                <td
                  colSpan={4}
                  className="p-10 text-center text-[#888894] text-[14px]"
                >
                  No sync history yet. Activate a supplier to see updates here.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
