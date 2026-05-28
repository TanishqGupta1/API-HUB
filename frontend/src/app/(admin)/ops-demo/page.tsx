"use client";

import { useState } from "react";
import { CheckCircle2, ChevronDown, ChevronRight, Loader2, Play, RefreshCw, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";

// Override via NEXT_PUBLIC_DEMO_PRODUCT_ID / NEXT_PUBLIC_DEMO_CUSTOMER_ID in
// .env.local to use a different product or customer without touching code.
const DEMO_PRODUCT_ID  = process.env.NEXT_PUBLIC_DEMO_PRODUCT_ID  ?? "cc12cd6e-b84b-4806-b585-40fa2b5c634f";
const DEMO_CUSTOMER_ID = process.env.NEXT_PUBLIC_DEMO_CUSTOMER_ID ?? "5a47202b-b5ae-410a-afc0-10d13cd32c98";
const DEMO_SUPPLIER_SLUG = process.env.NEXT_PUBLIC_DEMO_SUPPLIER_SLUG ?? "sanmar";

interface StepResult {
  step: number;
  mutation: string;
  source_key: string;
  ops_ids: Record<string, unknown>;
  attempted_at: string;
  status: "ok" | "failed";
  latency_ms?: number;
  error?: string;
}

interface PushResult {
  push_log_id: string;
  status: string;
  supplier_sku: string;
  step_results: StepResult[];
}

type DemoState = "idle" | "running" | "done" | "error";

// ── Phase definitions ─────────────────────────────────────────────────────────
const PHASES: { key: string; label: string; accent: string; bg: string; mutations: string[] }[] = [
  {
    key: "product",
    label: "Create product",
    accent: "#1e4d92",
    bg: "#eef4fb",
    mutations: ["setProduct"],
  },
  {
    key: "variants",
    label: "Add variants",
    accent: "#247a52",
    bg: "#f0f9f4",
    mutations: ["setProductSize"],
  },
  {
    key: "pricing",
    label: "Set pricing",
    accent: "#7a4900",
    bg: "#fff7e0",
    mutations: ["setProductPrice", "setProductsAttributePrice"],
  },
  {
    key: "options",
    label: "Wire options",
    accent: "#6b21a8",
    bg: "#faf5ff",
    mutations: ["setAssignOptions", "setAdditionalOption", "setAdditionalOptionAttributes"],
  },
  {
    key: "inventory",
    label: "Set inventory",
    accent: "#0f766e",
    bg: "#f0fdfa",
    mutations: ["updateProductStock"],
  },
];

const MUTATION_LABELS: Record<string, string> = {
  setProduct: "Register product on storefront",
  setProductSize: "Create size/colour variant",
  setProductPrice: "Attach wholesale + retail price",
  setAssignOptions: "Link master decoration option",
  setAdditionalOption: "Create product-local option",
  setAdditionalOptionAttributes: "Add attribute to option",
  setProductsAttributePrice: "Set decoration attribute price",
  updateProductStock: "Reset inventory count",
};

function phaseFor(mutation: string) {
  return PHASES.find((p) => p.mutations.includes(mutation)) ?? PHASES[0];
}

function groupByPhase(steps: StepResult[]) {
  const groups: { phase: (typeof PHASES)[0]; steps: StepResult[] }[] = [];
  for (const step of steps) {
    const phase = phaseFor(step.mutation);
    const existing = groups.find((g) => g.phase.key === phase.key);
    if (existing) existing.steps.push(step);
    else groups.push({ phase, steps: [step] });
  }
  return groups;
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function OpsDemoPage() {
  const [state, setState]           = useState<DemoState>("idle");
  const [result, setResult]         = useState<PushResult | null>(null);
  const [errorMsg, setErrorMsg]     = useState<string | null>(null);
  const [openStep, setOpenStep]     = useState<number | null>(null);

  async function runDemo() {
    setState("running");
    setResult(null);
    setErrorMsg(null);
    setOpenStep(null);

    try {
      const resp = await api<{ push_log_id: string; status: string; supplier_sku: string }>(
        "/api/integrations/admin/push-requests",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source: { supplier_slug: DEMO_SUPPLIER_SLUG },
            product_ref: { product_id: DEMO_PRODUCT_ID },
            target: { customer_id: DEMO_CUSTOMER_ID },
            dry_run: true,
          }),
        }
      );
      const poll = await api<PushResult>(
        `/api/integrations/admin/push-requests/${resp.push_log_id}`
      );
      setResult(poll);
      setState("done");
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : String(e));
      setState("error");
    }
  }

  const groups     = result ? groupByPhase(result.step_results ?? []) : [];
  const totalSteps = result?.step_results?.length ?? 0;
  const passed     = result?.step_results?.filter((s) => s.status === "ok").length ?? 0;

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 space-y-6">

      {/* ── Header ── */}
      <div className="space-y-1">
        <span
          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded border font-mono text-[10px] font-bold uppercase tracking-wide"
          style={{ background: "#eef4fb", color: "#1e4d92", borderColor: "#1e4d92" }}
        >
          <ShieldCheck className="w-3 h-3" />
          Dry-run · No real OPS writes
        </span>
        <h1 className="text-[26px] font-extrabold tracking-[-0.04em] text-[#1e1e24]">
          SanMar → OPS Push Pipeline
        </h1>
        <p className="text-[12px] text-[#888894]">
          Executes all mutations through <span className="font-mono">FakeOpsClient</span> — simulated IDs, zero network writes.
        </p>
      </div>

      {/* ── Product card ── */}
      <div className="bg-white border border-[#cfccc8] rounded-xl overflow-hidden">
        <div className="flex items-center gap-4 px-5 py-4">
          <div className="w-12 h-12 rounded-lg border border-[#cfccc8] overflow-hidden shrink-0 bg-[#f9f7f4] flex items-center justify-center text-[9px] font-mono text-[#888894]">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="https://images.sanmar.com/imgindex/PC61_NAVY_front.jpg"
              alt="PC61"
              className="w-full h-full object-contain"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-bold text-[13px] text-[#1e1e24]">Port &amp; Company Essential Tee</div>
            <div className="font-mono text-[10px] text-[#888894] mt-0.5">PC61 · SanMar</div>
            <div className="flex flex-wrap gap-1 mt-1.5">
              {["Navy/S", "Navy/M", "Navy/L", "White/M"].map((v) => (
                <span key={v} className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-[#f2f0ed] text-[#484852]">{v}</span>
              ))}
            </div>
          </div>
          <div className="text-right shrink-0 space-y-0.5">
            <div className="text-[10px] font-bold text-[#888894] uppercase tracking-widest">Sell price</div>
            <div className="text-[16px] font-extrabold text-[#1e1e24]">$5.59</div>
            <div className="text-[9px] text-[#247a52] font-bold">$3.99 + 40% markup</div>
          </div>
        </div>
        <div className="px-5 py-2 border-t border-[#f2f0ed] flex items-center gap-2 text-[10px] text-[#888894]">
          <span>Target:</span>
          <span className="font-semibold text-[#484852]">Demo Showcase Customer</span>
          <span className="opacity-40">·</span>
          <span className="font-mono bg-[#fff7e0] text-[#c17c00] px-1.5 py-0.5 rounded border border-[#c17c00] text-[9px] font-bold">fake / dry-run</span>
        </div>
      </div>

      {/* ── Run button ── */}
      <div className="flex items-center gap-3">
        <button
          onClick={runDemo}
          disabled={state === "running"}
          className="inline-flex items-center gap-2 px-5 h-9 rounded-lg font-bold text-[12px] text-white"
          style={{ background: state === "running" ? "#6b8cbf" : "#1e4d92", cursor: state === "running" ? "not-allowed" : "pointer" }}
        >
          {state === "running" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
          {state === "running" ? "Executing…" : "Run Pipeline"}
        </button>
        {state === "done" && (
          <button
            onClick={runDemo}
            className="inline-flex items-center gap-1.5 px-3 h-9 rounded-lg border border-[#cfccc8] text-[11px] font-bold text-[#484852] hover:border-[#1e4d92] hover:text-[#1e4d92] transition-colors"
          >
            <RefreshCw className="w-3 h-3" /> Run again
          </button>
        )}
      </div>

      {/* ── Error ── */}
      {state === "error" && errorMsg && (
        <div className="bg-[#fdf2f2] border border-[#b93232] rounded-xl px-5 py-4">
          <div className="font-bold text-[12px] text-[#b93232] mb-1">Pipeline error</div>
          <pre className="font-mono text-[10px] text-[#7b1d1d] whitespace-pre-wrap break-all">{errorMsg}</pre>
        </div>
      )}

      {/* ── Pipeline result ── */}
      {state === "done" && result && (
        <div className="space-y-4">

          {/* Summary bar */}
          <div className="flex items-center gap-3 px-4 py-3 rounded-xl border-2 border-[#247a52] bg-[#f0f9f4]">
            <CheckCircle2 className="w-5 h-5 text-[#247a52] shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="font-extrabold text-[13px] text-[#247a52]">
                {passed}/{totalSteps} mutations passed — pipeline complete
              </div>
              <div className="text-[10px] text-[#247a52] opacity-70 mt-0.5 font-mono">
                push_log {result.push_log_id.slice(0, 8)} · FakeOpsClient · no real writes
              </div>
            </div>
            {/* Phase summary pills */}
            <div className="hidden sm:flex items-center gap-1 shrink-0">
              {groups.map(({ phase, steps: ps }) => (
                <span
                  key={phase.key}
                  className="px-2 py-0.5 rounded-full text-[9px] font-bold font-mono border"
                  style={{ background: phase.bg, color: phase.accent, borderColor: phase.accent }}
                >
                  {ps.length}×
                </span>
              ))}
            </div>
          </div>

          {/* Phase-grouped pipeline */}
          <div className="bg-white border border-[#cfccc8] rounded-xl overflow-hidden">
            <div className="px-5 py-3 bg-[#f9f7f4] border-b border-[#cfccc8] flex items-center justify-between">
              <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#1e1e24]">
                Mutation pipeline
              </span>
              <span className="font-mono text-[10px] text-[#888894]">{totalSteps} steps</span>
            </div>

            <div className="divide-y divide-[#f2f0ed]">
              {groups.map(({ phase, steps: phaseSteps }, gi) => (
                <div key={phase.key}>
                  {/* Phase header */}
                  <div
                    className="flex items-center gap-3 px-5 py-2"
                    style={{ background: phase.bg }}
                  >
                    <div
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ background: phase.accent }}
                    />
                    <span className="text-[9px] font-extrabold uppercase tracking-widest" style={{ color: phase.accent }}>
                      {phase.label}
                    </span>
                    <span className="text-[9px] font-mono opacity-60" style={{ color: phase.accent }}>
                      {phaseSteps.length} mutation{phaseSteps.length !== 1 ? "s" : ""}
                    </span>
                    {gi < groups.length - 1 && (
                      <span className="ml-auto text-[9px] font-mono opacity-40" style={{ color: phase.accent }}>↓ next phase</span>
                    )}
                  </div>

                  {/* Steps in this phase */}
                  {phaseSteps.map((step, si) => {
                    const isLast = si === phaseSteps.length - 1;
                    const isOpen = openStep === step.step;
                    const opsEntry = Object.entries(step.ops_ids ?? {})[0];

                    return (
                      <div key={step.step}>
                        <button
                          onClick={() => setOpenStep(isOpen ? null : step.step)}
                          className="w-full flex items-center gap-4 px-5 py-2.5 hover:bg-[#fcfbf9] transition-colors text-left"
                        >
                          {/* Connector line + step number */}
                          <div className="relative flex flex-col items-center w-5 shrink-0 self-stretch">
                            <div
                              className="w-5 h-5 rounded-full flex items-center justify-center font-mono text-[9px] font-bold text-white shrink-0"
                              style={{ background: step.status === "ok" ? phase.accent : "#b93232" }}
                            >
                              {step.step}
                            </div>
                            {!isLast && (
                              <div
                                className="w-px flex-1 mt-1"
                                style={{ background: phase.accent, opacity: 0.2 }}
                              />
                            )}
                          </div>

                          {/* Label */}
                          <div className="flex-1 min-w-0">
                            <div className="font-mono text-[11px] font-bold text-[#1e1e24] truncate">
                              {step.mutation}
                            </div>
                            <div className="text-[10px] text-[#888894] truncate">
                              {MUTATION_LABELS[step.mutation] ?? ""}
                            </div>
                          </div>

                          {/* OPS ID output */}
                          {opsEntry && (
                            <div className="hidden sm:flex items-center gap-1 shrink-0">
                              <span className="font-mono text-[9px] text-[#888894]">{opsEntry[0]}</span>
                              <span className="font-mono text-[10px] font-bold" style={{ color: phase.accent }}>
                                ={String(opsEntry[1])}
                              </span>
                            </div>
                          )}

                          {/* Status + expand */}
                          <div className="flex items-center gap-2 shrink-0">
                            <span
                              className="w-3.5 h-3.5 rounded-full flex items-center justify-center text-white shrink-0"
                              style={{ background: step.status === "ok" ? "#247a52" : "#b93232" }}
                            >
                              {step.status === "ok"
                                ? <svg className="w-2 h-2" fill="none" viewBox="0 0 8 8"><path d="M1 4l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                                : <svg className="w-2 h-2" fill="none" viewBox="0 0 8 8"><path d="M2 2l4 4M6 2L2 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                              }
                            </span>
                            {isOpen
                              ? <ChevronDown className="w-3.5 h-3.5 text-[#888894]" />
                              : <ChevronRight className="w-3.5 h-3.5 text-[#888894]" />}
                          </div>
                        </button>

                        {/* Expanded detail */}
                        {isOpen && (
                          <div className="mx-5 mb-3 rounded-lg border overflow-hidden text-[10px]" style={{ borderColor: phase.accent + "40" }}>
                            <div
                              className="px-3 py-1 font-mono font-bold uppercase tracking-widest"
                              style={{ background: phase.bg, color: phase.accent }}
                            >
                              OPS response (simulated)
                            </div>
                            <pre className="p-3 font-mono text-[10px] text-[#1e1e24] bg-white overflow-x-auto">
                              {JSON.stringify(step.ops_ids, null, 2)}
                            </pre>
                            <div className="px-3 py-1.5 border-t font-mono text-[#888894]" style={{ borderColor: phase.accent + "20", background: phase.bg }}>
                              called_at: {new Date(step.attempted_at).toLocaleTimeString()}
                              {step.error && <span className="ml-3 text-[#b93232]">{step.error}</span>}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
