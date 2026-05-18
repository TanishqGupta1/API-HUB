/**
 * Central status-map for push & selection states.
 *
 * Vocabulary
 *   selected         — customer added a product to their catalog (no push yet)
 *   accepted         — gateway accepted the push request (queued for execute_push)
 *   processing       — gateway is executing the mutation plan against OPS
 *   pushed           — push completed successfully
 *   stale            — supplier source updated since the last successful push
 *   failed           — push failed before any OPS row was created
 *   partial_failure  — some OPS mutations succeeded; cleanup_targets populated
 *   rejected         — preflight refused the request (missing decoration, etc.)
 *   dry_run_pushed   — dry-run completed via FakeOpsClient (no real OPS write)
 *
 * Legacy fallbacks
 *   pending  — old admin-route status string before the T19 gateway rewire;
 *              still appears on existing push_log rows written pre-rewire.
 *   skipped  — legacy push-log status from the n8n callback era.
 *
 * Anything not in this map renders with the FALLBACK config so the UI never
 * shows a blank pill — orchestrators that emit new vocabulary will at least
 * surface a labeled-but-uncolored badge until this file catches up.
 */

export type PushStatus =
  | "selected"
  | "accepted"
  | "processing"
  | "pushed"
  | "stale"
  | "failed"
  | "partial_failure"
  | "rejected"
  | "canceled"
  | "dry_run_pushed"
  | "pending"
  | "skipped";

export interface StatusConfig {
  /** Short display label (e.g. "Pushed", "Partial"). */
  label: string;
  /** Tailwind background utility class. */
  bg: string;
  /** Tailwind border utility class. */
  border: string;
  /** Tailwind text-color utility class. */
  text: string;
  /** Raw hex for inline styles (the push-log page uses style={} not classes). */
  color: string;
  /** Semantic category for downstream behavior (filtering, sorting, icons). */
  category: "pre" | "in_flight" | "success" | "warning" | "error" | "neutral";
}

export const PUSH_STATUS_CONFIG: Record<PushStatus, StatusConfig> = {
  selected: {
    label: "Selected",
    bg: "bg-[#f2f0ed]",
    border: "border-[#cfccc8]",
    text: "text-[#484852]",
    color: "#484852",
    category: "pre",
  },
  accepted: {
    label: "Accepted",
    bg: "bg-[#eef2fb]",
    border: "border-[#5a6fb8]",
    text: "text-[#3b4ea0]",
    color: "#3b4ea0",
    category: "in_flight",
  },
  processing: {
    label: "Processing",
    bg: "bg-[#e6effa]",
    border: "border-[#3b6fb0]",
    text: "text-[#1e4d92]",
    color: "#1e4d92",
    category: "in_flight",
  },
  pushed: {
    label: "Pushed",
    bg: "bg-[#f0f9f4]",
    border: "border-[#247a52]",
    text: "text-[#247a52]",
    color: "#247a52",
    category: "success",
  },
  stale: {
    label: "Stale",
    bg: "bg-orange-50",
    border: "border-[#c77d2e]",
    text: "text-[#c77d2e]",
    color: "#c77d2e",
    category: "warning",
  },
  failed: {
    label: "Failed",
    bg: "bg-[#fdf2f2]",
    border: "border-[#b93232]",
    text: "text-[#b93232]",
    color: "#b93232",
    category: "error",
  },
  partial_failure: {
    label: "Partial",
    bg: "bg-[#fdf5e7]",
    border: "border-[#a06023]",
    text: "text-[#a06023]",
    color: "#a06023",
    category: "warning",
  },
  rejected: {
    label: "Rejected",
    bg: "bg-[#f4eefb]",
    border: "border-[#7c4dbe]",
    text: "text-[#5e35a6]",
    color: "#5e35a6",
    category: "error",
  },
  dry_run_pushed: {
    label: "Dry Run",
    bg: "bg-[#f4f4f6]",
    border: "border-[#6b7280]",
    text: "text-[#4b5563]",
    color: "#4b5563",
    category: "neutral",
  },
  canceled: {
    label: "Canceled",
    bg: "bg-[#f2f0ed]",
    border: "border-[#888894]",
    text: "text-[#484852]",
    color: "#484852",
    category: "neutral",
  },
  pending: {
    label: "Pending",
    bg: "bg-[#fef7e7]",
    border: "border-[#d97706]",
    text: "text-[#b85f06]",
    color: "#b85f06",
    category: "in_flight",
  },
  skipped: {
    label: "Skipped",
    bg: "bg-[#f2f0ed]",
    border: "border-[#888894]",
    text: "text-[#888894]",
    color: "#888894",
    category: "neutral",
  },
};

const FALLBACK: StatusConfig = {
  label: "Unknown",
  bg: "bg-[#f9f7f4]",
  border: "border-[#ebe8e3]",
  text: "text-[#888894]",
  color: "#888894",
  category: "neutral",
};

/** Lookup a status's UI config. Returns a labeled fallback for unknown
 * strings so the badge never renders blank. */
export function getStatusConfig(status: string | null | undefined): StatusConfig {
  if (!status) return FALLBACK;
  const cfg = PUSH_STATUS_CONFIG[status as PushStatus];
  if (cfg) return cfg;
  // Unknown status — preserve the raw value as the label so admins can debug.
  return { ...FALLBACK, label: status };
}

/** True for statuses where another push attempt won't change anything new
 * (i.e. don't show "Push to OPS" while one is in flight). */
const IN_FLIGHT: ReadonlySet<string> = new Set([
  "accepted",
  "processing",
  "pending",
]);

export function isInFlight(status: string | null | undefined): boolean {
  return !!status && IN_FLIGHT.has(status);
}

/** Terminal = won't change without another deliberate action.
 * 'pushed' is terminal until the source updates → 'stale'.
 * 'partial_failure' is terminal until cleanup_targets are resolved. */
const TERMINAL: ReadonlySet<string> = new Set([
  "pushed",
  "failed",
  "partial_failure",
  "rejected",
  "canceled",
  "dry_run_pushed",
  "skipped",
]);

export function isTerminal(status: string | null | undefined): boolean {
  return !!status && TERMINAL.has(status);
}
