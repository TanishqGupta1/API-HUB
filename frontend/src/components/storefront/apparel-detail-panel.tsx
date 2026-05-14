"use client";

import { useState } from "react";
import type { Product, Variant } from "@/lib/types";
import type { ReactNode } from "react";
import { VariantPicker } from "@/components/storefront/variant-picker";
import { PriceBlock } from "@/components/storefront/price-block";
import { PriceTierTable } from "@/components/storefront/price-tier-table";

interface Props {
  product: Product;
  cta?: ReactNode;
  onColorChange?: (color: string) => void;
}

export function ApparelDetailPanel({ product, cta, onColorChange }: Props) {
  const [selectedVariantId, setSelectedVariantId] = useState<string | null>(
    product.variants[0]?.id ?? null,
  );
  const selected: Variant | null =
    product.variants.find((v) => v.id === selectedVariantId) ?? null;

  return (
    <div className="flex flex-col gap-6">
      <PriceBlock variant={selected} fallback={product.variants} adjustment={0} />

      {product.variants.length > 0 && (
        <div className="py-5 border-t border-dashed border-[#cfccc8]">
          <VariantPicker
            variants={product.variants}
            selectedVariantId={selectedVariantId}
            onSelect={setSelectedVariantId}
            onColorChange={onColorChange}
          />
        </div>
      )}

      {/* CTA slot — rendered right after variant selection */}
      {cta}

      {selected ? (
        <div className="border-t border-dashed border-[#cfccc8] pt-5">
          <PriceTierTable tiers={selected.prices} />
        </div>
      ) : null}

      {product.apparel_details ? (
        <ApparelMeta details={product.apparel_details} />
      ) : null}
    </div>
  );
}

function ApparelMeta({
  details,
}: {
  details: NonNullable<Product["apparel_details"]>;
}) {
  const fabricEntries = Object.entries(details.fabric_specs ?? {});
  return (
    <div className="pt-5 border-t border-dashed border-[#cfccc8] flex flex-col gap-3">
      <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#888894]">
        Specs
      </div>
      <div className="flex flex-wrap gap-2">
        {details.apparel_style ? <Badge>{details.apparel_style}</Badge> : null}
        {details.is_closeout ? <Badge tone="warn">Closeout</Badge> : null}
        {details.is_hazmat ? <Badge tone="warn">Hazmat</Badge> : null}
        {details.is_caution ? <Badge tone="warn">Caution</Badge> : null}
      </div>
      {fabricEntries.length > 0 ? (
        <ul className="grid grid-cols-2 gap-1 font-mono text-[11px] text-[#484852]">
          {fabricEntries.map(([k, v]) => (
            <li key={k}>
              {k}: {String(v)}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function Badge({
  children,
  tone = "default",
}: {
  children: React.ReactNode;
  tone?: "default" | "warn";
}) {
  const cls =
    tone === "warn"
      ? "border-[#b93232] bg-[#fdeded] text-[#b93232]"
      : "border-[#1e4d92] bg-[#eef4fb] text-[#1e4d92]";
  return (
    <span
      className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase border ${cls}`}
    >
      {children}
    </span>
  );
}
