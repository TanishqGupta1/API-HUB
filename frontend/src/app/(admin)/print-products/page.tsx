"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { api } from "@/lib/api";
import type { ProductListItem, Supplier } from "@/lib/types";

export default function PrintProductsPage() {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [search, setSearch] = useState("");
  const [supplierFilter, setSupplierFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    api<Supplier[]>("/api/suppliers").then(setSuppliers).catch(() => {});
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setLoading(true);
      const params = new URLSearchParams({ product_type: "print", limit: "100" });
      if (search) params.set("search", search);
      if (supplierFilter !== "all") params.set("supplier_id", supplierFilter);
      api<ProductListItem[]>(`/api/products?${params}`)
        .then(setProducts)
        .catch(() => setProducts([]))
        .finally(() => setLoading(false));
    }, 300);
  }, [search, supplierFilter]);

  const printSuppliers = suppliers.filter((s) =>
    ["4over", "print", "4over-rest"].some((k) => s.slug?.toLowerCase().includes(k) || s.name?.toLowerCase().includes(k))
  );

  return (
    <div>
      {/* ── Page Header ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Print Products</h1>
          <p className="page-subtitle">
            Manage print products from 4Over and other print suppliers
          </p>
        </div>
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <button
            className="btn btn-ghost"
            disabled
            title="4Over API integration coming in V1d"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 1 0 .49-4.5" />
            </svg>
            Sync from 4Over
          </button>
          <Link href="/print-products/new" className="btn btn-primary">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Add Product
          </Link>
        </div>
      </div>

      {/* ── Info banner ── */}
      <div style={{
        marginBottom: "20px",
        padding: "12px 16px",
        background: "#eef4fb",
        border: "1px solid #c0d6f0",
        borderRadius: "8px",
        display: "flex",
        alignItems: "center",
        gap: "10px",
      }}>
        <svg viewBox="0 0 24 24" fill="none" stroke="#1e4d92" strokeWidth="2" width="16" height="16" style={{ flexShrink: 0 }}>
          <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <span style={{ fontSize: "12px", color: "#1e4d92" }}>
          <strong>4Over integration</strong> is planned for V1d. Once connected, products will be fetched automatically via the 4Over REST API.
          Until then, you can add print products manually.
        </span>
      </div>

      {/* ── Filters ── */}
      <div style={{ display: "flex", gap: "10px", marginBottom: "20px", flexWrap: "wrap" }}>
        <div style={{ position: "relative", flex: "1", minWidth: "200px", maxWidth: "340px" }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14"
            style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)", color: "#888894", pointerEvents: "none" }}>
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            className="input"
            style={{ paddingLeft: "34px", width: "100%" }}
            placeholder="Search print products…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="input"
          style={{ width: "200px" }}
          value={supplierFilter}
          onChange={(e) => setSupplierFilter(e.target.value)}
        >
          <option value="all">All suppliers</option>
          {suppliers.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        <div style={{
          marginLeft: "auto",
          display: "flex",
          alignItems: "center",
          gap: "6px",
          fontSize: "12px",
          color: "#888894",
          fontFamily: "var(--font-mono)",
        }}>
          <span className="badge badge-blue">{products.length}</span>
          products
        </div>
      </div>

      {/* ── Table ── */}
      <div className="card" style={{ overflow: "hidden", padding: 0 }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "var(--surface-raised)", borderBottom: "2px solid var(--border)" }}>
              {["#", "Image", "Product Details", "Supplier", "Sizes / Dimensions", "Status", "Actions"].map((col) => (
                <th key={col} style={{
                  padding: "10px 14px",
                  textAlign: "left",
                  fontSize: "10px",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  color: "var(--ink-muted)",
                  whiteSpace: "nowrap",
                }}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                  {[60, 80, 280, 120, 140, 80, 100].map((w, j) => (
                    <td key={j} style={{ padding: "12px 14px" }}>
                      <div style={{ height: "14px", width: `${w}px`, background: "var(--surface-raised)", borderRadius: "4px", animation: "pulse 1.5s infinite" }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : products.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: "60px 20px", textAlign: "center" }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "12px" }}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="var(--ink-faint)" strokeWidth="1.5" width="48" height="48">
                      <polyline points="6 9 6 2 18 2 18 9" />
                      <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
                      <rect x="6" y="14" width="12" height="8" />
                    </svg>
                    <div>
                      <div style={{ fontSize: "14px", fontWeight: 700, color: "var(--ink)", marginBottom: "4px" }}>
                        No print products yet
                      </div>
                      <div style={{ fontSize: "12px", color: "var(--ink-muted)" }}>
                        Add products manually or wait for the 4Over API integration in V1d
                      </div>
                    </div>
                    <Link href="/print-products/new" className="btn btn-primary" style={{ marginTop: "4px" }}>
                      + Add first print product
                    </Link>
                  </div>
                </td>
              </tr>
            ) : (
              products.map((p, idx) => (
                <PrintProductRow key={p.id} product={p} index={idx + 1} />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PrintProductRow({ product: p, index }: { product: ProductListItem; index: number }) {
  const isActive = !p.archived_at;

  return (
    <tr style={{
      borderBottom: "1px solid var(--border)",
      transition: "background 0.15s",
    }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-raised)")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    >
      {/* # */}
      <td style={{ padding: "12px 14px", fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--ink-muted)", width: "48px" }}>
        {index}
      </td>

      {/* Image */}
      <td style={{ padding: "8px 14px", width: "72px" }}>
        <div style={{
          width: "56px", height: "56px",
          background: "var(--surface-raised)",
          border: "1px solid var(--border)",
          borderRadius: "8px",
          overflow: "hidden",
          position: "relative",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          {p.image_url ? (
            <Image src={p.image_url} alt="" fill sizes="56px" style={{ objectFit: "contain", padding: "4px" }} />
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="var(--ink-faint)" strokeWidth="1.5" width="22" height="22">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21 15 16 10 5 21" />
            </svg>
          )}
        </div>
      </td>

      {/* Product Details */}
      <td style={{ padding: "12px 14px", maxWidth: "300px" }}>
        <Link
          href={`/products/${p.id}`}
          style={{ fontSize: "13px", fontWeight: 700, color: "var(--blue)", textDecoration: "none" }}
          className="hover:underline"
        >
          {p.product_name}
        </Link>
        <div style={{ display: "flex", gap: "6px", marginTop: "4px", flexWrap: "wrap" }}>
          {p.brand && (
            <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: "var(--ink-muted)", background: "var(--surface-raised)", padding: "1px 6px", borderRadius: "4px", border: "1px solid var(--border)" }}>
              {p.brand}
            </span>
          )}
          <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: "var(--ink-muted)" }}>
            SKU: {p.supplier_sku}
          </span>
        </div>
      </td>

      {/* Supplier */}
      <td style={{ padding: "12px 14px" }}>
        <span style={{ fontSize: "12px", color: "var(--ink)", fontWeight: 600 }}>
          {p.supplier_name ?? "—"}
        </span>
      </td>

      {/* Sizes / Dimensions */}
      <td style={{ padding: "12px 14px" }}>
        {p.variant_count > 0 ? (
          <span style={{ fontSize: "12px", color: "var(--ink)" }}>
            {p.variant_count} size{p.variant_count !== 1 ? "s" : ""}
          </span>
        ) : (
          <span style={{ fontSize: "11px", color: "var(--ink-faint)" }}>—</span>
        )}
        {p.price_min != null && (
          <div style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--blue)", marginTop: "2px" }}>
            {p.price_min === p.price_max
              ? `$${Number(p.price_min).toFixed(2)}`
              : `$${Number(p.price_min).toFixed(2)} – $${Number(p.price_max).toFixed(2)}`}
          </div>
        )}
      </td>

      {/* Status */}
      <td style={{ padding: "12px 14px" }}>
        <span style={{
          display: "inline-flex", alignItems: "center", gap: "5px",
          padding: "3px 8px",
          borderRadius: "999px",
          fontSize: "10px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em",
          background: isActive ? "#e8f5ec" : "#f5f5f5",
          color: isActive ? "#1e7a3c" : "#888894",
          border: `1px solid ${isActive ? "#a8d5b5" : "#e0ddd9"}`,
        }}>
          <span style={{ width: "5px", height: "5px", borderRadius: "50%", background: isActive ? "#1e7a3c" : "#b4b4bc" }} />
          {isActive ? "Active" : "Archived"}
        </span>
      </td>

      {/* Actions */}
      <td style={{ padding: "12px 14px" }}>
        <div style={{ display: "flex", gap: "6px" }}>
          <Link
            href={`/products/${p.id}`}
            style={{
              padding: "5px 10px", borderRadius: "6px",
              border: "1px solid var(--border)",
              fontSize: "11px", fontWeight: 600, color: "var(--ink)",
              textDecoration: "none",
              background: "white",
            }}
          >
            Edit
          </Link>
          <Link
            href={`/storefront/vg/product/${p.id}`}
            target="_blank"
            style={{
              padding: "5px 10px", borderRadius: "6px",
              border: "1px solid var(--border)",
              fontSize: "11px", fontWeight: 600, color: "var(--blue)",
              textDecoration: "none",
              background: "white",
            }}
          >
            View
          </Link>
        </div>
      </td>
    </tr>
  );
}
