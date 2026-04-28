"use client";

import type { Supplier } from "@/lib/types";

interface Props {
  supplier: Supplier;
}

/** OPS-specific panel. Master options + attribute_key mapping lives on the
    per-product Configure Options page; this panel just points users there. */
export function OpsMappingPanel({ supplier }: Props) {
  return (
    <div className="bg-white rounded-[10px] border border-[#cfccc8] shadow-[4px_5px_0_rgba(30,77,146,0.08)] p-5 flex flex-col gap-3">
      <h3 className="font-bold text-[#1e4d92] text-sm flex items-center gap-2">
        <span className="w-1 h-4 bg-[#1e4d92]" />
        OPS-specific settings
      </h3>
      <p className="text-sm text-[#484852]">
        OPS master options and per-product option configuration are managed on
        the dedicated <strong>Master Options Catalog</strong> page and
        per-product <strong>Configure Options</strong> pages.
      </p>
      <p className="text-xs text-[#888894]">
        Field mappings for {supplier.name} apply to product-level fields only.
        Option-level configuration (attributes, prices, sort order) is per-product.
      </p>
    </div>
  );
}
