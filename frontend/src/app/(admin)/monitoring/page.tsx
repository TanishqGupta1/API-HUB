"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { RefreshCw, Activity, Database, Server, ExternalLink } from "lucide-react";

interface Stats {
  suppliers: number;
  products: number;
  variants: number;
}

interface HealthStatus {
  status: string;
  service: string;
}

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
  ok?: boolean;
}

function StatCard({ label, value, sub, icon, ok = true }: StatCardProps) {
  return (
    <div
      style={{
        background: "var(--paper)",
        border: "1px solid var(--border)",
        borderRadius: "6px",
        padding: "20px 24px",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--ink-muted)" }}>
        {icon}
        <span style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
          {label}
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
        <span style={{ fontSize: "28px", fontWeight: 800, color: ok ? "var(--ink)" : "#dc2626", letterSpacing: "-0.03em" }}>
          {value}
        </span>
        {sub && (
          <span style={{ fontSize: "12px", color: "var(--ink-muted)", fontWeight: 500 }}>{sub}</span>
        )}
      </div>
    </div>
  );
}

function ExternalDashboardLink({ label, url, description }: { label: string; url: string; description: string }) {
  if (!url) return null;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "16px 20px",
        background: "var(--paper)",
        border: "1px solid var(--border)",
        borderRadius: "6px",
        textDecoration: "none",
        color: "var(--ink)",
        transition: "border-color 0.15s",
      }}
    >
      <div>
        <div style={{ fontSize: "14px", fontWeight: 700 }}>{label}</div>
        <div style={{ fontSize: "12px", color: "var(--ink-muted)", marginTop: "2px" }}>{description}</div>
      </div>
      <ExternalLink style={{ width: "14px", height: "14px", color: "var(--ink-muted)", flexShrink: 0 }} />
    </a>
  );
}

export default function MonitoringPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);

  const grafanaUrl = process.env.NEXT_PUBLIC_GRAFANA_URL || "";
  const datadogUrl = process.env.NEXT_PUBLIC_DATADOG_URL || "";

  async function load() {
    setLoading(true);
    try {
      const [h, s] = await Promise.all([
        fetch("/health").then((r) => r.json() as Promise<HealthStatus>),
        api<Stats>("/api/stats"),
      ]);
      setHealth(h);
      setStats(s);
    } catch {
      setHealth(null);
    } finally {
      setLoading(false);
      setCheckedAt(new Date());
    }
  }

  useEffect(() => {
    load();
  }, []);

  const apiOk = health?.status === "ok";

  return (
    <div className="page-container">
      <div
        className="page-header"
        style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}
      >
        <div>
          <h1 className="page-title">System Health</h1>
          {checkedAt && (
            <p style={{ fontSize: "12px", color: "var(--ink-muted)", marginTop: "4px" }}>
              Last checked: {checkedAt.toLocaleTimeString()}
            </p>
          )}
        </div>
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
        <div style={{ color: "var(--ink-muted)", fontSize: "13px", padding: "40px 0" }}>
          Checking system health…
        </div>
      ) : (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
              gap: "16px",
              marginBottom: "32px",
            }}
          >
            <StatCard
              label="API Status"
              value={apiOk ? "Online" : "Offline"}
              icon={<Server style={{ width: "13px", height: "13px" }} />}
              ok={apiOk}
            />
            <StatCard
              label="Suppliers"
              value={stats?.suppliers ?? "—"}
              sub="connected"
              icon={<Activity style={{ width: "13px", height: "13px" }} />}
            />
            <StatCard
              label="Products"
              value={stats?.products?.toLocaleString() ?? "—"}
              sub="in catalog"
              icon={<Database style={{ width: "13px", height: "13px" }} />}
            />
            <StatCard
              label="Variants"
              value={stats?.variants?.toLocaleString() ?? "—"}
              sub="total SKUs"
              icon={<Database style={{ width: "13px", height: "13px" }} />}
            />
          </div>

          {(grafanaUrl || datadogUrl) && (
            <div>
              <h2
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  color: "var(--ink-muted)",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  marginBottom: "12px",
                }}
              >
                External Dashboards
              </h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {grafanaUrl && (
                  <ExternalDashboardLink
                    label="Grafana"
                    url={grafanaUrl}
                    description="Infrastructure metrics — latency, error rates, DB connections"
                  />
                )}
                {datadogUrl && (
                  <ExternalDashboardLink
                    label="Datadog"
                    url={datadogUrl}
                    description="APM traces, logs, and SLO tracking"
                  />
                )}
              </div>
            </div>
          )}

          {!grafanaUrl && !datadogUrl && (
            <div
              style={{
                padding: "24px",
                background: "var(--paper)",
                border: "1px dashed var(--border)",
                borderRadius: "6px",
                fontSize: "13px",
                color: "var(--ink-muted)",
              }}
            >
              No external monitoring dashboards configured.{" "}
              Set <code style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}>NEXT_PUBLIC_GRAFANA_URL</code> or{" "}
              <code style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}>NEXT_PUBLIC_DATADOG_URL</code> to add links here.
            </div>
          )}
        </>
      )}
    </div>
  );
}
