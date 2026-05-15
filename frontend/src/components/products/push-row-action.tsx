"use client";

import { useEffect, useState } from "react";
import { Send, Store, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
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

type MessageType = "info" | "error" | "success";

// Terminal status set — push log enters one of these and stops moving.
// Mirrors push-status.ts TERMINAL_STATUSES (kept inline to keep T21 PR
// from depending on T4's status-map PR).
const TERMINAL_STATUSES = new Set([
  "pushed",
  "failed",
  "partial_failure",
  "rejected",
  "canceled",
  "dry_run_pushed",
]);

// Poll cadence — 1.5s × 30 attempts = 45s max wait before "still running".
const POLL_INTERVAL_MS = 1500;
const POLL_MAX_ATTEMPTS = 30;

interface PushAccepted {
  push_log_id: string;
  status: string;
  dry_run: boolean;
  callback_status: string;
}

interface PushStatus {
  push_log_id: string;
  status: string;
  ops_product_id: string | null;
  error: string | null;
}

interface ProductDetail {
  supplier_id: string;
  supplier_sku: string;
}

interface SupplierListItem {
  id: string;
  slug: string;
}

export function PushRowAction({ productId, productName }: Props) {
  const [open, setOpen] = useState(false);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [supplierSlug, setSupplierSlug] = useState("");
  const [supplierSku, setSupplierSku] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: MessageType } | null>(null);

  useEffect(() => {
    if (!open) return;
    setMessage(null);
    Promise.all([
      api<Customer[]>("/api/customers"),
      api<ProductDetail>(`/api/products/${productId}`),
      api<SupplierListItem[]>("/api/suppliers"),
    ])
      .then(([custs, product, suppliers]) => {
        setCustomers(custs);
        const first = custs.find((c) => c.is_active);
        if (first) setCustomerId(first.id);
        setSupplierSku(product.supplier_sku);
        const supplier = suppliers.find((s) => s.id === product.supplier_id);
        setSupplierSlug(supplier?.slug ?? "");
      })
      .catch((e) =>
        setMessage({ text: e instanceof Error ? e.message : String(e), type: "error" })
      );
  }, [open, productId]);

  async function run() {
    if (!customerId) {
      setMessage({ text: "Pick a storefront first", type: "error" });
      return;
    }
    if (!supplierSlug || !supplierSku) {
      setMessage({ text: "Product supplier info still loading — try again", type: "error" });
      return;
    }
    setBusy(true);
    setMessage({ text: "Submitting push request…", type: "info" });
    try {
      // POST to admin proxy — JWT-authed, no orchestrator key needed.
      // Idempotency key = product + customer + timestamp so accidental
      // double-clicks don't double-push.
      const idempotencyKey = `ui-${productId}-${customerId}-${Date.now()}`;
      const accepted = await api<PushAccepted>(
        "/api/integrations/admin/push-requests",
        {
          method: "POST",
          headers: { "Idempotency-Key": idempotencyKey },
          body: JSON.stringify({
            target: { system: "ops", customer_id: customerId },
            source: { supplier_slug: supplierSlug },
            product_ref: { supplier_sku: supplierSku },
            dry_run: false,
          }),
        },
      );
      setMessage({
        text: `Push queued (${accepted.push_log_id.slice(0, 8)}…) — polling for status…`,
        type: "info",
      });

      // Poll until terminal status or max attempts reached.
      const terminal = await pollUntilTerminal(accepted.push_log_id);
      if (terminal.status === "pushed") {
        setMessage({
          text: `Pushed to OPS as products_id=${terminal.ops_product_id ?? "?"}`,
          type: "success",
        });
        setTimeout(() => setOpen(false), 2400);
      } else if (terminal.status === "dry_run_pushed") {
        setMessage({ text: "Dry-run completed (no OPS writes)", type: "success" });
        setTimeout(() => setOpen(false), 2400);
      } else if (terminal.status === "still_running") {
        setMessage({
          text: "Still running — check Push Log for final status.",
          type: "info",
        });
      } else {
        setMessage({
          text: `Push ${terminal.status}: ${terminal.error ?? "see Push Log for details"}`,
          type: "error",
        });
      }
    } catch (e) {
      setMessage({
        text: e instanceof Error ? e.message : String(e),
        type: "error",
      });
    } finally {
      setBusy(false);
    }
  }

  /** Poll the status endpoint until terminal or timeout. Returns the last
   *  status seen, with a special `still_running` marker if max attempts hit. */
  async function pollUntilTerminal(pushLogId: string): Promise<PushStatus & { status: string }> {
    for (let attempt = 0; attempt < POLL_MAX_ATTEMPTS; attempt++) {
      const status = await api<PushStatus>(
        `/api/integrations/admin/push-requests/${pushLogId}`,
      );
      if (TERMINAL_STATUSES.has(status.status)) return status;
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    }
    return {
      push_log_id: pushLogId,
      status: "still_running",
      ops_product_id: null,
      error: null,
    };
  }

  const selectedCustomer = customers.find((c) => c.id === customerId);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          size="sm"
          variant="outline"
          className="h-8 gap-1.5 border-[#cfccc8] text-[#1e4d92] hover:bg-[#f2f0ed] hover:border-[#1e4d92] hover:text-[#163f78] transition-all font-semibold text-[12px]"
          onClick={(e) => e.stopPropagation()}
        >
          <Send className="h-3.5 w-3.5" />
          Push to OPS
        </Button>
      </DialogTrigger>
      <DialogContent
        className="max-w-md bg-white border-[#cfccc8] shadow-[8px_10px_0_rgba(30,77,146,0.12)] p-0 gap-0 overflow-hidden"
        onClick={(e: React.MouseEvent) => e.stopPropagation()}
      >
        {/* Header */}
        <DialogHeader className="px-6 pt-6 pb-4 bg-gradient-to-br from-[#f9f7f4] to-white border-b border-[#ebe8e3]">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-[#1e4d92] text-white shadow-sm">
              <Send className="h-5 w-5" />
            </div>
            <div className="flex flex-col text-left">
              <DialogTitle className="text-[16px] font-extrabold text-[#1e1e24] tracking-tight">
                Push to OPS
              </DialogTitle>
              <span className="text-[11px] font-mono uppercase tracking-[0.08em] text-[#888894] mt-0.5">
                Publish product to storefront
              </span>
            </div>
          </div>
        </DialogHeader>

        {/* Body */}
        <div className="px-6 py-5 flex flex-col gap-4">
          {/* Product summary */}
          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-[#888894]">
              Product
            </span>
            <span className="text-[14px] font-bold text-[#1e1e24] leading-tight">
              {productName}
            </span>
          </div>

          {/* Storefront picker */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="push-storefront"
              className="text-[10px] font-bold uppercase tracking-[0.12em] text-[#888894] flex items-center gap-1.5"
            >
              <Store className="h-3 w-3" />
              Storefront
            </label>
            <div className="relative">
              <select
                id="push-storefront"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                className="w-full h-10 px-3 pr-9 text-[13px] font-mono border-[1.5px] border-[#cfccc8] rounded-lg bg-white text-[#1e1e24] focus:border-[#1e4d92] focus:outline-none focus:ring-2 focus:ring-[#1e4d92]/10 transition-colors appearance-none cursor-pointer"
              >
                <option value="">Select storefront…</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id} disabled={!c.is_active}>
                    {c.name} {c.is_active ? "" : "(inactive)"}
                  </option>
                ))}
              </select>
              <svg
                className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#888894] pointer-events-none"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
            {selectedCustomer && (
              <span className="text-[11px] font-mono text-[#888894] mt-0.5 truncate">
                → {selectedCustomer.ops_base_url}
              </span>
            )}
          </div>

          {/* Status message */}
          {message && (
            <div
              className={`flex items-start gap-2 text-[12px] px-3 py-2.5 rounded-lg border ${
                message.type === "error"
                  ? "bg-[#fdf2f2] text-[#b93232] border-[#f9d7d7]"
                  : message.type === "success"
                    ? "bg-[#f2fcf5] text-[#247a52] border-[#c3e6d2]"
                    : "bg-[#f9f7f4] text-[#484852] border-[#ebe8e3]"
              }`}
            >
              {message.type === "error" ? (
                <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              ) : message.type === "success" ? (
                <CheckCircle2 className="h-4 w-4 flex-shrink-0 mt-0.5" />
              ) : (
                <Loader2 className="h-4 w-4 flex-shrink-0 mt-0.5 animate-spin" />
              )}
              <span>{message.text}</span>
            </div>
          )}
        </div>

        <DialogFooter className="px-6 py-4 border-t border-[#ebe8e3] bg-[#fafaf9]">
          <Button
            variant="ghost"
            onClick={() => setOpen(false)}
            className="text-[#484852] hover:text-[#1e1e24]"
          >
            Cancel
          </Button>
          <Button
            onClick={run}
            disabled={busy || !customerId}
            className="bg-[#1e4d92] hover:bg-[#163f78] text-white gap-1.5 font-bold"
          >
            {busy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Pushing…
              </>
            ) : (
              <>
                <Send className="h-4 w-4" />
                Push
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
