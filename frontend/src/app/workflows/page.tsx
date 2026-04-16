"use client";

import PipelineView from "@/components/workflows/pipeline-view";

const N8N_EDITOR_URL = process.env.NEXT_PUBLIC_N8N_URL ?? "http://localhost:5678";

const PIPELINES = [
  {
    id: "full-sync",
    name: "Full Catalog Sync",
    description: "ProductData + MediaContent → normalize → push to OPS",
    schedule: "Daily at 02:00",
    nodes: [
      { id: "ps-fetch", label: "PS Fetch", sublabel: "ProductData", status: "done" as const },
      { id: "ps-media", label: "PS Media", sublabel: "MediaContent", status: "done" as const },
      { id: "normalize", label: "Normalize", sublabel: "Canonical schema", status: "running" as const },
      { id: "ops-push", label: "OPS Push", sublabel: "Storefront API", status: "idle" as const },
    ],
  },
  {
    id: "inventory",
    name: "Inventory Delta",
    description: "Inventory service → update variant stock levels",
    schedule: "Every hour",
    nodes: [
      { id: "inv-fetch", label: "INV Fetch", sublabel: "Inventory svc", status: "idle" as const },
      { id: "delta", label: "Delta Check", sublabel: "Compare cache", status: "idle" as const },
      { id: "inv-push", label: "OPS Update", sublabel: "Stock levels", status: "idle" as const },
    ],
  },
];

export default function WorkflowsPage() {
  return (
    <div>
      <div className="flex justify-between items-end mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>Workflows</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--ink-muted)" }}>n8n pipeline status</p>
        </div>
        <a
          href={N8N_EDITOR_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 rounded-md text-sm font-semibold border"
          style={{ borderColor: "var(--blueprint)", color: "var(--blueprint)" }}
        >
          Open n8n Editor ↗
        </a>
      </div>

      <div className="flex flex-col gap-5">
        {PIPELINES.map((p) => (
          <div
            key={p.id}
            className="rounded-lg border overflow-hidden"
            style={{ borderColor: "var(--border)", background: "white" }}
          >
            <div className="px-5 py-4 border-b" style={{ borderColor: "var(--border)" }}>
              <div className="flex justify-between items-start">
                <div>
                  <div className="font-semibold" style={{ color: "var(--ink)" }}>{p.name}</div>
                  <div className="text-xs mt-0.5" style={{ color: "var(--ink-muted)" }}>{p.description}</div>
                </div>
                <span
                  className="text-xs px-2 py-0.5 rounded font-semibold"
                  style={{ background: "var(--bp-pale)", color: "var(--blueprint)", fontFamily: "var(--font-mono)" }}
                >
                  {p.schedule}
                </span>
              </div>
            </div>
            <div className="px-3">
              <PipelineView nodes={p.nodes} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
