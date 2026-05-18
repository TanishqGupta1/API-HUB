"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Category, Customer, Product } from "@/lib/types";
import { PDPLayout } from "@/components/storefront/pdp-layout";
import { ImageGallery } from "@/components/storefront/image-gallery";
import { DescriptionHtml } from "@/components/storefront/description-html";
import { RelatedProducts } from "@/components/storefront/related-products";
import { ProductDetailPanel } from "@/components/storefront/product-detail-panel";
import { DecorationEditor } from "@/components/storefront/decoration-editor";

export default function VGProductDetailPage() {
  const params = useParams<{ product_id: string }>();
  const productId = params?.product_id;
  const router = useRouter();

  const [product, setProduct] = useState<Product | null>(null);
  const [category, setCategory] = useState<Category | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>("");
  const [selectedColor, setSelectedColor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!productId) return;
    setLoading(true);
    setError(null);

    Promise.all([
      api<Product>(`/api/products/${productId}`),
      api<Customer[]>("/api/customers"),
    ])
      .then(async ([p, custs]) => {
        setProduct(p);
        setCustomers(custs.filter((c) => c.is_active));
        const catId = (p as Product & { category_id?: string }).category_id;
        if (catId) {
          try {
            setCategory(await api<Category>(`/api/categories/${catId}`));
          } catch { /* ignore */ }
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [productId]);

  if (loading) {
    return (
      <div className="flex h-full gap-0">
        {/* Left panel skeleton */}
        <div className="flex flex-col w-[55%] border-r border-[#cfccc8] pr-6">
          <div className="h-[20px] w-[180px] bg-[#ebe8e3] rounded animate-pulse mb-3" />
          <div className="flex-1 min-h-0 bg-[#ebe8e3] rounded-[10px] animate-pulse" />
        </div>
        {/* Right panel skeleton */}
        <div className="flex flex-col w-[45%] pl-6 gap-4">
          <div className="h-[14px] w-[80px] bg-[#ebe8e3] rounded animate-pulse" />
          <div className="h-[32px] w-[85%] bg-[#ebe8e3] rounded animate-pulse" />
          <div className="h-[14px] w-[140px] bg-[#ebe8e3] rounded animate-pulse" />
          <div className="h-[40px] w-[100px] bg-[#ebe8e3] rounded animate-pulse mt-2" />
          <div className="flex gap-2 mt-2">
            {[1,2,3,4].map((i) => (
              <div key={i} className="h-[36px] w-[72px] bg-[#ebe8e3] rounded-full animate-pulse" />
            ))}
          </div>
          <div className="flex gap-2">
            {["S","M","L","XL"].map((s) => (
              <div key={s} className="h-[36px] w-[44px] bg-[#ebe8e3] rounded animate-pulse" />
            ))}
          </div>
          <div className="h-[44px] bg-[#ebe8e3] rounded animate-pulse mt-2" />
        </div>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="p-6 border border-[#b93232] rounded-[10px] bg-[#fdeded] text-[13px] text-[#b93232]">
        <div className="font-bold mb-1">Product not found</div>
        <div className="font-mono">{error ?? "Missing product"}</div>
        <Link href="/storefront/vg" className="inline-block mt-4 px-4 py-2 rounded-md border border-[#1e4d92] text-[#1e4d92] text-[13px] font-semibold hover:bg-[#eef4fb]">
          ← Back to catalog
        </Link>
      </div>
    );
  }

  const showDecorationTab = product.supplier_has_decoration_overlay && selectedCustomerId;

  const ctaButtons = (
    <div className="flex flex-col gap-3">
      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="px-4 py-2.5 rounded-md border border-[#cfccc8] text-[#484852] text-[13px] font-semibold hover:border-[#1e4d92] hover:text-[#1e4d92] transition-colors"
        >
          ← Back
        </button>
        <button
          type="button"
          disabled
          className="flex-1 px-5 py-2.5 rounded-md bg-[#1e4d92] text-white text-[13px] font-bold cursor-not-allowed relative overflow-hidden"
          title="Quote flow coming in future phase"
        >
          <span className="opacity-50">Add to quote</span>
          <span className="absolute inset-0 flex items-center justify-end pr-3 pointer-events-none">
            <span className="text-[9px] font-bold uppercase tracking-[0.1em] bg-white/20 px-1.5 py-0.5 rounded">
              Soon
            </span>
          </span>
        </button>
      </div>
    </div>
  );

  const info = (
    <div className="flex flex-col gap-5">
      <div>
        {product.brand && (
          <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#1e4d92] mb-1.5">
            {product.brand}
          </div>
        )}
        <h1 className="text-[24px] font-extrabold tracking-[-0.02em] leading-snug text-[#1e1e24]">
          {product.product_name}
        </h1>
        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
          <span className="font-mono text-[11px] text-[#888894] bg-[#f2f0ed] px-2 py-0.5 rounded">
            {product.supplier_sku}
          </span>
          <span className="font-mono text-[11px] text-[#888894] capitalize">
            {product.product_type}
          </span>
          {product.external_catalogue === 1 && (
            <span className="px-2 py-0.5 rounded bg-[#eef4fb] border border-[#1e4d92] text-[#1e4d92] text-[10px] font-bold tracking-wide uppercase">
              External Catalogue
            </span>
          )}
        </div>
      </div>

      <ProductDetailPanel product={product} cta={ctaButtons} onColorChange={setSelectedColor} />

      {customers.length > 0 && (
        <div className="border-t border-dashed border-[#cfccc8] pt-4">
          <div className="flex items-center gap-2 mb-2">
            <svg className="w-3.5 h-3.5 text-[#1e4d92] shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <label className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#484852]">
              Push to OPS storefront
            </label>
          </div>
          <select
            value={selectedCustomerId}
            onChange={(e) => setSelectedCustomerId(e.target.value)}
            className="w-full h-9 px-3 rounded-md border border-[#cfccc8] bg-white text-[13px] text-[#1e1e24] outline-none focus:border-[#1e4d92] transition-colors"
          >
            <option value="">— select a customer —</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          {product.supplier_has_decoration_overlay && !selectedCustomerId && (
            <p className="mt-1.5 text-[11px] text-[#b47a00] font-medium">
              Select a customer to configure decoration options
            </p>
          )}
        </div>
      )}
    </div>
  );

  return (
    <PDPLayout
      breadcrumbCategory={category ? { id: category.id, name: category.name } : null}
      breadcrumbProduct={product.supplier_sku}
      gallery={
        <ImageGallery images={product.images} fallbackUrl={product.image_url} alt={product.product_name} selectedColor={selectedColor} />
      }
      info={info}
      options={
        showDecorationTab ? (
          <div>
            <div className="flex items-center gap-2 mb-4">
              <span className="w-[3px] h-5 bg-[#1e4d92] rounded-full" />
              <h2 className="text-[15px] font-extrabold text-[#1e1e24] tracking-[-0.01em]">
                Decoration Options
              </h2>
              <span className="ml-auto text-[11px] font-mono text-[#888894]">
                {customers.find((c) => c.id === selectedCustomerId)?.name}
              </span>
            </div>
            <DecorationEditor customerId={selectedCustomerId} productId={product.id} />
          </div>
        ) : undefined
      }
      description={<DescriptionHtml html={product.description} />}
      related={
        <RelatedProducts
          supplierId={product.supplier_id}
          categoryId={(product as Product & { category_id?: string }).category_id ?? null}
          excludeId={product.id}
        />
      }
    />
  );
}
