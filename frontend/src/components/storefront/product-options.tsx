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

interface ProductOptionsProps {
  options: ProductOption[] | undefined | null;
  priceLookup?: Map<number, number>;
  onPriceChange?: (adjustment: number) => void;
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
  const hiddenCount = sorted.length - visible.length;

  const [showAll, setShowAll] = useState(false);
  const COLLAPSE_AT = 6;
  const shown = showAll || visible.length <= COLLAPSE_AT ? visible : visible.slice(0, COLLAPSE_AT);

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
    <div className="pt-5 border-t border-dashed border-[#cfccc8]">
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#888894]">
          Options
        </div>
        {hiddenCount > 0 ? (
          <div className="text-[10px] font-mono text-[#b4b4bc]">
            {hiddenCount} system / single-value hidden
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-2">
        {shown.map((opt) => {
          const attrs = visibleAttrs(opt);
          const optType = opt.options_type ?? "combo";
          const isRadio = optType === "radio" && attrs.length <= 4;

          return (
            <div
              key={opt.id}
              className="grid grid-cols-[minmax(0,9rem)_1fr] items-center gap-3 px-3 py-2 rounded-md bg-white border border-[#ebe8e3]"
            >
              <div className="min-w-0">
                <div className="truncate text-[13px] font-semibold text-[#1e1e24]">
                  {opt.title}
                  {opt.required ? <span className="ml-1 text-[#b93232]">*</span> : null}
                </div>
                <div className="truncate font-mono text-[10px] text-[#b4b4bc]">
                  {opt.option_key}
                </div>
              </div>

              {isRadio ? (
                <div className="flex flex-wrap gap-1 justify-end">
                  {attrs.map((a) => {
                    const active = picked[opt.id] === a.id;
                    const mod = a.ops_attribute_id != null ? priceLookup?.get(a.ops_attribute_id) : undefined;
                    return (
                      <button
                        key={a.id}
                        type="button"
                        onClick={() => setPicked((p) => ({ ...p, [opt.id]: a.id }))}
                        className={
                          "px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-colors " +
                          (active
                            ? "border-[#1e4d92] bg-[#1e4d92] text-white"
                            : "border-[#e9e7e3] bg-[#f9f7f4] text-[#484852] hover:border-[#1e4d92] hover:text-[#1e4d92]")
                        }
                      >
                        {a.title}
                        {mod != null && mod !== 0 && (
                          <span className={`ml-1 text-[10px] font-mono ${active ? "text-blue-200" : mod > 0 ? "text-[#1e7a3c]" : "text-[#b93232]"}`}>
                            {mod > 0 ? `+$${mod.toFixed(2)}` : `-$${Math.abs(mod).toFixed(2)}`}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <select
                  value={picked[opt.id] ?? ""}
                  onChange={(e) =>
                    setPicked((p) => ({ ...p, [opt.id]: e.target.value || null }))
                  }
                  className="h-8 px-2 text-[12px] border border-[#e9e7e3] rounded-md bg-[#f9f7f4] text-[#1e1e24] font-medium focus:outline-none focus:border-[#1e4d92] min-w-0 max-w-full"
                >
                  {!opt.required ? <option value="">—</option> : null}
                  {attrs.map((a) => {
                    const mod = a.ops_attribute_id != null ? priceLookup?.get(a.ops_attribute_id) : undefined;
                    return (
                      <option key={a.id} value={a.id}>
                        {a.title}{mod != null && mod !== 0 ? (mod > 0 ? ` (+$${mod.toFixed(2)})` : ` (-$${Math.abs(mod).toFixed(2)})`) : ""}
                      </option>
                    );
                  })}
                </select>
              )}
            </div>
          );
        })}
      </div>

      {visible.length > COLLAPSE_AT ? (
        <button
          type="button"
          onClick={() => setShowAll((v) => !v)}
          className="mt-3 text-[11px] font-mono text-[#1e4d92] hover:underline"
        >
          {showAll
            ? `Hide ${visible.length - COLLAPSE_AT} options`
            : `Show ${visible.length - COLLAPSE_AT} more options`}
        </button>
      ) : null}
    </div>
  );
}
