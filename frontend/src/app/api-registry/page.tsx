"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface PSCompany {
  Code: string;
  Name: string;
  Type: string;
}

export default function ApiRegistryPage() {
  const [companies, setCompanies] = useState<PSCompany[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api<PSCompany[]>("/api/ps-directory/companies")
      .then(setCompanies)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = companies.filter(
    (c) =>
      c.Name?.toLowerCase().includes(search.toLowerCase()) ||
      c.Code?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="screen active" id="s-api-registry">
      <div className="page-header">
        <div>
          <div className="page-title">API Registry</div>
          <div className="page-subtitle">
            PromoStandards supplier directory — {companies.length} vendors indexed
          </div>
        </div>
        <input
          type="text"
          placeholder="Search suppliers..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: "10px 16px",
            borderRadius: "5px",
            border: "1.5px solid var(--border)",
            fontFamily: "var(--font-head)",
            fontSize: "13px",
            background: "white",
            width: "240px",
          }}
        />
      </div>

      <div className="panel">
        <div className="panel-header">
          <div className="panel-title">PromoStandards Directory</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--ink-muted)" }}>
            {filtered.length} results
          </div>
        </div>

        {loading && (
          <div style={{ padding: "48px 24px", textAlign: "center", color: "var(--ink-muted)" }}>
            Loading directory...
          </div>
        )}

        {error && (
          <div style={{ padding: "24px", color: "var(--red)" }}>
            Error fetching directory: {error}
          </div>
        )}

        {!loading && !error && (
          <table>
            <thead>
              <tr>
                <th>Code</th>
                <th>Company Name</th>
                <th>Type</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 100).map((c) => (
                <tr key={c.Code}>
                  <td className="cell-mono">{c.Code}</td>
                  <td className="cell-primary">{c.Name}</td>
                  <td><span className="cell-tag">{c.Type}</span></td>
                </tr>
              ))}
              {filtered.length > 100 && (
                <tr>
                  <td colSpan={3} style={{ textAlign: "center", color: "var(--ink-muted)", padding: "16px" }}>
                    Showing 100 of {filtered.length} — refine your search
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
