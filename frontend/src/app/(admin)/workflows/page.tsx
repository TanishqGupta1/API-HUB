"use client";

import { ExternalLink, ArrowRight, RefreshCw, Database, Zap, Globe, Clock } from "lucide-react";

const N8N_URL = process.env.NEXT_PUBLIC_N8N_URL || "http://localhost:5678";

const PIPELINE_STAGES = [
  {
    id: "supplier",
    label: "Supplier API",
    sublabel: "SOAP / REST",
    icon: <Globe style={{ width: "18px", height: "18px" }} />,
    color: "var(--ink-muted)",
    description: "PromoStandards endpoints — product data, inventory, pricing, media",
  },
  {
    id: "ingest",
    label: "Ingest",
    sublabel: "FastAPI",
    icon: <Zap style={{ width: "18px", height: "18px" }} />,
    color: "#d97706",
    description: "Adapter fetches & normalises supplier data into a unified schema",
  },
  {
    id: "store",
    label: "Catalog DB",
    sublabel: "PostgreSQL",
    icon: <Database style={{ width: "18px", height: "18px" }} />,
    color: "#0369a1",
    description: "Upserted products, variants, images, pricing tiers, and sync history",
  },
  {
    id: "push",
    label: "OPS Push",
    sublabel: "Integration Gateway",
    icon: <Zap style={{ width: "18px", height: "18px" }} />,
    color: "#7c3aed",
    description: "Preflight checks, payload build, markup application, GraphQL mutation plan",
  },
  {
    id: "ops",
    label: "OnPrintShop",
    sublabel: "GraphQL API",
    icon: <Globe style={{ width: "18px", height: "18px" }} />,
    color: "#059669",
    description: "setProduct → setProductSize → setProductPrice → setProductImage",
  },
];

const SYNC_WORKFLOWS = [
  {
    name: "Full Sync",
    trigger: "Manual / Weekly",
    description: "Full product + variant + image fetch from supplier",
    icon: <RefreshCw style={{ width: "14px", height: "14px" }} />,
    status: "active",
  },
  {
    name: "Delta Sync",
    trigger: "Every 6 hours",
    description: "Changed products only, based on last-modified timestamp",
    icon: <Clock style={{ width: "14px", height: "14px" }} />,
    status: "active",
  },
  {
    name: "Inventory Sync",
    trigger: "Every hour",
    description: "Inventory quantities and availability flags only",
    icon: <Database style={{ width: "14px", height: "14px" }} />,
    status: "active",
  },
  {
    name: "Pricing Sync",
    trigger: "Every 12 hours",
    description: "Price tier updates and markup recalculation",
    icon: <Zap style={{ width: "14px", height: "14px" }} />,
    status: "active",
  },
];

function PipelineNode({
  stage,
  isLast,
}: {
  stage: (typeof PIPELINE_STAGES)[0];
  isLast: boolean;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", flex: isLast ? "0 0 auto" : "1 1 0" }}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "10px",
          minWidth: "120px",
        }}
      >
        <div
          style={{
            width: "52px",
            height: "52px",
            borderRadius: "10px",
            background: "var(--paper)",
            border: `2px solid ${stage.color}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: stage.color,
            flexShrink: 0,
          }}
        >
          {stage.icon}
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--ink)" }}>{stage.label}</div>
          <div
            style={{
              fontSize: "10px",
              fontFamily: "var(--font-mono)",
              color: "var(--ink-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginTop: "2px",
            }}
          >
            {stage.sublabel}
          </div>
        </div>
        <div
          style={{
            fontSize: "11px",
            color: "var(--ink-muted)",
            textAlign: "center",
            lineHeight: "1.4",
            maxWidth: "130px",
          }}
        >
          {stage.description}
        </div>
      </div>

      {!isLast && (
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "center",
            paddingTop: "14px",
            paddingBottom: "60px",
            color: "var(--border)",
            minWidth: "32px",
          }}
        >
          <ArrowRight style={{ width: "18px", height: "18px", color: "var(--ink-faint)" }} />
        </div>
      )}
    </div>
  );
}

export default function WorkflowsPage() {
  return (
    <div className="page-container">
      <div className="page-header" style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <h1 className="page-title">Workflows</h1>
          <p style={{ fontSize: "13px", color: "var(--ink-muted)", marginTop: "4px" }}>
            Data pipeline from PromoStandards suppliers to OnPrintShop storefronts.
          </p>
        </div>
        <a
          href={N8N_URL}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "7px 14px",
            background: "var(--blue)",
            color: "#fff",
            borderRadius: "3px",
            fontSize: "12px",
            fontWeight: 700,
            textDecoration: "none",
            flexShrink: 0,
          }}
        >
          <ExternalLink style={{ width: "12px", height: "12px" }} />
          Open n8n
        </a>
      </div>

      {/* Pipeline diagram */}
      <div style={{ marginBottom: "40px" }}>
        <div
          style={{
            fontSize: "11px",
            fontWeight: 700,
            color: "var(--ink-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            marginBottom: "20px",
          }}
        >
          Integration Pipeline
        </div>
        <div
          style={{
            background: "var(--paper)",
            border: "1px solid var(--border)",
            borderRadius: "8px",
            padding: "32px 28px 24px",
            overflowX: "auto",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", minWidth: "680px" }}>
            {PIPELINE_STAGES.map((stage, i) => (
              <PipelineNode key={stage.id} stage={stage} isLast={i === PIPELINE_STAGES.length - 1} />
            ))}
          </div>
        </div>
      </div>

      {/* Sync workflows */}
      <div>
        <div
          style={{
            fontSize: "11px",
            fontWeight: 700,
            color: "var(--ink-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            marginBottom: "12px",
          }}
        >
          Sync Schedules
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: "12px" }}>
          {SYNC_WORKFLOWS.map((wf) => (
            <div
              key={wf.name}
              style={{
                background: "var(--paper)",
                border: "1px solid var(--border)",
                borderRadius: "6px",
                padding: "16px 20px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ color: "var(--ink-muted)" }}>{wf.icon}</span>
                  <span style={{ fontSize: "13px", fontWeight: 700, color: "var(--ink)" }}>{wf.name}</span>
                </div>
                <span
                  style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    color: "#059669",
                    background: "#d1fae5",
                    padding: "2px 7px",
                    borderRadius: "3px",
                  }}
                >
                  Active
                </span>
              </div>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "10px",
                  color: "var(--blue)",
                  marginBottom: "6px",
                }}
              >
                {wf.trigger}
              </div>
              <div style={{ fontSize: "12px", color: "var(--ink-muted)", lineHeight: "1.5" }}>
                {wf.description}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* n8n link card */}
      <div style={{ marginTop: "32px" }}>
        <a
          href={N8N_URL}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "18px 22px",
            background: "var(--paper)",
            border: "1px solid var(--border)",
            borderRadius: "6px",
            textDecoration: "none",
            color: "var(--ink)",
          }}
        >
          <div>
            <div style={{ fontSize: "14px", fontWeight: 700, marginBottom: "3px" }}>n8n Workflow Editor</div>
            <div style={{ fontSize: "12px", color: "var(--ink-muted)" }}>
              Manage cron triggers, webhook flows, and OPS push orchestration at{" "}
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}>{N8N_URL}</span>
            </div>
          </div>
          <ExternalLink style={{ width: "14px", height: "14px", color: "var(--ink-muted)", flexShrink: 0, marginLeft: "16px" }} />
        </a>
      </div>
    </div>
  );
}
