# Task 6 (NEW Sprint) — Per-Row "Push to OPS" Button — Detail Guide

**Status:** ✅ Completed on 2026-04-24
**Branch:** `Vidhi`
**Sprint:** Demo Push Pipeline
**What you can say in one sentence:** *"I added a 'Push to OPS' button to every product card on the catalog page — clicking it opens a dialog where you pick a storefront, and confirming triggers the n8n push workflow for that specific product."*

---

## 1. What Got Built

| File | What Changed |
|---|---|
| `frontend/src/components/products/push-row-action.tsx` | New component — compact dialog-based push button (113 lines) |
| `frontend/src/components/products/product-card.tsx` | Added action row at the bottom of every card with `PushRowAction` |

---

## 2. Background — What Is This Task About?

### Task Type
**Frontend component + page integration** — TypeScript + React + shadcn Dialog. No backend changes.

### What Problem Does This Solve?

Before this task, pushing a product to OPS was a **two-click journey**:
1. Click a product card to open its detail page
2. Use the `PublishButton` at the top to select storefront + push

This meant users had to dive into each product before pushing. For anyone managing many products at once (the common case), that's a lot of clicks.

**After this task:** you can push any product directly from the catalog — no need to open the detail page first.

### Why a Dialog Instead of Just a Button?

We need to know **which storefront** to push to. A customer might have 3 storefronts configured. A direct "Push" button would be ambiguous. The dialog:
1. Opens on button click
2. Shows the product name (so user is sure what they're pushing)
3. Shows a storefront dropdown (pre-selecting the first active one)
4. Has a confirm button that fires the real n8n trigger
5. Auto-closes after success

---

## 3. How It Fits — The Flow

```
User on /products page
    ↓
Clicks "Push to OPS" button on a product card
    ↓
(stopPropagation prevents card click from navigating)
    ↓
Dialog opens
    ↓
useEffect fires — GET /api/customers
    ↓
Dropdown pre-selects first is_active=true customer
    ↓
User confirms → POST /api/n8n/workflows/vg-ops-push-001/trigger
                ?product_id=X&customer_id=Y
    ↓
Backend n8n_proxy looks up the workflow, forwards to webhook
    ↓
n8n runs ops-push workflow → writes to push_log
    ↓
Dialog shows "Push started. Check history." then auto-closes (1.5s)
```

---

## 4. The Component — Key Decisions

### stopPropagation is critical

`ProductCard` has `onClick={() => router.push(...)}` on its outer div. Without stopPropagation, clicking the "Push to OPS" button would:
1. Fire the dialog trigger (good)
2. **AND** navigate the user to the detail page (bad!)

Two `stopPropagation` calls are needed:
1. On the trigger `<Button>` — stops card click when user opens dialog
2. On the `<DialogContent>` — stops clicks inside the dialog from reaching the card

### Fetch customers ONLY when dialog opens

```tsx
useEffect(() => {
  if (!open) return;  // ← skip fetch when dialog is closed
  api<Customer[]>("/api/customers").then(...)
}, [open]);
```

Without the `if (!open) return`, every card on a grid of 50 products would fire its own customers fetch on mount → 50 simultaneous network requests. Gating by `open` means the fetch only happens when a user actually clicks a button.

### Reused pattern from `publish-button.tsx`

The existing `PublishButton` (used on the product detail page) already had the pattern of "fetch customers + pre-select first active + POST to n8n trigger." This new component is the **compact dialog version** of the same idea — different UI, same logic.

---

## 5. Deviation From The Spec (and why)

The task spec said:
> "Find the products **table** `<tr>` row rendering. Add an **Action column**."

But `/products` is actually a **grid of `ProductCard` components**, not a table. The spec was written assuming a different UI structure that doesn't exist in the current codebase.

**What I did instead:** put `PushRowAction` inside `ProductCard` (in a new action row at the bottom of each card, after the type/variant-count footer). This gives the same user-facing behavior — one button per product — without pretending there's a table.

If a table view is added later, the component drops in there with zero changes: `<td><PushRowAction productId={p.id} productName={p.product_name} /></td>` just works.

---

## 6. Exact Code Structure

### Props
```tsx
interface Props {
  productId: string;    // Which product to push
  productName: string;  // Shown in the dialog for confirmation
}
```

### State
```tsx
const [open, setOpen] = useState(false);          // Dialog open/close
const [customers, setCustomers] = useState([]);   // Loaded on open
const [customerId, setCustomerId] = useState(""); // Selected storefront
const [busy, setBusy] = useState(false);          // Request in-flight
const [message, setMessage] = useState(null);     // Status/error text
```

### The trigger call
```tsx
const res = await api<{ triggered: boolean }>(
  `/api/n8n/workflows/vg-ops-push-001/trigger?product_id=${productId}&customer_id=${customerId}`,
  { method: "POST" },
);
```

This hits the existing `n8n_proxy.trigger_workflow` endpoint. The backend:
1. Looks up `vg-ops-push-001` in n8n's REST API
2. Finds its webhook path
3. Forwards the query string params to the webhook
4. Returns `{ triggered: true }` when n8n ack's the call

---

## 7. Edge Cases Handled

| Scenario | What Happens |
|---|---|
| No customers configured | Dropdown shows only "Select Storefront…" — Push button stays disabled |
| Only inactive customers | All options marked `(inactive)` and disabled — Push stays disabled |
| User clicks Push without selecting | Message shows "Pick a storefront first" |
| n8n is down | Message shows the error from the backend (e.g. 503) |
| Workflow ID not found in n8n | Message shows 404 error from backend |
| Workflow inactive | Message shows 409 error from backend |
| Success | Message "Push started. Check history." → dialog auto-closes after 1.5s |

---

## 8. Build Verification

Ran `npx tsc --noEmit` after the changes:

- ✅ No TypeScript errors in `push-row-action.tsx`
- ✅ No TypeScript errors in `product-card.tsx`
- ⚠️ Needed to add explicit `React.MouseEvent` type on the DialogContent onClick handler (implicit `any` error)
- ⚠️ Pre-existing errors elsewhere (e.g. `active-filter-chips SortKey`) — not introduced by this task

---

## 9. Manual Check Steps

1. Start stack: `docker compose up -d postgres n8n` + `uvicorn main:app --reload` + `npm run dev`
2. Open `http://localhost:3000/products`
3. Expect: every product card now has a "Push to OPS" button at the bottom
4. Click the button — dialog opens with product name + storefront dropdown
5. Select a storefront → click "Push"
6. Expect: message "Push started. Check history." + dialog closes after 1.5s
7. Open `http://localhost:5678` — confirm workflow execution appears in n8n

---

## 10. What Comes Next

| Next Task | What It Adds | Blocked? |
|---|---|---|
| **New Task 4** — `/ops-options` backend endpoint | Converts master-option product config to OPS-push shape | 🔴 Yes — needs Sinchana's Task 2 schemas |
| **New Task 5** — n8n workflow: add 4 nodes | Adds ops-options fetch + push-mapping logging to the workflow | 🔴 Yes — needs Sinchana's Task 3 endpoint |
| **Old Task 5** — n8n smoke test | Manually chain mutations with real OPS | 🔴 Yes — needs OPS credentials |
