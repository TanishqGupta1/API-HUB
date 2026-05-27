"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { CheckCircle2, XCircle, Loader2, Layers, X, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import type { Customer } from "@/lib/types";

// ── Types ─────────────────────────────────────────────────────────────────────

interface BatchPushItem {
  customer_id: string;
  customer_name: string;
  push_log_id: string | null;
  status: string;
  error?: string | null;
}

interface BatchPushResponse {
  batch_id: string;
  total: number;
  items: BatchPushItem[];
}

interface PushStatusPoll {
  push_log_id: string;
  status: string;
  ops_product_id?: string | null;
  error?: string | null;
  finished_at?: string | null;
}

type ItemState = BatchPushItem & {
  ops_product_id?: string | null;
  polling: boolean;
};

const TERMINAL = new Set([
  "pushed", "failed", "partial_failure", "rejected", "canceled", "dry_run_pushed", "error"
]);

function isTerminal(s: string) { return TERMINAL.has(s); }

function StatusIcon({ status, polling }: { status: string; polling: boolean }) {
  if (polling && !isTerminal(status)) {
    return <Loader2 className="w-4 h-4 animate-spin text-[#1e4d92]" />;
  }
  if (status === "pushed" || status === "dry_run_pushed") {
    return <CheckCircle2 className="w-4 h-4 text-emerald-600" />;
  }
  if (status === "partial_failure") {
    return <AlertTriangle className="w-4 h-4 text-amber-500" />;
  }
  if (isTerminal(status)) {
    return <XCircle className="w-4 h-4 text-red-500" />;
  }
  return <Loader2 className="w-4 h-4 animate-spin text-[#888894]" />;
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    accepted:        "Queued",
    queued:          "Queued",
    processing:      "Pushing…",
    pushed:          "Pushed",
    dry_run_pushed:  "Dry run OK",
    partial_failure: "Partial",
    failed:          "Failed",
    rejected:        "Rejected",
    canceled:        "Canceled",
    error:           "Error",
  };
  return map[status] ?? status;
}

// ── Main component ─────────────────────────────────────────────────────────────

interface Props {
  productId: string;
  supplierSlug?: string;
  supplierSku?: string;
  onClose: () => void;
}

