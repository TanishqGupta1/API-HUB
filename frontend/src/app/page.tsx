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
  supplier_name: string;
  job_type: string;
  status: string;
  records_processed: number;
  started_at: string;
  finished_at: string | null;
  error_log: string | null;
};

const JOB_TYPE_LABELS: Record<string, string> = {
  inventory: "Inventory Update",
  delta: "Product Sync",
  full_sync: "Full Refresh",
  pricing: "Pricing Update",
  push_to_ops: "Published to Store",
};

export default function Dashboard() {
  const [stats, setStats] = useState<Stats>({ suppliers: 0, products: 0, variants: 0 });
  const [jobs, setJobs] = useState<SyncJob[]>([]);

  useEffect(() => {
    api<Stats>("/api/stats").then(setStats).catch(console.error);
    api<SyncJob[]>("/api/sync-jobs?limit=5").then(setJobs).catch(console.error);
  }, []);

  return (
    <div className="screen active" id="s-dashboard">
      <div className="page-header">
        <div>
          <div className="page-title">Operational Overview</div>
          <div className="page-subtitle">
            Live sync metrics from active suppliers
          </div>
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
          <div className="stat-label">System Health</div>
          <div className="stat-value">
            <span style={{ fontSize: "14px", color: "var(--ink-muted)" }}>—</span>
          </div>
        </div>
      </div>

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
            {jobs.map((job) => (
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

            {jobs.length === 0 && (
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
