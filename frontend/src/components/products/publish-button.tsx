"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Customer } from "@/lib/types";

interface Props {
  productId: string;
  supplierSlug?: string;
  onDone?: () => void;
}

interface PushResponse {
  push_log_id: string;
  status: string;
  dry_run: boolean;
  supplier_sku?: string;
}

export function PublishButton({ productId, supplierSlug, onDone }: Props) {
  const router = useRouter();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "info" | "error" | "success" } | null>(null);

  useEffect(() => {
    api<Customer[]>("/api/customers").then((list) => {
      setCustomers(list);
      const first = list.find((c) => c.is_active);
      if (first) setCustomerId(first.id);
    });
  }, []);

  async function run() {
    if (!customerId) {
      setMessage({ text: "Pick a storefront first", type: "error" });
      return;
    }
    if (!supplierSlug) {
      setMessage({ text: "Supplier not loaded yet — refresh and try again", type: "error" });
      return;
    }
    setBusy(true);
    setMessage({ text: "Submitting push request…", type: "info" });
    try {
      const res = await api<PushResponse>("/api/integrations/admin/push-requests", {
        method: "POST",
        body: JSON.stringify({
          source: { supplier_slug: supplierSlug },
          target: { customer_id: customerId },
          product_ref: { product_id: productId },
          dry_run: false,
        }),
      });
      setMessage({ text: `Push accepted — status: ${res.status}`, type: "success" });
      onDone?.();
      if (res.push_log_id) {
        setTimeout(() => router.push(`/push-log/${res.push_log_id}`), 1500);
      }
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : String(err), type: "error" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        {customers.length > 1 && (
          <select
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            disabled={busy}
            className="text-[12px] border border-[#cfccc8] rounded-md px-2 py-1.5 bg-white text-[#484852] focus:outline-none focus:border-[#1e4d92]"
          >
            {customers.filter((c) => c.is_active).map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        )}
        <button
          type="button"
          onClick={run}
          disabled={busy || !customerId}
          className="px-5 py-2 rounded-lg bg-[#1e4d92] text-white text-[13px] font-bold hover:bg-[#163f78] disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm active:scale-[0.98]"
        >
          {busy ? "Pushing…" : "Publish to OPS"}
        </button>
      </div>
      {message && (
        <div className={`text-[12px] font-mono px-3 py-2 rounded-md border ${
          message.type === "error" ? "bg-[#fdf2f2] text-[#b93232] border-[#f9d7d7]" :
          message.type === "success" ? "bg-[#f2fcf5] text-[#247a52] border-[#c3e6d2]" :
          "bg-[#f9f7f4] text-[#484852] border-[#ebe8e3]"
        }`}>
          {message.text}
        </div>
      )}
    </div>
  );
}
