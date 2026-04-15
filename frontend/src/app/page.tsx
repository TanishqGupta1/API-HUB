"use client";

import React from "react";

export default function Dashboard() {
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
          <div className="stat-value">04</div>
          <div className="stat-note">
            +1 <span style={{ fontFamily: "Arial" }}>&uarr;</span> 7d
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">SKUs Indexed</div>
          <div className="stat-value">32.4k</div>
          <div className="stat-note">+1.2k today</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Variants</div>
          <div className="stat-value">187k</div>
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
            <tr>
              <td className="cell-primary">SanMar Corporation</td>
              <td className="cell-mono">inventory_sync_v2</td>
              <td className="cell-mono">12,450</td>
              <td className="cell-mono">42.4s</td>
              <td>
                <span className="badge badge-ok">
                  <span className="badge-dot"></span> Complete
                </span>
              </td>
            </tr>
            <tr>
              <td className="cell-primary">S&S Activewear</td>
              <td className="cell-mono">pricing_update</td>
              <td className="cell-mono">8,201</td>
              <td className="cell-mono">18.1s</td>
              <td>
                <span className="badge badge-ok">
                  <span className="badge-dot"></span> Complete
                </span>
              </td>
            </tr>
            <tr>
              <td className="cell-primary">alphabroder</td>
              <td className="cell-mono">delta_product_ingest</td>
              <td className="cell-mono">11,800</td>
              <td className="cell-mono">1m 12s</td>
              <td>
                <span className="badge badge-ok">
                  <span className="badge-dot"></span> Complete
                </span>
              </td>
            </tr>
            <tr>
              <td className="cell-primary">4Over</td>
              <td className="cell-mono">full_catalog_push</td>
              <td className="cell-mono">0</td>
              <td className="cell-mono">2.2s</td>
              <td>
                <span className="badge badge-err">
                  <span className="badge-dot"></span> Auth_Error
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
