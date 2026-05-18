"use client";

/**
 * Phase 8 — Push execution timeline.
 *
 * Renders `execution_steps[]` from a PushLog as a vertical timeline.
 * Each row: mutation name, status pill, latency, started_at, and an
 * expandable JSON viewer for the full request + response bodies.
 *
 * When wired to SSE (Task 9), this component will receive new steps
 * in real-time via a stream; today it just renders a static array.
 */
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Loader2,
} from "lucide-react";
import { useState } from "react";

import type { OPSStepResult, PushStatus } from "@/lib/types";

interface Props {
  steps: OPSStepResult[];
  /** Overall push status — shown in the header. */
  status: PushStatus;
  /** When true, the last row pulses to show "live" execution in progress. */
  live?: boolean;
}

export function PushTimeline({ steps, status, live }: Props) {
  const overall = STATUS_PILL[status] ?? STATUS_PILL.queued;
  const isLive = status === "queued" || status === "processing";
  return (
    <section className="bg-white border-2 border-[#cfccc8] rounded-2xl overflow-hidden">
      <header className="flex items-center justify-between px-6 py-4 bg-[#f9f7f4] border-b-2 border-[#cfccc8]">
        <div className="text-[13px] font-extrabold uppercase tracking-widest text-[#1e1e24]">
          Execution Timeline
        </div>
        <span
          className={`inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full border font-mono text-[10px] font-bold uppercase tracking-wide`}
          style={{ background: overall.bg, color: overall.fg, borderColor: overall.fg }}
        >
          {isLive && <Loader2 className="w-3 h-3 animate-spin" />}
          {status}
        </span>
      </header>

      {steps.length === 0 ? (
        <div className="px-6 py-10 text-center text-[12px] text-[#888894]">
          No execution steps yet — push hasn&apos;t started.
        </div>
      ) : (
        <ul className="divide-y divide-[#f2f0ed]">
          {steps.map((step, i) => (
            <TimelineRow
              key={step.step}
              step={step}
              isLast={i === steps.length - 1}
              pulse={
                (live || isLive) &&
                i === steps.length - 1 &&
                step.status !== "failed"
              }
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function TimelineRow({
  step,
  isLast,
  pulse,
}: {
  step: OPSStepResult;
  isLast: boolean;
  pulse?: boolean;
}) {
  const isOk = step.status === "ok";
  const [open, setOpen] = useState(!isOk);
  const pill = STATUS_PILL[isOk ? "pushed" : "failed"];

  // Surface the first ops_id (e.g. products_id=12345) as a quick reference
  const opsIdLabel = (() => {
    const ids = step.ops_ids || {};
    const firstKey = Object.keys(ids)[0];
    if (!firstKey) return null;
    return `${firstKey}=${ids[firstKey]}`;
  })();

  return (
    <li className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-start gap-4 px-6 py-4 hover:bg-[#fcfbf9] transition-colors text-left"
      >
        {/* Step number + connector line */}
        <div className="relative flex flex-col items-center shrink-0">
          <div
            className={`w-7 h-7 rounded-full flex items-center justify-center font-mono text-[11px] font-bold ${
              isOk
                ? "bg-[#247a52] text-white"
                : "bg-[#b93232] text-white"
            } ${pulse ? "ring-4 ring-[#247a52]/30 animate-pulse" : ""}`}
          >
            {isOk ? (
              <CheckCircle2 className="w-3.5 h-3.5" />
            ) : (
              <AlertCircle className="w-3.5 h-3.5" />
            )}
          </div>
          {!isLast && (
            <div className="absolute top-7 w-0.5 h-full bg-[#cfccc8]" />
          )}
        </div>

        {/* Step details */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-mono text-[10px] font-bold text-[#888894]">
              step {step.step}
            </span>
            <span className="font-mono text-[13px] font-bold text-[#1e1e24]">
              {step.mutation}
            </span>
            <span
              className="inline-flex items-center px-2 py-0.5 rounded-full border font-mono text-[9px] font-bold uppercase tracking-wide"
              style={{ background: pill.bg, color: pill.fg, borderColor: pill.fg }}
            >
              {isOk ? "ok" : "failed"}
            </span>
            <span className="font-mono text-[10px] text-[#484852]">
              {step.source_key}
            </span>
            {opsIdLabel && (
              <span className="font-mono text-[10px] text-[#1e4d92]">
                {opsIdLabel}
              </span>
            )}
            <span className="ml-auto font-mono text-[10px] text-[#888894]">
              {new Date(step.attempted_at).toLocaleTimeString()}
            </span>
            {open ? (
              <ChevronDown className="w-4 h-4 text-[#888894]" />
            ) : (
              <ChevronRight className="w-4 h-4 text-[#888894]" />
            )}
          </div>
        </div>
      </button>

      {open && (
        <div className="ml-[3.25rem] mr-6 mb-4 space-y-3">
          {!isOk && step.error && (
            <div className="bg-[#fdf2f2] border border-[#b93232] rounded-lg px-4 py-3 font-mono text-[12px] text-[#7b1d1d]">
              <span className="font-bold text-[#b93232]">Error: </span>{step.error}
            </div>
          )}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <JsonPanel label="OPS IDs returned" data={step.ops_ids} />
            <JsonPanel
              label="Request fingerprint"
              data={{
                fingerprint: step.request_fingerprint,
                attempted_at: step.attempted_at,
                latency_ms: step.latency_ms ?? "—",
              }}
              tone={isOk ? "default" : "error"}
            />
          </div>
        </div>
      )}
    </li>
  );
}

function JsonPanel({
  label,
  data,
  tone,
}: {
  label: string;
  data: Record<string, unknown>;
  tone?: "default" | "error";
}) {
  const isError = tone === "error";
  return (
    <div
      className={`border rounded-lg overflow-hidden ${
        isError ? "border-[#b93232]" : "border-[#cfccc8]"
      }`}
    >
      <div
        className={`px-3 py-1 text-[10px] font-bold uppercase tracking-widest ${
          isError ? "bg-[#fdf2f2] text-[#b93232]" : "bg-[#f9f7f4] text-[#888894]"
        }`}
      >
        {label}
      </div>
      <pre
        className={`p-3 font-mono text-[11px] overflow-x-auto ${
          isError ? "text-[#7b1d1d] bg-[#fdf2f2]" : "text-[#1e1e24] bg-white"
        }`}
      >
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status pill palette — matches Blueprint design tokens
// ---------------------------------------------------------------------------

const STATUS_PILL: Record<
  string,
  { bg: string; fg: string }
> = {
  queued:           { bg: "#f9f7f4", fg: "#888894" },
  processing:       { bg: "#fff7e0", fg: "#c17c00" },
  pushed:           { bg: "#f0f9f4", fg: "#247a52" },
  failed:           { bg: "#fdf2f2", fg: "#b93232" },
  partial_failure:  { bg: "#fdf2f2", fg: "#b93232" },
  rejected:         { bg: "#fdf2f2", fg: "#b93232" },
  canceled:         { bg: "#f9f7f4", fg: "#888894" },
  dry_run_pushed:   { bg: "#eef4fb", fg: "#1e4d92" },
};
