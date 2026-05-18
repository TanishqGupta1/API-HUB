"use client";

/**
 * Phase 8 — Dry-Run + Live push controls.
 *
 * Two buttons:
 *   1. "Send Dry-Run" — primary (default). One click, no confirmation.
 *      Uses FakeOpsClient on the backend; no real OPS writes.
 *   2. "Send to OPS staging (LIVE)" — secondary, red-outlined.
 *      Opens a confirm dialog requiring the operator to type the exact
 *      confirmation string (e.g. "PUSH PC61 TO STAGING") before the
 *      submit button enables.
 *
 * Per spec §Dry-run semantics — the typed-confirm pattern is the safety
 * gate. Operator can't fat-finger a live push.
 */
import { AlertTriangle, Loader2, Send, ShieldAlert, X } from "lucide-react";
import { useState } from "react";

interface Props {
  /** What the user has to type to enable the Live button. e.g. `PUSH PC61 TO STAGING`. */
  liveConfirmText: string;
  /** Disable while a previous click is in flight, or if blockers prevent push. */
  disabled?: boolean;
  /** Optional reason to surface in the disabled tooltip. */
  disabledReason?: string;
  /** Marks the page as in mock mode — adds a "MOCK" pill so reviewers know. */
  mockMode?: boolean;
  onDryRun: () => Promise<void> | void;
  onLive: () => Promise<void> | void;
}

export function DryRunControls({
  liveConfirmText,
  disabled,
  disabledReason,
  mockMode,
  onDryRun,
  onLive,
}: Props) {
  const [dryRunLoading, setDryRunLoading] = useState(false);
  const [liveDialogOpen, setLiveDialogOpen] = useState(false);

  async function handleDryRun() {
    if (disabled || dryRunLoading) return;
    setDryRunLoading(true);
    try {
      await onDryRun();
    } finally {
      setDryRunLoading(false);
    }
  }

  return (
    <>
      <div
        className="flex items-center justify-between gap-4 p-5 bg-white border-2 border-[#cfccc8] rounded-2xl"
        title={disabled ? disabledReason : undefined}
      >
        <div className="text-[12px] text-[#888894]">
          {disabled ? (
            <span className="flex items-center gap-1.5 text-[#b93232]">
              <AlertTriangle className="w-3.5 h-3.5" />
              {disabledReason ?? "Push is blocked"}
            </span>
          ) : (
            <span>
              Dry-run uses a fake OPS client — safe to click. Live push
              talks to staging.
            </span>
          )}
          {mockMode && (
            <span className="ml-2 inline-flex items-center px-1.5 py-0.5 bg-[#fff7e0] border border-[#c17c00] rounded font-mono text-[9px] font-bold uppercase tracking-wide text-[#c17c00]">
              mock mode
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleDryRun}
            disabled={disabled || dryRunLoading}
            className="inline-flex items-center gap-2 px-5 h-10 bg-[#1e4d92] hover:bg-[#173d74] text-white rounded-full font-bold text-[12px] uppercase tracking-wide shadow-md shadow-blue-900/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {dryRunLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-3.5 h-3.5" />
            )}
            Send Dry-Run
          </button>
          <button
            onClick={() => !disabled && setLiveDialogOpen(true)}
            disabled={disabled}
            className="inline-flex items-center gap-2 px-5 h-10 bg-white border-2 border-[#b93232] text-[#b93232] hover:bg-[#fdf2f2] rounded-full font-bold text-[12px] uppercase tracking-wide transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            Send to OPS staging (LIVE)
          </button>
        </div>
      </div>

      {liveDialogOpen && (
        <LiveConfirmDialog
          confirmText={liveConfirmText}
          onClose={() => setLiveDialogOpen(false)}
          onConfirmed={async () => {
            setLiveDialogOpen(false);
            await onLive();
          }}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Typed-confirmation modal
// ---------------------------------------------------------------------------

function LiveConfirmDialog({
  confirmText,
  onClose,
  onConfirmed,
}: {
  confirmText: string;
  onClose: () => void;
  onConfirmed: () => Promise<void> | void;
}) {
  const [typed, setTyped] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const match = typed === confirmText;

  async function handleSubmit() {
    if (!match || submitting) return;
    setSubmitting(true);
    try {
      await onConfirmed();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="bg-white border-2 border-[#b93232] rounded-2xl max-w-lg w-full shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between px-6 py-4 bg-[#fdf2f2] border-b-2 border-[#b93232] rounded-t-2xl">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-[#b93232]" />
            <span className="text-[13px] font-extrabold uppercase tracking-widest text-[#b93232]">
              Confirm Live Push
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-[#888894] hover:text-[#1e1e24]"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </header>
        <div className="px-6 py-5 space-y-4">
          <div className="text-[13px] text-[#1e1e24] leading-relaxed">
            This will create a real product in the OPS staging storefront.
            <strong className="block mt-2 text-[#b93232]">
              Halt-no-rollback: if any mutation fails mid-sequence, you&apos;ll
              need to clean up the partial OPS state by hand.
            </strong>
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-widest text-[#484852] mb-1.5">
              Type the confirmation string to enable
            </label>
            <div className="font-mono text-[12px] text-[#b93232] bg-[#fdf2f2] border border-[#b93232] rounded px-3 py-1.5 inline-block mb-2">
              {confirmText}
            </div>
            <input
              autoFocus
              type="text"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder="…"
              className="w-full h-11 px-3 font-mono text-[13px] border-2 border-[#cfccc8] rounded-lg outline-none focus:border-[#b93232] transition-colors"
            />
          </div>
        </div>
        <footer className="flex items-center justify-end gap-2 px-6 py-4 bg-[#f9f7f4] border-t border-[#cfccc8] rounded-b-2xl">
          <button
            onClick={onClose}
            className="px-4 h-9 text-[12px] font-semibold text-[#484852] hover:text-[#1e1e24] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!match || submitting}
            className="inline-flex items-center gap-2 px-4 h-9 bg-[#b93232] hover:bg-[#9c2626] text-white rounded-full font-bold text-[12px] uppercase tracking-wide transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {submitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Push to OPS
          </button>
        </footer>
      </div>
    </div>
  );
}
