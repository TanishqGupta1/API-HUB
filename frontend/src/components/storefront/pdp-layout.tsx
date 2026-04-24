"use client";

import Link from "next/link";
import type { ReactNode } from "react";

interface Props {
  breadcrumbCategory?: { id: string; name: string } | null;
  breadcrumbProduct: string;
  gallery: ReactNode;
  info: ReactNode;
  description?: ReactNode;
  related?: ReactNode;
}

export function PDPLayout({ breadcrumbCategory, breadcrumbProduct, gallery, info, description, related }: Props) {
  return (
    <div className="flex flex-col gap-6 pb-12 max-w-[1200px] mx-auto w-full">
      <div className="flex items-center gap-2 text-[12px] text-[#888894]">
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

      <div className="grid grid-cols-1 lg:grid-cols-[6fr_4fr] gap-10">
        <div>{gallery}</div>
        <div className="lg:sticky lg:top-[80px] lg:self-start">{info}</div>
      </div>

      {description && (
        <section className="pt-2">{description}</section>
      )}

      {related && (
        <section className="pt-6 border-t border-dashed border-[#cfccc8]">{related}</section>
      )}
    </div>
  );
}
