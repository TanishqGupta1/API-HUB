"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import type { ProductPreview, ProductImage, Supplier } from "@/lib/types";
import { useSelectedCustomer } from "@/lib/customer-context";
import { AlertTriangle, CheckCircle2, ArrowLeft, Send, Package } from "lucide-react";
import { SafeImage as Image } from "@/components/common/safe-image";

const IMAGE_TAB_ORDER = ["front", "back", "swatch", "detail"] as const;

function pickImage(images: ProductImage[], tab: string): string | null {
  return images.find((img) => img.image_type.toLowerCase() === tab)?.url ?? null;
}

export default function ProductPreviewPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { selectedCustomerId } = useSelectedCustomer();

  const [preview, setPreview] = useState<ProductPreview | null>(null);
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>("front");

  useEffect(() => {
    async function load() {
      try {
        const p = await api<ProductPreview>(`/api/products/${id}/preview`);
        setPreview(p);

        // fetch full product just for supplier info
        const full = await api<{ supplier_id: string; supplier_name: string; supplier_slug: string | null }>(
          `/api/products/${id}`
        );
        if (full.supplier_id) {
          const sup = await api<Supplier>(`/api/suppliers/${full.supplier_id}`).catch(() => null);
          setSupplier(sup);
        }
      } catch (e) {
        log.error("preview load failed", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  const imageTabs = useMemo(() => {
    if (!preview) return [];
    const present = new Set(preview.images.map((img) => img.image_type.toLowerCase()));
    return IMAGE_TAB_ORDER.map((key) => ({ key, available: present.has(key) }));
  }, [preview]);

  const activeImage = useMemo(() => {
    if (!preview) return null;
    return pickImage(preview.images, activeTab) ?? preview.images[0]?.url ?? null;
  }, [preview, activeTab]);

  function handlePush() {
    const params = new URLSearchParams();
    if (selectedCustomerId) params.set("customer_id", selectedCustomerId);
    if (supplier?.slug) params.set("supplier_slug", supplier.slug);
    router.push(`/products/${id}/push?${params}`);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-[#888894] text-[14px]">
        <div className="text-center">
          <div className="font-mono text-[12px] mb-2">LOADING_PREVIEW</div>
          Fetching product data…
        </div>
      </div>
    );
  }

  if (!preview) {
    return (
      <div className="flex items-center justify-center py-20 text-[#b93232] text-[14px] font-semibold">
        Product not found or backend is offline.
      </div>
    );
  }

  // Collapse per-variant missing field noise into summary counts
  const inventoryMissing = preview.missing_fields.filter((f) => f.startsWith("inventory")).length;
  const priceMissing = preview.missing_fields.filter((f) => f.startsWith("price")).length;
  const otherMissing = preview.missing_fields.filter(
    (f) => !f.startsWith("inventory") && !f.startsWith("price")
  );
  const summaryFields = [
    ...otherMissing,
    ...(priceMissing > 0 ? [`price missing on ${priceMissing} variant${priceMissing !== 1 ? "s" : ""}`] : []),
    ...(inventoryMissing > 0 ? [`inventory missing on ${inventoryMissing} variant${inventoryMissing !== 1 ? "s" : ""}`] : []),
  ];
  const isReady = summaryFields.length === 0;

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">

      {/* ── Back + header ── */}
      <div className="mb-6">
        <button
          onClick={() => router.push(`/products/${id}`)}
          className="flex items-center gap-1.5 text-[13px] text-[#888894] hover:text-[#1e4d92] transition-colors mb-4 font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Product
        </button>

        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold border border-[#cfccc8] text-[#484852] bg-white">
                <Package className="w-3 h-3" />
                {supplier?.name ?? "Supplier Product"}
              </span>
            </div>
            <h1 className="text-[28px] font-extrabold text-[#1e1e24] tracking-tight leading-tight">
              {preview.title}
            </h1>
            <p className="text-[13px] text-[#888894] mt-1 font-mono">
              {preview.brand && <span className="text-[#484852] font-semibold not-italic font-sans mr-2">{preview.brand}</span>}
              {preview.category && <span className="mr-2">{preview.category}</span>}
              · {preview.variants.length} variants
            </p>
          </div>

        </div>
      </div>

      {/* ── Status banner ── */}
      {isReady ? (
        <div className="mb-6 bg-[#f0f9f4] border-2 border-[#247a52] rounded-xl px-5 py-3 flex items-center gap-3">
          <CheckCircle2 className="w-5 h-5 text-[#247a52] shrink-0" />
          <div>
            <div className="text-[13px] font-bold text-[#1a5c3a]">Ready to push</div>
            <div className="text-[12px] text-[#247a52]/80 mt-0.5">
              All product fields are present. Click <span className="font-semibold">Push to OPS</span> to send this product to your storefront.
            </div>
          </div>
        </div>
      ) : (
        <div className="mb-6 bg-[#fffbf0] border border-[#e8c840] rounded-xl px-5 py-3 flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-[#b8860b] shrink-0 mt-0.5" />
          <div>
            <div className="text-[12px] font-semibold text-[#7a6000] mb-1.5">
              {summaryFields.length} field{summaryFields.length !== 1 ? "s" : ""} incomplete — push may be blocked
            </div>
            <ul className="flex flex-wrap gap-x-5 gap-y-0.5">
              {summaryFields.map((f) => (
                <li key={f} className="text-[11px] text-[#8a7000] font-mono">· {f}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* ── Two-column: image + stats ── */}
      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6 mb-8">

        {/* Image viewer */}
        <div>
          <div className="relative bg-[#ebe8e3] border border-[#cfccc8] rounded-xl h-[280px] flex items-center justify-center overflow-hidden shadow-[3px_4px_0_rgba(30,77,146,0.08)]">
            {activeImage ? (
              <Image
                src={activeImage}
                alt={`${preview.title} ${activeTab}`}
                fill
                sizes="300px"
                className="object-contain p-4"
              />
            ) : (
              <div className="text-center">
                <div className="text-[10px] uppercase text-[#b4b4bc] tracking-[0.1em] font-bold">No image</div>
                <div className="text-[9px] text-[#b4b4bc] mt-1">Run media sync to fetch images</div>
              </div>
            )}
            <div className="absolute bottom-2 right-2 text-[9px] bg-black/40 text-white px-2 py-0.5 rounded-full font-mono">
              {activeTab.toUpperCase()}
            </div>
          </div>

          {/* Image tabs */}
          <div className="grid grid-cols-4 gap-1.5 mt-2">
            {imageTabs.map(({ key, available }) => (
              <button
                key={key}
                type="button"
                onClick={() => available && setActiveTab(key)}
                disabled={!available}
                className={`h-[44px] flex items-center justify-center rounded-lg border text-[9px] font-bold uppercase tracking-widest transition-all
                  ${activeTab === key
                    ? "border-[#1e4d92] bg-[#eef4fb] text-[#1e4d92]"
                    : available
                      ? "border-[#cfccc8] bg-[#ebe8e3] text-[#484852] hover:border-[#1e4d92] cursor-pointer"
                      : "border-[#cfccc8] bg-[#ebe8e3] text-[#cfccc8] cursor-not-allowed opacity-50"
                  }`}
              >
                {key}
              </button>
            ))}
          </div>
        </div>

        {/* Stats + description */}
        <div className="flex flex-col gap-4">
          {/* Stat cards */}
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Brand", value: preview.brand || "—", blue: true },
              { label: "Category", value: preview.category || "—", blue: false },
              { label: "Variants", value: String(preview.variants.length), mono: true },
              {
                label: "Base Price",
                value: preview.variants[0]?.price != null
                  ? `$${preview.variants[0].price.toFixed(2)}`
                  : "—",
                mono: true,
              },
            ].map(({ label, value, blue, mono }) => (
              <div
                key={label}
                className="bg-white border border-[#cfccc8] rounded-lg p-3 shadow-[2px_3px_0_rgba(30,77,146,0.06)]"
              >
                <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#888894] mb-0.5">{label}</div>
                <div className={`text-[15px] font-bold ${blue ? "text-[#1e4d92]" : "text-[#1e1e24]"} ${mono ? "font-mono" : ""}`}>
                  {value}
                </div>
              </div>
            ))}
          </div>

          {/* Description */}
          {preview.description && (
            <div className="bg-white border border-[#cfccc8] rounded-lg p-4 text-[13px] text-[#484852] leading-relaxed flex-1 overflow-auto max-h-[160px]">
              {preview.description}
            </div>
          )}
        </div>
      </div>

      {/* ── Variants table ── */}
      <div className="bg-white border border-[#cfccc8] rounded-xl overflow-hidden shadow-[3px_4px_0_rgba(30,77,146,0.08)] mb-8">
        <div className="px-5 py-3 bg-[#ebe8e3] border-b border-[#cfccc8] flex items-center justify-between">
          <div className="text-[13px] font-bold uppercase tracking-[0.06em] text-[#1e1e24]">
            Variants
          </div>
          <span className="font-mono text-[11px] text-[#888894]">{preview.variants.length} total</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse min-w-[500px]">
            <thead>
              <tr>
                {["Color", "Size", "SKU", "Price", "Inventory"].map((h) => (
                  <th
                    key={h}
                    className="text-left px-5 py-2.5 text-[10px] font-bold uppercase tracking-[0.1em] text-[#888894] border-b border-[#cfccc8]"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.variants.map((v, i) => (
                <tr key={i} className="hover:bg-[rgba(30,77,146,0.04)] transition-colors">
                  <td className="px-5 py-3 text-[13px] font-semibold text-[#1e1e24] border-b border-[#f9f7f4]">
                    {v.color || "—"}
                  </td>
                  <td className="px-5 py-3 text-[13px] text-[#484852] border-b border-[#f9f7f4]">
                    {v.size || "—"}
                  </td>
                  <td className="px-5 py-3 font-mono text-[11px] text-[#484852] border-b border-[#f9f7f4]">
                    {v.sku || <span className="text-[#b93232]">missing</span>}
                  </td>
                  <td className="px-5 py-3 font-mono text-[12px] border-b border-[#f9f7f4]">
                    {v.price != null
                      ? <span className="text-[#1e1e24]">${v.price.toFixed(2)}</span>
                      : <span className="text-[#b93232]">missing</span>
                    }
                  </td>
                  <td className="px-5 py-3 font-mono text-[12px] font-semibold border-b border-[#f9f7f4]">
                    {v.inventory != null
                      ? <span className={v.inventory > 0 ? "text-[#247a52]" : "text-[#b93232]"}>{v.inventory}</span>
                      : <span className="text-[#888894]">—</span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Bottom push CTA ── */}
      <div className="bg-[#1e4d92] rounded-2xl p-6 flex items-center justify-between gap-6">
        <div>
          <div className="text-white font-bold text-[15px] mb-1">
            {isReady ? "Product is ready to push" : "Review missing fields before pushing"}
          </div>
          <div className="text-white/70 text-[12px]">
            {selectedCustomerId
              ? "OPS credentials, markup rules, and master options are verified at push time."
              : "Select a customer from the top bar first."}
          </div>
        </div>
        <button
          onClick={handlePush}
          disabled={!selectedCustomerId}
          className="flex items-center gap-2 px-6 py-3 bg-white text-[#1e4d92] text-[13px] font-bold rounded-xl shadow-[0_3px_0_rgba(0,0,0,0.15)] active:shadow-none active:translate-y-px transition-all disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap shrink-0 hover:bg-[#f0f9f4]"
        >
          <Send className="w-4 h-4" />
          Push to OPS
        </button>
      </div>

    </div>
  );
}
