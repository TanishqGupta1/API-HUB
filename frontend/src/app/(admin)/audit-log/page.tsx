"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { RefreshCw } from "lucide-react";

interface AuditLogEntry {
  id: string;
  user_email: string | null;
  method: string;
  path: string;
  status_code: number | null;
  created_at: string;
}

const METHOD_COLORS: Record<string, string> = {
  POST: "#1e4d92",
  PUT: "#d97706",
  PATCH: "#7c3aed",
  DELETE: "#dc2626",
};

function StatusBadge({ code }: { code: number | null }) {
  if (!code) return <span style={{ color: "var(--ink-muted)", fontSize: "11px" }}>—</span>;
  const ok = code < 400;
  return (
    <span
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: "10px",
        fontWeight: 700,
        color: ok ? "#16a34a" : "#dc2626",
        background: ok ? "#dcfce7" : "#fee2e2",
        border: `1px solid ${ok ? "#bbf7d0" : "#fecaca"}`,
        padding: "2px 7px",
        borderRadius: "999px",
      }}
    >
      {code}
    </span>
  );
}

export default function AuditLogPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    api<AuditLogEntry[]>("/api/audit-log?limit=200")
      .then(setLogs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="page-container">
      <div className="page-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h1 className="page-title">Audit Log</h1>
        <button
          onClick={load}
          disabled={loading}
          style={{
            display: "flex", alignItems: "center", gap: "6px",
            padding: "6px 14px", background: "var(--blue)", color: "#fff",
            border: "none", borderRadius: "3px", fontSize: "12px", fontWeight: 700,
            cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.7 : 1,
          }}
        >
          <RefreshCw style={{ width: "12px", height: "12px" }} />
          Refresh
        </button>
      </div>

      {loading ? (
        <div style={{ color: "var(--ink-muted)", fontSize: "13px", padding: "40px 0" }}>Loading…</div>
      ) : logs.length === 0 ? (
        <div style={{ padding: "60px", textAlign: "center", border: "2px dashed var(--border)", borderRadius: "8px", color: "var(--ink-muted)", fontSize: "14px" }}>
          No write activity recorded yet.
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--border)" }}>
                {["Time", "User", "Method", "Path", "Status"].map((h) => (
                  <th key={h} style={{ textAlign: "left", padding: "8px 12px", fontSize: "10px", fontWeight: 700, color: "var(--ink-muted)", textTransform: "uppercase", letterSpacing: "0.06em", whiteSpace: "nowrap" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "9px 12px", color: "var(--ink-muted)", fontFamily: "var(--font-mono)", fontSize: "11px", whiteSpace: "nowrap" }}>
                    {new Date(log.created_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                  </td>
                  <td style={{ padding: "9px 12px", fontSize: "12px", color: "var(--ink)" }}>
                    {log.user_email ?? <span style={{ color: "var(--ink-faint)", fontStyle: "italic" }}>anonymous</span>}
                  </td>
                  <td style={{ padding: "9px 12px" }}>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "10px", fontWeight: 700, color: METHOD_COLORS[log.method] ?? "var(--ink)", background: `${METHOD_COLORS[log.method] ?? "#888"}18`, border: `1px solid ${METHOD_COLORS[log.method] ?? "#888"}40`, padding: "2px 7px", borderRadius: "999px" }}>
                      {log.method}
                    </span>
                  </td>
                  <td style={{ padding: "9px 12px", fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--ink)", maxWidth: "360px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {log.path}
                  </td>
                  <td style={{ padding: "9px 12px" }}>
                    <StatusBadge code={log.status_code} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
