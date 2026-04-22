"use client";

import { useSearch } from "./search-context";
import { countActive, type SortKey } from "@/lib/storefront-url";

const SORT_LABEL: Record<SortKey, string> = {
  name: "Name",
  price_asc: "Price ↑",
  price_desc: "Price ↓",
  newest: "Newest",
};

export function ActiveFilterChips() {
  const { filters, setFilter, clearAll } = useSearch();
  if (countActive(filters) === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 mb-3 text-[11px]">
      {filters.stock === "in" && (
        <Chip label="In stock" onClear={() => setFilter("stock", null)} />
      )}
      {filters.sort !== "name" && (
        <Chip label={`Sort: ${SORT_LABEL[filters.sort]}`} onClear={() => setFilter("sort", "name")} />
      )}
      <button
        onClick={clearAll}
        className="text-[#888894] hover:text-[#1e4d92] font-medium underline underline-offset-2"
      >
        Clear all
      </button>
    </div>
  );
}

function Chip({ label, onClear }: { label: string; onClear: () => void }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-[#eef4fb] text-[#1e4d92] font-semibold">
      {label}
      <button
        aria-label={`Clear ${label}`}
        onClick={onClear}
        className="w-3 h-3 rounded-full text-[#1e4d92] hover:bg-[#d5e2f0] flex items-center justify-center"
      >
        ×
      </button>
    </span>
  );
}
