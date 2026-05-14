/**
 * Central push-status map — single source of truth for the 11 status
 * values used across Phase 8's gateway pipeline. Components (SelectionBadge,
 * customer catalog row, push-log list, push-history) import from here
 * instead of hard-coding their own status colors / labels.
 *
 * Spec: docs/superpowers/specs/2026-05-13-centralized-fastapi-ops-design.md
 * Plan: docs/superpowers/plans/2026-05-14-centralized-fastapi-ops-m1.md (T4)
 *
 * Status vocabulary (locked in spec Rev 1 + 2 + 3):
 *   selected         — customer added to catalog, not pushed yet
 *   accepted         — gateway recorded the request, preflight pending
 *   queued           — preflight passed, awaiting worker claim
 *   processing       — worker actively calling OPS
 *   pushed           — OPS confirmed product created/updated
 *   failed           — hard failure before any OPS writes; no cleanup needed
 *   partial_failure  — some OPS steps succeeded; cleanup_targets populated
 *   rejected         — preflight blocker, caller error; no OPS writes
 *   canceled         — operator canceled before terminal state
 *   dry_run_pushed   — dry-run path completed cleanly via FakeOpsClient
 *   stale            — selection out of date vs supplier catalog
 */

export type PushStatus =
  | "selected"
  | "accepted"
  | "queued"
  | "processing"
  | "pushed"
  | "failed"
  | "partial_failure"
  | "rejected"
  | "canceled"
  | "dry_run_pushed"
  | "stale";

export interface StatusMeta {
  label: string;
  /** Tailwind classes for shadcn Badge (background + text + border). */
  badgeClass: string;
  /** When true, the status pill should pulse to indicate live in-flight work. */
  dotPulse?: boolean;
  description?: string;
}

export const PUSH_STATUS: Record<PushStatus, StatusMeta> = {
  selected:        { label: "Selected",        badgeClass: "bg-slate-100 text-slate-700 border-slate-200" },
  accepted:        { label: "Accepted",        badgeClass: "bg-blue-50 text-blue-700 border-blue-200", dotPulse: true },
  queued:          { label: "Queued",          badgeClass: "bg-blue-50 text-blue-700 border-blue-200", dotPulse: true },
  processing:      { label: "Processing",      badgeClass: "bg-blue-100 text-blue-800 border-blue-300", dotPulse: true },
  pushed:          { label: "Pushed",          badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  failed:          { label: "Failed",          badgeClass: "bg-rose-50 text-rose-700 border-rose-200" },
  partial_failure: { label: "Partial Failure", badgeClass: "bg-amber-50 text-amber-700 border-amber-200" },
  rejected:        { label: "Rejected",        badgeClass: "bg-rose-50 text-rose-700 border-rose-200" },
  canceled:        { label: "Canceled",        badgeClass: "bg-slate-100 text-slate-500 border-slate-200" },
  dry_run_pushed:  { label: "Dry-Run OK",      badgeClass: "bg-violet-50 text-violet-700 border-violet-200" },
  stale:           { label: "Stale",           badgeClass: "bg-amber-50 text-amber-700 border-amber-200" },
};

/** Safe lookup with fallback for unknown statuses (forward-compat). */
export function getStatusMeta(status: string): StatusMeta {
  return PUSH_STATUS[status as PushStatus] ?? {
    label: status,
    badgeClass: "bg-slate-100 text-slate-700 border-slate-200",
  };
}

/** Statuses where no further work happens — polling can stop. */
export const TERMINAL_STATUSES: PushStatus[] = [
  "pushed",
  "failed",
  "rejected",
  "canceled",
  "dry_run_pushed",
];

/** Statuses where work is in motion — UI should poll and pulse. */
export const IN_FLIGHT_STATUSES: PushStatus[] = [
  "accepted",
  "queued",
  "processing",
];

export function isTerminal(status: string): boolean {
  return TERMINAL_STATUSES.includes(status as PushStatus);
}

export function isInFlight(status: string): boolean {
  return IN_FLIGHT_STATUSES.includes(status as PushStatus);
}
