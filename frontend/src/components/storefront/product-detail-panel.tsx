"use client";

import type { ReactNode } from "react";
import type { Product } from "@/lib/types";
import { ApparelDetailPanel } from "@/components/storefront/apparel-detail-panel";
import { PrintDetailPanel } from "@/components/storefront/print-detail-panel";

interface Props {
  product: Product;
  cta?: ReactNode;
  onColorChange?: (color: string) => void;
}

export function ProductDetailPanel({ product, cta, onColorChange }: Props) {
  if (product.product_type === "print") {
    return <PrintDetailPanel product={product} />;
  }
  return <ApparelDetailPanel product={product} cta={cta} onColorChange={onColorChange} />;
}
