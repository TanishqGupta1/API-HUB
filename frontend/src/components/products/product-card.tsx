"use client";

import { useRouter } from "next/navigation";
import type { ProductListItem } from "@/lib/types";
import { PushRowAction } from "@/components/products/push-row-action";

interface ProductCardProps {
  product: ProductListItem;
  onArchive?: (product: ProductListItem) => void;
}

export function ProductCard({ product, onArchive }: ProductCardProps) {
  const router = useRouter();

  const badge =
    product.supplier_name?.split(" ")[0].toUpperCase() ||
    product.brand?.substring(0, 5).toUpperCase() ||
    "API";

  const isVgProduct = (product.supplier_name || "").toLowerCase().includes("visual graphics");
  const isPushed = Boolean(product.ops_product_id);

  return (
    <div
      onClick={() => router.push(`/products/${product.id}`)}
      className="group bg-white border border-[#cfccc8] rounded-[10px] overflow-hidden
                 shadow-[4px_5px_0_rgba(30,77,146,0.08)] cursor-pointer
                 transition-all duration-300 cubic-bezier-[0.175,0.885,0.32,1.275]
                 hover:-translate-x-[3px] hover:-translate-y-[5px] hover:scale-[1.02]
                 hover:shadow-[12px_16px_0_rgba(30,77,146,0.08)] hover:border-[#1e4d92]"
    >
      {/* Card header – image area */}
      <div className="relative h-[180px] bg-[#ebe8e3] flex items-center justify-center border-b border-[#cfccc8]">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.product_name}
            className="w-full h-full object-contain p-3"
          />
        ) : (
          <div className="px-6 pt-12 pb-10 text-center select-none pointer-events-none opacity-20 group-hover:opacity-30 transition-opacity">
            <span className="text-[20px] font-black uppercase tracking-tight text-[#1e1e24] line-clamp-2">
              {product.product_name}
            </span>
          </div>
        )}
        {/* Origin tag - top-left: distinguishes supplier-sourced vs VG-owned products */}
        <div
          className={`absolute top-3 left-3 px-[10px] py-[4px] rounded font-mono text-[10px] font-bold shadow-sm z-10 ${
            isVgProduct
              ? "bg-[#1e4d92] text-white border border-[#1e4d92]"
              : "bg-white/90 backdrop-blur-sm text-[#484852] border border-[#cfccc8]"
          }`}
          title={isVgProduct ? "Owned by Visual Graphics OPS" : `Sourced from ${product.supplier_name}`}
        >
          {isVgProduct ? "★ VG PRODUCT" : "↓ SOURCE"}
        </div>
        {/* Supplier badge - bottom-right */}
        <div className="absolute bottom-3 right-3 px-[10px] py-[4px] bg-white/90 backdrop-blur-sm border border-[#cfccc8] rounded
                        font-mono text-[10px] font-bold text-[#1e4d92] shadow-sm z-10">
          {badge}
        </div>
      </div>

      {/* Card body */}
      <div className="p-5">
        <div className="text-[16px] font-extrabold leading-[1.3] mb-2 text-[#1e1e24]">
          {product.product_name}
        </div>
        <div className="flex items-center gap-2 text-[12px] text-[#888894]">
          <span className="text-[#1e4d92] font-bold">
            {product.brand || "Generic"}
          </span>
          <span>·</span>
          <span className="font-mono">{product.supplier_sku}</span>
        </div>
      </div>

      {/* Card footer */}
      <div className="flex items-center justify-between px-5 py-3 bg-[#f9f7f4] border-t border-dashed border-[#cfccc8]">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase text-[#484852]">
            {product.product_type}
          </span>
          {/* Push status pill */}
          <span
            className={`inline-flex items-center gap-1 px-[8px] py-[2px] rounded-full text-[10px] font-bold uppercase ${
              isPushed
                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                : "bg-stone-100 text-stone-500 border border-stone-200"
            }`}
            title={isPushed ? `Published to OPS (id: ${product.ops_product_id})` : "Not yet published to OPS"}
          >
            <span
              className={`inline-block w-[6px] h-[6px] rounded-full ${
                isPushed ? "bg-emerald-500" : "bg-stone-400"
              }`}
            />
            {isPushed ? "Published" : "Not pushed"}
          </span>
        </div>
        <div className="flex items-center gap-3">
          {/* Price range */}
          {product.price_min != null && (
            <span className="font-mono text-[12px] font-semibold text-[#247a52]">
              {product.price_max != null && product.price_max !== product.price_min
                ? `$${Number(product.price_min).toFixed(2)}–$${Number(product.price_max).toFixed(2)}`
                : `$${Number(product.price_min).toFixed(2)}`}
            </span>
          )}
          <span className="font-mono text-[12px] font-semibold text-[#1e4d92]">
            {product.variant_count} variants
          </span>
          {onArchive ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onArchive(product);
              }}
              className="text-[11px] font-semibold text-[#b93232] hover:underline cursor-pointer"
            >
              Archive
            </button>
          ) : null}
        </div>
      </div>

      {/* Action row */}
      <div
        className="flex items-center justify-end px-5 py-3 bg-white border-t border-[#cfccc8]"
        onClick={(e) => e.stopPropagation()}
      >
        <PushRowAction productId={product.id} productName={product.product_name} />
      </div>

      {/* Action row — Push to OPS */}
      <div
        className="flex items-center justify-end px-5 py-2 bg-white border-t border-[#cfccc8]"
        onClick={(e) => e.stopPropagation()}
      >
        <PushRowAction productId={product.id} productName={product.product_name} />
      </div>
    </div>
  );
}
