"use client";

import Link from "next/link";
import { useSearch } from "./search-context";

export function TopBar() {
  const { query, setQuery } = useSearch();

  return (
    <header className="sticky top-0 z-30 h-[60px] bg-white border-b border-[#cfccc8] flex items-center px-6 gap-6">
      <Link href="/storefront/vg" className="flex items-center gap-3 shrink-0">
        <span className="w-7 h-7 rounded-md bg-[#1e4d92] text-white font-mono text-[12px] font-bold flex items-center justify-center">
          VG
        </span>
        <span className="text-[15px] font-extrabold text-[#1e1e24] tracking-[-0.02em]">
          Visual Graphics
        </span>
      </Link>

      <div className="flex-1 max-w-[480px]">
        <div className="relative">
          <svg
            className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#b4b4bc] pointer-events-none"
            viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search products…"
            className="w-full pl-10 pr-4 py-2 bg-[#f9f7f4] border border-[#cfccc8] rounded-md
                       text-[13px] outline-none transition-all
                       focus:border-[#1e4d92] focus:bg-white focus:shadow-[0_0_0_3px_#eef4fb]"
          />
        </div>
      </div>

      <div className="ml-auto shrink-0">
        <Link
          href="/"
          className="text-[12px] font-semibold text-[#484852] hover:text-[#1e4d92]"
        >
          ← Admin
        </Link>
      </div>
    </header>
  );
}
