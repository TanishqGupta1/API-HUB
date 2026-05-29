"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Supplier, SyncJob } from "@/lib/types";
import { toast } from "sonner";
import {
  ArrowRight,
  Clock,
  Download,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react";

interface Props {
  supplier: Supplier;
}

const PRODUCT_FIELDS: { key: string; note: string }[] = [
  { key: "uuid",         note: "Unique product identifier" },
  { key: "id",           note: "Integer product ID" },
  { key: "name",         note: "Product title / name" },
  { key: "description",  note: "Full product description" },
  { key: "brand",        note: "Brand or manufacturer" },
  { key: "category",     note: "Product category string" },
  { key: "imageUrl",     note: "Primary product image URL" },
  { key: "thumbnailUrl", note: "Thumbnail image URL" },
];

const VARIANT_FIELDS: { key: string; note: string }[] = [
  { key: "partId",      note: "Variant / part identifier" },
  { key: "paperType",   note: "Paper stock type" },
  { key: "coating",     note: "Coating finish" },
  { key: "fold",        note: "Fold style" },
  { key: "paperWeight", note: "Paper weight (gsm / lb)" },
  { key: "finish",      note: "Surface finish" },
  { key: "color",       note: "Color (apparel)" },
  { key: "size",        note: "Size (apparel)" },
];

const CANONICAL_OPTIONS: { value: string; label: string; badge?: string }[] = [
  { value: "",             label: "— skip —" },
  { value: "supplier_sku", label: "supplier_sku", badge: "required" },
  { value: "product_name", label: "product_name" },
  { value: "brand",        label: "brand" },
  { value: "description",  label: "description" },
  { value: "product_type", label: "product_type" },
  { value: "image_url",    label: "image_url" },
  { value: "color",        label: "color",  badge: "variant" },
  { value: "size",         label: "size",   badge: "variant" },
];

const DEFAULT_MAPPING: Record<string, string> = {
  uuid:        "supplier_sku",
  name:        "product_name",
  description: "description",
  brand:       "brand",
  category:    "product_type",
  imageUrl:    "image_url",
};

export function FourOverMappingPanel({ supplier }: Props) {
  const savedMapping = (supplier.field_mappings as Record<string, unknown> | null)?.mapping;
  const initialMapping =
    savedMapping && typeof savedMapping === "object" && !Array.isArray(savedMapping)
      ? (savedMapping as Record<string, string>)
      : DEFAULT_MAPPING;

  const [mapping, setMapping] = useState<Record<string, string>>(initialMapping);

  // Custom source fields the user added manually
  const knownKeys = new Set([
    ...PRODUCT_FIELDS.map((f) => f.key),
    ...VARIANT_FIELDS.map((f) => f.key),
  ]);
  const [customFields, setCustomFields] = useState<string[]>(() =>
    Object.keys(initialMapping).filter((k) => !knownKeys.has(k))
  );
  const [newField, setNewField] = useState("");
  const [saving, setSaving] = useState(false);

  // Import job
  const [importing, setImporting] = useState(false);
  const [importLimit, setImportLimit] = useState(20);
  const [activeJob, setActiveJob] = useState<SyncJob | null>(null);
  const pollFailures = useRef(0);

  // Poll active job
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
        if (updated.status === "completed") {
          toast.success(`Imported ${updated.records_processed ?? 0} products from 4Over`);
        } else if (updated.status === "failed") {
          toast.error(
            `Import failed: ${updated.error_log?.slice(0, 120) ?? "unknown error"}`
          );
        }
      } catch (e: unknown) {
        pollFailures.current += 1;
        const status = (e as { status?: number })?.status;
        if (status === 404 || pollFailures.current >= 5) {
          setActiveJob((prev) =>
            prev ? { ...prev, status: "failed", error_log: "Job not found or API unreachable." } : null
          );
        }
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [activeJob?.id, activeJob?.status]);

  const setField = (key: string, val: string) =>
    setMapping((prev) => ({ ...prev, [key]: val }));

  const addCustomField = () => {
    const key = newField.trim();
    if (!key || knownKeys.has(key) || customFields.includes(key)) return;
    setCustomFields((prev) => [...prev, key]);
    setNewField("");
  };

  const removeCustomField = (key: string) => {
    setCustomFields((prev) => prev.filter((k) => k !== key));
    setMapping((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api(`/api/suppliers/${supplier.id}/mappings`, {
        method: "PUT",
        body: JSON.stringify({ mapping }),
      });
      toast.success("Field mappings saved");
    } catch {
      toast.error("Failed to save mappings");
    } finally {
      setSaving(false);
    }
  };

  const handleImport = async () => {
    setImporting(true);
    try {
      const res = await api<{ sync_job_id: string }>(`/api/suppliers/${supplier.id}/import`, {
        method: "POST",
        body: JSON.stringify({ limit: importLimit }),
      });
      setActiveJob({
        id: res.sync_job_id,
        status: "running",
        records_processed: 0,
        total_products: 0,
        success_count: 0,
        failed_count: 0,
        discovery_mode: null,
        supplier_id: supplier.id,
        supplier_name: supplier.name,
        job_type: "full",
        started_at: new Date().toISOString(),
        completed_at: null,
        error_log: null,
      });
      toast.success(`Import started — fetching up to ${importLimit} products`);
    } catch {
      toast.error("Failed to start import — check credentials and adapter_class");
    } finally {
      setImporting(false);
    }
  };

  const mappedCount = Object.values(mapping).filter(Boolean).length;
  const hasSku = Object.values(mapping).includes("supplier_sku");

  return (
    <div className="bg-white rounded-2xl border border-[#f2f0ed] p-10 flex flex-col gap-10">

      {/* ── Section header ── */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <div className="w-1.5 h-1.5 rounded-full bg-[#1e4d92]" />
          <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-[#1e1e24]">
            Field Mapping — REST + HMAC
          </h3>
        </div>
        <p className="text-sm text-[#888894] font-medium leading-relaxed max-w-2xl">
          Map 4Over JSON fields to the canonical hub schema.{" "}
          <span className="font-mono font-bold text-[#1e1e24]">supplier_sku</span> is
          required — everything else is optional. Unmapped variant fields (paperType,
          coating, etc.) are kept in the attributes dict automatically.
        </p>
      </div>

      {/* ── Mapping table ── */}
      <div>
        <div className="flex items-center justify-between mb-5">
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-[#484852]">
            Source → Canonical
          </span>
          <div className="flex items-center gap-3">
            {!hasSku && (
              <span className="text-[10px] font-bold text-[#b93232] bg-[#fdf2f2] px-2 py-0.5 rounded-full">
                supplier_sku not mapped
              </span>
            )}
            <span className="text-[10px] font-bold text-[#888894]">
              {mappedCount} field{mappedCount !== 1 ? "s" : ""} mapped
            </span>
          </div>
        </div>

        {/* Product-level */}
        <FieldGroup label="Product-level fields">
          {PRODUCT_FIELDS.map((f) => (
            <MappingRow
              key={f.key}
              sourceKey={f.key}
              note={f.note}
              value={mapping[f.key] ?? ""}
              onChange={(v) => setField(f.key, v)}
            />
          ))}
        </FieldGroup>

        {/* Variant-level */}
        <FieldGroup label="Variant-level fields">
          {VARIANT_FIELDS.map((f) => (
            <MappingRow
              key={f.key}
              sourceKey={f.key}
              note={f.note}
              value={mapping[f.key] ?? ""}
              onChange={(v) => setField(f.key, v)}
            />
          ))}
        </FieldGroup>

        {/* Custom fields */}
        {customFields.length > 0 && (
          <FieldGroup label="Custom fields">
            {customFields.map((key) => (
              <div key={key} className="flex items-center gap-2">
                <div className="flex-1">
                  <MappingRow
                    sourceKey={key}
                    note="Custom"
                    value={mapping[key] ?? ""}
                    onChange={(v) => setField(key, v)}
                  />
                </div>
                <button
                  onClick={() => removeCustomField(key)}
                  className="shrink-0 w-8 h-10 rounded-xl border border-[#cfccc8] flex items-center justify-center text-[#888894] hover:text-[#b93232] hover:border-[#b93232] transition-all"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </FieldGroup>
        )}

        {/* Add custom field row */}
        <div className="flex items-center gap-2 mt-2">
          <input
            type="text"
            placeholder="Add custom source field name…"
            value={newField}
            onChange={(e) => setNewField(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addCustomField()}
            className="flex-1 h-9 px-3 text-[12px] font-mono border border-dashed border-[#cfccc8] rounded-xl bg-[#f9f7f4]/50 outline-none focus:border-[#1e4d92] focus:ring-4 focus:ring-blue-50 transition-all placeholder:text-[#cfccc8]"
          />
          <button
            onClick={addCustomField}
            disabled={!newField.trim()}
            className="h-9 px-4 rounded-xl border border-[#cfccc8] text-[#1e4d92] font-bold text-[10px] uppercase tracking-wider hover:border-[#1e4d92] hover:bg-blue-50 disabled:opacity-40 transition-all flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            Add
          </button>
        </div>

        {/* Save mappings */}
        <div className="flex justify-end mt-6 pt-5 border-t border-[#f2f0ed]">
          <button
            onClick={handleSave}
            disabled={saving}
            className="h-10 px-8 bg-[#1e4d92] hover:bg-[#173d74] text-white rounded-xl font-black text-[10px] uppercase tracking-wider flex items-center gap-2 shadow-lg shadow-blue-900/10 disabled:opacity-50 transition-all"
          >
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            {saving ? "Saving…" : "Save Mappings"}
          </button>
        </div>
      </div>

      {/* ── Import section ── */}
      <div className="pt-4 border-t border-[#f2f0ed]">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-1.5 h-1.5 rounded-full bg-[#1e4d92]" />
          <h3 className="text-[10px] font-black uppercase tracking-[0.3em] text-[#1e1e24]">
            Import Products
          </h3>
        </div>
        <p className="text-sm text-[#888894] font-medium leading-relaxed mb-5">
          Pull 4Over&apos;s full print catalog into the hub. Credentials must be saved
          on the supplier page and{" "}
          <span className="font-mono font-bold text-[#1e1e24]">adapter_class</span> set
          to <span className="font-mono">FourOverAdapter</span> before importing.
        </p>

        <div className="flex items-center gap-4">
          <div className="flex flex-col items-center">
            <input
              type="number"
              value={importLimit}
              onChange={(e) => setImportLimit(Number(e.target.value))}
              min={1}
              max={500}
              step={10}
              disabled={importing || activeJob?.status === "running"}
              className="w-24 h-11 px-3 text-sm font-bold text-center border border-[#f2f0ed] rounded-xl bg-[#f9f7f4]/30 outline-none focus:border-[#1e4d92] focus:ring-4 focus:ring-blue-50 transition-all disabled:opacity-50"
            />
            <span className="text-[9px] font-bold uppercase tracking-widest text-[#888894] mt-1">
              limit
            </span>
          </div>

          <button
            onClick={handleImport}
            disabled={importing || activeJob?.status === "running"}
            className="px-8 h-11 bg-[#1e4d92] hover:bg-[#173d74] text-white rounded-xl font-black text-[10px] uppercase tracking-wider flex items-center gap-3 shadow-lg shadow-blue-900/10 disabled:opacity-50 transition-all"
          >
            {importing || activeJob?.status === "running" ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            Import Products
          </button>
        </div>

        {/* Job status card */}
        {activeJob && (
          <div className="bg-[#f9f7f4] border border-[#f2f0ed] rounded-2xl p-6 mt-5 animate-in fade-in slide-in-from-top-2 duration-500">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div
                  className={`w-2 h-2 rounded-full ${
                    activeJob.status === "running"
                      ? "bg-blue-500 animate-pulse"
                      : activeJob.status === "completed"
                        ? "bg-emerald-500"
                        : "bg-rose-500"
                  }`}
                />
                <span className="text-[11px] font-black text-[#1e1e24] uppercase tracking-widest">
                  {activeJob.status}
                </span>
              </div>
              <span className="text-[10px] font-mono font-bold text-[#cfccc8]">
                JOB: {activeJob.id.slice(0, 8)}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <div className="text-sm font-medium text-[#888894]">
                <span className="font-black text-[#1e4d92] mr-1">
                  {activeJob.records_processed}
                </span>
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
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function FieldGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-6">
      <div className="text-[9px] font-black uppercase tracking-[0.3em] text-[#888894] mb-3 flex items-center gap-2">
        <span className="w-4 h-px bg-[#cfccc8] inline-block" />
        {label}
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function MappingRow({
  sourceKey,
  note,
  value,
  onChange,
}: {
  sourceKey: string;
  note: string;
  value: string;
  onChange: (val: string) => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 min-w-0 flex items-center gap-2 h-10 px-3 rounded-xl bg-[#f9f7f4] border border-[#f2f0ed]">
        <span className="font-mono text-[12px] font-bold text-[#1e1e24] truncate">
          {sourceKey}
        </span>
        <span className="text-[10px] text-[#cfccc8] truncate hidden sm:inline">{note}</span>
      </div>
      <ArrowRight className="w-3.5 h-3.5 text-[#cfccc8] shrink-0" />
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`w-48 h-10 px-3 text-[12px] font-bold border rounded-xl outline-none focus:ring-4 focus:ring-blue-50 transition-all appearance-none cursor-pointer ${
          value
            ? "border-[#1e4d92] bg-blue-50 text-[#1e4d92]"
            : "border-[#f2f0ed] bg-white text-[#888894]"
        }`}
      >
        {CANONICAL_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.value
              ? `→ ${opt.label}${opt.badge ? ` (${opt.badge})` : ""}`
              : opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
