"use client";

import type { Variant } from "@/lib/types";

interface PriceBlockProps {
  variant: Variant | null;
  fallback?: Variant[];
  adjustment?: number;
}

function fmt(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return "—";
  return `$${Number(amount).toFixed(2)}`;
}

export function PriceBlock({ variant, fallback = [], adjustment = 0 }: PriceBlockProps) {
  if (variant?.base_price !== null && variant?.base_price !== undefined) {
    return (
      <div className="flex flex-col gap-1">
        <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852]">
          Price
        </div>
        <div className="font-mono text-[28px] font-extrabold text-[#1e4d92] leading-none">
          {fmt((variant.base_price ?? 0) + adjustment)}
        </div>
        {adjustment !== 0 && (
          <div className="text-[11px] font-mono text-[#484852]">
            Base {fmt(variant.base_price)}
            <span className={adjustment > 0 ? "text-[#1e7a3c] ml-1" : "text-[#b93232] ml-1"}>
              {adjustment > 0 ? `+${fmt(adjustment)}` : fmt(adjustment)} options
            </span>
          </div>
        )}
        {variant.inventory !== null && (
          <div className="text-[12px] text-[#484852] font-medium">
            {variant.inventory > 0
              ? `${variant.inventory} in stock${variant.warehouse ? ` · ${variant.warehouse}` : ""}`
              : "Out of stock"}
          </div>
        )}
      </div>
    );
  }

  // No variant selected — show price range from fallback variants.
  const prices = fallback
    .map((v) => v.base_price)
    .filter((p): p is number => typeof p === "number");

  if (prices.length === 0) {
    return (
      <div className="flex flex-col gap-1">
        <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852]">
          Price
        </div>
        <div className="font-mono text-[20px] font-extrabold text-[#888894]">
          Not priced yet
        </div>
      </div>
    );
  }

  const min = Math.min(...prices);
  const max = Math.max(...prices);

  return (
    <div className="flex flex-col gap-1">
      <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852]">
        Price range
      </div>
      <div className="font-mono text-[24px] font-extrabold text-[#1e4d92] leading-none">
        {min === max ? fmt(min) : `${fmt(min)} – ${fmt(max)}`}
      </div>
      <div className="text-[12px] text-[#484852]">Pick a variant to see exact price</div>
    </div>
  );
}
