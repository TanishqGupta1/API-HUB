"use client";

import PipelineView, { type PipelineNode, type NodeIcon } from "@/components/workflows/pipeline-view";

const N8N_URL = process.env.NEXT_PUBLIC_N8N_URL ?? "http://localhost:5678";

const PIPELINE_NODES: PipelineNode[] = [
  {
    id: "supplier", label: "Supplier", sublabel: "Source data", status: "idle",
    icon: "supplier",
  },
  {
    id: "fetch", label: "Fetch Data", sublabel: "SOAP / REST", status: "idle",
    icon: "fetch",
  },
  {
    id: "normalize", label: "Normalize", sublabel: "Canonical schema", status: "idle",
    icon: "normalize",
  },
  {
    id: "store", label: "Store in DB", sublabel: "PostgreSQL", status: "idle",
    icon: "store",
  },
  {
    id: "publish", label: "Publish to Store", sublabel: "OnPrintShop", status: "idle",
    icon: "publish",
  },
];

export default function WorkflowsPage() {
  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold" style={{ color: "var(--ink)" }}>
          Data Pipeline
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--ink-muted)" }}>
          How products flow from suppliers to your storefronts
        </p>
      </div>

      <div className="mb-5" style={{ borderBottom: "1px solid var(--border)" }} />

      {/* Pipeline diagram */}
      <div
        className="rounded-lg border mb-6"
        style={{ borderColor: "var(--border)", background: "white" }}
      >
        <PipelineView nodes={PIPELINE_NODES} />
      </div>

      {/* Open n8n Editor button */}
      <div className="mb-6">
        <a
          href={N8N_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-semibold border"
          style={{ borderColor: "var(--blue)", color: "var(--blue)" }}
        >
          Open n8n Editor ↗
        </a>
      </div>

      {/* Info panel */}
      <div
        className="rounded-lg border px-5 py-4 text-sm"
        style={{
          borderColor: "var(--border)",
          background: "var(--paper)",
          color: "var(--ink-muted)",
        }}
      >
        Sync schedules are managed in n8n. The pipeline runs automatically once activated.
      </div>
    </div>
  );
}
