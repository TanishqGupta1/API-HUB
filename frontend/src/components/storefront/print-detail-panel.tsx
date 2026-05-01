"use client";

import { useState } from "react";
import type { Product } from "@/lib/types";
import { DimensionInput, type DimensionInputValue } from "@/components/storefront/dimension-input";
import { OptionGroupedForm } from "@/components/storefront/option-grouped-form";
import { LivePriceQuote } from "@/components/storefront/live-price-quote";

interface Props {
  product: Product;
}

const num = (s: string | null | undefined): number | null =>
  s == null || s === "" ? null : Number(s);

export function PrintDetailPanel({ product }: Props) {
  const detail = product.print_details;
  const [dim, setDim] = useState<DimensionInputValue>({ width: null, height: null });
  const [qty, setQty] = useState<number>(1);
  const [selected, setSelected] = useState<Record<string, string>>({});

  const selectedAttributeIds = Object.values(selected).filter((v): v is string => !!v);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#888894]">
          Size
        </div>
        <DimensionInput
          width={dim.width}
          height={dim.height}
          widthMin={num(detail?.width_min ?? null)}
          widthMax={num(detail?.width_max ?? null)}
          heightMin={num(detail?.height_min ?? null)}
          heightMax={num(detail?.height_max ?? null)}
          onChange={setDim}
        />
      </div>

      <div className="flex flex-col gap-3">
        <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#888894]">
          Quantity
        </div>
        <input
          aria-label="Quantity"
          type="number"
          min={1}
          step={1}
          value={qty}
          onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))}
          className="h-9 w-32 px-2 text-[13px] border border-[#cfccc8] rounded-md bg-white text-[#1e1e24] focus:outline-none focus:border-[#1e4d92]"
        />
      </div>

      <OptionGroupedForm
        options={product.options}
        selected={selected}
        onChange={setSelected}
      />

      <LivePriceQuote
        productId={product.id}
        qty={qty}
        width={dim.width}
        height={dim.height}
        selectedAttributeIds={selectedAttributeIds}
      />
    </div>
  );
}
