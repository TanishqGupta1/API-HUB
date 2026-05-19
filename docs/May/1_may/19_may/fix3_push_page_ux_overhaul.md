# Fix 3 — Push Page UX Overhaul (4 connected fixes)

**Date:** 2026-05-19
**Author:** Vidhi
**Branch:** Vidhi
**Status:** Done (uncommitted)

---

## What type of task is this?

**Frontend — UX fixes to the product push flow.**

---

## Overview

Four separate but connected problems were fixed in the push pipeline UI today. Together they make the push flow usable end-to-end.

---

## Problem 1 — Demo URL crashed with raw UUID error

**URL:** `/products/demo/push?customer_id=demo`

**What happened:** Page showed "Preflight blocked" with raw Pydantic validation error JSON:
```
[{"type":"uuid_parsing","loc":["body","target","customer_id"],"msg":"Input should be a valid UUID..."}]
```

**Root cause:** `NEXT_PUBLIC_PHASE8_LIVE=true` in `.env.local` means the push hook calls the real backend. The backend schema `PushRequestTarget.customer_id: UUID` rejected `"demo"` as an invalid UUID.

**Fix:** Added UUID validation in `use-push-preview.ts` — if either ID is not a valid UUID, use fixtures regardless of live mode:

```typescript
const _UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-...-[0-9a-f]{12}$/i;

// In usePushDryRun:
if (IS_MOCK_MODE || !_isUuid(customerId) || !_isUuid(productId)) {
  // return fixture data — no backend call
}
```

Real product pages with actual UUIDs still call the live backend. Only demo/placeholder URLs fall back to fixtures.

---

## Problem 2 — "Publish to OPS" showed raw JSON on product page

**What happened:** Clicking "Publish to OPS" showed a block of raw JSON in a red box directly on the product detail page:
```
{"status":"error","code":"PREFLIGHT_BLOCKER","message":"no markup rule matches...","details":{...}}
```

**Root cause:** `PublishButton` was calling `/api/integrations/admin/push-requests` directly and showing `err.message` in the UI. When the backend returns a 422 with a JSON body, `api.ts` does `JSON.stringify(detail)` which becomes the full raw JSON string.

**Fix:** Changed `PublishButton` to navigate to the push preview page instead of calling the API directly:

```typescript
function go() {
  const params = new URLSearchParams({ customer_id: customerId });
  if (supplierSlug) params.set("supplier_slug", supplierSlug);
  router.push(`/products/${productId}/push?${params}`);
}
```

The push preview page already has proper preflight error display — no need to duplicate it.

---

## Problem 3 — Push page showed blank page on preflight failure

**What happened:** When preflight failed, the entire push page was replaced by a bare red error card — no header, no "Back to product" link, no context. Looked broken.

**Root cause:** The page had an early return:
```typescript
if (dryRunError && !payload) {
  return <ErrorCard ... />;   // ← replaced entire page
}
```

**Fix:** Removed the early return. The preflight error is now rendered inline inside the full page layout:
- Header always shows ("Push to OPS" + back link)
- Error card shows below the header
- `PreviewPanel` and `DryRunControls` are hidden when there is an error (nothing to show)

---

## Problem 4 — Wrong customer selected by default

**What happened:** "Publish to OPS" defaulted to the first active customer in the DB — a test fixture called "Test Customer" with no markup rules. "Visual Graphics" was selected in the top bar but ignored.

**Root cause:** `PublishButton` was calling `/api/customers` and picking `list.find(c => c.is_active)` — the first active customer, regardless of what was selected in the global customer context.

**Fix:** Updated `PublishButton` to use `useSelectedCustomer()` hook as the default:

```typescript
const { selectedCustomerId } = useSelectedCustomer();

// In useEffect:
const preferred = active.find((c) => c.id === selectedCustomerId) ?? active[0];
if (preferred) setCustomerId(preferred.id);
```

Now if Visual Graphics is selected in the top bar, the push goes to Visual Graphics by default.

---

## End result

After all four fixes, the full flow works:

1. Open any product → click **Publish to OPS** → navigates to push page with correct customer
2. Push page shows **"Push to OPS"** header + back link
3. Preflight runs against the real backend
4. If blocked → clean error card with message, field, and suggestion inside the full layout
5. If passed → PreviewPanel + SEND DRY-RUN / SEND TO OPS (LIVE!) buttons appear

---

## Files changed

| File | Change |
|------|--------|
| `frontend/src/lib/use-push-preview.ts` | UUID check before API call; fallback to fixtures for non-UUID IDs |
| `frontend/src/components/products/publish-button.tsx` | Navigate to push page instead of calling API; use selected customer as default |
| `frontend/src/app/(admin)/products/[id]/push/page.tsx` | Preflight error inline in full layout; hide PreviewPanel/DryRunControls on error |

---

## Manual Test Steps

### Demo URL (should show fixtures, no error)
1. Go to `http://localhost:3000/products/demo/push?customer_id=demo`
2. Should show Push to OPS page with fixture data — no UUID error

### Real product push (should use correct customer)
1. Select **Visual Graphics** in the top bar
2. Go to any product → click **Publish to OPS**
3. URL should contain `customer_id=c665d5ee-...` (Visual Graphics UUID)
4. If preflight fails → full page with header + red error card
5. If preflight passes → SEND DRY-RUN button appears
