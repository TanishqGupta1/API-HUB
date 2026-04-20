"use client";

import Link from "next/link";
import type { ProductListItem } from "@/lib/types";

interface StorefrontProductCardProps {
  product: ProductListItem;
}

export function StorefrontProductCard({ product }: StorefrontProductCardProps) {
  return (
    <Link
      href={`/storefront/vg/product/${product.id}`}
      className="group bg-white border border-[#cfccc8] rounded-[10px] overflow-hidden
                 shadow-[4px_5px_0_rgba(30,77,146,0.08)]
                 transition-all duration-300
                 hover:-translate-y-1 hover:shadow-[8px_12px_0_rgba(30,77,146,0.1)]
                 hover:border-[#1e4d92]"
    >
      <div className="relative h-[220px] bg-[#ebe8e3] flex items-center justify-center border-b border-[#cfccc8]">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.product_name}
            className="w-full h-full object-contain p-4"
          />
        ) : (
          <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#b4b4bc]">
            No image
          </span>
        )}
        <div className="absolute top-3 left-3 px-[10px] py-[4px] bg-white border border-[#cfccc8] rounded
                        font-mono text-[10px] font-bold text-[#1e4d92]">
          VG
        </div>
      </div>

      <div className="p-5">
        <div className="text-[15px] font-extrabold leading-[1.3] mb-2 text-[#1e1e24] line-clamp-2 min-h-[40px]">
          {product.product_name}
        </div>
        <div className="flex items-center gap-2 text-[12px] text-[#888894]">
          {product.brand && (
            <>
              <span className="text-[#1e4d92] font-bold">{product.brand}</span>
              <span>·</span>
            </>
          )}
          <span className="font-mono truncate">{product.supplier_sku}</span>
        </div>
      </div>

      <div className="flex items-center justify-between px-5 py-3 bg-[#f9f7f4] border-t border-dashed border-[#cfccc8]">
        <span className="text-[10px] font-bold uppercase text-[#484852]">
          {product.product_type}
        </span>
        <span className="font-mono text-[12px] font-semibold text-[#1e4d92]">
          {product.variant_count} variant{product.variant_count === 1 ? "" : "s"}
        </span>
      </div>
    </Link>
  );
}
