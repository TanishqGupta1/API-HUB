"use client";

/**
 * Phase 8 — Preview panel.
 *
 * Three sections rendered top-to-bottom:
 *   1. Preflight panel — 8 named checks with ✓/✗ + detail string
 *   2. Computed prices table — per-variant vendor + final + markup
 *   3. Mutation plan — readable cards for each OPS GraphQL call
 *
 * Pure presentational — receives data from the `usePushPreview` hook.
 * Renders the same whether data is mock or live.
 */
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Info,
} from "lucide-react";
import { useState } from "react";

import type {
  OPSComputedPrice,
  OPSMutationStep,
  PreflightCheck,
  PreflightResult,
} from "@/lib/types";

interface Props {
  preflight: PreflightResult | null;
  plan: OPSMutationStep[];
  computedPrices?: OPSComputedPrice[];
}

export function PreviewPanel({ preflight, plan, computedPrices }: Props) {
  return (
    <div className="space-y-6">
      {preflight && <PreflightSection result={preflight} />}
      {computedPrices && computedPrices.length > 0 && (
        <ComputedPricesSection prices={computedPrices} />
      )}
      {plan.length > 0 && <PlanSection plan={plan} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Preflight
// ---------------------------------------------------------------------------

function PreflightSection({ result }: { result: PreflightResult }) {
  const passCount = result.checks.filter((c) => c.ok).length;
  const failCount = result.checks.length - passCount;
  const allPass = failCount === 0;

  return (
    <section className="bg-white border-2 border-[#cfccc8] rounded-2xl overflow-hidden">
      <header
        className={`flex items-center justify-between px-6 py-4 border-b-2 ${
          allPass ? "bg-[#f0f9f4] border-[#247a52]" : "bg-[#fdf2f2] border-[#b93232]"
        }`}
      >
        <div className="flex items-center gap-3">
          {allPass ? (
            <CheckCircle2 className="w-5 h-5 text-[#247a52]" />
          ) : (
            <AlertCircle className="w-5 h-5 text-[#b93232]" />
          )}
          <div>
            <div className="text-[13px] font-extrabold uppercase tracking-widest text-[#1e1e24]">
              Preflight
            </div>
            <div
              className={`text-[11px] font-semibold ${
                allPass ? "text-[#247a52]" : "text-[#b93232]"
              }`}
            >
              {allPass
                ? `All ${result.checks.length} checks passed`
                : `${failCount} blocker${failCount === 1 ? "" : "s"} · ${passCount} passed`}
            </div>
          </div>
        </div>
        <span className="font-mono text-[10px] text-[#888894]">
          {new Date(result.computed_at).toLocaleTimeString()}
        </span>
      </header>

      <ul className="divide-y divide-[#f2f0ed]">
        {result.checks.map((c) => (
          <CheckRow key={c.name} check={c} />
        ))}
      </ul>
    </section>
  );
}

function CheckRow({ check }: { check: PreflightCheck }) {
  return (
    <li className="px-6 py-3 flex items-start gap-3">
      {check.ok ? (
        <CheckCircle2 className="w-4 h-4 mt-0.5 text-[#247a52] shrink-0" />
      ) : (
        <AlertCircle className="w-4 h-4 mt-0.5 text-[#b93232] shrink-0" />
      )}
      <div className="flex-1 min-w-0">
        <div className="font-mono text-[12px] font-bold text-[#1e1e24]">
          {check.name}
        </div>
        <div
          className={`text-[12px] mt-0.5 ${
            check.ok ? "text-[#484852]" : "text-[#b93232]"
          }`}
        >
          {check.detail}
        </div>
        {!check.ok && check.suggestion && (
          <div className="text-[11px] mt-1 text-[#b93232] italic flex items-start gap-1">
            <span className="font-bold not-italic">→</span>
            <span>{check.suggestion}</span>
          </div>
        )}
        {!check.ok && check.field && (
          <div className="font-mono text-[10px] mt-1 text-[#888894]">
            field: {check.field}
          </div>
        )}
      </div>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Computed prices
// ---------------------------------------------------------------------------

function ComputedPricesSection({ prices }: { prices: OPSComputedPrice[] }) {
  const ruleLabel = prices[0]?.markup_pct != null
    ? `${prices[0].markup_pct}%`
    : prices[0]?.markup_amount != null
      ? `$${prices[0].markup_amount}`
      : "pass-through";

  return (
    <section className="bg-white border-2 border-[#cfccc8] rounded-2xl overflow-hidden">
      <header className="flex items-center justify-between px-6 py-4 bg-[#f9f7f4] border-b-2 border-[#cfccc8]">
        <div className="text-[13px] font-extrabold uppercase tracking-widest text-[#1e1e24]">
          Computed Prices ({prices.length} variant{prices.length === 1 ? "" : "s"})
        </div>
        <span className="font-mono text-[10px] text-[#888894]">
          markup: {ruleLabel}
        </span>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead className="bg-[#fcfbf9] border-b border-[#cfccc8]">
            <tr>
              <Th>SKU</Th>
              <Th>Color</Th>
              <Th>Size</Th>
              <Th align="right">Vendor</Th>
              <Th align="right">Final</Th>
              <Th align="right">Markup</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#f2f0ed]">
            {prices.map((p) => (
              <tr key={p.variant_sku} className="hover:bg-[#fcfbf9]">
                <Td mono bold>{p.variant_sku}</Td>
                <Td>{p.color ?? "—"}</Td>
                <Td>{p.size ?? "—"}</Td>
                <Td mono align="right">${p.base_price.toFixed(2)}</Td>
                <Td mono align="right" className="text-[#247a52] font-bold">
                  ${p.final_price.toFixed(2)}
                </Td>
                <Td mono align="right" className="text-[#1e4d92]">
                  {p.markup_pct != null
                    ? `${p.markup_pct}%`
                    : p.markup_amount != null
                      ? `+$${p.markup_amount}`
                      : "—"}
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Mutation plan
// ---------------------------------------------------------------------------

function PlanSection({ plan }: { plan: OPSMutationStep[] }) {
  return (
    <section className="bg-white border-2 border-[#cfccc8] rounded-2xl overflow-hidden">
      <header className="flex items-center justify-between px-6 py-4 bg-[#f9f7f4] border-b-2 border-[#cfccc8]">
        <div className="text-[13px] font-extrabold uppercase tracking-widest text-[#1e1e24]">
          Mutation Plan
        </div>
        <span className="font-mono text-[10px] text-[#888894]">
          {plan.length} step{plan.length === 1 ? "" : "s"}
        </span>
      </header>
      <ul className="divide-y divide-[#f2f0ed]">
        {plan.map((step) => (
          <PlanStepRow key={step.step} step={step} />
        ))}
      </ul>
      <footer className="px-6 py-3 bg-[#fcfbf9] border-t border-[#cfccc8] flex items-start gap-2 text-[11px] text-[#888894]">
        <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        <span>
          <span className="font-mono">$stepN.field</span> markers are
          placeholders. They&apos;re resolved to real OPS IDs at execute time
          when the corresponding mutation responds.
        </span>
      </footer>
    </section>
  );
}

function PlanStepRow({ step }: { step: OPSMutationStep }) {
  const [open, setOpen] = useState(false);
  return (
    <li>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-6 py-3 hover:bg-[#fcfbf9] transition-colors text-left"
      >
        <span className="font-mono text-[10px] font-bold bg-[#1e4d92] text-white px-2 py-0.5 rounded shrink-0">
          {step.step}
        </span>
        <span className="font-mono text-[13px] font-bold text-[#1e1e24] flex-1 min-w-0 truncate">
          {step.mutation}
        </span>
        <span className="font-mono text-[10px] text-[#888894] shrink-0 hidden sm:inline">
          {step.source_key}
        </span>
        {step.requires_response_from.length > 0 && (
          <span className="font-mono text-[10px] text-[#888894] shrink-0">
            depends on step {step.requires_response_from.join(", ")}
          </span>
        )}
        {open ? (
          <ChevronDown className="w-4 h-4 text-[#888894]" />
        ) : (
          <ChevronRight className="w-4 h-4 text-[#888894]" />
        )}
      </button>
      {open && (
        <div className="px-6 pb-4 -mt-1">
          <pre className="bg-[#fcfbf9] border border-[#cfccc8] rounded-lg p-3 font-mono text-[11px] text-[#1e1e24] overflow-x-auto">
            {JSON.stringify(step.variables, null, 2)}
          </pre>
        </div>
      )}
    </li>
  );
}

// ---------------------------------------------------------------------------
// Tiny table helpers (kept local — no global table primitive)
// ---------------------------------------------------------------------------

function Th({
  children,
  align,
}: {
  children: React.ReactNode;
  align?: "left" | "right";
}) {
  return (
    <th
      className={`px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-[#888894] ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  mono,
  bold,
  align,
  className,
}: {
  children: React.ReactNode;
  mono?: boolean;
  bold?: boolean;
  align?: "left" | "right";
  className?: string;
}) {
  const base =
    "px-4 py-2 text-[12px] " +
    (mono ? "font-mono " : "") +
    (bold ? "font-bold " : "") +
    (align === "right" ? "text-right " : "");
  return <td className={base + (className ?? "")}>{children}</td>;
}
