"use client";

import type { Supplier } from "@/lib/types";

interface Props {
  supplier: Supplier;
}

/** Stub for 4Over-specific config — extend when the 4Over connector adds options. */
export function FourOverMappingPanel({ supplier }: Props) {
  return (
    <div className="bg-white rounded-[10px] border border-[#cfccc8] shadow-[4px_5px_0_rgba(30,77,146,0.08)] p-5 flex flex-col gap-3">
      <h3 className="font-bold text-[#1e4d92] text-sm flex items-center gap-2">
        <span className="w-1 h-4 bg-[#1e4d92]" />
        4Over-specific settings
      </h3>
      <p className="text-sm text-[#888894]">
        Supplier-specific options coming soon. For now, configure base field
        mappings above to pipe 4Over's HMAC REST data into the hub schema.
      </p>
    </div>
  );
}
