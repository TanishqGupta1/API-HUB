"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Customer } from "@/lib/types";

interface Props {
  productId: string;
  onDone?: () => void;
}

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
    setMessage({ text: "Dispatching to gateway…", type: "info" });
    try {
      const res = await api<{ status: string; message?: string; push_log_id?: string }>(
        `/api/push/${customerId}/${productId}`,
        { method: "POST" },
      );
      const ok = ["accepted", "processing", "queued", "pushed", "dry_run_pushed"].includes(res.status);
      if (ok) {
        setMessage({ text: res.message || "Push dispatched. Refreshing history in 5s…", type: "success" });
        onDone?.();
      } else {
        setMessage({ text: res.message || `Push ${res.status}.`, type: "error" });
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