export function BatchPushModal({ productId, supplierSlug, supplierSku, onClose }: Props) {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loadingCustomers, setLoadingCustomers] = useState(true);
  const [phase, setPhase] = useState<"select" | "running" | "done">("select");
  const [items, setItems] = useState<ItemState[]>([]);
  const [pushing, setPushing] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    api<Customer[]>("/api/customers")
      .then((data) => {
        const active = data.filter((c) => c.is_active);
        setCustomers(active);
        setSelected(new Set(active.map((c) => c.id)));
      })
      .catch(() => toast.error("Failed to load storefronts"))
      .finally(() => setLoadingCustomers(false));
  }, []);

  // Poll in-flight items
  useEffect(() => {
    if (phase !== "running") return;

    pollRef.current = setInterval(async () => {
      setItems((prev) => {
        const inFlight = prev.filter((i) => i.push_log_id && !isTerminal(i.status));
        if (inFlight.length === 0) {
          clearInterval(pollRef.current!);
          setPhase("done");
        }
        return prev;
      });

      // Fetch status for each in-flight item
      setItems((prev) => {
        const inFlight = prev.filter((i) => i.push_log_id && !isTerminal(i.status));
        inFlight.forEach(async (item) => {
          try {
            const poll = await api<PushStatusPoll>(
              `/api/integrations/admin/push-requests/${item.push_log_id}`
            );
            setItems((cur) =>
              cur.map((i) =>
                i.push_log_id === item.push_log_id
                  ? { ...i, status: poll.status, ops_product_id: poll.ops_product_id, error: poll.error }
                  : i
              )
            );
          } catch {
            // keep polling, transient error
          }
        });
        return prev;
      });
    }, 2000);

    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [phase]);

  async function handlePush() {
    if (selected.size === 0) return;
    setPushing(true);
    try {
      const res = await api<BatchPushResponse>("/api/integrations/admin/batch-push-requests", {
        method: "POST",
        body: JSON.stringify({
          product_id: productId,
          supplier_slug: supplierSlug,
          supplier_sku: supplierSku,
          customer_ids: Array.from(selected),
          dry_run: false,
        }),
      });

      setItems(
        res.items.map((i) => ({
          ...i,
          polling: !!i.push_log_id && !isTerminal(i.status),
        }))
      );
      setPhase("running");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Push failed";
      toast.error(msg);
    } finally {
      setPushing(false);
    }
  }

  const allDone = phase === "done" || (phase === "running" && items.every((i) => isTerminal(i.status)));
  const successCount = items.filter((i) => i.status === "pushed" || i.status === "dry_run_pushed").length;
  const failCount = items.filter((i) => isTerminal(i.status) && i.status !== "pushed" && i.status !== "dry_run_pushed").length;

  return (
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden animate-in slide-in-from-bottom-4 duration-300">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-[#f2f0ed]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#1e4d92]/10 flex items-center justify-center">
              <Layers className="w-5 h-5 text-[#1e4d92]" />
            </div>
            <div>
              <h2 className="text-base font-black text-[#1e1e24] tracking-tight">Push to All Storefronts</h2>
              <p className="text-[11px] text-[#888894] font-medium">Select storefronts and push simultaneously</p>
            </div>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-lg hover:bg-[#f2f0ed] flex items-center justify-center text-[#888894] transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 max-h-[60vh] overflow-y-auto">

          {/* Storefront selection phase */}
          {phase === "select" && (
            <>
              {loadingCustomers ? (
                <div className="flex items-center justify-center py-10">
                  <Loader2 className="w-6 h-6 animate-spin text-[#1e4d92]" />
                </div>
              ) : customers.length === 0 ? (
                <p className="text-sm text-[#888894] text-center py-8">No active storefronts found.</p>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[11px] font-black uppercase tracking-widest text-[#888894]">
                      {customers.length} Active Storefronts
                    </span>
                    <button
                      className="text-[11px] font-bold text-[#1e4d92] hover:underline"
                      onClick={() =>
                        selected.size === customers.length
                          ? setSelected(new Set())
                          : setSelected(new Set(customers.map((c) => c.id)))
                      }
                    >
                      {selected.size === customers.length ? "Deselect all" : "Select all"}
                    </button>
                  </div>
                  {customers.map((c) => (
                    <label
                      key={c.id}
                      className="flex items-center gap-3 p-3 rounded-xl border border-[#f2f0ed] hover:border-[#cfccc8] cursor-pointer transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={selected.has(c.id)}
                        onChange={(e) => {
                          const next = new Set(selected);
                          e.target.checked ? next.add(c.id) : next.delete(c.id);
                          setSelected(next);
                        }}
                        className="w-4 h-4 rounded accent-[#1e4d92]"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-bold text-[#1e1e24] truncate">{c.name}</div>
                        <div className="text-[10px] text-[#888894] font-mono truncate">{c.ops_base_url}</div>
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </>
          )}

          {/* Progress phase */}
          {(phase === "running" || phase === "done") && (
            <div className="space-y-2">
              {allDone && (
                <div className={`rounded-xl px-4 py-3 mb-4 text-sm font-bold flex items-center gap-2 ${
                  failCount === 0
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "bg-amber-50 text-amber-700 border border-amber-200"
                }`}>
                  {failCount === 0
                    ? <><CheckCircle2 className="w-4 h-4" /> All {successCount} pushes succeeded</>
                    : <><AlertTriangle className="w-4 h-4" /> {successCount} succeeded, {failCount} failed</>
                  }
                </div>
              )}
              {items.map((item) => (
                <div key={item.customer_id} className="flex items-center gap-3 p-3 rounded-xl border border-[#f2f0ed]">
                  <StatusIcon status={item.status} polling={!isTerminal(item.status)} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-bold text-[#1e1e24] truncate">{item.customer_name}</div>
                    {item.ops_product_id && (
                      <div className="text-[10px] font-mono text-[#888894]">OPS ID: {item.ops_product_id}</div>
                    )}
                    {item.error && (
                      <div className="text-[10px] text-red-500 truncate">{item.error}</div>
                    )}
                  </div>
                  <span className={`text-[10px] font-black uppercase tracking-wider shrink-0 ${
                    item.status === "pushed" || item.status === "dry_run_pushed"
                      ? "text-emerald-600"
                      : isTerminal(item.status)
                      ? "text-red-500"
                      : "text-[#888894]"
                  }`}>
                    {statusLabel(item.status)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[#f2f0ed] flex items-center justify-between gap-3">
          {phase === "select" ? (
            <>
              <Button variant="outline" onClick={onClose} className="border-[#cfccc8] text-[#888894]">
                Cancel
              </Button>
              <Button
                onClick={handlePush}
                disabled={pushing || selected.size === 0}
                className="bg-[#1e4d92] hover:bg-[#173d74] text-white font-black text-xs uppercase tracking-wider px-6"
              >
                {pushing ? (
                  <><Loader2 className="w-3.5 h-3.5 animate-spin mr-2" /> Starting…</>
                ) : (
                  <><Layers className="w-3.5 h-3.5 mr-2" /> Push to {selected.size} Storefront{selected.size !== 1 ? "s" : ""}</>
                )}
              </Button>
            </>
          ) : (
            <Button
              onClick={onClose}
              disabled={!allDone}
              className="ml-auto bg-[#1e4d92] hover:bg-[#173d74] text-white font-black text-xs uppercase tracking-wider px-6"
            >
              {allDone ? "Done" : <><Loader2 className="w-3.5 h-3.5 animate-spin mr-2" /> Pushing…</>}
            </Button>
          )}
        </div>

      </div>
    </div>
  );
}
