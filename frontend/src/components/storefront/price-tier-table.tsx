"use client";

import type { VariantPriceTier } from "@/lib/types";

interface Props {
  tiers: VariantPriceTier[];
}

const UNBOUNDED = 2147483647;

export function PriceTierTable({ tiers }: Props) {
  if (tiers.length === 0) return null;
  const sorted = [...tiers].sort((a, b) => a.qty_min - b.qty_min);

  return (
    <div className="rounded-md border border-[#cfccc8] overflow-hidden">
      <table className="w-full text-[12px]">
        <thead className="bg-[#f2f0ed] text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852]">
          <tr>
            <th className="text-left px-3 py-1.5">Quantity</th>
            <th className="text-right px-3 py-1.5">Price each</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((t) => (
            <tr key={`${t.group_name}-${t.qty_min}`} className="odd:bg-white even:bg-[#f9f7f4]">
              <td className="px-3 py-1.5 font-mono">
                {t.qty_max >= UNBOUNDED ? `${t.qty_min}+` : `${t.qty_min} – ${t.qty_max}`}
              </td>
              <td className="px-3 py-1.5 text-right font-semibold text-[#1e1e24]">
                ${t.price}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
