# Task 6 (Demo Push Pipeline) — Per-Row Push to OPS Button — Detail Guide

**Status:** ✅ Completed on 2026-04-27
**Branch:** `Vidhi`
**Sprint spec:** `plans/tasks/vidhi-tasks.md` (Demo Push Pipeline)
**Plan reference:** `docs/superpowers/plans/2026-04-23-demo-push-pipeline.md` → Task 6
**What you can say in one sentence:** *"I built a compact 'Push to OPS' button that sits on every product card in the catalog grid, opens a dialog for picking the storefront, and fires the n8n push workflow on confirmation — so an operator can push a single product to a single customer without leaving the catalog page."*

---

## 1. What Got Built

| File | What Changed |
|---|---|
| `frontend/src/components/products/push-row-action.tsx` | New component — ~110 lines |
| `frontend/src/components/products/product-card.tsx` | Imported `PushRowAction`, added a new action row in the card footer with `stopPropagation` |

---

## 2. Background — What Is This Task About?

### Task Type
**Frontend component** — TypeScript + React + shadcn/ui Dialog + Tailwind CSS. No backend.

### Why a Per-Row Action?

We already had a full-page **Publish** widget on the product **detail** page (`publish-button.tsx`). It works, but it forces an operator to click into each product just to push it. In the demo flow we want to:

1. Land on `/products` (the catalog grid).
2. Pick a product.
3. Pick a storefront.
4. Push.

The per-row action makes that a 3-click operation — no page navigation needed.

### One Important Surprise — There Is No Table

The plan says:
> "Add an Action `<th>` to the products table header, and a `<td>` per row."

But the actual `/products` page renders a **CSS grid of `ProductCard` components**, not a `<table>`. So the plan's literal instructions don't fit. The implementation embeds the button in the card footer instead — same UX intent, fits the actual layout.

Flagged in the commit message and PR description so reviewers don't think we missed the spec.

---

## 3. The Component — What It Shows

A compact button on each product card. On click it opens a shadcn Dialog with:

| Element | Purpose |
|---|---|
| Product name | Confirms which product the operator is about to push |
| Storefront `<select>` | Lists all customers from `/api/customers`. Inactive ones are disabled in the dropdown. The first active one is preselected. |
| Inline message strip | Shows status: "Triggering push…" → "Push started" or an error message. Monospace font, paper background — matches the Blueprint design system. |
| Cancel + Push buttons | Push is disabled when no customer is picked or while a request is in flight. Auto-closes 1.5s after a successful trigger. |

---

## 4. Component Flow

```
User clicks "Push to OPS" on a card
       ↓
e.stopPropagation()       ← critical: prevents the card's
                            onClick navigation to /products/[id]
       ↓
Dialog opens (open=true)
       ↓
useEffect sees open=true, fetches /api/customers
       ↓
First active customer auto-selected
       ↓
User picks (or accepts) a customer
       ↓
User clicks Push
       ↓
POST /api/n8n/workflows/vg-ops-push-001/trigger?product_id=…&customer_id=…
       ↓
Response.triggered === true → message + auto-close after 1.5s
                       false → message stays so user sees it
       ↓
n8n workflow fires (visible in n8n UI)
```

---

## 5. Code Walkthrough

### Props

```tsx
interface Props {
  productId: string;
  productName: string;
}
```

Just the minimum. Customer list is fetched lazily inside the component — the parent doesn't need to thread it through.

### State

| State | Role |
|---|---|
| `open` | Controls the Dialog's open prop |
| `customers` | Fetched on first open — cached for the lifetime of the open dialog |
| `customerId` | Selected storefront ID |
| `busy` | True while the trigger request is in flight — disables the Push button |
| `message` | The inline status/error string |

### Lazy Customer Fetch

```tsx
useEffect(() => {
  if (!open) return;
  api<Customer[]>("/api/customers")
    .then((list) => {
      setCustomers(list);
      const first = list.find((c) => c.is_active);
      if (first) setCustomerId(first.id);
    })
    .catch((e) => setMessage(e instanceof Error ? e.message : String(e)));
}, [open]);
```

Why lazy? With ~thousands of cards on the grid, fetching customers eagerly per card would be hundreds of identical requests. Fetch-on-open keeps the cost zero until the operator actually needs it.

### The Trigger Call

```tsx
const res = await api<{ triggered: boolean }>(
  `/api/n8n/workflows/vg-ops-push-001/trigger?product_id=${productId}&customer_id=${customerId}`,
  { method: "POST" },
);
```

