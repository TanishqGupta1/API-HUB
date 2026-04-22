"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ProductListItem } from "@/lib/types";
import { StorefrontProductCard } from "./storefront-product-card";

interface Props {
  supplierId: string;
  categoryId: string | null;
  excludeId: string;
}

export function RelatedProducts({ supplierId, categoryId, excludeId }: Props) {
  const [items, setItems] = useState<ProductListItem[]>([]);
  const [label, setLabel] = useState("Related products");

  useEffect(() => {
    (async () => {
      const url = categoryId
        ? `/api/products?supplier_id=${supplierId}&category_id=${categoryId}&limit=16`
        : `/api/products?supplier_id=${supplierId}&limit=16`;
      setLabel(categoryId ? "Related products" : "Other VG products");
      try {
        const list = await api<ProductListItem[]>(url);
        setItems(list.filter((p) => p.id !== excludeId).slice(0, 8));
      } catch {
        setItems([]);
      }
    })();
  }, [supplierId, categoryId, excludeId]);

  if (items.length === 0) return null;

  return (
    <div>
      <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852] mb-3">{label}</div>
      <div className="flex gap-4 overflow-x-auto pb-2 -mx-2 px-2">
        {items.map((p) => (
          <div key={p.id} className="shrink-0 w-[180px]">
            <StorefrontProductCard product={p} />
          </div>
        ))}
      </div>
    </div>
  );
}
