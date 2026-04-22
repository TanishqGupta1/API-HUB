"use client";

import type { ProductOption } from "@/lib/types";

export function ProductOptions({ options }: { options: ProductOption[] | undefined | null }) {
  const list = (options ?? [])
    .slice()
    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.title.localeCompare(b.title));

  if (list.length === 0) return null;

  return (
    <div className="pt-5 border-t border-dashed border-[#cfccc8]">
      <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#888894] mb-3">
        Options
      </div>

      <div className="flex flex-col gap-3">
        {list.map((opt) => {
          const attrs = (opt.attributes ?? [])
            .slice()
            .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.title.localeCompare(b.title));

          return (
            <div
              key={opt.id}
              className="rounded-[10px] border border-[#e9e7e3] bg-white px-4 py-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-[14px] font-semibold text-[#1e1e24]">
                    {opt.title}
                  </div>
                  <div className="mt-1 font-mono text-[11px] text-[#888894]">
                    {opt.option_key}
                    {opt.options_type ? ` · ${opt.options_type}` : ""}
                  </div>
                </div>
                {opt.required ? (
                  <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[#fff7e0] text-[#c17c00]">
                    required
                  </span>
                ) : null}
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                {attrs.length ? (
                  attrs.map((a) => (
                    <span
                      key={a.id}
                      className="px-2.5 py-1 rounded-full text-[11px] font-semibold border border-[#e9e7e3] bg-[#f9f7f4] text-[#1e1e24]"
                    >
                      {a.title}
                    </span>
                  ))
                ) : (
                  <span className="text-[12px] text-[#888894]">No values</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

