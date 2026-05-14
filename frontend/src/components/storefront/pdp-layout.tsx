"use client";

import Link from "next/link";
import type { ReactNode } from "react";

interface Props {
  breadcrumbCategory?: { id: string; name: string } | null;
  breadcrumbProduct: string;
  gallery: ReactNode;
  info: ReactNode;
  options?: ReactNode;
  description?: ReactNode;
  related?: ReactNode;
}

export function PDPLayout({ breadcrumbCategory, breadcrumbProduct, gallery, info, options, description, related }: Props) {
  return (
    <div className="flex h-full gap-0">

      {/* ── LEFT PANEL: Image ── */}
      <div className="flex flex-col w-[55%] border-r border-[#cfccc8] pr-6">
        {/* breadcrumb */}
        <div className="flex items-center gap-2 text-[11px] text-[#888894] mb-3">
          <Link href="/storefront/vg" className="hover:text-[#1e4d92] font-medium">Visual Graphics</Link>
          <span>/</span>
          {breadcrumbCategory ? (
            <>
              <Link href={`/storefront/vg/category/${breadcrumbCategory.id}`}
                className="hover:text-[#1e4d92] font-medium">{breadcrumbCategory.name}</Link>
              <span>/</span>
            </>
          ) : null}
          <span className="font-mono text-[#1e1e24]">{breadcrumbProduct}</span>
        </div>

        {/* image takes all remaining left-panel height */}
        <div className="flex-1 min-h-0">
          {gallery}
        </div>
      </div>

      {/* ── RIGHT PANEL: Details + Description + Related ── */}
      <div className="flex flex-col w-[45%] pl-6 overflow-y-auto">

        {/* Product info + options */}
        <div className="flex-shrink-0">
          {info}
        </div>

        {options && (
          <div className="mt-4 pt-4 border-t border-dashed border-[#cfccc8] flex-shrink-0">
            {options}
          </div>
        )}

        {/* Description — DescriptionHtml owns its own heading */}
        {description && (
          <div className="mt-4 pt-4 border-t border-dashed border-[#cfccc8] flex-shrink-0">
            {description}
          </div>
        )}

        {/* Related products */}
        {related && (
          <div className="mt-4 pt-4 border-t border-dashed border-[#cfccc8]">
            {related}
          </div>
        )}
      </div>

    </div>
  );
}
