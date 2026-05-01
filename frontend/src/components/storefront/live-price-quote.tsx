"use client";

import { useDebouncedQuote } from "@/lib/use-debounced-quote";

interface Props {
  productId: string;
  qty: number;
  width: number | null;
  height: number | null;
  selectedAttributeIds: string[];
}

export function LivePriceQuote({
  productId,
  qty,
  width,
  height,
  selectedAttributeIds,
}: Props) {
  const ready = qty > 0 && width != null && height != null && width > 0 && height > 0;
  const { quote, loading, error } = useDebouncedQuote({
    enabled: ready,
    body: {
      product_id: productId,
      qty,
      width: width ?? undefined,
      height: height ?? undefined,
      selected_attribute_ids: selectedAttributeIds,
    },
  });

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
        <summary className="cursor-pointer text-[#1e4d92] font-semibold">Breakdown</summary>
        <ul className="mt-2 grid grid-cols-2 gap-1 font-mono text-[11px] text-[#484852]">
          {Object.entries(quote.breakdown).map(([k, v]) => (
            <li key={k}>
              {k}: {typeof v === "object" ? JSON.stringify(v) : String(v)}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
