"use client";

import { useEffect, useRef, useState } from "react";
import { useSearch } from "./search-context";
import { countActive, type SortKey } from "@/lib/storefront-url";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "name", label: "Name (A→Z)" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "newest", label: "Newest" },
];

export function FilterButton() {
  const { filters, setFilter } = useSearch();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const active = countActive(filters);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div ref={ref} className="relative inline-block">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md border border-[#cfccc8]
                   bg-white text-[12px] font-semibold text-[#1e1e24] hover:border-[#1e4d92]"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
          <line x1="4" y1="6" x2="20" y2="6" />
          <line x1="7" y1="12" x2="17" y2="12" />
          <line x1="10" y1="18" x2="14" y2="18" />
        </svg>
        Filter
        {active > 0 && (
          <span className="ml-1 w-5 h-5 rounded-full bg-[#1e4d92] text-white text-[10px] font-bold flex items-center justify-center">
            {active}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-[280px] z-40 bg-white border border-[#cfccc8] rounded-md shadow-lg p-4">
          <label className="flex items-center gap-2 text-[12px] font-medium text-[#1e1e24] cursor-pointer">
            <input
              type="checkbox"
              checked={filters.stock === "in"}
              onChange={(e) => setFilter("stock", e.target.checked ? "in" : null)}
              className="w-3.5 h-3.5 accent-[#1e4d92]"
            />
            In stock only
          </label>

          <div className="mt-4 pt-3 border-t border-[#ebe8e3]">
            <div className="text-[10px] font-bold uppercase tracking-widest text-[#888894] mb-2">
              Sort
            </div>
            <div className="flex flex-col gap-1.5">
              {SORT_OPTIONS.map((o) => (
                <label key={o.value} className="flex items-center gap-2 text-[12px] cursor-pointer">
                  <input
                    type="radio"
                    name="sort"
                    checked={filters.sort === o.value}
                    onChange={() => setFilter("sort", o.value)}
                    className="w-3.5 h-3.5 accent-[#1e4d92]"
                  />
                  {o.label}
                </label>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
