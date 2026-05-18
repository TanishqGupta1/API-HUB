"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { log } from "@/lib/log";
import { isInFlight } from "@/lib/push-status";
import type { Customer, CustomerProductSelection, SelectionStatus } from "@/lib/types";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Package,
  Search,
  Trash2,
} from "lucide-react";
import { SelectionBadge } from "@/components/SelectionBadge";

type StatusFilter = "all" | SelectionStatus;

// Filter options shown in the catalog header. We intentionally keep this
// list short — the broadened SelectionStatus union (T22) covers in-flight
// states too, but admins filter by the *outcome*, not the in-flight detail.
const STATUS_FILTER_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "selected", label: "Selected" },
  { value: "pushed", label: "Pushed" },
  { value: "stale", label: "Stale" },
  { value: "failed", label: "Failed" },
  { value: "partial_failure", label: "Partial" },
];

// 8-4-4-4-12 hex UUID — guards against the literal `{customer_id}`
// placeholder accidentally hit during routing experimentation.
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function CustomerCatalogPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const supplierId = searchParams.get("supplier_id");
  const isValidId = typeof id === "string" && UUID_RE.test(id);

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [selections, setSelections] = useState<CustomerProductSelection[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  useEffect(() => {
    if (!id) return;
    if (!isValidId) {
      // Don't fetch — the URL contains a literal placeholder or junk.
      // Render the "invalid id" empty state below instead.
      setLoading(false);
      return;
    }
    setLoading(true);
    const url = `/api/customers/${id}/selections${supplierId ? `?supplier_id=${supplierId}` : ""}`;

    Promise.all([
      api<Customer>(`/api/customers/${id}`),
      api<CustomerProductSelection[]>(url),
    ])
      .then(([cust, sels]) => {
        setCustomer(cust);
        setSelections(sels);
      })
      .catch((err) => {
        log.error("Failed to fetch selections", err);
        toast.error(err.message || "Failed to load customer catalog");
      })
      .finally(() => setLoading(false));
  }, [id, isValidId, supplierId]);

  if (!isValidId) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-16">
        <div className="border-2 border-dashed border-[#cfccc8] rounded-2xl p-10 text-center">
          <Package className="w-10 h-10 text-[#b4b4bc] mx-auto mb-3" />
          <div className="text-[16px] font-bold text-[#1e1e24]">
            Invalid customer id
          </div>
          <p className="text-[13px] text-[#888894] mt-2">
            The URL contains <code className="font-mono text-[12px]">{String(id)}</code>{" "}
            which is not a valid UUID. Pick a customer from{" "}
            <Link href="/customers" className="text-[#1e4d92] font-semibold hover:underline">
              /customers
            </Link>{" "}
            to navigate to its catalog.
          </p>
        </div>
      </div>
    );
  }

  const filtered = useMemo(() => {
    return selections.filter((s) => {
      if (statusFilter !== "all" && s.status !== statusFilter) return false;
      if (
        search &&
        !s.product_name.toLowerCase().includes(search.toLowerCase()) &&
        !s.supplier_sku.toLowerCase().includes(search.toLowerCase())
      ) {
        return false;
      }
      return true;
    });
  }, [selections, search, statusFilter]);

  const counts = useMemo(() => {
    const c: Partial<Record<SelectionStatus, number>> = {
      selected: 0,
      accepted: 0,
      processing: 0,
      pushed: 0,
      stale: 0,
      failed: 0,
      partial_failure: 0,
      rejected: 0,
      dry_run_pushed: 0,
    };
    for (const s of selections) {
      if (c[s.status] !== undefined) c[s.status]! += 1;
    }
    return c;
  }, [selections]);

  const needsDecorationCount = useMemo(
    () => selections.filter((s) => s.supplier_has_decoration_overlay && !s.decoration_ready).length,
    [selections],
  );

  const handlePush = async (e: React.MouseEvent, productId: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!id) return;
    try {
      await api(`/api/push/${id}/${productId}`, { method: "POST" });
      // Optimistic — backend writes status="accepted" first (gateway pipeline),
      // then BackgroundTasks flips it to "pushed"/"failed"/"partial_failure".
      // Show "accepted" so the button gates correctly and the badge updates;
      // a refresh or push-history fetch will reveal the terminal state.
      setSelections((prev) =>
        prev.map((s) =>
          s.product_id === productId
            ? { ...s, status: "accepted", pushed_at: new Date().toISOString() }
            : s,
        ),
      );
      toast.success("Push queued — gateway will deliver to OPS.");
    } catch (err: unknown) {
      const rawMsg = err instanceof Error ? err.message : "Push failed";
      log.error("Failed to push product", err);

      // If the gateway returned a structured PREFLIGHT_BLOCKER envelope,
      // show a human-readable summary instead of dumping the JSON.
      try {
        const env = JSON.parse(rawMsg);
        if (env?.code === "PREFLIGHT_BLOCKER" && Array.isArray(env?.details?.checks)) {
          const failed = env.details.checks.filter((c: { ok: boolean }) => c && !c.ok);
          const names = failed
            .map((c: { name: string }) => c.name.replace(/_/g, " "))
            .join(", ");
          toast.error(`Push blocked by ${failed.length} preflight checks: ${names}`, {
            description: "Open the Push Log or product preview for full details.",
            duration: 6000,
          });
          return;
        }
      } catch {
        // not JSON — fall through to raw message
      }
      toast.error(rawMsg);
    }
  };

  const handleRemove = async (e: React.MouseEvent, productId: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!id) return;
    if (!confirm("Remove this product from the customer's catalog?")) return;
    try {
      await api(`/api/customers/${id}/selections/${productId}`, { method: "DELETE" });
      setSelections((prev) => prev.filter((s) => s.product_id !== productId));
      toast.success("Removed from catalog");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Remove failed";
      log.error("Failed to remove selection", err);
      toast.error(msg);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8 pb-6 border-b-2 border-[#1e1e24]">
        <Link
          href={`/customers/${id}`}
          className="flex items-center gap-1.5 text-[12px] font-semibold text-[#888894] hover:text-[#1e4d92] transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back
        </Link>
        <div className="h-4 w-px bg-[#cfccc8]" />
        <div>
          <div className="text-[28px] font-extrabold tracking-tight leading-none text-[#1e1e24]">
            Customer Catalog
          </div>
          {customer && (
            <p className="text-[13px] text-[#888894] mt-1">{customer.name}</p>
          )}
        </div>

        {needsDecorationCount > 0 && (
          <div className="ml-auto flex items-center gap-2 px-4 py-2 bg-yellow-50 border border-yellow-300 rounded-lg">
            <AlertTriangle className="w-4 h-4 text-yellow-600" />
            <span className="text-[12px] font-bold text-yellow-800">
              {needsDecorationCount} product{needsDecorationCount > 1 ? "s" : ""} need decoration
            </span>
          </div>
        )}
      </div>

      {/* Status filter pills */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {STATUS_FILTER_OPTIONS.map((opt) => {
          const isActive = statusFilter === opt.value;
          const count =
            opt.value === "all"
              ? selections.length
              : (counts[opt.value as SelectionStatus] ?? 0);
          return (
            <button
              key={opt.value}
              onClick={() => setStatusFilter(opt.value)}
              className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-[12px] font-semibold transition-colors ${
                isActive
                  ? "bg-[#1e4d92] border-[#1e4d92] text-white"
                  : "bg-white border-[#cfccc8] text-[#484852] hover:border-[#1e4d92]"
              }`}
            >
              {opt.label}
              <span
                className={`font-mono text-[10px] px-1.5 rounded ${
                  isActive ? "bg-white/20" : "bg-[#f2f0ed] text-[#888894]"
                }`}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-4 mb-6">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#b4b4bc]" />
          <input
            type="text"
            placeholder="Search by name or SKU…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 h-10 bg-white border border-[#cfccc8] rounded-lg text-[13px] text-[#1e1e24] placeholder:text-[#b4b4bc] outline-none focus:border-[#1e4d92] transition-colors"
          />
        </div>
        <div className="text-[11px] font-mono text-[#888894]">
          {filtered.length} / {selections.length} products
          {supplierId && " (Filtered by Supplier)"}
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 animate-pulse">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="h-48 bg-white border border-[#f2f0ed] rounded-xl" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="py-20 text-center border-2 border-dashed border-[#cfccc8] rounded-2xl">
          <Package className="w-10 h-10 text-[#b4b4bc] mx-auto mb-3" />
          <div className="text-[15px] font-bold text-[#1e1e24]">
            {selections.length === 0 ? "No products selected yet" : "No products match"}
          </div>
          <p className="text-[12px] text-[#888894] mt-1">
            {selections.length === 0 ? (
              <>
                Browse{" "}
                <Link
                  href="/products"
                  className="text-[#1e4d92] font-semibold hover:underline"
                >
                  /products
                </Link>{" "}
                and add some to this customer&apos;s catalog.
              </>
            ) : (
              "Try a different search or status filter."
            )}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((s) => {
            const needsDecoration = s.supplier_has_decoration_overlay && !s.decoration_ready;
            const isPushable = !needsDecoration;
            const showPushUpdate =
              s.status === "stale" || s.status === "failed" || s.status === "partial_failure";
            const pushInFlight = isInFlight(s.status);
            const alreadyPushed = s.status === "pushed";

            return (
              <div
                key={s.id}
                className="group flex flex-col bg-white border border-[#cfccc8] rounded-xl overflow-hidden shadow-sm hover:border-[#1e4d92] hover:shadow-md transition-all relative"
              >
                <Link href={`/storefront/vg/product/${s.product_id}`} className="block flex-1">
                  {/* Image */}
                  <div className="aspect-square bg-[#f2f0ed] relative overflow-hidden">
                    {s.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={s.image_url}
                        alt={s.product_name}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Package className="w-10 h-10 text-[#cfccc8]" />
                      </div>
                    )}

                    {/* Status badge (top-left) */}
                    <div className="absolute top-2 left-2 flex flex-col gap-1">
                      <SelectionBadge status={s.status} />
                      {needsDecoration && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-yellow-100 border border-yellow-300 px-2 py-0.5 text-[10px] font-bold text-yellow-800">
                          <AlertTriangle className="w-3 h-3" />
                          Needs Decoration
                        </span>
                      )}
                      {s.supplier_has_decoration_overlay && s.decoration_ready && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 border border-emerald-300 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                          <CheckCircle2 className="w-3 h-3" />
                          Decorated
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Info */}
                  <div className="p-3 flex flex-col gap-1">
                    <p className="text-[12px] font-bold text-[#1e1e24] leading-snug line-clamp-2">
                      {s.product_name}
                    </p>
                    <div className="flex items-center gap-2 mt-auto pt-2">
                      <span className="font-mono text-[10px] text-[#888894]">{s.supplier_sku}</span>
                      <span className="ml-auto text-[10px] font-semibold uppercase tracking-wide text-[#888894] bg-[#f2f0ed] px-1.5 py-0.5 rounded">
                        {s.product_type}
                      </span>
                    </div>
                  </div>
                </Link>

                {/* Actions */}
                <div className="p-3 pt-0 mt-auto border-t border-[#f2f0ed] flex items-center justify-between gap-2">
                  <button
                    onClick={(e) => handleRemove(e, s.product_id)}
                    title="Remove from customer catalog"
                    className="inline-flex items-center gap-1 text-[10px] font-semibold text-[#888894] hover:text-[#b93232] transition-colors"
                  >
                    <Trash2 className="w-3 h-3" />
                    Remove
                  </button>
                  {isPushable && (
                    <button
                      onClick={(e) => handlePush(e, s.product_id)}
                      disabled={alreadyPushed || pushInFlight}
                      className="text-[10px] font-bold bg-[#1e1e24] text-white px-3 py-1.5 rounded hover:bg-[#383842] disabled:bg-[#b4b4bc] disabled:cursor-not-allowed transition-colors"
                    >
                      {alreadyPushed
                        ? "Pushed"
                        : pushInFlight
                          ? "Pushing…"
                          : showPushUpdate
                            ? "Push Update"
                            : "Push to OPS"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
