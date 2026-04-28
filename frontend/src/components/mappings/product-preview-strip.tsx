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
    <div className="flex gap-3">
      {products.map((p) => (
        <div
          key={p.id}
          className="bg-white rounded border border-[#cfccc8] overflow-hidden w-36"
        >
          {p.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={p.image_url}
              alt={p.product_name}
              className="w-full h-28 object-contain bg-[#ebe8e3]"
            />
          ) : (
            <div className="w-full h-28 bg-[#ebe8e3] flex items-center justify-center text-[10px] text-[#b4b4bc] font-bold uppercase">
              No image
            </div>
          )}
          <div className="p-2">
            <div className="text-[11px] font-bold text-[#1e1e24] truncate">
              {p.product_name}
            </div>
            <div className="text-[10px] font-mono text-[#888894]">{p.supplier_sku}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
