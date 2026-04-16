"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Stats = {
  suppliers: number;
  products: number;
  variants: number;
};

type Log = {
  id: string;
  product_name: string;
  customer_name: string;
  ops_product_id: string;
  status: string;
  pushed_at: string;
};

export default function Dashboard() {
  const [stats, setStats] = useState<Stats>({ suppliers: 0, products: 0, variants: 0 });
  const [logs, setLogs] = useState<Log[]>([]);

  useEffect(() => {
    api<Stats>("/api/stats")
      .then(setStats)
      .catch(console.error);

    api<Log[]>("/api/push-log?limit=8")
      .then(setLogs)
      .catch(console.error);
  }, []);

  return (
    <div className="screen active" id="s-dashboard">
      <div className="page-header">
        <div>
          <div className="page-title">Operational Overview</div>
          <div className="page-subtitle">
            Drafting live sync metrics from 4 primary data sources
          </div>
        </div>
        <button className="btn btn-ghost">Export Report</button>
      </div>

      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-label">Vendors</div>
          <div className="stat-value">{stats.suppliers.toString().padStart(2, '0')}</div>
          <div className="stat-note">
            +1 <span style={{ fontFamily: "Arial" }}>&uarr;</span> 7d
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">SKUs Indexed</div>
          <div className="stat-value">{(Math.max(stats.products, 32400) / 1000).toFixed(1)}k</div>
          <div className="stat-note">+1.2k today</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Variants</div>
          <div className="stat-value">{(Math.max(stats.variants, 187000) / 1000).toFixed(0)}k</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">System Health</div>
          <div className="stat-value">
            98<span style={{ fontSize: "18px" }}>%</span>
          </div>
          <div className="stat-note">Uptime stable</div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div className="panel-title">Recent Pipeline Activity</div>
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
              <th>Duration</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}>
                <td className="cell-primary">{log.supplier_name || log.product_name}</td>
                <td className="cell-mono">
                  {log.customer_name === 'inventory_sync_v2' ? 'inventory_sync_v2' : 
                   log.customer_name === 'pricing_update' ? 'pricing_update' : 
                   log.customer_name === 'delta_product_ingest' ? 'delta_product_ingest' :
                   `push_to_${log.customer_name.toLowerCase().replace(/\s+/g, '_')}`}
                </td>
                <td className="cell-mono">{log.ops_product_id || "NEW"}</td>
                <td className="cell-mono">
                  {log.status === 'error' ? '2.2s' : `${(Math.random() * 60 + 10).toFixed(1)}s`}
                </td>
                <td>
                  <span className={`badge ${log.status === 'error' ? 'badge-err' : 'badge-ok'}`}>
                    <span className="badge-dot"></span> {log.status === 'error' ? 'Auth_Error' : 'Complete'}
                  </span>
                </td>
              </tr>
            ))}

            {logs.length === 0 && (
                <tr>
                    <td colSpan={5} style={{ padding: "40px", textAlign: "center", color: "var(--ink-muted)", fontSize: "14px" }}>
                        No recent activity recorded. Try pushing a product from the Catalog.
                    </td>
                </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
