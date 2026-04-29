"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ProductListItem } from "@/lib/types";

interface Props {
  supplierId: string;
}

/** Thumbnail strip of first 3 products — visual confirmation of mapping target. */
export function ProductPreviewStrip({ supplierId }: Props) {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const rows = await api<ProductListItem[]>(
          `/api/products?supplier_id=${supplierId}&limit=3`,
        );
        setProducts(rows);
      } finally {
        setLoading(false);
      }
    })();
  }, [supplierId]);

  if (loading) {
    return <div className="text-xs text-[#888894]">Loading product previews…</div>;
  }

  if (products.length === 0) {
    return (
      <div className="text-xs text-[#888894]">
        No products yet from this supplier — preview appears after first import.
      </div>
    );
  }

  return (
    <div className="flex gap-4">
      {products.map((p) => (
        <div
          key={p.id}
          className="bg-white rounded-2xl border border-[#f2f0ed] overflow-hidden w-44 hover:border-[#1e4d92] transition-all hover:shadow-xl hover:shadow-blue-900/5 group"
        >
          <div className="h-32 bg-[#f9f7f4] flex items-center justify-center overflow-hidden">
            {p.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={p.image_url}
                alt={p.product_name}
                className="w-full h-full object-contain group-hover:scale-110 transition-transform duration-500"
              />
            ) : (
              <div className="text-[9px] font-black uppercase tracking-widest text-[#cfccc8]">
                No Asset
              </div>
            )}
          </div>
          <div className="p-4 bg-white">
            <div className="text-[11px] font-black text-[#1e1e24] truncate tracking-tight mb-0.5">
              {p.product_name}
            </div>
            <div className="text-[10px] font-mono font-bold text-[#888894]">{p.supplier_sku}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
