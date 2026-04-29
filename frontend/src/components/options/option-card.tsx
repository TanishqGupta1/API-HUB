"use client";

import { useState } from "react";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { AttributeRow } from "./attribute-row";
import type { OptionConfigItem, AttributeConfigItem } from "@/lib/types";
import { humanizeOptionName } from "@/lib/humanize-options";

interface Props {
  card: OptionConfigItem;
  dirty: boolean;
  onChange: (next: OptionConfigItem) => void;
  onSave: () => void | Promise<void>;
  onDelete: () => void | Promise<void>;
}

export function OptionCard({ card, dirty, onChange, onSave, onDelete }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);

  const visible = expanded ? card.attributes : card.attributes.slice(0, 5);

  const updateAttr = (idx: number, patch: Partial<AttributeConfigItem>) => {
    const next = { ...card, attributes: card.attributes.map((a, i) => (i === idx ? { ...a, ...patch } : a)) };
    onChange(next);
  };

  const handleSave = async () => {
    setSaving(true);
    try { await onSave(); } finally { setSaving(false); }
  };

  return (
    <div className="bg-white rounded-[10px] border border-[#cfccc8] shadow-[4px_5px_0_rgba(30,77,146,0.08)]">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#cfccc8] bg-[#ebe8e3] rounded-t-[10px]">
        <div className="font-bold text-[#1e4d92] text-sm flex items-center gap-2">
          <span className="w-1 h-4 bg-[#1e4d92]" />
          {humanizeOptionName(card.title, card.option_key)}
        </div>
        <Switch
          checked={card.enabled}
          onCheckedChange={(v) => onChange({ ...card, enabled: Boolean(v) })}
          className="data-[state=checked]:bg-green-500"
        />
      </div>

      <div className="px-4 py-2">
        {visible.map((attr, i) => (
          <AttributeRow key={attr.ops_attribute_id} attr={attr} onChange={(p) => updateAttr(i, p)} />
        ))}
        {card.attributes.length > 5 && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-[#1e4d92] font-semibold mt-2"
          >
            {expanded ? "Show Less ▲" : `Show More ▼ (${card.attributes.length - 5})`}
          </button>
        )}
      </div>

      <div className="flex items-center justify-end gap-2 px-4 py-2 border-t border-[#cfccc8]">
        <Button variant="ghost" size="sm" onClick={onDelete} className="text-[#b93232]">
          Delete
        </Button>
        <Button
          size="sm"
          onClick={handleSave}
          disabled={!dirty || saving}
          className="bg-[#1e4d92] hover:bg-[#173d74] text-white"
        >
          {saving ? "Saving..." : "Save"}
        </Button>
      </div>
    </div>
  );
}
