"use client";

import { useMemo } from "react";
import { useDebouncedQuote } from "@/lib/use-debounced-quote";

// Human-readable labels for breakdown keys returned by the pricing API.
// snake_case backend keys → readable UI labels (N2).
const BREAKDOWN_LABELS: Record<string, string> = {
  base: "Base price",
  area: "Area (sq in)",
  area_factor: "Area rate",
  setup_cost: "Setup cost",
  qty: "Quantity",
  fallback: "Base price fallback",
  tier_match: "Tier applied",
};

function formatBreakdownValue(key: string, value: unknown): string {
  if (key === "tier_match" && value && typeof value === "object") {
    const t = value as { group?: string; qty_band?: string; tier_price?: string };
    return `${t.group ?? ""} ${t.qty_band ?? ""} @ $${t.tier_price ?? ""}`;
  }
  if (key === "fallback") return value ? "Yes (no tier matched)" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

interface Props {
  productId: string;
  qty: number;
  width: number | null;
  height: number | null;
  // selectedAttributeIds intentionally removed (Phase 5b) —
  // FormulaResolver does not yet read them; passing them implied
  // options affect price when they do not (B2).
}

export function LivePriceQuote({
  productId,
  qty,
  width,
  height,
}: Props) {
  const ready = qty > 0 && width != null && height != null && width > 0 && height > 0;

  // Stabilise body object so useDebouncedQuote's JSON.stringify runs only
  // when values actually change, not on every parent render (M4).
  const body = useMemo(
    () => ({
      product_id: productId,
      qty,
      width: width ?? undefined,
      height: height ?? undefined,
    }),
    [productId, qty, width, height],
  );

  const { quote, loading, error } = useDebouncedQuote({ enabled: ready, body });

  if (!ready) {
    return (
      <div className="px-4 py-3 rounded-md border border-dashed border-[#cfccc8] text-[12px] text-[#888894]">
        Enter dimensions and quantity to see your price
      </div>
    );
  }
  if (error) {
    return (
      <div className="px-4 py-3 rounded-md border border-[#b93232] bg-[#fdeded] text-[12px] text-[#b93232]">
        {error}
      </div>
    );
  }
  if (loading || !quote) {
    return (
      <div className="px-4 py-3 rounded-md border border-[#cfccc8] text-[12px] text-[#888894]">
        Pricing…
      </div>
    );
  }
  return (
    <div className="px-4 py-3 rounded-md border border-[#1e4d92] bg-[#eef4fb]">
      <div className="flex items-baseline justify-between">
        <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#1e4d92]">
          Total
        </div>
        <div className="text-[24px] font-extrabold text-[#1e1e24]">${quote.total}</div>
      </div>
      <div className="mt-1 text-[12px] text-[#484852]">
        ${quote.unit_price} per unit · {quote.currency}
      </div>
      <details className="mt-3 text-[11px]">
        <summary className="cursor-pointer text-[#1e4d92] font-semibold">Price breakdown</summary>
        <ul className="mt-2 flex flex-col gap-1 font-mono text-[11px] text-[#484852]">
          {Object.entries(quote.breakdown).map(([k, v]) => (
            <li key={k} className="flex justify-between gap-4">
              <span className="text-[#888894]">{BREAKDOWN_LABELS[k] ?? k}</span>
              <span>{formatBreakdownValue(k, v)}</span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
