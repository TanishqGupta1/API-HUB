"use client";

import { useMemo } from "react";
import type { Variant } from "@/lib/types";
import { getColorHex } from "@/lib/color-map";

interface VariantPickerProps {
  variants: Variant[];
  selectedVariantId: string | null;
  onSelect: (variantId: string) => void;
  onColorChange?: (color: string) => void;
}

export function VariantPicker({
  variants,
  selectedVariantId,
  onSelect,
  onColorChange,
}: VariantPickerProps) {
  const colors = useMemo(() => {
    const seen = new Set<string>();
    return variants
      .map((v) => v.color)
      .filter((c): c is string => !!c && !seen.has(c) && !!seen.add(c));
  }, [variants]);

  const sizes = useMemo(() => {
    const seen = new Set<string>();
    return variants
      .map((v) => v.size)
      .filter((s): s is string => !!s && !seen.has(s) && !!seen.add(s));
  }, [variants]);

  const selected = variants.find((v) => v.id === selectedVariantId) ?? null;

  const matchingForColor = (color: string) =>
    variants.filter((v) => v.color === color);

  const pickForColor = (color: string) => {
    const match = matchingForColor(color).find(
      (v) => !selected?.size || v.size === selected.size
    ) ?? matchingForColor(color)[0];
    if (match) {
      onSelect(match.id);
      onColorChange?.(color);
    }
  };

  const pickForSize = (size: string) => {
    if (!selected?.color) {
      const match = variants.find((v) => v.size === size);
      if (match) onSelect(match.id);
      return;
    }
    const match = variants.find(
      (v) => v.color === selected.color && v.size === size
    );
    if (match) onSelect(match.id);
  };

  return (
    <div className="flex flex-col gap-5">
      {colors.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852]">Color</span>
            {selected?.color && (
              <span className="text-[11px] font-semibold text-[#1e1e24]">{selected.color}</span>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {colors.map((color) => {
              const active = selected?.color === color;
              const hex = getColorHex(color);
              return (
                <button
                  key={color}
                  onClick={() => pickForColor(color)}
                  title={color}
                  className={`group relative flex items-center gap-2 px-3 py-1.5 rounded-full border text-[12px] font-semibold transition-all
                    ${active
                      ? "border-[#1e4d92] bg-[#eef4fb] text-[#1e4d92] shadow-sm"
                      : "border-[#cfccc8] bg-white text-[#484852] hover:border-[#1e4d92] hover:text-[#1e4d92]"
                    }`}
                >
                  {/* Color dot — only shown when we have a real color match */}
                  {hex && (
                    <span
                      className="w-4 h-4 rounded-full border border-black/10 shrink-0"
                      style={{ backgroundColor: hex }}
                    />
                  )}
                  {color}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {sizes.length > 0 && (
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852] mb-2">
            Size
          </div>
          <div className="flex flex-wrap gap-2">
            {sizes.map((size) => {
              const active = selected?.size === size;
              const matching = selected?.color
                ? variants.find(
                    (v) => v.color === selected.color && v.size === size
                  )
                : variants.find((v) => v.size === size);
              const disabled = !matching;
              return (
                <button
                  key={size}
                  onClick={() => !disabled && pickForSize(size)}
                  disabled={disabled}
                  className={`min-w-[52px] px-3 py-2 rounded-md border text-[13px] font-semibold transition-all
                    ${active
                      ? "bg-[#1e4d92] text-white border-[#1e4d92]"
                      : disabled
                        ? "bg-[#f9f7f4] text-[#b4b4bc] border-[#ebe8e3] cursor-not-allowed"
                        : "bg-white text-[#1e1e24] border-[#cfccc8] hover:border-[#1e4d92] hover:text-[#1e4d92]"
                    }`}
                >
                  {size}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
