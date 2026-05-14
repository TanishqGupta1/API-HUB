"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import type { SupplierCategoryBrowse, ImportCategoryResponse, SyncJob } from "@/lib/types";
import { toast } from "sonner";
import { Download, Loader2, CheckCircle2, AlertCircle, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  supplierId: string;
  value: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
  onSyncComplete?: () => void;
}

/** SanMar-specific mapping panel — category default + image opts + sync status. */
const DEFAULT_IMPORT_LIMIT = 50;
const MIN_IMPORT_LIMIT = 1;
const MAX_IMPORT_LIMIT = 500;

export function SanMarMappingPanel({ supplierId, value, onChange, onSyncComplete }: Props) {
  const [categories, setCategories] = useState<SupplierCategoryBrowse[]>([]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [activeJob, setActiveJob] = useState<SyncJob | null>(null);
  const [importLimit, setImportLimit] = useState<number>(DEFAULT_IMPORT_LIMIT);
  // Track which category was just imported so the completion toast can name it.
  // (SyncJob row doesn't carry the category name, so we keep it client-side.)
  const lastImportedCategoryRef = useRef<string | null>(null);

  // 1. Initial Load
  useEffect(() => {
    (async () => {
      try {
        const cats = await api<SupplierCategoryBrowse[]>(
          `/api/suppliers/${supplierId}/categories`,
        );
        setCategories(cats);
      } catch {
        /* OK */
      } finally {
        setLoading(false);
      }
    })();
  }, [supplierId]);

  // 2. Polling for Active Job
  const pollFailures = useRef(0);
  useEffect(() => {
    if (!activeJob || activeJob.status === "completed" || activeJob.status === "failed") {
      pollFailures.current = 0;
      return;
    }

    const interval = setInterval(async () => {
      try {
        const updated = await api<SyncJob>(`/api/sync-jobs/${activeJob.id}`);
        pollFailures.current = 0;
        setActiveJob(updated);
        if (updated.status === "completed" || updated.status === "failed") {
          // Fire completion toast with real counts (uses backend
          // records_processed — the source of truth).
          const cat = lastImportedCategoryRef.current ?? "category";
          if (updated.status === "completed") {
            const count = updated.records_processed ?? 0;
            toast.success(
              count > 0
                ? `Imported ${count} product${count === 1 ? "" : "s"} from ${cat}`
                : `Import finished for ${cat} — 0 new products (the catalog returned no rows)`,
            );
          } else {
            toast.error(
              updated.error_log
                ? `Import failed for ${cat}: ${updated.error_log.slice(0, 120)}`
                : `Import failed for ${cat}`,
            );
          }
          if (onSyncComplete) onSyncComplete();
        }
      } catch (e: any) {
        pollFailures.current += 1;
        log.error("Polling error", e);
        // Stop polling if the job no longer exists (404) or after 5 consecutive failures
        if (e?.status === 404 || pollFailures.current >= 5) {
          setActiveJob((prev) => prev ? { ...prev, status: "failed", error_log: "Job not found or API unreachable. Refresh to check." } : null);
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [activeJob?.id, activeJob?.status]);

  const defaultCategory = value["sanmar.default_category"] || "";
  const includeImages = value["sanmar.include_images"] === "true";

  const handleImportCategory = async () => {
    if (!defaultCategory) {
      toast.error("Please select a category first");
      return;
    }
    // Clamp limit defensively — backend also validates (1..500) but a clear
    // client-side error is friendlier than a 422.
    const limit = Math.max(
      MIN_IMPORT_LIMIT,
      Math.min(MAX_IMPORT_LIMIT, Math.floor(importLimit) || DEFAULT_IMPORT_LIMIT),
    );
    setImporting(true);
    lastImportedCategoryRef.current = defaultCategory;
    try {
      const res = await api<ImportCategoryResponse>(`/api/suppliers/${supplierId}/import-category`, {
        method: "POST",
        body: JSON.stringify({
          category_name: defaultCategory,
          limit,
          fetch_images: includeImages,
        }),
      });
      
      // Set initial job state to start polling
      setActiveJob({
        id: res.job_id,
        status: "running",
        records_processed: 0,
        total_products: 0,
        success_count: 0,
        failed_count: 0,
        discovery_mode: null,
        supplier_id: supplierId,
        supplier_name: "SanMar",
        job_type: "full",
        started_at: new Date().toISOString(),
        completed_at: null,
        error_log: null,
      });

      toast.success(
        `Import started — fetching up to ${limit} products from ${defaultCategory}`,
      );
    } catch (e) {
      toast.error(`Failed to start import for ${defaultCategory}`);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-[#f2f0ed] p-10 flex flex-col gap-10">
      <div>
        <div className="flex items-center gap-3 mb-2">
           <div className="w-1.5 h-1.5 rounded-full bg-[#1e4d92]" />
           <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-[#1e1e24]">
             Protocol Configuration
           </h3>
        </div>
        <p className="text-sm text-[#888894] font-medium leading-relaxed max-w-2xl">
          Manage specialized PromoStandards extensions for this node, including bulk category synchronization and media asset injection.
        </p>
      </div>

      <div className="space-y-6">
        <div>
          <label className="block text-[10px] font-black uppercase tracking-widest text-[#484852] mb-3">
            Default Sync Category
          </label>
          <div className="flex gap-4">
            <select
              value={defaultCategory}
              onChange={(e) =>
                onChange({ ...value, "sanmar.default_category": e.target.value })
              }
              className="flex-1 h-11 px-4 text-sm font-bold border border-[#f2f0ed] rounded-xl bg-[#f9f7f4]/30 outline-none focus:border-[#1e4d92] focus:ring-4 focus:ring-blue-50 transition-all appearance-none cursor-pointer"
              disabled={loading || (activeJob?.status === "running")}
            >
              <option value="">— Choose per import —</option>
              {categories.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name} {c.product_count ? `(${c.product_count})` : ""}
                </option>
              ))}
            </select>
            <div className="flex flex-col">
              <input
                type="number"
                value={importLimit}
                onChange={(e) => setImportLimit(Number(e.target.value))}
                min={MIN_IMPORT_LIMIT}
                max={MAX_IMPORT_LIMIT}
                step={10}
                disabled={importing || (activeJob?.status === "running")}
                title={`How many products to import (max ${MAX_IMPORT_LIMIT}). SanMar returns the first N items of the category — no pagination yet.`}
                className="w-24 h-11 px-3 text-sm font-bold text-center border border-[#f2f0ed] rounded-xl bg-[#f9f7f4]/30 outline-none focus:border-[#1e4d92] focus:ring-4 focus:ring-blue-50 transition-all disabled:opacity-50"
              />
              <span className="text-[9px] font-bold uppercase tracking-widest text-[#888894] text-center mt-1">
                limit
              </span>
            </div>
            <Button
              onClick={handleImportCategory}
              disabled={importing || !defaultCategory || (activeJob?.status === "running")}
              className="px-8 h-11 bg-[#1e4d92] hover:bg-[#173d74] text-white rounded-xl font-black text-[10px] uppercase tracking-wider flex items-center gap-3 shadow-lg shadow-blue-900/10 transition-all disabled:opacity-50"
            >
              {importing || activeJob?.status === "running" ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )}
              Initialize Import
            </Button>
          </div>
          <p className="text-[11px] text-[#888894] mt-2">
            SanMar returns the first <span className="font-mono font-bold">N</span> products of the chosen category.
            Re-importing the same category fetches the same N rows again (no pagination yet) —
            increase <span className="font-mono font-bold">limit</span> here to pull more in one go (max {MAX_IMPORT_LIMIT}).
          </p>
        </div>

        {activeJob && (
          <div className="bg-[#f9f7f4] border border-[#f2f0ed] rounded-2xl p-6 animate-in fade-in slide-in-from-top-2 duration-500">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${activeJob.status === "running" ? "bg-blue-500 animate-pulse" : activeJob.status === "completed" ? "bg-emerald-500" : "bg-rose-500"}`} />
                <span className="text-[11px] font-black text-[#1e1e24] uppercase tracking-widest">
                  {activeJob.status}
                </span>
              </div>
              <span className="text-[10px] font-mono font-bold text-[#cfccc8]">NODE_SESSION: {activeJob.id.slice(0, 8)}</span>
            </div>
            
            <div className="flex items-center justify-between">
              <div className="text-sm font-medium text-[#888894]">
                <span className="font-black text-[#1e4d92] mr-1">{activeJob.records_processed}</span>
                records synchronized
              </div>
              {activeJob.completed_at && (
                <div className="text-[10px] font-bold text-[#cfccc8] uppercase tracking-wider flex items-center gap-2">
                  <Clock className="w-3.5 h-3.5" />
                  {new Date(activeJob.completed_at).toLocaleTimeString()}
                </div>
              )}
            </div>

            {activeJob.error_log && (
              <div className="mt-4 p-4 bg-rose-50 border border-rose-100 rounded-xl text-[11px] text-rose-600 font-mono whitespace-pre-wrap leading-relaxed">
                {activeJob.error_log}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="pt-2 border-t border-[#f2f0ed]">
        <label className="flex items-center gap-2 text-sm cursor-pointer group">
          <input
            type="checkbox"
            checked={includeImages}
            onChange={(e) =>
              onChange({
                ...value,
                "sanmar.include_images": e.target.checked ? "true" : "false",
              })
            }
            className="w-4 h-4 rounded border-[#cfccc8] text-[#1e4d92] focus:ring-[#1e4d92]"
          />
          <span className="group-hover:text-[#1e4d92] transition-colors font-medium">Fetch images from Media Content service during import</span>
        </label>
        <p className="text-[11px] text-[#888894] mt-1 ml-6">
          Adds an extra SOAP call per product but populates image_url + variant
          image arrays from SanMar&apos;s Media service.
        </p>
      </div>
    </div>
  );
}
