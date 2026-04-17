"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Product, Customer, ProductPushStatus } from "@/lib/types";

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [product, setProduct] = useState<Product | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [pushStatuses, setPushStatuses] = useState<ProductPushStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [pushing, setPushing] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const [p, c, s] = await Promise.all([
        api<Product>(`/api/products/${id}`),
        api<Customer[]>("/api/customers"),
        api<ProductPushStatus[]>(`/api/products/${id}/push-status`),
      ]);
      setProduct(p);
      setCustomers(c);
      setPushStatuses(s);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [id]);

  const handlePush = async (customerId?: string) => {
    if (!product) return;
    const targetId = customerId || (customers.length > 0 ? customers[0].id : null);
    if (!targetId) {
      alert("Please configure a customer in the Customers page first.");
      return;
    }
    setPushing(targetId);
    try {
      await api("/api/push-log", {
        method: "POST",
        body: JSON.stringify({
          product_id: product.id,
          customer_id: targetId,
          status: "pushed",
          ops_product_id: `ops-prod-${Math.floor(Math.random() * 9000) + 1000}`,
        }),
      });
      const newStatuses = await api<ProductPushStatus[]>(`/api/products/${id}/push-status`);
      setPushStatuses(newStatuses);
    } catch (e) {
      console.error(e);
      alert("Push failed. Check connection.");
    } finally {
      setPushing(null);
    }
  };

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
          <button
            onClick={() => handlePush()}
            disabled={!!pushing}
            className="inline-flex items-center gap-2 px-5 py-[10px] rounded-md text-[13px] font-semibold
                       bg-[#1e4d92] text-white shadow-[0_4px_0_#143566] transition-all
                       hover:-translate-y-px hover:shadow-[0_5px_0_#143566] disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {pushing ? "Publishing..." : "Publish to Store"}
          </button>
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
      <div className="grid grid-cols-[320px_1fr] gap-8 mb-10">

        {/* Left — image viewer */}
        <div>
          <div className="relative bg-[#ebe8e3] border border-[#cfccc8] rounded-[10px] h-[300px]
                          flex items-center justify-center mb-3
                          shadow-[4px_5px_0_rgba(30,77,146,0.08)] overflow-hidden">
            {product.image_url ? (
              <img
                src={product.image_url}
                alt={product.product_name}
                className="w-full h-full object-contain p-5"
              />
            ) : (
              <div className="text-center">
                <div className="text-[10px] uppercase text-[#b4b4bc] tracking-[0.1em] font-bold">
                  Blueprint Detail View
                </div>
                <div className="text-[9px] text-[#b4b4bc] mt-1">IMAGE_NOT_FOUND</div>
              </div>
            )}
            <div className="absolute bottom-2 right-2 text-[9px] bg-black/40 text-white px-2 py-0.5 rounded-full font-semibold">
              SOURCE: MEDIA_V1.1
            </div>
          </div>
          {/* Thumbnail strip */}
          <div className="grid grid-cols-4 gap-2">
            {["FRONT", "BACK", "SWATCH", "DETAIL"].map((label, i) => (
              <div
                key={label}
                className={`h-[60px] flex items-center justify-center rounded-md cursor-pointer
                  border text-[8px] font-bold
                  ${i === 0
                    ? "border-[#1e4d92] text-[#1e4d92] bg-[#ebe8e3]"
                    : "border-[#cfccc8] text-[#b4b4bc] bg-[#ebe8e3] hover:border-[#1e4d92]"
                  }`}
              >
                {label}
              </div>
            ))}
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
            <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#1e4d92] mb-3">
              ℹ Data Sources
            </div>
            <div className="grid gap-[5px] text-[12px]">
              {[
                ["product_name", "PS Product Data v2 → productName"],
                ["brand", "PS Product Data v2 → brandName"],
                ["base_price", "PS Pricing v1 → partPrice"],
                ["inventory", "PS Inventory v2 → quantityAvailable"],
                ["images", "PS Media v1.1 → url"],
              ].map(([field, source]) => (
                <div key={field} className="flex justify-between">
                  <span className="text-[#484852] font-medium">{field}</span>
                  <span className="font-mono text-[11px] text-[#888894]">{source}</span>
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
        <table className="w-full border-collapse">
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

      {/* ── Storefront Publish Status ────────────────────────────── */}
      <div className="bg-white border border-[#cfccc8] rounded-lg shadow-[4px_6px_0_rgba(30,77,146,0.08)] overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 bg-[#ebe8e3] border-b border-[#cfccc8]">
          <div className="text-[14px] font-bold uppercase tracking-[0.05em] text-[#1e1e24]">
            Storefront Publish Status
          </div>
        </div>
        <table className="w-full border-collapse">
          <thead>
            <tr>
              {["Storefront", "Status", "Pushed", "Store Product ID", "Action"].map((h) => (
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
            {pushStatuses.map((s) => (
              <tr key={s.customer_id} className="hover:bg-[rgba(30,77,146,0.05)] transition-colors">
                <td className="px-6 py-[14px] text-[14px] text-[#1e1e24] font-semibold border-b border-[#f9f7f4]">
                  {s.customer_name}
                </td>
                <td className="px-6 py-[14px] border-b border-[#f9f7f4]">
                  {s.status === "pushed" ? (
                    <span className="inline-flex items-center gap-1.5 text-[12px] font-semibold px-3 py-1 rounded-full bg-[#f0f9f4] text-[#247a52]">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#247a52]" />
                      Published
                    </span>
                  ) : s.status === "failed" ? (
                    <span className="inline-flex items-center gap-1.5 text-[12px] font-semibold px-3 py-1 rounded-full bg-[#fdf2f2] text-[#b93232]">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#b93232]" />
                      Connection Failed
                    </span>
                  ) : (
                    <span className="text-[12px] text-[#b4b4bc]">Not pushed</span>
                  )}
                </td>
                <td className="px-6 py-[14px] font-mono text-[12px] text-[#484852] border-b border-[#f9f7f4]">
                  {s.pushed_at ? new Date(s.pushed_at).toLocaleString() : "—"}
                </td>
                <td className="px-6 py-[14px] font-mono text-[12px] text-[#484852] border-b border-[#f9f7f4]">
                  {s.ops_product_id || "—"}
                </td>
                <td className="px-6 py-[14px] border-b border-[#f9f7f4]">
                  <button
                    onClick={() => handlePush(s.customer_id)}
                    disabled={pushing === s.customer_id}
                    className="px-3 py-1 text-[11px] font-semibold bg-white border border-[#cfccc8] rounded
                               shadow-[0_2px_0_rgba(30,77,146,0.08)] hover:border-[#1e4d92] transition-all
                               disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {pushing === s.customer_id ? "..." : "Push Now"}
                  </button>
                </td>
              </tr>
            ))}
            {pushStatuses.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-5 text-center text-[#888894] text-[13px]">
                  No customers configured. Add one in the Customers page to enable pushing.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
