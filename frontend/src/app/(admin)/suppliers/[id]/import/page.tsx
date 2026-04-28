"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import type { Supplier } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Category {
  name: string;
  slug: string | null;
  product_count: number | null;
  preview_image_url: string | null;
}

interface ImportCategoryResponse {
  job_id: string;
  status: string;
  category_name: string;
  limit: number;
}

interface SyncJob {
  id: string;
  status: "pending" | "queued" | "running" | "completed" | "failed";
  records_processed: number;
  error_log: string | null;
  started_at: string;
  finished_at: string | null;
}

export default function ImportFromSupplierPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [limit, setLimit] = useState(10);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [job, setJob] = useState<SyncJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [sup, cats] = await Promise.all([
          api<Supplier>(`/api/suppliers/${id}`),
          api<Category[]>(`/api/suppliers/${id}/categories`),
        ]);
        setSupplier(sup);
        setCategories(cats);
        if (cats.length > 0) setSelectedCategory(cats[0].name);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    const interval = setInterval(async () => {
      try {
        const updated = await api<SyncJob>(`/api/sync-jobs/${job.id}`);
        setJob(updated);
      } catch (e) {
        log.error("Job status check failed", e);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [job]);

  const startImport = async () => {
    if (!selectedCategory) {
      setError("Pick a category first");
      return;
    }
    setImporting(true);
    setError(null);
    try {
      const res = await api<ImportCategoryResponse>(
        `/api/suppliers/${id}/import-category`,
        {
          method: "POST",
          body: JSON.stringify({
            category_name: selectedCategory,
            limit,
          }),
        },
      );
      // Seed a job record; polling will overwrite
      setJob({
        id: res.job_id,
        status: res.status as SyncJob["status"],
        records_processed: 0,
        error_log: null,
        started_at: new Date().toISOString(),
        finished_at: null,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setImporting(false);
    }
  };

  if (loading) {
    return <div className="p-6 text-[#888894]">Loading…</div>;
  }

  if (error && categories.length === 0) {
    return (
      <div className="p-6">
        <div className="bg-[#fdf2f2] border border-[#b93232] rounded-lg px-4 py-3 text-sm text-[#b93232]">
          {error}
        </div>
      </div>
    );
  }

  const categoryInfo = categories.find((c) => c.name === selectedCategory);

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-[#888894]">
            <button onClick={() => router.back()} className="hover:underline">
              ← Back to Suppliers
            </button>
          </div>
          <h1 className="text-xl font-bold text-[#1e1e24] mt-1">
            Import from <span className="text-[#1e4d92]">{supplier?.name}</span>
          </h1>
          <p className="text-sm text-[#888894] mt-1">
            Pick a category and number of products to pull into your hub.
          </p>
        </div>
      </div>

      {error && (
        <div className="bg-[#fdf2f2] border border-[#b93232] rounded-lg px-4 py-3 text-sm text-[#b93232]">
          {error}
        </div>
      )}

      <div className="bg-white rounded-[10px] border border-[#cfccc8] shadow-[4px_5px_0_rgba(30,77,146,0.08)] p-5 flex flex-col gap-5 max-w-2xl">
        <div>
          <label className="block text-[11px] font-bold uppercase tracking-[0.1em] text-[#484852] mb-2">
            Category
          </label>
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            disabled={importing || (job !== null && job.status === "running")}
            className="w-full h-10 px-3 text-sm border border-[#cfccc8] rounded bg-white"
          >
            {categories.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
                {c.product_count ? ` (${c.product_count})` : ""}
              </option>
            ))}
          </select>
          {categoryInfo?.preview_image_url && (
            <img
              src={categoryInfo.preview_image_url}
              alt={categoryInfo.name}
              className="mt-3 h-32 w-32 object-cover rounded border border-[#cfccc8]"
            />
          )}
        </div>

        <div>
          <label className="block text-[11px] font-bold uppercase tracking-[0.1em] text-[#484852] mb-2">
            Number of products to import
          </label>
          <Input
            type="number"
            min={1}
            max={500}
            value={limit}
            onChange={(e) => setLimit(parseInt(e.target.value) || 10)}
            disabled={importing || (job !== null && job.status === "running")}
            className="w-32"
          />
          <p className="text-[11px] text-[#888894] mt-1">
            Between 1 and 500. Default 10 for first test.
          </p>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <Button
            onClick={startImport}
            disabled={
              importing ||
              !selectedCategory ||
              (job !== null && (job.status === "queued" || job.status === "running"))
            }
            className="bg-[#1e4d92] hover:bg-[#173d74]"
          >
            {importing ? "Starting…" : "Import"}
          </Button>
          {job && (
            <span className="text-[11px] font-mono text-[#888894]">
              Job {job.id.slice(0, 8)}…
            </span>
          )}
        </div>

        {job && (
          <div className="border-t border-[#ebe8e3] pt-4 flex flex-col gap-2">
            <div className="flex items-center gap-2 text-sm">
              <span className="font-semibold">Status:</span>
              <span
                className={
                  job.status === "completed"
                    ? "text-[#247a52]"
                    : job.status === "failed"
                    ? "text-[#b93232]"
                    : "text-[#1e4d92]"
                }
              >
                {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
              </span>
            </div>
            <div className="text-sm text-[#484852]">
              Records processed: <span className="font-mono">{job.records_processed}</span>
            </div>
            {job.error_log && (
              <div className="text-xs text-[#b93232] font-mono bg-[#fdf2f2] p-2 rounded">
                {job.error_log}
              </div>
            )}
            {job.status === "completed" && (
              <div>
                <Button
                  variant="outline"
                  onClick={() => router.push("/products")}
                  className="mt-2"
                >
                  View Products →
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
