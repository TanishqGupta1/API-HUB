"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Category, Product } from "@/lib/types";
import { ImageGallery } from "@/components/storefront/image-gallery";
import { VariantPicker } from "@/components/storefront/variant-picker";
import { PriceBlock } from "@/components/storefront/price-block";

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
        if (p.variants.length > 0) {
          setSelectedVariantId(p.variants[0].id);
        }

        // Best-effort category fetch. Catalog API doesn't return category_id on
        // the product read model yet, so skip unless we extend later.
        const catParam = (p as Product & { category_id?: string }).category_id;
        if (catParam) {
          try {
            const c = await api<Category>(`/api/categories/${catParam}`);
            setCategory(c);
          } catch {
            /* category absent — ignore */
          }
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [productId]);

  const selectedVariant =
    product?.variants.find((v) => v.id === selectedVariantId) ?? null;

  if (loading) {
    return (
      <div className="pb-12">
        <div className="h-[20px] w-[300px] bg-[#ebe8e3] rounded mb-8 animate-pulse" />
        <div className="grid grid-cols-[1fr_1fr] gap-10">
          <div className="aspect-square bg-[#ebe8e3] rounded-[10px] animate-pulse" />
          <div className="flex flex-col gap-4">
            <div className="h-[40px] bg-[#ebe8e3] rounded animate-pulse" />
            <div className="h-[20px] w-[200px] bg-[#ebe8e3] rounded animate-pulse" />
            <div className="h-[80px] bg-[#ebe8e3] rounded animate-pulse mt-4" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="p-6 border border-[#e94b4b] rounded-[10px] bg-[#fef2f2] text-[13px] text-[#b91c1c]">
        <div className="font-bold mb-1">Product not found</div>
        <div className="font-mono">{error ?? "Missing product"}</div>
        <Link
          href="/storefront/vg"
          className="inline-block mt-4 px-4 py-2 rounded-md border border-[#1e4d92] text-[#1e4d92] text-[13px] font-semibold hover:bg-[#eef4fb]"
        >
          ← Back to catalog
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 pb-12">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-[12px] text-[#888894]">
        <Link href="/storefront/vg" className="hover:text-[#1e4d92] font-medium">
          Visual Graphics
        </Link>
        <span>/</span>
        {category ? (
          <>
            <Link
              href={`/storefront/vg/category/${category.id}`}
              className="hover:text-[#1e4d92] font-medium"
            >
              {category.name}
            </Link>
            <span>/</span>
          </>
        ) : product.category ? (
          <>
            <span className="font-medium">{product.category}</span>
            <span>/</span>
          </>
        ) : null}
        <span className="font-mono text-[#1e1e24]">{product.supplier_sku}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr] gap-10">
        {/* Left — gallery */}
        <ImageGallery
          images={product.images}
          fallbackUrl={product.image_url}
          alt={product.product_name}
        />

        {/* Right — detail */}
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
            <div className="font-mono text-[12px] text-[#888894] mt-2">
              {product.supplier_sku} · {product.product_type}
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

          {product.description && (
            <div className="py-5 border-t border-dashed border-[#cfccc8]">
              <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852] mb-2">
                Description
              </div>
              <p className="text-[14px] leading-[1.6] text-[#1e1e24] whitespace-pre-line">
                {product.description}
              </p>
            </div>
          )}

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={() => router.back()}
              className="px-5 py-3 rounded-md border border-[#cfccc8] text-[#1e1e24] text-[13px] font-semibold hover:border-[#1e4d92] hover:text-[#1e4d92]"
            >
              ← Back
            </button>
            <button
              type="button"
              disabled
              className="flex-1 px-5 py-3 rounded-md bg-[#1e4d92] text-white text-[13px] font-semibold opacity-60 cursor-not-allowed"
              title="Cart/checkout coming in a future phase"
            >
              Add to quote (coming soon)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
