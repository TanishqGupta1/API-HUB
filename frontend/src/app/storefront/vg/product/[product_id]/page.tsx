"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Category, Product } from "@/lib/types";
import { PDPLayout } from "@/components/storefront/pdp-layout";
import { ImageGallery } from "@/components/storefront/image-gallery";
import { VariantPicker } from "@/components/storefront/variant-picker";
import { PriceBlock } from "@/components/storefront/price-block";
import { DescriptionHtml } from "@/components/storefront/description-html";
import { RelatedProducts } from "@/components/storefront/related-products";
import { ProductOptions } from "@/components/storefront/product-options";

export default function VGProductDetailPage() {
  const params = useParams<{ product_id: string }>();
  const productId = params?.product_id;
  const router = useRouter();

  const [product, setProduct] = useState<Product | null>(null);
  const [category, setCategory] = useState<Category | null>(null);
  const [selectedVariantId, setSelectedVariantId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!productId) return;
    setLoading(true);
    setError(null);

    api<Product>(`/api/products/${productId}`)
      .then(async (p) => {
        setProduct(p);
        if (p.variants.length > 0) setSelectedVariantId(p.variants[0].id);
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

  const selectedVariant = product?.variants.find((v) => v.id === selectedVariantId) ?? null;

  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-[6fr_4fr] gap-10">
        <div className="aspect-square bg-[#ebe8e3] rounded-[10px] animate-pulse" />
        <div className="flex flex-col gap-4">
          <div className="h-[40px] bg-[#ebe8e3] rounded animate-pulse" />
          <div className="h-[20px] w-[200px] bg-[#ebe8e3] rounded animate-pulse" />
          <div className="h-[80px] bg-[#ebe8e3] rounded animate-pulse mt-4" />
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

  const info = (
    <div className="flex flex-col gap-6">
      <div>
        {product.brand && (
          <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#1e4d92] mb-2">
            {product.brand}
          </div>
        )}
        <h1 className="text-[28px] font-extrabold tracking-[-0.03em] leading-tight text-[#1e1e24]">
          {product.product_name}
        </h1>
        <div className="flex items-center gap-3 mt-2">
          <div className="font-mono text-[12px] text-[#888894]">
            {product.supplier_sku} · {product.product_type}
          </div>
          {product.external_catalogue === 1 && (
            <span className="px-2 py-0.5 rounded bg-[#eef4fb] border border-[#1e4d92] text-[#1e4d92] text-[10px] font-bold tracking-wide uppercase">
              External Catalogue
            </span>
          )}
        </div>
      </div>

      <PriceBlock variant={selectedVariant} fallback={product.variants} />

      {product.variants.length > 0 && (
        <div className="py-5 border-t border-dashed border-[#cfccc8]">
          <VariantPicker
            variants={product.variants}
            selectedVariantId={selectedVariantId}
            onSelect={setSelectedVariantId}
          />
        </div>
      )}

      <ProductOptions options={product.options} />

      <div className="flex gap-3 pt-2">
        <button type="button" onClick={() => router.back()}
          className="px-5 py-3 rounded-md border border-[#cfccc8] text-[#1e1e24] text-[13px] font-semibold hover:border-[#1e4d92] hover:text-[#1e4d92]">
          ← Back
        </button>
        <button type="button" disabled
          className="flex-1 px-5 py-3 rounded-md bg-[#1e4d92] text-white text-[13px] font-semibold opacity-60 cursor-not-allowed"
          title="Quote flow coming in future phase">
          Add to quote
        </button>
      </div>
    </div>
  );

  return (
    <PDPLayout
      breadcrumbCategory={category ? { id: category.id, name: category.name } : null}
      breadcrumbProduct={product.supplier_sku}
      gallery={
        <ImageGallery images={product.images} fallbackUrl={product.image_url} alt={product.product_name} />
      }
      info={info}
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
