"use client";

import DOMPurify from "isomorphic-dompurify";

interface Props {
  html: string | null;
}

export function DescriptionHtml({ html }: Props) {
  if (!html) return null;
  const clean = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ["p", "br", "strong", "em", "ul", "ol", "li", "a", "span", "h1", "h2", "h3", "h4", "h5", "h6"],
    ALLOWED_ATTR: ["href", "target", "rel"],
  });

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
