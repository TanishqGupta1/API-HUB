"use client";

/**
 * Integration Gateway (M0–M5) — push-log detail page.
 *
 * URL: /push-log/[id]
 *
 * Replaces the old VPCE detail page. Shows the full post-execute view
 * of one push attempt:
 *   - Header: status pill, dry-run badge, OPS product id, callback status
 *   - Idempotency block: key_id + idempotency_key + payload_hash + request_id
 *   - CleanupChecklist when status=partial_failure
 *   - PushTimeline with step_results (expandable per step)
 *
 * Polls `GET /api/integrations/v1/push-requests/{id}` while non-terminal.
 */
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  Copy,
  ExternalLink,
  Loader2,
  Send,
  XCircle,
} from "lucide-react";
import { useState } from "react";

import { CleanupChecklist } from "@/components/push/CleanupChecklist";
import { PushTimeline } from "@/components/push/PushTimeline";
import { IS_MOCK_MODE, usePushStatus } from "@/lib/use-push-preview";
import type { CallbackStatus, PushLog, PushStatus } from "@/lib/types";

export default function PushLogDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const { log, loading, error } = usePushStatus(id);

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-16 text-center">
        <Loader2 className="w-8 h-8 text-[#1e4d92] animate-spin mx-auto mb-3" />
        <div className="text-[13px] text-[#484852]">Loading push log…</div>
      </div>
    );
  }

  if (error || !log) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-16">
        <div className="border-2 border-dashed border-[#cfccc8] rounded-2xl p-10 text-center bg-white">
          <div className="text-[14px] font-bold text-[#1e1e24]">
            Push log not found
          </div>
          <p className="text-[12px] text-[#888894] mt-2">
            ID <code className="font-mono">{id}</code> doesn&apos;t match any
            push attempt. {error && <span>({error})</span>}
          </p>
          <Link
            href="/push-log"
            className="inline-flex items-center gap-1.5 mt-4 text-[12px] font-semibold text-[#1e4d92] hover:underline"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to push log
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
      {/* Header */}
      <header className="flex items-start justify-between gap-4 pb-5 border-b-2 border-[#1e1e24]">
        <div className="min-w-0">
          <Link
            href="/push-log"
            className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-widest text-[#888894] hover:text-[#1e4d92] transition-colors mb-3"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            All push logs
          </Link>
          <div className="text-[28px] font-extrabold tracking-[-0.04em] leading-none text-[#1e1e24]">
            Push {id.slice(0, 8)}
          </div>
          <div className="flex items-center gap-2 text-[12px] text-[#888894] mt-2 flex-wrap">
            <span className="font-mono">{log.supplier_sku ?? "—"}</span>
            <span>·</span>
            <span>{new Date(log.created_at).toLocaleString()}</span>
            {log.dry_run && (
              <>
                <span>·</span>
                <span className="inline-flex items-center px-1.5 py-0.5 bg-[#eef4fb] border border-[#1e4d92] rounded font-mono text-[9px] font-bold uppercase tracking-wide text-[#1e4d92]">
                  dry-run
                </span>
              </>
            )}
            {IS_MOCK_MODE && (
              <>
                <span>·</span>
                <span className="inline-flex items-center px-1.5 py-0.5 bg-[#fff7e0] border border-[#c17c00] rounded font-mono text-[9px] font-bold uppercase tracking-wide text-[#c17c00]">
                  mock
                </span>
              </>
            )}
          </div>
        </div>

        <TerminalBanner log={log} />
      </header>

      {/* Idempotency / callback metadata block */}
      <IdempotencyBlock log={log} />

      {/* Cleanup checklist (only when partial_failure) */}
      {log.status === "partial_failure" && log.cleanup_targets && (
        <CleanupChecklist
          targets={log.cleanup_targets}
          opsBaseUrl={undefined}
        />
      )}

      {/* Error message for failed/rejected */}
      {(log.status === "failed" || log.status === "rejected") && log.error && (
        <div className="bg-[#fdf2f2] border-2 border-[#b93232] rounded-2xl px-5 py-4 flex items-start gap-3">
          <XCircle className="w-5 h-5 text-[#b93232] shrink-0 mt-0.5" />
          <div>
            <div className="text-[11px] font-extrabold uppercase tracking-widest text-[#b93232]">
              {log.status === "rejected" ? "Rejected" : "Failed"}
            </div>
            <div className="text-[12px] text-[#7b1d1d] mt-1">{log.error}</div>
          </div>
        </div>
      )}

      {/* Timeline */}
      <PushTimeline
        steps={log.step_results}
        status={log.status}
        live={log.status === "queued" || log.status === "processing"}
      />

      {/* Worker lease info (only while actively processing) */}
      {log.status === "processing" && log.worker_id && log.lease_until && (
        <div className="text-[10px] font-mono text-[#888894] text-center">
          worker: {log.worker_id} · lease until{" "}
          {new Date(log.lease_until).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Terminal banner — shown on top right of the header
// ---------------------------------------------------------------------------

function TerminalBanner({ log }: { log: PushLog }) {
  if (log.status === "pushed") {
    return (
      <div className="bg-[#f0f9f4] border-2 border-[#247a52] rounded-xl px-4 py-3 flex items-center gap-3 shrink-0">
        <CheckCircle2 className="w-5 h-5 text-[#247a52]" />
        <div className="flex flex-col">
          <span className="text-[11px] font-extrabold uppercase tracking-widest text-[#247a52]">
            Pushed to OPS
          </span>
          {log.ops_product_id != null && (
            <span className="font-mono text-[12px] text-[#1e1e24] font-bold">
              products_id = {log.ops_product_id}
            </span>
          )}
        </div>
      </div>
    );
  }
  if (log.status === "dry_run_pushed") {
    return (
      <div className="bg-[#eef4fb] border-2 border-[#1e4d92] rounded-xl px-4 py-3 flex items-center gap-3 shrink-0">
        <CheckCircle2 className="w-5 h-5 text-[#1e4d92]" />
        <div className="flex flex-col">
          <span className="text-[11px] font-extrabold uppercase tracking-widest text-[#1e4d92]">
            Dry-run complete
          </span>
          <span className="font-mono text-[12px] text-[#484852]">
            FakeOpsClient — no real writes
          </span>
        </div>
      </div>
    );
  }
  return null;
}

// ---------------------------------------------------------------------------
// Idempotency block — orchestrator key id, idem key, payload hash, callback
// ---------------------------------------------------------------------------

function IdempotencyBlock({ log }: { log: PushLog }) {
  const rows: { label: string; value: string | null; mono?: boolean }[] = [
    { label: "Orchestrator key", value: log.key_id, mono: true },
    { label: "Idempotency key", value: log.idempotency_key, mono: true },
    {
      label: "Payload hash",
      value: log.payload_hash ? `${log.payload_hash.slice(0, 16)}…` : null,
      mono: true,
    },
    { label: "Request id", value: log.request_id, mono: true },
  ];
  return (
    <section className="bg-white border-2 border-[#cfccc8] rounded-2xl overflow-hidden">
      <header className="px-6 py-3 bg-[#f9f7f4] border-b-2 border-[#cfccc8] flex items-center justify-between">
        <div className="text-[11px] font-extrabold uppercase tracking-widest text-[#1e1e24]">
          Gateway metadata
        </div>
        <CallbackStatusPill status={log.callback_status} attempts={log.callback_attempts} />
      </header>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 px-6 py-4 text-[12px]">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center gap-2 min-w-0">
            <span className="text-[10px] font-bold uppercase tracking-widest text-[#888894] w-32 shrink-0">
              {r.label}
            </span>
            {r.value ? (
              <CopyableValue value={r.value} mono={r.mono} />
            ) : (
              <span className="text-[#888894]">—</span>
            )}
          </div>
        ))}
        {log.callback_url && (
          <div className="flex items-center gap-2 min-w-0 sm:col-span-2">
            <span className="text-[10px] font-bold uppercase tracking-widest text-[#888894] w-32 shrink-0">
              Callback url
            </span>
            <a
              href={log.callback_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-[11px] text-[#1e4d92] hover:underline truncate flex items-center gap-1"
            >
              <span className="truncate">{log.callback_url}</span>
              <ExternalLink className="w-3 h-3 shrink-0" />
            </a>
          </div>
        )}
      </div>
    </section>
  );
}

function CallbackStatusPill({
  status,
  attempts,
}: {
  status: CallbackStatus;
  attempts: number;
}) {
  const palette: Record<CallbackStatus, { bg: string; fg: string; icon: React.ReactNode; label: string }> = {
    not_requested: { bg: "#f9f7f4", fg: "#888894", icon: null, label: "no callback" },
    pending: { bg: "#fff7e0", fg: "#c17c00", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: "callback pending" },
    sent: { bg: "#f0f9f4", fg: "#247a52", icon: <Send className="w-3 h-3" />, label: "callback sent" },
    failed: { bg: "#fdf2f2", fg: "#b93232", icon: <XCircle className="w-3 h-3" />, label: "callback failed" },
  };
  const p = palette[status];
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border font-mono text-[9px] font-bold uppercase tracking-wide"
      style={{ background: p.bg, color: p.fg, borderColor: p.fg }}
    >
      {p.icon}
      {p.label}
      {attempts > 0 && status !== "not_requested" && (
        <span className="opacity-70">· {attempts} attempt{attempts === 1 ? "" : "s"}</span>
      )}
    </span>
  );
}

function CopyableValue({ value, mono }: { value: string; mono?: boolean }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        } catch {
          /* silent */
        }
      }}
      title="Click to copy"
      className={`inline-flex items-center gap-1 truncate hover:text-[#1e4d92] transition-colors group ${
        mono ? "font-mono text-[11px]" : "text-[12px]"
      } text-[#1e1e24]`}
    >
      <span className="truncate">{value}</span>
      {copied ? (
        <CheckCircle2 className="w-3 h-3 text-[#247a52] shrink-0" />
      ) : (
        <Copy className="w-2.5 h-2.5 opacity-0 group-hover:opacity-60 shrink-0" />
      )}
    </button>
  );
}

type _PushStatusUsed = PushStatus;
