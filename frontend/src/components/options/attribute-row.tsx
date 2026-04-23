"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import type { AttributeConfigItem } from "@/lib/types";

interface Props {
  attr: AttributeConfigItem;
  onChange: (patch: Partial<AttributeConfigItem>) => void;
}

export function AttributeRow({ attr, onChange }: Props) {
  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-dashed border-[#ebe8e3] last:border-b-0">
      <Checkbox
        checked={attr.enabled}
        onCheckedChange={(v) => onChange({ enabled: Boolean(v) })}
      />
      <div className="flex-1 text-sm text-[#1e1e24] truncate">{attr.title}</div>
      <div className="flex items-center gap-1 text-xs text-[#888894]">
        <span>$</span>
        <Input
          type="number"
          step="0.01"
          value={attr.price}
          onChange={(e) => onChange({ price: parseFloat(e.target.value) || 0 })}
          className="h-7 w-20 text-xs"
        />
      </div>
      <div className="flex items-center gap-1 text-xs text-[#888894]">
        <span>#</span>
        <Input
          type="number"
          value={attr.numeric_value}
          onChange={(e) => onChange({ numeric_value: parseFloat(e.target.value) || 0 })}
          className="h-7 w-16 text-xs"
        />
      </div>
      <div className="flex items-center gap-1 text-xs text-[#888894]">
        <span>↕</span>
        <Input
          type="number"
          value={attr.sort_order}
          onChange={(e) => onChange({ sort_order: parseInt(e.target.value) || 0 })}
          className="h-7 w-14 text-xs"
        />
      </div>
    </div>
  );
}
