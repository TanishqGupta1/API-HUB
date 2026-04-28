"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Customer } from "@/lib/types";

interface Props {
  productId: string;
  onDone?: () => void;
}

const N8N_URL = process.env.NEXT_PUBLIC_N8N_URL ?? "http://localhost:5678";
const PUSH_WORKFLOW_ID = process.env.NEXT_PUBLIC_PUSH_WORKFLOW_ID ?? "vg-ops-push-001";

export function PublishButton({ productId, onDone }: Props) {
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
    setBusy(true);
    setMessage({ text: "Triggering push workflow...", type: "info" });
    try {
      // Fires the single-product push path via n8n proxy
      const res = await api<{ triggered: boolean }>(
        `/api/n8n/workflows/${PUSH_WORKFLOW_ID}/trigger?product_id=${productId}&customer_id=${customerId}`,
        { method: "POST" },
      );
      if (res.triggered) {
        setMessage({ text: "Push started. Refreshing history in 5s...", type: "success" });
        onDone?.();
      } else {
        setMessage({ text: "Push request failed.", type: "error" });
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
        <select
          value={customerId}
          onChange={(e) => setCustomerId(e.target.value)}
          className="px-3 py-2 border-[1.5px] border-[#cfccc8] rounded-lg text-[13px] bg-white focus:border-[#1e4d92] outline-none font-mono transition-colors"
        >
          <option value="">Select Storefront…</option>
          {customers.map((c) => (
            <option key={c.id} value={c.id} disabled={!c.is_active}>
              {c.name} {c.is_active ? "" : "(inactive)"}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={run}
          disabled={busy || !customerId}
          className="px-5 py-2 rounded-lg bg-[#1e4d92] text-white text-[13px] font-bold hover:bg-[#163f78] disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm active:scale-[0.98]"
        >
          {busy ? "Pushing…" : "Publish to OPS"}
        </button>
        <a
          href={`${N8N_URL}/workflow/${PUSH_WORKFLOW_ID}`}
          target="_blank" rel="noopener noreferrer"
          className="text-[11px] font-bold text-[#888894] hover:text-[#1e4d92] flex items-center transition-colors ml-2"
        >
          Monitor in n8n <span className="ml-1">↗</span>
        </a>
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
