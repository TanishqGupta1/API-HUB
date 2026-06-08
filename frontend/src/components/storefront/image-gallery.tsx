"use client";

import { useEffect, useMemo, useState } from "react";
import { SafeImage as Image } from "@/components/common/safe-image";
import type { ProductImage } from "@/lib/types";

interface ImageGalleryProps {
  images: ProductImage[];
  fallbackUrl: string | null;
  alt: string;
  selectedColor?: string | null;
}

export function ImageGallery({ images, fallbackUrl, alt, selectedColor }: ImageGalleryProps) {
  const [activeIdx, setActiveIdx] = useState(0);

  const list = useMemo(() => {
    if (images.length > 0) return images;
    if (fallbackUrl) return [
      {
        id: "fallback",
        url: fallbackUrl,
        image_type: "front",
        color: null,
        sort_order: 0,
      } as ProductImage,
    ];
    return [];
  }, [images, fallbackUrl]);

  // When selected color changes, jump to the first image that matches
  useEffect(() => {
    if (!selectedColor || list.length === 0) return;
    const idx = list.findIndex(
      (img) => img.color?.toLowerCase() === selectedColor.toLowerCase()
    );
    if (idx >= 0) setActiveIdx(idx);
  }, [selectedColor, list]);

  useEffect(() => {
    if (list.length < 2) return;
    const onKey = (e: KeyboardEvent) => {
      const tag = document.activeElement?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowRight") setActiveIdx((i) => (i + 1) % list.length);
      if (e.key === "ArrowLeft") setActiveIdx((i) => (i - 1 + list.length) % list.length);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [list.length]);

  if (list.length === 0) {
    return (
      <div className="w-full h-full bg-[#ebe8e3] border border-[#cfccc8] rounded-[10px] flex items-center justify-center">
        <span className="text-[11px] font-bold uppercase tracking-[0.1em] text-[#b4b4bc]">
          No images
        </span>
      </div>
    );
  }

  const active = list[Math.min(activeIdx, list.length - 1)];

  return (
    <div className="flex flex-col h-full gap-2">
      {/* Main image — grows to fill available height */}
      <div className="flex-1 min-h-0 flex flex-col gap-1">
        <a
          href={active.url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Open ${alt} full size`}
          className="relative flex-1 min-h-0 w-full bg-[#ebe8e3] border border-[#cfccc8] rounded-[10px] overflow-hidden flex items-center justify-center cursor-zoom-in"
        >
          <Image src={active.url} alt={alt} fill sizes="(max-width: 768px) 100vw, 50vw" className="object-contain p-8" />
        </a>
        <div className="text-[10px] font-mono uppercase tracking-[0.1em] text-[#888894] text-center">
          {active.image_type}{active.color ? ` · ${active.color}` : ""}
        </div>
      </div>

      {/* Horizontal thumbnail strip below the main image */}
      {list.length > 1 && (
        <div className="flex flex-row gap-2 overflow-x-auto shrink-0 pb-1">
          {list.map((img, idx) => (
            <button
              key={img.id}
              onClick={() => setActiveIdx(idx)}
              className={`shrink-0 w-[60px] h-[60px] border rounded-lg overflow-hidden transition-all
                ${idx === activeIdx
                  ? "border-[#1e4d92] shadow-[0_0_0_2px_#eef4fb]"
                  : "border-[#cfccc8] hover:border-[#1e4d92] opacity-70 hover:opacity-100"
                }`}
            >
              <Image src={img.url} alt="" width={60} height={60} className="w-full h-full object-contain bg-[#f9f7f4] p-1" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
