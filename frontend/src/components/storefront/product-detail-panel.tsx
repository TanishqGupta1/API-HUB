"use client";

import type { Product } from "@/lib/types";
import { ApparelDetailPanel } from "@/components/storefront/apparel-detail-panel";
import { PrintDetailPanel } from "@/components/storefront/print-detail-panel";

interface Props {
  product: Product;
}

export function ProductDetailPanel({ product }: Props) {
  if (product.product_type === "print") {
    return <PrintDetailPanel product={product} />;
  }
  return <ApparelDetailPanel product={product} />;
}
