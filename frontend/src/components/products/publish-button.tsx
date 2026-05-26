"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Send } from "lucide-react";
import { api } from "@/lib/api";
import { useSelectedCustomer } from "@/lib/customer-context";
import type { Customer } from "@/lib/types";

interface Props {
  productId: string;
  supplierSlug?: string;
  onDone?: () => void;
}

export function PublishButton({ productId, supplierSlug, onDone }: Props) {
  const router = useRouter();
  const { selectedCustomerId } = useSelectedCustomer();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState<string>("");

  useEffect(() => {
    api<Customer[]>("/api/customers").then((list) => {
      const active = list.filter((c) => c.is_active);
      setCustomers(active);
      // Prefer the globally selected customer; fall back to first active
      const preferred = active.find((c) => c.id === selectedCustomerId) ?? active[0];
      if (preferred) setCustomerId(preferred.id);
    });
  }, [selectedCustomerId]);

  function go() {
    if (!customerId) return;
    const params = new URLSearchParams({ customer_id: customerId });
    if (supplierSlug) params.set("supplier_slug", supplierSlug);
    onDone?.();
    router.push(`/products/${productId}/push?${params}`);
  }

  return (
    <div className="flex items-center gap-3">
      {customers.length > 1 && (
        <select
          value={customerId}
          onChange={(e) => setCustomerId(e.target.value)}
          className="text-[12px] border border-[#cfccc8] rounded-md px-2 py-1.5 bg-white text-[#484852] focus:outline-none focus:border-[#1e4d92]"
        >
          {customers.filter((c) => c.is_active).map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      )}
      <button
        type="button"
        onClick={go}
        disabled={!customerId}
        className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-[#1e4d92] text-white text-[13px] font-bold uppercase tracking-wide whitespace-nowrap hover:bg-[#163f78] disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-[0_3px_0_#143566] active:shadow-none active:translate-y-px"
      >
        <Send className="w-4 h-4" />
        Publish to OPS
      </button>
    </div>
  );
}
