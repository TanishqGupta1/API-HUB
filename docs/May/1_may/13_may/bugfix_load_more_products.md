# Bug Fix — Load More Products Button Not Working

**Owner:** Vidhi
**Status:** Fixed
**Date:** 2026-05-13
**File:** `frontend/src/app/(admin)/products/page.tsx`

---

## What was the bug?

The **Load More Products** button on the Product Catalog page was visible but completely non-functional. Clicking it did nothing — no new products loaded, no network request fired, no feedback to the user.

---

## Why is it important?

The catalog currently has **126 products** across 5 suppliers and is growing. The page fetches a maximum of 50 products per load. Without a working Load More button:

- Operators can only see the first 50 products — the rest are invisible
- Products that were recently synced (and sorted to the bottom) can never be found
- Pushing a product to OPS requires finding it on this page first — so hidden products can never be pushed
- As the catalog grows to hundreds or thousands of products this becomes a critical blocker

---

## Root Cause

The button was a **placeholder** — it had no `onClick` handler and was commented as `{/* Pagination (placeholder) */}` in the code:

```tsx
// Before fix — button does nothing
<button className="...">
    Load More Products
</button>
```

The page also had no pagination state — it always fetched exactly 50 products with a hardcoded `limit: "50"` and no `skip` parameter. There was no concept of "how many have already loaded" or "are there more to fetch."

---

## What was fixed

### Added pagination state

```tsx
const [offset, setOffset] = useState(0);
const [hasMore, setHasMore] = useState(true);
const [loadingMore, setLoadingMore] = useState(false);
const PAGE_SIZE = 50;
```

### Updated initial fetch to use `skip` + detect end of results

```tsx
api<ProductListItem[]>(`/api/products?limit=50&skip=0`)
  .then((data) => {
    setProducts(data);
    setHasMore(data.length === PAGE_SIZE); // hide button if last page
  })
```

### Added `handleLoadMore` function

Fetches the next page using the current offset, appends results to the existing list, advances the offset, and hides the button when the last page is returned:

```tsx
async function handleLoadMore() {
    const nextOffset = offset + PAGE_SIZE;
    const data = await api(`/api/products?limit=50&skip=${nextOffset}`);
    setProducts((prev) => [...prev, ...data]);
    setOffset(nextOffset);
    setHasMore(data.length === PAGE_SIZE);
}
```

### Wired button with loading state

```tsx
<button
    onClick={handleLoadMore}
    disabled={loadingMore}
>
    {loadingMore ? "Loading..." : "Load More Products"}
</button>
```

---

## Improvements made

| Before | After |
|--------|-------|
| Button visible but does nothing | Button fetches next 50 products and appends them |
| Always loads exactly 50 products | Loads 50 at a time, unlimited pages |
| Button always visible | Button hides automatically when no more products exist |
| No loading feedback | Shows "Loading..." while fetching |
| Changing filters doesn't reset | Filter change resets to page 1 automatically |

---

## Result

Operators can now scroll through the entire product catalog regardless of size. The button disappears cleanly when all products are loaded, and responds immediately with visual feedback on click.
