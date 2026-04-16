"use client";

import React from "react";

export default function MarkupPage() {
  return (
    <div className="screen active">
      <div className="page-header">
        <div>
          <div className="page-title">Markup Rules</div>
          <div className="page-subtitle">Defining pricing transformations for OPS synchronization</div>
        </div>
        <button className="btn btn-primary">+ Create Rule</button>
      </div>

      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-label">Active Rules</div>
          <div className="stat-value">03</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Avg Markup</div>
          <div className="stat-value">22<span style={{ fontSize: "18px" }}>%</span></div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div className="panel-title">Pricing Tables</div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Rule Name</th>
              <th>Destination</th>
              <th>Formula</th>
              <th>Priority</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="cell-primary">Standard Retail 2.2x</td>
              <td className="cell-mono">Acme Corp (Prod)</td>
              <td className="cell-mono">unit_cost * 2.2</td>
              <td className="cell-mono">10</td>
              <td><span className="badge badge-ok"><span className="badge-dot"></span> Active</span></td>
            </tr>
            <tr>
              <td className="cell-primary">VIP Wholesale 1.4x</td>
              <td className="cell-mono">B2B Portal</td>
              <td className="cell-mono">unit_cost * 1.4</td>
              <td className="cell-mono">20</td>
              <td><span className="badge badge-ok"><span className="badge-dot"></span> Active</span></td>
            </tr>
            <tr>
              <td className="cell-primary">Clearance / Sale</td>
              <td className="cell-mono">Acme Corp (Prod)</td>
              <td className="cell-mono">unit_cost * 1.05</td>
              <td className="cell-mono">5</td>
              <td><span className="badge badge-ok"><span className="badge-dot"></span> Active</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: "40px", padding: "32px", border: "2px dashed var(--border)", borderRadius: "12px", background: "var(--vellum)" }}>
         <div style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--blue)", marginBottom: "8px" }}>Interactive Preview</div>
         <div style={{ fontSize: "13px", color: "var(--ink-muted)", marginBottom: "20px" }}>Test how rules apply to specific products before syncing.</div>
         <div style={{ display: "flex", gap: "20px", alignItems: "flex-end" }}>
            <div style={{ flex: 1 }}>
                <label className="field-label">Test SKU</label>
                <input type="text" className="input-control" placeholder="e.g. SAN-L100" defaultValue="SAN-L100" />
            </div>
            <div style={{ flex: 1 }}>
                <label className="field-label">Source Cost</label>
                <div style={{ fontSize: "24px", fontWeight: 800, fontFamily: "var(--font-mono)", color: "var(--ink-light)" }}>$12.45</div>
            </div>
            <div style={{ flex: 1, padding: "10px", background: "var(--blue-pale)", borderRadius: "8px", border: "1.5px solid var(--blue)" }}>
                <label className="field-label" style={{ color: "var(--blue)" }}>Final Price</label>
                <div style={{ fontSize: "24px", fontWeight: 800, fontFamily: "var(--font-mono)", color: "var(--blue)" }}>$27.39</div>
            </div>
         </div>
      </div>
    </div>
  );
}
