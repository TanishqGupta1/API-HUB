"use client";

import { useEffect, useMemo, useState } from "react";
import type { ProductOption, ProductOptionAttribute } from "@/lib/types";

type AttrLoose = ProductOptionAttribute & {
  attribute_key?: string | null;
  default_attribute?: string | number | null;
};

const HIDDEN_TYPES = new Set(["admin_only", "textmp"]);
const TRIVIAL_KEY_RX = /^(None|none)(?:_|$)/;

function visibleAttrs(opt: ProductOption): AttrLoose[] {
  return (opt.attributes ?? [])
    .slice()
    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.title.localeCompare(b.title)) as AttrLoose[];
}

function isMeaningful(opt: ProductOption): boolean {
  if (HIDDEN_TYPES.has(opt.options_type ?? "")) return false;
  const attrs = (opt.attributes ?? []) as AttrLoose[];
  if (attrs.length < 2) {
    if (attrs.length === 0) return false;
    if (TRIVIAL_KEY_RX.test(attrs[0].attribute_key ?? "")) return false;
    if (!opt.required) return false;
  }
  return true;
}

function defaultAttrId(opt: ProductOption): string | null {
  const attrs = visibleAttrs(opt);
  const def = attrs.find((a) => a.default_attribute === "1" || a.default_attribute === 1);
  return (def ?? attrs[0])?.id ?? null;
}

function fmtMod(mod: number): string {
  return mod > 0 ? `+$${mod.toFixed(2)}` : `-$${Math.abs(mod).toFixed(2)}`;
}

interface ProductOptionsProps {
  options: ProductOption[] | undefined | null;
  priceLookup?: Map<number, number>;
  onPriceChange?: (adjustment: number) => void;
}

function OptionCard({
  opt,
  pickedAttrId,
  onPick,
  priceLookup,
}: {
  opt: ProductOption;
  pickedAttrId: string | null;
  onPick: (attrId: string) => void;
  priceLookup?: Map<number, number>;
}) {
  const [expanded, setExpanded] = useState(false);
  const COLLAPSE_AT = 5;
  const attrs = visibleAttrs(opt);
  const shown = expanded ? attrs : attrs.slice(0, COLLAPSE_AT);

  return (
    <div className="bg-white rounded-[10px] border border-[#cfccc8] shadow-[4px_5px_0_rgba(30,77,146,0.08)] flex flex-col overflow-hidden">
      {/* Card header */}
      <div className="flex items-center gap-2 px-4 py-3 bg-[#ebe8e3] border-b border-[#cfccc8] rounded-t-[10px]">
        <span className="w-[3px] h-4 bg-[#1e4d92] rounded-full shrink-0" />
        <span className="font-bold text-[13px] text-[#1e4d92] truncate flex-1">{opt.title}</span>
        {opt.required && (
          <span className="text-[10px] font-bold text-[#b93232] uppercase tracking-wide shrink-0">Required</span>
        )}
      </div>

      {/* Attribute rows */}
      <div className="flex-1 px-3 py-2 flex flex-col gap-0.5">
        {shown.map((attr) => {
          const selected = pickedAttrId === attr.id;
          const mod = attr.ops_attribute_id != null ? priceLookup?.get(attr.ops_attribute_id) : undefined;
          return (
            <button
              key={attr.id}
              type="button"
              onClick={() => onPick(attr.id)}
              className={`w-full flex items-center gap-2.5 px-2 py-1.5 rounded-md text-left transition-colors
                ${selected
                  ? "bg-[#eef4fb] border border-[#1e4d92]"
                  : "border border-transparent hover:bg-[#f5f3f0]"
                }`}
            >
              {/* Radio circle */}
              <span className={`shrink-0 w-4 h-4 rounded-full border-2 flex items-center justify-center transition-colors
                ${selected ? "border-[#1e4d92]" : "border-[#cfccc8]"}`}>
                {selected && <span className="w-2 h-2 rounded-full bg-[#1e4d92]" />}
              </span>

              <span className={`flex-1 text-[12px] truncate ${selected ? "font-semibold text-[#1e1e24]" : "text-[#484852]"}`}>
                {attr.title}
              </span>

              {mod != null && mod !== 0 && (
                <span className={`text-[10px] font-mono shrink-0 ${mod > 0 ? "text-[#1e7a3c]" : "text-[#b93232]"}`}>
                  {fmtMod(mod)}
                </span>
              )}
              {(mod == null || mod === 0) && (
                <span className="text-[10px] font-mono text-[#b4b4bc] shrink-0">—</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Show more */}
      {attrs.length > COLLAPSE_AT && (
        <div className="px-4 pb-2">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="text-[11px] font-semibold text-[#1e4d92] hover:underline"
          >
            {expanded ? "Show Less ▲" : `Show More ▼ (${attrs.length - COLLAPSE_AT})`}
          </button>
        </div>
      )}
    </div>
  );
}

export function ProductOptions({ options, priceLookup, onPriceChange }: ProductOptionsProps) {
  const sorted = useMemo(
    () =>
      (options ?? [])
        .slice()
        .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.title.localeCompare(b.title)),
    [options],
  );

  const visible = useMemo(() => sorted.filter(isMeaningful), [sorted]);

  const [picked, setPicked] = useState<Record<string, string | null>>(() =>
    Object.fromEntries(visible.map((o) => [o.id, defaultAttrId(o)])),
  );

  useEffect(() => {
    if (!priceLookup || !onPriceChange) return;
    let total = 0;
    visible.forEach((opt) => {
      const attr = opt.attributes.find((a) => a.id === picked[opt.id]);
      if (attr?.ops_attribute_id != null) {
        total += priceLookup.get(attr.ops_attribute_id) ?? 0;
      }
    });
    onPriceChange(total);
  }, [picked, visible, priceLookup, onPriceChange]);

  if (visible.length === 0) return null;

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-[15px] font-extrabold text-[#1e1e24] tracking-[-0.01em]">
          Customize Your Product
        </h2>
        <span className="text-[11px] font-mono text-[#888894]">{visible.length} options</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {visible.map((opt) => (
          <OptionCard
            key={opt.id}
            opt={opt}
            pickedAttrId={picked[opt.id] ?? null}
            onPick={(attrId) => setPicked((p) => ({ ...p, [opt.id]: attrId }))}
            priceLookup={priceLookup}
          />
        ))}
      </div>
    </div>
  );
}
