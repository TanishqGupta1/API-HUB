"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Category } from "@/lib/types";

export interface BreadcrumbSegment {
  label: string;
  href?: string;
}

export function BreadcrumbBar({
  segments,
}: {
  segments: BreadcrumbSegment[];
}) {
  const router = useRouter();
  return (
    <div
      className="sticky top-[60px] z-20 h-[36px] bg-white border-b border-[#e9e7e3]
                 flex items-center px-6 gap-2 text-[12px] font-medium text-[#484852]"
    >
      <button
        aria-label="Back"
        onClick={() => router.back()}
        className="flex items-center justify-center w-6 h-6 rounded-md
                   text-[#888894] hover:bg-[#f2f0ed] hover:text-[#1e4d92]"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </button>
      <ol className="flex items-center gap-1.5">
        {segments.map((seg, i) => {
          const last = i === segments.length - 1;
          return (
            <li key={i} className="flex items-center gap-1.5">
              {i > 0 && <span className="text-[#cfccc8]">›</span>}
              {seg.href && !last ? (
                <Link href={seg.href} className="hover:text-[#1e4d92]">
                  {seg.label}
                </Link>
              ) : (
                <span className={last ? "text-[#1e1e24] font-semibold" : ""}>{seg.label}</span>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function deriveSegments(
  categories: Category[],
  activeCategoryId: string | null,
  trailing?: BreadcrumbSegment,
): BreadcrumbSegment[] {
  const root: BreadcrumbSegment = { label: "Catalog", href: "/storefront/vg" };
  if (!activeCategoryId) return trailing ? [root, trailing] : [root];

  const byId = new Map(categories.map((c) => [c.id, c]));
  const chain: Category[] = [];
  let cur = byId.get(activeCategoryId);
  while (cur) {
    chain.unshift(cur);
    cur = cur.parent_id ? byId.get(cur.parent_id) : undefined;
  }

  const segs: BreadcrumbSegment[] = [
    root,
    ...chain.map((c) => ({
      label: c.name,
      href: `/storefront/vg?category=${c.id}`,
    })),
  ];
  return trailing ? [...segs, trailing] : segs;
}
