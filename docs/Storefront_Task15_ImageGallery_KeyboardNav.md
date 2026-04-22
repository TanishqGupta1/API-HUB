# Storefront Task 15 — ImageGallery Keyboard Navigation

Adds keyboard navigation (`←` `→` arrow keys) to the storefront product image gallery, and makes the hero image clickable to open the full-size version in a new tab.

Last updated: 2026-04-21

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/components/storefront/image-gallery.tsx` | Added `useEffect` keyboard listener + wrapped hero in `<a>` tag |

**Commit:** `e6bff6a` on branch `Vidhi`

---

## Why This Task Exists

The storefront PDP (Product Detail Page) shows a gallery of product images — one hero image with a thumbnail strip below it. Before this task, users could only switch images by clicking thumbnails. There was no way to use the keyboard to browse images, and no way to view the full-resolution image.

This task adds two UX improvements:
1. **Keyboard navigation** — press `←` or `→` to cycle through product images without touching the mouse.
2. **Click to full-size** — clicking the hero image opens the original full-resolution URL in a new browser tab.

Both are standard e-commerce interactions that users expect on a product page.

---

## What Changed

### 1. Keyboard Navigation (`useEffect` listener)

```tsx
useEffect(() => {
  if (list.length <= 1) return;
  function onKey(e: KeyboardEvent) {
    if (e.key === "ArrowLeft")  setActiveIdx(i => (i - 1 + list.length) % list.length);
    if (e.key === "ArrowRight") setActiveIdx(i => (i + 1) % list.length);
  }
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}, [list.length]);
```

- Only attaches the listener when there are **2 or more images** — skips the overhead for single-image products.
- Uses **modular wrap-around**: pressing `→` on the last image goes back to the first; pressing `←` on the first image jumps to the last.
- Cleans up the event listener on unmount to avoid memory leaks.

### 2. Hero image click → full-size in new tab

```tsx
<a href={active.url} target="_blank" rel="noopener noreferrer" className="w-full h-full flex items-center justify-center">
  <img src={active.url} alt={alt} className="w-full h-full object-contain p-6" />
</a>
```

- Wraps the hero `<img>` in an `<a>` tag pointing to the raw image URL.
- Opens in a new tab (`target="_blank"`) with `rel="noopener noreferrer"` for security.
- The image still renders at `object-contain` size inside the gallery — clicking it reveals the original resolution.

---

## How It Works End-to-End

1. The PDP page passes a `ProductImage[]` array and a `fallbackUrl` to `<ImageGallery>`.
2. The component builds `list` — either the real images array, or a single-item fallback from `image_url`.
3. If `list.length > 1`, the keyboard listener attaches on mount.
4. `activeIdx` state tracks which image is currently shown in the hero.
5. Arrow keys update `activeIdx` (with wrap-around). Thumbnails stay in sync via `idx === activeIdx` highlight.

---

## Testing

The feature was verified against the live app (`localhost:3000/storefront/vg`) with 3 test images seeded directly into the `product_images` table for the PC61 product:

| Slot | URL | Type | Color |
|------|-----|------|-------|
| 0 | cdn.sanmar.com/…/PC61_red_model_front.jpg | front | Red |
| 1 | cdn.sanmar.com/…/PC61_navy_model_front.jpg | front | Navy |
| 2 | cdn.sanmar.com/…/PC61_white_model_back.jpg | back | White |

**Results:**
- Thumbnail strip showed 3 thumbnails ✅
- Label updated (e.g. `FRONT · RED`) as active image changed ✅
- Click on hero image opened CDN URL in new tab ✅
- Keyboard nav: `←`/`→` cycles between images with wrap-around ✅
- Single-image products: keyboard listener not attached (guard works) ✅

> **Note:** SanMar CDN image URLs return 404 without authentication — images appear as broken placeholders in dev. This is expected; real images will load once supplier sync is configured.

---

## Acceptance Criteria (from `plans/tasks/vidhi-tasks.md`)

- [x] `useEffect` listener on `ArrowLeft`/`ArrowRight` cycles the hero image
- [x] Hero wrapped in `<a href={active.url} target="_blank" rel="noopener noreferrer">` so click opens full-size in new tab