Reuses the established `api<T>()` helper from `lib/api.ts` — it auto-attaches `X-Ingest-Secret` if `NEXT_PUBLIC_INGEST_SECRET` is set, and surfaces backend errors as thrown `Error`s with the response status + body. Same pattern as `publish-button.tsx`.

---

## 6. The Card Wiring

`product-card.tsx`'s root `<div>` has `onClick={() => router.push(...)}` — the whole card is a giant link. That's a problem for an embedded button: every click on the dialog trigger or inside the dialog content would *also* fire the navigation.

Two fixes:

1. **Wrap the action row in a `div` with `onClick={(e) => e.stopPropagation()}`** so the entire footer doesn't bubble.
2. **Also `stopPropagation` on the trigger button and the DialogContent** as a belt-and-braces guard for portal/event-bubbling edge cases (shadcn Dialog uses Radix's portal, so events leave the DOM tree the card lives in — but mousedown/click on the trigger still bubbles before that).

Result: clicking the button opens the dialog, clicking elsewhere on the card still navigates to the product detail page.

---

## 7. Design System Consistency

| Element | Value | Why |
|---|---|---|
| Trigger button | `border-[#1e4d92] text-[#1e4d92]` outline | Blueprint blue accent — matches existing `publish-button.tsx` |
| Push (confirm) button | `bg-[#1e4d92] hover:bg-[#173d74]` | Same primary blue used in the rest of the admin |
| Dialog | shadcn `Dialog` + `max-w-md` | Same component used elsewhere — no new UI primitives |
| Inline status | `bg-[#f9f7f4] border-[#ebe8e3] text-[#484852] font-mono` | Paper palette + monospace = matches the rest of the admin's status messaging |

---

## 8. Edge Cases Handled

| Scenario | Behavior |
|---|---|
| `/api/customers` returns empty list | Dropdown shows only "Select Storefront…" — Push stays disabled |
| All customers are inactive | First-active fallback finds none, dropdown options are all disabled, Push stays disabled |
| User clicks Push without selecting | Inline message: "Pick a storefront first"; no request fires |
| Trigger returns `{ triggered: false }` | Dialog stays open, message reads "Push failed." — user can pick a different storefront and retry |
| Trigger throws (500, network error, etc.) | Caught in the try/catch — error message displayed inline, busy flag cleared |
| User clicks Cancel mid-request | Dialog closes; the in-flight request still completes server-side (n8n trigger is fire-and-forget — that's expected) |
| Card click vs. button click | `stopPropagation` keeps them separate — no accidental navigation |

---

## 9. Build Verification

| Check | Result |
|---|---|
| Component imports resolve (`Dialog`, `Button`, `Customer`, `api`) | ✅ All exist in this repo at expected paths |
| Workflow ID `vg-ops-push-001` matches the n8n JSON | ✅ Same workflow Task 5 just edited |
| Mirrors existing pattern in `publish-button.tsx` line-for-line on the trigger call | ✅ |

`npx tsc --noEmit` not run here — `node_modules` not installed in this clone. Run locally:

```bash
cd frontend
npm install
npx tsc --noEmit 2>&1 | grep -E "push-row-action|product-card" | head -5
```

Expected: no errors mentioning either file. Pre-existing errors elsewhere in the tree are unrelated.

### Manual Smoke Test (After Local Setup)

1. `docker compose up -d` — Postgres + API + n8n
2. `cd frontend && npm run dev`
3. Open `http://localhost:3000/products`.
4. Each product card now has a "Push to OPS" button in its footer row.
5. Click → dialog opens → customer dropdown populated.
6. Pick a customer → Push.
7. Inline message: "Triggering push…" → "Push started. Check history."
8. Open `http://localhost:5678` → confirm a new execution of `Hub → OPS Push`.

---

## 10. What Comes Next

| Next Task | What It Adds | Blocked? |
|---|---|---|
| **Sinchana Task 3** — `/api/push-mappings` | Without this, the n8n workflow's POST step (Task 5) 404s — but the trigger still fires + you'd see the failure in n8n executions | 🔴 Owned by Sinchana |
| **OPS beta option mutations** | When they ship, replace the Stub Apply Options node — no frontend change needed | 🔴 Waiting on OPS |
| **Task 7 — Ingest 5–10 SanMar products** | Real products to actually demo against | ❌ Owned by Urvashi |
