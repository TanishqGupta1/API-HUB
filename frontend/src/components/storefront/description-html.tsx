"use client";

import { useEffect, useState } from "react";

interface Props {
  html: string | null;
}

export function DescriptionHtml({ html }: Props) {
  const [clean, setClean] = useState<string | null>(null);

  useEffect(() => {
    if (!html) { setClean(null); return; }
    import("dompurify").then(({ default: DOMPurify }) => {
      setClean(DOMPurify.sanitize(html, {
        ALLOWED_TAGS: ["p", "br", "strong", "em", "ul", "ol", "li", "a", "span", "h1", "h2", "h3", "h4", "h5", "h6"],
        ALLOWED_ATTR: ["href", "target", "rel"],
      }));
    });
  }, [html]);

  if (!clean) return null;

  return (
    <div>
      <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852] mb-3">Description</div>
      <div
        className="prose-storefront text-[14px] leading-[1.7] text-[#1e1e24]"
        dangerouslySetInnerHTML={{ __html: clean }}
      />
    </div>
  );
}
