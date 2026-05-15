/**
 * Status pill — single source of truth for colors/labels is
 * `frontend/src/lib/push-status.ts`. Used on the customer-curated catalog
 * page and on the Products page when a customer is selected via top-nav.
 *
 * Renders any value from the broadened SelectionStatus union (T22). Unknown
 * strings fall through to the labeled-fallback config in push-status.ts so
 * the badge never renders blank — useful when the backend ships a new
 * status string before this map gets updated.
 */
import { getStatusConfig } from "@/lib/push-status";
import type { SelectionStatus } from "@/lib/types";

export function SelectionBadge({ status }: { status: SelectionStatus | string }) {
  const c = getStatusConfig(status);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${c.bg} ${c.border} ${c.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${c.text.replace("text-", "bg-")}`} aria-hidden />
      {c.label}
    </span>
  );
}
