"use client";

import { useEffect, useState } from "react";
import type { Category } from "@/lib/types";
import { LeftRail } from "./left-rail";

interface Props {
  categories: Category[];
  counts: Record<string, number>;
}

export function MobileFilterSheet({ categories, counts }: Props) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="md:hidden fixed bottom-5 right-5 z-40 h-14 px-5 rounded-full bg-[#1e4d92] text-white
                   text-[13px] font-semibold shadow-[4px_6px_0_rgba(30,77,146,0.2)]"
        aria-label="Open category filter"
      >
        Filter
      </button>
      {open && (
        <div
          className="md:hidden fixed inset-0 z-50 bg-black/40"
          onClick={() => setOpen(false)}
          role="dialog" aria-modal="true"
        >
          <div
            className="absolute inset-x-0 bottom-0 bg-white rounded-t-[16px] max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-4 h-12 border-b border-[#cfccc8]">
              <span className="text-[12px] font-bold uppercase tracking-[0.1em]">Filter</span>
              <button onClick={() => setOpen(false)} className="text-[#484852]" aria-label="Close">
                ✕
              </button>
            </div>
            <div className="overflow-y-auto flex-1">
              <LeftRail categories={categories} counts={counts} />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
