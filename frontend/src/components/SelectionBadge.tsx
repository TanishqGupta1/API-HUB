/**
 * 4-state selection status pill, used on the customer-curated catalog page
 * and on the Products page when a customer is selected via top-nav.
 *
 * Colors map to the Blueprint design system in globals.css:
 *   selected → ink-muted gray (neutral, "intent recorded")
 *   pushed   → success green
 *   stale    → orange (action needed — re-push)
 *   failed   → error red (last push attempt failed)
 */
import type { SelectionStatus } from "@/lib/types";

const COLOR_MAP: Record<SelectionStatus, { bg: string; border: string; text: string; label: string }> = {
  selected: {
    bg: "bg-[#f2f0ed]",
    border: "border-[#cfccc8]",
    text: "text-[#484852]",
    label: "Selected",
  },
  pushed: {
    bg: "bg-[#f0f9f4]",
    border: "border-[#247a52]",
    text: "text-[#247a52]",
    label: "Pushed",
  },
  stale: {
    bg: "bg-orange-50",
    border: "border-[#c77d2e]",
    text: "text-[#c77d2e]",
    label: "Stale",
  },
  failed: {
    bg: "bg-[#fdf2f2]",
    border: "border-[#b93232]",
    text: "text-[#b93232]",
    label: "Failed",
  },
};

export function SelectionBadge({ status }: { status: SelectionStatus }) {
  const c = COLOR_MAP[status];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${c.bg} ${c.border} ${c.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${c.text.replace("text-", "bg-")}`} aria-hidden />
      {c.label}
    </span>
  );
}
