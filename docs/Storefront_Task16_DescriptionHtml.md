# Storefront Task 16 — DescriptionHtml Sanitized Renderer

Adds a safe HTML description renderer to the storefront PDP. Product descriptions from suppliers often contain HTML markup — this component sanitizes them to a safe whitelist before rendering, preventing XSS while preserving formatting like bold, lists, and links.

Last updated: 2026-04-21

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/components/storefront/description-html.tsx` | NEW — sanitized HTML renderer component |
| `frontend/src/app/globals.css` | EDIT — added `.prose-storefront` CSS rules |
| `frontend/package.json` + `frontend/package-lock.json` | EDIT — added `isomorphic-dompurify` dependency |

---

## Why This Task Exists

Supplier product descriptions (from SanMar, S&S Activewear, etc.) arrive as raw HTML strings — e.g. `<p>100% cotton. <strong>Pre-shrunk.</strong></p>`. Rendering these directly with `dangerouslySetInnerHTML` without sanitization is an XSS vulnerability — a malicious supplier or corrupted data could inject `<script>` tags or event handlers.

`isomorphic-dompurify` sanitizes the HTML to a strict whitelist on both server and client, so the component is safe to use in Next.js (SSR + CSR). The `.prose-storefront` CSS class provides clean typography styling for the sanitized output.

---

## What Was Built

### Component — `description-html.tsx`

```tsx
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
```

**Sanitization rules:**
- **Allowed tags:** `p`, `br`, `strong`, `em`, `ul`, `ol`, `li`, `a`, `span`, `h1`–`h6`
- **Allowed attributes:** `href`, `target`, `rel` only
- Everything else (e.g. `<script>`, `onclick`, `style`, `class`, `id`) is stripped

### CSS — `.prose-storefront` rules in `globals.css`

```css
.prose-storefront p { margin-bottom: 0.9em; }
.prose-storefront strong { font-weight: 700; color: #1e1e24; }
.prose-storefront a { color: #1e4d92; text-decoration: underline; }
.prose-storefront ul { padding-left: 1.25em; list-style: disc; margin-bottom: 0.9em; }
.prose-storefront ol { padding-left: 1.25em; list-style: decimal; margin-bottom: 0.9em; }
.prose-storefront li { margin-bottom: 0.3em; }
```

---

## How to Use

Import and drop into any page that has an HTML description string:

```tsx
import { DescriptionHtml } from "@/components/storefront/description-html";

<DescriptionHtml html={product.description} />
```

- Pass `null` or an empty string → renders nothing (safe no-op).
- Pass any HTML string → sanitized and rendered with `.prose-storefront` styles.

---

## Testing

Tested on the PDP page (`/storefront/vg/product/:id`) with an HTML description seeded into the PC61 product:

```html
<p>A <strong>customer favorite</strong>, this value-priced tee hits the mark on quality and comfort.</p>
<ul>
  <li>100% cotton pre-shrunk jersey</li>
  <li>Available in <em>50+ colors</em></li>
  <li>Sizes XS–4XL</li>
</ul>
<p>Perfect for <a href="#" target="_blank" rel="noopener noreferrer">screen printing</a> and embroidery.</p>
```

**Results:**
- Bold text rendered correctly (`font-weight: 700`) ✅
- Bullet list rendered with disc style and correct indentation ✅
- Link rendered in blueprint blue (`#1e4d92`) with underline ✅
- No raw HTML tags visible in the browser ✅
- XSS tags stripped — `<script>`, `onclick`, `style` attributes removed by DOMPurify ✅

---

## Acceptance Criteria (from `plans/tasks/vidhi-tasks.md`)

- [x] `npm install isomorphic-dompurify`
- [x] Sanitize whitelist: `p, br, strong, em, ul, ol, li, a, span, h1–h6`; attrs: `href, target, rel`
- [x] Add `.prose-storefront` CSS rules to `globals.css`
