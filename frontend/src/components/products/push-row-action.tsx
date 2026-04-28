"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Customer } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface Props {
  productId: string;
  productName: string;
}

export function PushRowAction({ productId, productName }: Props) {
  const [open, setOpen] = useState(false);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    api<Customer[]>("/api/customers")
      .then((list) => {
        setCustomers(list);
        const first = list.find((c) => c.is_active);
        if (first) setCustomerId(first.id);
      })
      .catch((e) => setMessage(e instanceof Error ? e.message : String(e)));
  }, [open]);

  async function run() {
    if (!customerId) {
      setMessage("Pick a storefront first");
      return;
    }
    setBusy(true);
    setMessage("Triggering push…");
    try {
      const res = await api<{ triggered: boolean }>(
        `/api/n8n/workflows/vg-ops-push-001/trigger?product_id=${productId}&customer_id=${customerId}`,
        { method: "POST" },
      );
      setMessage(res.triggered ? "Push started. Check history." : "Push failed.");
      if (res.triggered) setTimeout(() => setOpen(false), 1500);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          size="sm"
          variant="outline"
          className="border-[#1e4d92] text-[#1e4d92]"
          onClick={(e) => e.stopPropagation()}
        >
          Push to OPS
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md" onClick={(e) => e.stopPropagation()}>
        <DialogHeader>
          <DialogTitle>Push to OPS</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3 py-2">
          <div className="text-sm text-[#484852]">{productName}</div>
          <select
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            className="h-9 px-3 text-sm border border-[#cfccc8] rounded bg-white"
          >
            <option value="">Select Storefront…</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id} disabled={!c.is_active}>
                {c.name}
                {c.is_active ? "" : " (inactive)"}
              </option>
            ))}
          </select>
          {message && (
            <div className="text-xs font-mono px-3 py-2 rounded bg-[#f9f7f4] text-[#484852] border border-[#ebe8e3]">
              {message}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={run}
            disabled={busy || !customerId}
            className="bg-[#1e4d92] hover:bg-[#173d74]"
          >
            {busy ? "Pushing…" : "Push"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
