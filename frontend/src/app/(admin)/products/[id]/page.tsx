"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { log } from "@/lib/log";
import type {
  Product,
  ProductImage,
  Supplier,
  OptionConfigItem,
} from "@/lib/types";
import { Button } from "@/components/ui/button";
import { PublishButton } from "@/components/products/publish-button";
import { PushHistory } from "@/components/products/push-history";

const IMAGE_TAB_ORDER = ["front", "back", "swatch", "detail"] as const;

const DEFAULT_DATA_SOURCES: Array<[string, string]> = [
  ["product_name", "PS Product Data v2 → productName"],
  ["brand", "PS Product Data v2 → brandName"],
  ["base_price", "PS Pricing v1 → partPrice"],
  ["inventory", "PS Inventory v2 → quantityAvailable"],
  ["images", "PS Media v1.1 → url"],
];

function pickImageForTab(images: ProductImage[], tab: string): ProductImage | null {
  if (!images.length) return null;
  const match = images.find((img) => img.image_type.toLowerCase() === tab);
  return match ?? null;
}

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [product, setProduct] = useState<Product | null>(null);
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [options, setOptions] = useState<OptionConfigItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeImageTab, setActiveImageTab] = useState<string>("front");
  const [pushStepsOpen, setPushStepsOpen] = useState(false);

  const fetchData = async () => {
    try {
      const [p] = await Promise.all([
        api<Product>(`/api/products/${id}`),
      ]);
      setProduct(p);
      try {
        const sup = await api<Supplier>(`/api/suppliers/${p.supplier_id}`);
        setSupplier(sup);
        // Fetch options config for VG/OPS products
        if (sup.protocol === "ops_graphql") {
          try {
            const opts = await api<OptionConfigItem[]>(`/api/products/${id}/options-config`);
            setOptions(opts);
          } catch {
            setOptions([]);
          }
        }
      } catch (err) {
        log.warn("supplier fetch failed", err);
      }
    } catch (e) {
      log.error("Product fetch failed", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [id]);

  const imageTabs = useMemo(() => {
    if (!product) return [] as Array<{ key: string; available: boolean }>;
    const present = new Set(
      (product.images ?? []).map((img) => img.image_type.toLowerCase())
    );
    return IMAGE_TAB_ORDER.map((key) => ({ key, available: present.has(key) }));
  }, [product]);

  const activeImage = useMemo(() => {
    if (!product) return null;
    const match = pickImageForTab(product.images ?? [], activeImageTab);
    if (match) return match.url;
    if (activeImageTab === "front" && product.image_url) return product.image_url;
    return null;
  }, [product, activeImageTab]);

  const dataSourceRows: Array<[string, string]> = useMemo(() => {
    const mappings = supplier?.field_mappings;
    if (!mappings || Object.keys(mappings).length === 0) return DEFAULT_DATA_SOURCES;
    return Object.entries(mappings).map(([source, target]) => [
      String(target),
      `${supplier?.protocol ?? "source"} → ${source}`,
    ]);
  }, [supplier]);


  if (loading) {
    return (
      <div className="py-10 text-center text-[#888894] text-[14px]">
        <div className="font-mono mb-2">Loading dashboard...</div>
        Accessing product data...
      </div>
    );
  }

  if (!product) {
    return (
      <div className="py-10 text-center text-[#b93232] text-[14px] font-semibold">
        Product not found or backend API is offline.
      </div>
    );
  }

  return (
    <div id="s-product-detail">

      {/* Source badge bar */}
      <div className="flex items-center gap-2 mb-4">
        {supplier?.protocol === "ops_graphql" ? (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-[#1e4d92] text-white">
            ★ VG PRODUCT — owned by Visual Graphics OPS
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold border border-[#cfccc8] text-[#484852] bg-white">
            ↓ SUPPLIER PRODUCT — sourced from {product.supplier_name}
          </span>
        )}
      </div>

      {/* ── Page header ─────────────────────────────────── */}
      <div className="flex items-end justify-between mb-10 pb-5 border-b-2 border-[#1e1e24]">
        <div>
          <div
            className="text-[12px] text-[#888894] mb-2 cursor-pointer font-semibold hover:text-[#1e4d92] transition-colors"
            onClick={() => router.push("/products")}
          >
            ← Back to Catalog
          </div>
          <div className="text-[32px] font-extrabold tracking-[-0.04em] leading-none text-[#1e1e24]">
            {product.product_name}
          </div>
          <div className="text-[13px] text-[#888894] mt-2">
            SKU: {product.supplier_sku} · Supplier: {product.supplier_name || "API Source"} ·{" "}
            {product.last_synced
              ? `Last synced ${new Date(product.last_synced).toLocaleDateString()}`
              : "New Item Entry"}
          </div>
        </div>
        <div className="flex gap-3">
          {supplier?.protocol === "ops_graphql" && (
            <Link href={`/products/${product.id}/options`}>
              <Button variant="outline" className="border-[#1e4d92] text-[#1e4d92]">
                Configure Options
              </Button>
            </Link>
          )}
          <PublishButton
            productId={id}
            onDone={() => {
              // History will auto-refresh due to its own effect if we trigger a state change,
              // but a full fetch is safer for now.
              setTimeout(fetchData, 2000);
            }}
          />
          <button
            onClick={fetchData}
            className="inline-flex items-center gap-2 px-5 py-[10px] rounded-md text-[13px] font-semibold
                       bg-white text-[#484852] border border-[#cfccc8] shadow-[0_3px_0_rgba(30,77,146,0.08)]
                       hover:border-[#1e4d92] transition-all"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* ── Two-column datasheet ─────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[320px_minmax(0,1fr)] gap-8 mb-10">

        {/* Left — image viewer */}
        <div>
          <div className="relative bg-[#ebe8e3] border border-[#cfccc8] rounded-[10px] h-[300px]
                          flex items-center justify-center mb-3
                          shadow-[4px_5px_0_rgba(30,77,146,0.08)] overflow-hidden">
            {activeImage ? (
              <img
                src={activeImage}
                alt={`${product.product_name} (${activeImageTab})`}
                className="w-full h-full object-contain p-5"
              />
            ) : (
              <div className="text-center">
                <div className="text-[10px] uppercase text-[#b4b4bc] tracking-[0.1em] font-bold">
                  Blueprint Detail View
                </div>
                <div className="text-[9px] text-[#b4b4bc] mt-1">
                  {product.images?.length
                    ? `No ${activeImageTab.toUpperCase()} image yet`
                    : "IMAGE_NOT_FOUND"}
                </div>
              </div>
            )}
            <div className="absolute bottom-2 right-2 text-[9px] bg-black/40 text-white px-2 py-0.5 rounded-full font-semibold">
              SOURCE: MEDIA_V1.1
            </div>
          </div>
          {/* Thumbnail strip */}
          <div className="grid grid-cols-4 gap-2">
            {imageTabs.map(({ key, available }) => {
              const isActive = activeImageTab === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setActiveImageTab(key)}
                  disabled={!available && key !== "front"}
                  className={`h-[60px] flex items-center justify-center rounded-md
                    border text-[8px] font-bold uppercase transition-colors
                    ${isActive
                      ? "border-[#1e4d92] text-[#1e4d92] bg-[#ebe8e3]"
                      : available
                        ? "border-[#cfccc8] text-[#484852] bg-[#ebe8e3] hover:border-[#1e4d92] cursor-pointer"
                        : "border-[#cfccc8] text-[#b4b4bc] bg-[#ebe8e3] cursor-not-allowed opacity-70"
                    }`}
                  title={available ? `View ${key} image` : `No ${key} image available`}
                >
                  {key}
                </button>
              );
            })}
          </div>
        </div>

        {/* Right — metadata */}
        <div>
          {/* Metric cards */}
          <div className="grid grid-cols-2 gap-4 mb-5">
            {[
              { label: "Brand", value: product.brand || "Generic", blue: true },
              { label: "Type", value: product.product_type, blue: false },
              {
                label: "Base Price",
                value: product.variants[0]?.base_price != null
                  ? `$${product.variants[0].base_price.toFixed(2)}`
                  : "—",
                mono: true, blue: false,
              },
              {
                label: "Total Variants",
                value: String(product.variants.length),
                mono: true, blue: false,
              },
            ].map(({ label, value, blue, mono }) => (
              <div
                key={label}
                className="bg-[#f9f7f4] border border-[#cfccc8] rounded-lg p-[14px] shadow-[3px_4px_0_rgba(30,77,146,0.08)]"
              >
                <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#888894] mb-1">
                  {label}
                </div>
                <div
                  className={`text-[16px] font-bold ${blue ? "text-[#1e4d92]" : "text-[#1e1e24]"} ${mono ? "font-mono" : ""}`}
                >
                  {value}
                </div>
              </div>
            ))}
          </div>

          {/* Description */}
          <div className="text-[13px] text-[#484852] leading-relaxed mb-5 bg-white p-4 rounded-lg border border-[#cfccc8]">
            {product.description || "No description provided by the API endpoint."}
          </div>

          {/* Data sources panel */}
          <div className="bg-[rgba(30,77,146,0.05)] border border-[rgba(30,77,146,0.15)] rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#1e4d92]">
                ℹ Data Sources
              </div>
              {supplier?.field_mappings && Object.keys(supplier.field_mappings).length > 0 ? (
                <button
                  type="button"
                  onClick={() => router.push(`/mappings/${product.supplier_id}`)}
                  className="text-[10px] font-semibold text-[#1e4d92] underline-offset-2 hover:underline"
                >
                  Configured ({Object.keys(supplier.field_mappings).length}) →
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => router.push(`/mappings/${product.supplier_id}`)}
                  className="text-[10px] font-semibold text-[#888894] underline-offset-2 hover:underline"
                >
                  Not configured → map fields
                </button>
              )}
            </div>
            <div className="grid gap-[5px] text-[12px]">
              {dataSourceRows.map(([field, source]) => (
                <div key={field} className="flex justify-between gap-4">
                  <span className="text-[#484852] font-medium">{field}</span>
                  <span className="font-mono text-[11px] text-[#888894] truncate" title={source}>
                    {source}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── Variants table ─────────────────────────────── */}
      <div className="bg-white border border-[#cfccc8] rounded-lg shadow-[4px_6px_0_rgba(30,77,146,0.08)] overflow-hidden mb-8">
        <div className="flex items-center justify-between px-6 py-4 bg-[#ebe8e3] border-b border-[#cfccc8]">
          <div className="text-[14px] font-bold uppercase tracking-[0.05em] text-[#1e1e24]">
            Variants ({product.variants.length})
          </div>
          <span className="font-mono text-[11px] text-[#888894]">LIVE_INVENTORY_SYNC</span>
        </div>
        <div className="overflow-x-auto">
        <table className="w-full border-collapse min-w-[640px]">
          <thead>
            <tr>
              {["Color", "Size", "SKU", "Price", "Inventory", "Warehouse"].map((h) => (
                <th
                  key={h}
                  className="text-left px-6 py-3 text-[10px] font-bold uppercase tracking-[0.1em] text-[#888894] border-b border-[#cfccc8]"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {product.variants.map((v) => (
              <tr key={v.id} className="hover:bg-[rgba(30,77,146,0.05)] transition-colors">
                <td className="px-6 py-[14px] text-[14px] text-[#1e1e24] font-semibold border-b border-[#f9f7f4]">
                  {v.color || "—"}
                </td>
                <td className="px-6 py-[14px] text-[14px] text-[#484852] border-b border-[#f9f7f4]">
                  {v.size || "—"}
                </td>
                <td className="px-6 py-[14px] font-mono text-[12px] text-[#484852] border-b border-[#f9f7f4]">
                  {v.sku || "—"}
                </td>
                <td className="px-6 py-[14px] font-mono text-[12px] text-[#484852] border-b border-[#f9f7f4]">
                  {v.base_price != null ? `$${v.base_price.toFixed(2)}` : "—"}
                </td>
                <td
                  className={`px-6 py-[14px] font-mono text-[12px] font-semibold border-b border-[#f9f7f4] ${
                    (v.inventory ?? 0) > 0 ? "text-[#247a52]" : "text-[#b93232]"
                  }`}
                >
                  {v.inventory ?? "—"}
                </td>
                <td className="px-6 py-[14px] font-mono text-[12px] text-[#484852] capitalize border-b border-[#f9f7f4]">
                  {v.warehouse || "HQ"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {/* ── Product Options (VG products only) ───────────── */}
      {supplier?.protocol === "ops_graphql" && (
        <div className="bg-white border border-[#cfccc8] rounded-lg shadow-[4px_6px_0_rgba(30,77,146,0.08)] overflow-hidden mb-8">
          <div className="flex items-center justify-between px-6 py-4 bg-[#ebe8e3] border-b border-[#cfccc8]">
            <div>
              <div className="text-[14px] font-bold uppercase tracking-[0.05em] text-[#1e1e24]">
                Product Options
              </div>
              <div className="text-[11px] text-[#888894] font-mono mt-0.5">
                Configure print options (substrate, ink type, laminate…) before pushing to OPS
              </div>
            </div>
            <Link href={`/products/${product.id}/options`}>
              <button className="px-4 py-2 text-[12px] font-semibold rounded-md border border-[#1e4d92] text-[#1e4d92] bg-white hover:bg-[#eef4fb] transition-colors">
                {options.length > 0 ? `Manage Options (${options.length})` : "Configure Options →"}
              </button>
            </Link>
          </div>
          <div className="p-6">
            {options.length === 0 ? (
              <div className="text-center py-6 text-[#888894]">
                <div className="text-[28px] mb-2">⚙️</div>
                <div className="text-[14px] font-semibold text-[#1e1e24] mb-1">No options configured yet</div>
                <div className="text-[12px] mb-4">
                  Options control what customers can choose when ordering — substrate, print sides, ink type, finish, etc.
                </div>
                <Link href={`/products/${product.id}/options`}>
                  <button className="px-5 py-2 text-[13px] font-semibold rounded-md bg-[#1e4d92] text-white hover:bg-[#173d74] transition-colors">
                    Open Options Configuration
                  </button>
                </Link>
              </div>
            ) : (
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
                {options.slice(0, 6).map((opt) => (
                  <div
                    key={opt.master_option_id}
                    className={`flex items-center justify-between px-4 py-3 rounded-lg border ${
                      opt.enabled
                        ? "border-[#247a52] bg-[#f0f9f4]"
                        : "border-[#cfccc8] bg-[#f9f7f4]"
                    }`}
                  >
                    <div>
                      <div className="text-[12px] font-semibold text-[#1e1e24]">{opt.title}</div>
                      <div className="text-[10px] text-[#888894] font-mono mt-0.5">
                        {opt.attributes.filter((a) => a.enabled).length}/{opt.attributes.length} active
                      </div>
                    </div>
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        opt.enabled
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-stone-100 text-stone-500"
                      }`}
                    >
                      <span className={`w-[5px] h-[5px] rounded-full ${opt.enabled ? "bg-emerald-500" : "bg-stone-400"}`} />
                      {opt.enabled ? "On" : "Off"}
                    </span>
                  </div>
                ))}
                {options.length > 6 && (
                  <Link href={`/products/${product.id}/options`}>
                    <div className="flex items-center justify-center px-4 py-3 rounded-lg border border-dashed border-[#1e4d92] text-[#1e4d92] text-[12px] font-semibold hover:bg-[#eef4fb] cursor-pointer transition-colors h-full">
                      +{options.length - 6} more →
                    </div>
                  </Link>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── How Push to OPS Works ─────────────────────────── */}
      <div className="bg-white border border-[#cfccc8] rounded-lg shadow-[4px_6px_0_rgba(30,77,146,0.08)] overflow-hidden mb-8">
        <button
          onClick={() => setPushStepsOpen((v) => !v)}
          className="w-full flex items-center justify-between px-6 py-4 bg-[#ebe8e3] border-b border-[#cfccc8] text-left"
        >
          <div className="text-[14px] font-bold uppercase tracking-[0.05em] text-[#1e1e24]">
            How to Push to OPS
          </div>
          <span className="text-[#888894] text-[12px] font-mono">
            {pushStepsOpen ? "▲ collapse" : "▼ expand"}
          </span>
        </button>
        {pushStepsOpen && (
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-5">
              {[
                { step: "1", icon: "📦", title: "Product data fetched", desc: "Hub pulls name, variants, images, pricing from supplier API" },
                { step: "2", icon: "💲", title: "Markup applied", desc: "Markup rules calculate final customer-facing price from base_price" },
                { step: "3", icon: "🚀", title: "n8n sends to OPS", desc: "Workflow calls OPS GraphQL: setProduct → setProductSize → setProductPrice → setProductImage" },
                { step: "4", icon: "✅", title: "Push logged", desc: "OPS product ID saved here. Re-pushing the same product updates it instead of creating a duplicate" },
              ].map(({ step, icon, title, desc }) => (
                <div key={step} className="flex flex-col gap-2 p-4 rounded-lg border border-[#cfccc8] bg-[#f9f7f4]">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-[#1e4d92] text-white text-[11px] font-bold flex items-center justify-center shrink-0">
                      {step}
                    </span>
                    <span className="text-[18px]">{icon}</span>
                  </div>
                  <div className="text-[12px] font-bold text-[#1e1e24]">{title}</div>
                  <div className="text-[11px] text-[#888894] leading-relaxed">{desc}</div>
                </div>
              ))}
            </div>
            <div className="text-[12px] text-[#484852] bg-[#eef4fb] border border-[rgba(30,77,146,0.2)] rounded-lg px-4 py-3">
              <strong className="text-[#1e4d92]">To push this product:</strong> click <strong>Publish to OPS</strong> above → select a customer/storefront → confirm.
              The job runs in the background via n8n. Check push history below for status.
            </div>
          </div>
        )}
      </div>

      {/* ── Storefront Push History ──────────────────────── */}
      <div className="bg-white border border-[#cfccc8] rounded-lg shadow-[4px_6px_0_rgba(30,77,146,0.08)] overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 bg-[#ebe8e3] border-b border-[#cfccc8]">
          <div>
            <div className="text-[14px] font-bold uppercase tracking-[0.05em] text-[#1e1e24]">
              Storefront Push History
            </div>
            <div className="text-[11px] text-[#888894] font-mono mt-0.5">
              Every time this product was sent to an OPS storefront
            </div>
          </div>
        </div>
        <div className="p-6">
          <PushHistory productId={id} />
        </div>
      </div>
    </div>
  );
}
