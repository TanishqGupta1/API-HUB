"use client";

import { useState } from "react";
import type { ProductImage } from "@/lib/types";

interface ImageGalleryProps {
  images: ProductImage[];
  fallbackUrl: string | null;
  alt: string;
}

export function ImageGallery({ images, fallbackUrl, alt }: ImageGalleryProps) {
  const [activeIdx, setActiveIdx] = useState(0);

  const list = images.length > 0
    ? images
    : fallbackUrl
      ? [
          {
            id: "fallback",
            url: fallbackUrl,
            image_type: "front",
            color: null,
            sort_order: 0,
          } as ProductImage,
        ]
      : [];

  if (list.length === 0) {
    return (
      <div className="aspect-square bg-[#ebe8e3] border border-[#cfccc8] rounded-[10px] flex items-center justify-center">
        <span className="text-[11px] font-bold uppercase tracking-[0.1em] text-[#b4b4bc]">
          No images
        </span>
      </div>
    );
  }

  const active = list[Math.min(activeIdx, list.length - 1)];

  return (
    <div className="flex flex-col gap-3">
      <div className="aspect-square bg-[#ebe8e3] border border-[#cfccc8] rounded-[10px] overflow-hidden flex items-center justify-center">
        <img
          src={active.url}
          alt={alt}
          className="w-full h-full object-contain p-6"
        />
      </div>

      {list.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {list.map((img, idx) => (
            <button
              key={img.id}
              onClick={() => setActiveIdx(idx)}
              className={`shrink-0 w-[70px] h-[70px] border rounded-md overflow-hidden transition-all
                ${idx === activeIdx
                  ? "border-[#1e4d92] shadow-[0_0_0_2px_#eef4fb]"
                  : "border-[#cfccc8] hover:border-[#1e4d92]"
                }`}
            >
              <img src={img.url} alt="" className="w-full h-full object-contain bg-[#f9f7f4] p-1" />
            </button>
          ))}
        </div>
      )}

      <div className="text-[10px] font-mono uppercase tracking-[0.1em] text-[#888894]">
        {active.image_type}{active.color ? ` · ${active.color}` : ""}
      </div>
    </div>
  );
}
