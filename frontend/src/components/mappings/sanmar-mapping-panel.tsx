"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
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
export function SanMarMappingPanel({ supplierId, value, onChange, onSyncComplete }: Props) {
  const [categories, setCategories] = useState<SupplierCategoryBrowse[]>([]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [activeJob, setActiveJob] = useState<SyncJob | null>(null);

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
  useEffect(() => {
    if (!activeJob || activeJob.status === "completed" || activeJob.status === "failed") return;

    const interval = setInterval(async () => {
      try {
        const updated = await api<SyncJob>(`/api/sync-jobs/${activeJob.id}`);
        setActiveJob(updated);
        if (updated.status === "completed" && onSyncComplete) {
          onSyncComplete();
        }
      } catch (e) {
        console.error("Polling error", e);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [activeJob]);

  const defaultCategory = value["sanmar.default_category"] || "";
  const includeImages = value["sanmar.include_images"] === "true";

  const handleImportCategory = async () => {
    if (!defaultCategory) {
      toast.error("Please select a category first");
      return;
    }
    setImporting(true);
    try {
      const res = await api<ImportCategoryResponse>(`/api/suppliers/${supplierId}/import-category`, {
        method: "POST",
        body: JSON.stringify({
          category_name: defaultCategory,
          limit: 10,
        }),
      });
      
      // Set initial job state to start polling
      setActiveJob({
        id: res.job_id,
        status: "running",
        records_processed: 0,
        supplier_id: supplierId,
        supplier_name: "SanMar",
        job_type: "full", // approximation
        started_at: new Date().toISOString(),
        finished_at: null,
        error_log: null
      });

      toast.success(`Import started for ${defaultCategory}`);
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
              {activeJob.finished_at && (
                <div className="text-[10px] font-bold text-[#cfccc8] uppercase tracking-wider flex items-center gap-2">
                  <Clock className="w-3.5 h-3.5" />
                  {new Date(activeJob.finished_at).toLocaleTimeString()}
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
