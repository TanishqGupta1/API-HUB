# Task 7 — Build push-history.tsx Component — Detail Guide

**Status:** ✅ Completed on 2026-04-24
**Branch:** `Vidhi`
**What you can say in one sentence:** *"I built a reusable React component that shows the full push history for a product — every time it was pushed to a customer storefront, whether it succeeded or failed, and the error message if it failed."*

---

## 1. What Got Built

| File | What Changed |
|---|---|
| `frontend/src/components/products/push-history.tsx` | New component — 253 lines |
| `frontend/src/app/(admin)/products/[id]/page.tsx` | Replaced inline table with `<PushHistory />` component |

---

## 2. Background — What Is This Task About?

### Task Type
**Frontend component** — TypeScript + React + Tailwind CSS. No backend changes.

### What Is the Push History?

Every time we push a product from our database to a customer's OPS storefront, the system writes an entry to the `push_log` table with:
- Which product was pushed
- Which customer it went to
- Whether it succeeded or failed
- The error message if it failed
- When it happened

Before this task, the product detail page showed only the **latest** status per customer — not the full history. You couldn't see *"we tried pushing this yesterday, it failed, then today it succeeded"*.

### Why Did It Need to Be a Separate Component?

The existing product page already had 70 lines of inline code for the "Storefront Publish Status" table. Problems with that:

1. **Not reusable** — if we want to show push history anywhere else (e.g. a dashboard), we'd have to copy-paste it
2. **Page too long** — the file was already 443 lines and hard to read
3. **No full history** — only showed the latest status, not the log

Task 7 extracts the table into a proper component AND adds the full log view.

---

## 3. The Component — What It Shows

The component displays **two tables stacked vertically**:

### Table 1 — Storefront Publish Status (Current State)
Shows the **latest** push attempt for each customer. One row per customer.

| Column | Shows |
|---|---|
| Storefront | Customer name |
| Status | ✅ Published / ❌ Failed / ⚪ Pending |
| Last Pushed | Date + time of latest attempt |
| OPS Product ID | The ID OPS assigned to this product |
| Action | "Push Now" button to push again |

### Table 2 — Push Log History (Full Log)
Shows **every push attempt ever** for this product, newest first.

| Column | Shows |
|---|---|
| Storefront | Customer name for that attempt |
| Status | Same badges as Table 1 |
| When | Full timestamp |
| OPS Product ID | What OPS returned |
| Error | Error message if failed (truncated to 60 chars with full message on hover) |

---

## 4. How the Component Works — Simple Flow

```
Page loads
    ↓
Component fetches /api/push-log?limit=200
    ↓
Filters entries to only this product_id
    ↓
Sorts newest → oldest
    ↓
Splits data:
  • Latest per customer → Table 1
  • All entries → Table 2
    ↓
Renders both tables with status badges
```

---

## 5. Exact Code Structure

### Props the Component Accepts

```tsx
interface Props {
  productId: string;           // Which product to show history for
  customers: Customer[];       // List of customers for push buttons
  pushing: string | null;      // Customer_id currently being pushed
  onPush: (customerId: string) => void;  // Callback when user clicks Push Now
}
```

The parent page passes these down. The component doesn't manage push state itself — it just displays data and calls `onPush()` when the button is clicked. This is called the **"dumb component" pattern** — it's told what to do, it doesn't make decisions.

### The StatusBadge Helper Component

Instead of copy-pasting badge styles 10 times, there's one small inner component:

```tsx
function StatusBadge({ status }: { status: string }) {
  if (status === "pushed")  → green "Published" pill
  if (status === "failed")  → red "Failed" pill
  else                      → gray "Pending" pill
}
```

This is reused in both tables, ensuring colors stay consistent.

### Data Fetching

```tsx
const fetchLogs = async () => {
  const all = await api<PushLogEntry[]>("/api/push-log?limit=200");
  const filtered = all.filter((entry) => entry.product_id === productId);
  filtered.sort(
    (a, b) => new Date(b.pushed_at).getTime() - new Date(a.pushed_at).getTime()
  );
  setLogs(filtered);
};

useEffect(() => {
  fetchLogs();
}, [productId]);
```

**What this does:**
1. Calls the existing backend endpoint `/api/push-log` (already available)
2. Filters results to only entries for this product — done client-side because the backend doesn't have a product-specific filter endpoint
3. Sorts newest first using the `pushed_at` timestamp
4. Refetches automatically if the productId changes

**Why `limit=200`?** It's a balance — enough to cover months of activity for a typical product, but not so many that the page is slow to load.

---

## 6. How It Connects to the Parent Page

**Before Task 7** — product detail page had 70 lines of inline JSX for the status table, hardcoded in place.

**After Task 7** — just 6 lines at the bottom of the page:

```tsx
<PushHistory
  productId={id}
  customers={customers}
  pushing={pushing}
  onPush={handlePush}
/>
```

The parent page still owns:
- The `handlePush` function (calls `/api/push-log` to record the push)
- The `customers` list (fetched once in `fetchData`)
- The `pushing` state (tracks which customer is mid-push)

The component owns:
- Its own push log fetch
- Its own loading/error states
- Rendering both tables

This split keeps the page focused on the product, and the component focused on push data.

---

## 7. Design System Consistency

The component uses the project's **Blueprint design system** — matches every other table on the site:

| Element | Value |
|---|---|
| Background | `bg-white` |
| Border | `border-[#cfccc8]` (warm grey) |
| Header strip | `bg-[#ebe8e3]` (paper) |
| Shadow | `shadow-[4px_6px_0_rgba(30,77,146,0.08)]` (offset blueprint blue) |
| Success color | `#247a52` (green) |
| Error color | `#b93232` (red) |
| Muted text | `#888894` (warm grey) |
| Primary text | `#1e1e24` (near-black) |
| Font for data | `font-mono` for timestamps, IDs, SKUs |

---

## 8. Edge Cases Handled

| Scenario | What Happens |
|---|---|
| No customers configured | Table 1 shows "No customers configured. Add one in the Customers page" |
| No push history yet | Table 2 shows "No push history yet. Click Push Now above" |
| Backend is down | Table 2 shows red error banner "Could not load push history" |
| Still loading | Table 2 shows "Loading push history..." in monospace |
| Very long error message | Truncated to 60 chars with `…`, full message shown on hover via `title` attribute |

---

## 9. Build Verification

Ran `npm run build` after the changes:

- ✅ TypeScript compiled successfully
- ✅ No ESLint errors in `push-history.tsx`
- ✅ No ESLint errors in `products/[id]/page.tsx`
- ⚠️ Pre-existing error in `/storefront/vg/page.tsx` (useSearchParams without Suspense) — this existed before Task 7, confirmed by `git stash` test
- Warnings about `<img>` tags and `useEffect` dependencies are pre-existing in the codebase — not introduced by this task

---

## 10. What Comes Next

| Next Task | What It Adds | Blocked? |
|---|---|---|
| **Task 8** — Wire real n8n trigger | Replace the mock push in products page with a real call to the n8n workflow webhook | ❌ No — can do now |
| **Task 5** — n8n smoke test | Chain all 4 mutations in a test workflow with real OPS | 🔴 Yes — needs credentials |
