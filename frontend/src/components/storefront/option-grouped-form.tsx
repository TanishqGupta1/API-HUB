"use client";

import type { ProductOption, ProductOptionAttribute } from "@/lib/types";
import { groupOptionsBySection, SECTION_ORDER } from "@/lib/option-groups";

interface Props {
  options: ProductOption[];
  selected: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
}

export function OptionGroupedForm({ options, selected, onChange }: Props) {
  const grouped = groupOptionsBySection(options);

  const setOpt = (optId: string, attrId: string) => {
    onChange({ ...selected, [optId]: attrId });
  };

  return (
    <div className="flex flex-col gap-6">
      {SECTION_ORDER.map((section) => {
        const opts = grouped[section];
        if (opts.length === 0) return null;
        return (
          <section key={section} className="flex flex-col gap-3">
            <header className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#888894]">
              {section}
            </header>
            <div className="grid grid-cols-1 gap-2">
              {opts.map((opt) => (
                <OptionRow
                  key={opt.id}
                  opt={opt}
                  selectedAttrId={selected[opt.id]}
                  onPick={(attrId) => setOpt(opt.id, attrId)}
                />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

interface RowProps {
  opt: ProductOption;
  selectedAttrId: string | undefined;
  onPick: (attrId: string) => void;
}

function OptionRow({ opt, selectedAttrId, onPick }: RowProps) {
  const attrs = (opt.attributes ?? []).slice().sort((a, b) => a.sort_order - b.sort_order);
  const type = opt.options_type ?? "combo";

  return (
    <div className="grid grid-cols-[minmax(0,9rem)_1fr] items-center gap-3 px-3 py-2 rounded-md bg-white border border-[#ebe8e3]">
      <div className="min-w-0">
        <div className="truncate text-[13px] font-semibold text-[#1e1e24]">
          {opt.title || opt.option_key}
          {opt.required ? <span className="ml-1 text-[#b93232]">*</span> : null}
        </div>
        <div className="truncate font-mono text-[10px] text-[#b4b4bc]">
          {opt.option_key}
        </div>
      </div>
      {type === "radio" || type === "checkbox" ? (
        <SegmentedAttrs attrs={attrs} selectedAttrId={selectedAttrId} onPick={onPick} />
      ) : (
        <SelectAttrs
          required={opt.required}
          attrs={attrs}
          selectedAttrId={selectedAttrId}
          onPick={onPick}
        />
      )}
    </div>
  );
}

function SegmentedAttrs({
  attrs,
  selectedAttrId,
  onPick,
}: {
  attrs: ProductOptionAttribute[];
  selectedAttrId: string | undefined;
  onPick: (attrId: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1 justify-end">
      {attrs.map((a) => {
        const active = selectedAttrId === a.id;
        return (
          <button
            key={a.id}
            type="button"
            onClick={() => onPick(a.id)}
            className={
              "px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-colors " +
              (active
                ? "border-[#1e4d92] bg-[#1e4d92] text-white"
                : "border-[#e9e7e3] bg-[#f9f7f4] text-[#484852] hover:border-[#1e4d92] hover:text-[#1e4d92]")
            }
          >
            {a.title}
          </button>
        );
      })}
    </div>
  );
}

function SelectAttrs({
  required,
  attrs,
  selectedAttrId,
  onPick,
}: {
  required: boolean;
  attrs: ProductOptionAttribute[];
  selectedAttrId: string | undefined;
  onPick: (attrId: string) => void;
}) {
  return (
    <select
      value={selectedAttrId ?? ""}
      onChange={(e) => {
        if (e.target.value) onPick(e.target.value);
      }}
      className="h-8 px-2 text-[12px] border border-[#e9e7e3] rounded-md bg-[#f9f7f4] text-[#1e1e24] font-medium focus:outline-none focus:border-[#1e4d92] min-w-0 max-w-full"
    >
      {!required ? <option value="">—</option> : null}
      {attrs.map((a) => (
        <option key={a.id} value={a.id}>
          {a.title}
        </option>
      ))}
    </select>
  );
}
