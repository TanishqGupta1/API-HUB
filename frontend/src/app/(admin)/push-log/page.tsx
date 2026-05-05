"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { CheckCircle2, Clock, XCircle, RefreshCw } from "lucide-react";

interface PushLogEntry {
  id: string;
  product_id: string;
  product_name: string | null;
  supplier_name: string | null;
  customer_id: string;
  customer_name: string | null;
  ops_product_id: string | null;
  status: string;
  error: string | null;
  pushed_at: string;
}

const STATUS_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  pushed: {
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    color: "#16a34a",
    label: "Pushed",
  },
  pending: {
    icon: <Clock className="w-3.5 h-3.5" />,
    color: "#d97706",
    label: "Pending",
  },
  failed: {
    icon: <XCircle className="w-3.5 h-3.5" />,
    color: "#dc2626",
    label: "Failed",
  },
  skipped: {
    icon: <XCircle className="w-3.5 h-3.5" />,
    color: "#888894",
    label: "Skipped",
  },
};

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? { icon: null, color: "#888894", label: status };
  return (
    <span
      className="inline-flex items-center gap-1 font-mono text-[10px] font-bold uppercase px-2 py-0.5 rounded-full"
      style={{ color: cfg.color, background: `${cfg.color}18`, border: `1px solid ${cfg.color}40` }}
    >
      {cfg.icon}
      {cfg.label}
    </span>
  );
}

export default function PushLogPage() {
  const [logs, setLogs] = useState<PushLogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    api<PushLogEntry[]>("/api/push-log?limit=100")
      .then(setLogs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="page-container">
      <div className="page-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h1 className="page-title">Push Log</h1>
        <button
          onClick={load}
          disabled={loading}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "6px 14px",
            background: "var(--blue)",
            color: "#fff",
            border: "none",
            borderRadius: "3px",
            fontSize: "12px",
            fontWeight: 700,
            cursor: loading ? "not-allowed" : "pointer",
            opacity: loading ? 0.7 : 1,
          }}
        >
          <RefreshCw style={{ width: "12px", height: "12px" }} />
          Refresh
        </button>
      </div>

      {loading ? (
        <div style={{ color: "var(--ink-muted)", fontSize: "13px", padding: "40px 0" }}>Loading…</div>
      ) : logs.length === 0 ? (
        <div
          style={{
            padding: "60px",
            textAlign: "center",
            border: "2px dashed var(--border)",
            borderRadius: "8px",
            color: "var(--ink-muted)",
            fontSize: "14px",
          }}
        >
          No push activity yet.
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--border)" }}>
                {["Time", "Product", "Supplier", "Storefront", "OPS ID", "Status", "Error"].map((h) => (
                  <th
                    key={h}
                    style={{
                      textAlign: "left",
                      padding: "8px 12px",
                      fontSize: "10px",
                      fontWeight: 700,
                      color: "var(--ink-muted)",
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr
                  key={log.id}
                  style={{ borderBottom: "1px solid var(--border)", verticalAlign: "top" }}
                >
                  <td style={{ padding: "10px 12px", color: "var(--ink-muted)", fontFamily: "var(--font-mono)", fontSize: "11px", whiteSpace: "nowrap" }}>
                    {new Date(log.pushed_at).toLocaleString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td style={{ padding: "10px 12px", color: "var(--ink)", maxWidth: "220px" }}>
                    <div style={{ fontWeight: 600, lineHeight: 1.3 }}>{log.product_name ?? "—"}</div>
                  </td>
                  <td style={{ padding: "10px 12px", color: "var(--ink-muted)", fontFamily: "var(--font-mono)", fontSize: "11px" }}>
                    {log.supplier_name ?? "—"}
                  </td>
                  <td style={{ padding: "10px 12px", color: "var(--ink-muted)", fontSize: "12px" }}>
                    {log.customer_name ?? "—"}
                  </td>
                  <td style={{ padding: "10px 12px", fontFamily: "var(--font-mono)", fontSize: "11px", color: log.ops_product_id ? "var(--blue)" : "var(--ink-faint)" }}>
                    {log.ops_product_id ?? "—"}
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    <StatusBadge status={log.status} />
                  </td>
                  <td style={{ padding: "10px 12px", color: "#dc2626", fontSize: "11px", maxWidth: "200px" }}>
                    {log.error ?? ""}
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
