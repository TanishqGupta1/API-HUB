"use client";

import React, { useEffect, useState } from "react";
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
          <div className="stat-value" style={{ color: invHealth.color, fontSize: "22px" }}>
            {invFreshIso ? timeAgo(invFreshIso) : "—"}
          </div>
          <div className="stat-note">{invHealth.label}</div>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: "20px" }}>
        <div className="panel-header">
          <div className="panel-title">Supplier Health</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--ink-muted)" }}>
            AUTO_REFRESH_30S
          </div>
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: "12px",
            padding: "16px",
          }}
        >
          {suppliers.length === 0 ? (
            <div
              style={{
                gridColumn: "1 / -1",
                padding: "20px",
                textAlign: "center",
                color: "var(--ink-muted)",
                fontSize: "14px",
              }}
            >
              No suppliers configured yet.
            </div>
          ) : (
            suppliers.map((s) => {
              const last = supplierLastSync.get(s.id);
              const lastIso = last?.finished_at ?? last?.started_at ?? null;
              const h = healthFor(lastIso);
              return (
                <div
                  key={s.id}
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: "8px",
                    padding: "12px",
                    background: "var(--paper)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "start",
                      marginBottom: "8px",
                      gap: "8px",
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: "13px", color: "var(--ink)" }}>
                      {s.name}
                    </div>
                    <span
                      style={{
                        fontSize: "10px",
                        fontWeight: 600,
                        padding: "2px 8px",
                        borderRadius: "10px",
                        background: h.color + "22",
                        color: h.color,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {h.label}
                    </span>
                  </div>
                  <div
                    style={{
                      fontSize: "11px",
                      color: "var(--ink-muted)",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    Last sync: {lastIso ? timeAgo(lastIso) : "—"}
                  </div>
                  <div
                    style={{
                      fontSize: "11px",
                      color: "var(--ink-muted)",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    Products: {s.product_count}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {latestFailed && (
        <div
          className="panel"
          style={{ marginBottom: "20px", borderColor: "var(--red)" }}
        >
          <div className="panel-header">
            <div className="panel-title" style={{ color: "var(--red)" }}>
              Latest Failed Sync
            </div>
            <span
              style={{
                fontSize: "11px",
                color: "var(--ink-muted)",
                fontFamily: "var(--font-mono)",
              }}
            >
              {timeAgo(latestFailed.started_at)}
            </span>
          </div>
          <div style={{ padding: "12px 16px" }}>
            <div style={{ fontSize: "13px", marginBottom: "8px" }}>
              <strong>{latestFailed.supplier_name}</strong> —{" "}
              {JOB_TYPE_LABELS[latestFailed.job_type] ?? latestFailed.job_type}
            </div>
            {latestFailed.error_log && (
              <>
                <button
                  onClick={() =>
                    setExpandedErr(expandedErr === latestFailed.id ? null : latestFailed.id)
                  }
                  style={{
                    fontSize: "12px",
                    color: "var(--red)",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: 0,
                    fontFamily: "var(--font-mono)",
                    textAlign: "left",
                  }}
                >
                  {latestFailed.error_log.split("\n")[0].slice(0, 80)}
                  {latestFailed.error_log.length > 80 && "…"}{" "}
                  {expandedErr === latestFailed.id ? "▲" : "▼"}
                </button>
                {expandedErr === latestFailed.id && (
                  <pre
                    style={{
                      marginTop: "8px",
                      padding: "12px",
                      background: "rgba(185,50,50,0.06)",
                      color: "var(--red)",
                      fontSize: "11px",
                      fontFamily: "var(--font-mono)",
                      borderRadius: "6px",
                      overflow: "auto",
                      maxHeight: "200px",
                      whiteSpace: "pre-wrap",
                    }}
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
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
              color: "var(--blue)",
            }}
          >
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
                  style={{
                    padding: "40px",
                    textAlign: "center",
                    color: "var(--ink-muted)",
                    fontSize: "14px",
                  }}
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
