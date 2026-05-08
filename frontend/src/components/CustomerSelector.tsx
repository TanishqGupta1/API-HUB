"use client";

/**
 * Top-bar customer dropdown. When a customer is picked, downstream
 * pages (Products, Dashboard) can act in that customer's context.
 *
 * Persists across navigation + reload via the customer-context
 * (localStorage-backed).
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, X, Users } from "lucide-react";

import { api } from "@/lib/api";
import { log } from "@/lib/log";
import { useSelectedCustomer } from "@/lib/customer-context";
import type { Customer } from "@/lib/types";

export function CustomerSelector() {
  const { selectedCustomerId, setSelectedCustomer } = useSelectedCustomer();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<Customer[]>("/api/customers")
      .then((cs) => setCustomers(cs.filter((c) => c.is_active)))
      .catch(log.error);
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const selected = useMemo(
    () => customers.find((c) => c.id === selectedCustomerId) ?? null,
    [customers, selectedCustomerId],
  );

  const filtered = customers.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-[12px] font-semibold transition-colors ${
          selected
            ? "bg-[#1e4d92] border-[#1e4d92] text-white"
            : "bg-white border-[#cfccc8] text-[#484852] hover:border-[#1e4d92]"
        }`}
      >
        <Users className="w-3.5 h-3.5" />
        <span>{selected ? selected.name : "Active customer"}</span>
        {selected ? (
          <X
            className="w-3 h-3 opacity-70 hover:opacity-100"
            onClick={(e) => {
              e.stopPropagation();
              setSelectedCustomer(null, null);
              setSearch("");
            }}
          />
        ) : (
          <ChevronDown
            className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`}
          />
        )}
      </button>

      {open && (
        <div className="absolute top-full right-0 mt-2 w-72 bg-white border border-[#cfccc8] rounded-lg shadow-lg z-50 overflow-hidden">
          <div className="p-2 border-b border-[#f2f0ed]">
            <input
              autoFocus
              type="text"
              placeholder="Search customers…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full px-3 py-[6px] text-[12px] bg-[#f9f7f4] border border-[#cfccc8] rounded-md outline-none focus:border-[#1e4d92]"
            />
          </div>

          <div className="overflow-y-auto max-h-[260px]">
            {filtered.length === 0 ? (
              <div className="px-3 py-4 text-[11px] text-[#888894] text-center">
                No customers found
              </div>
            ) : (
              filtered.map((c) => (
                <button
                  key={c.id}
                  onClick={() => {
                    setSelectedCustomer(c.id, c.name);
                    setOpen(false);
                    setSearch("");
                  }}
                  className={`w-full text-left px-3 py-[9px] text-[12px] font-medium flex items-center justify-between transition-colors ${
                    selectedCustomerId === c.id
                      ? "bg-[#eef4fb] text-[#1e4d92] font-bold"
                      : "text-[#1e1e24] hover:bg-[#f9f7f4]"
                  }`}
                >
                  <span className="truncate">{c.name}</span>
                  <span className="font-mono text-[10px] text-[#888894] ml-2 shrink-0">
                    {c.products_pushed ?? 0}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
