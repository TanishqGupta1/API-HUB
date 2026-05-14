"use client";

import { useEffect, useState } from "react";

interface Props {
  html: string | null;
}

/** Detect plain text (no block-level tags) and split into bullet list */
function hasBlockTags(str: string): boolean {
  return /<(p|ul|ol|li|h[1-6]|br\s*\/?>)/i.test(str);
}

function renderPlainAsFeatures(text: string) {
  // Strip any stray HTML, then split by period+space or newline to get features
  const stripped = text.replace(/<[^>]+>/g, "").trim();
  // Split on ". " but keep multi-sentence groupings reasonable
  const parts = stripped
    .split(/\.\s+/)
    .map((s) => s.trim())
    .filter(Boolean);

  if (parts.length <= 1) {
    return (
      <p className="text-[13px] leading-[1.75] text-[#484852]">{stripped}</p>
    );
  }

  return (
    <ul className="flex flex-col gap-1.5">
      {parts.map((item, i) => (
        <li key={i} className="flex items-start gap-2 text-[13px] text-[#1e1e24] leading-snug">
          <span className="mt-[5px] w-1 h-1 rounded-full bg-[#1e4d92] shrink-0" />
          <span>{item.replace(/\.$/, "")}</span>
        </li>
      ))}
    </ul>
  );
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

  const isPlain = !hasBlockTags(clean);

  return (
    <div>
      <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852] mb-3">
        Description
      </div>
      {isPlain ? (
        renderPlainAsFeatures(clean)
      ) : (
        <div
          className="prose-storefront text-[13px] leading-[1.7] text-[#484852]"
          dangerouslySetInnerHTML={{ __html: clean }}
        />
      )}
    </div>
  );
}
