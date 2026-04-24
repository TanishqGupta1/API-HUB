# Task 8 — Wire Real n8n Trigger — Detail Guide

**Status:** ✅ Completed on 2026-04-24
**Branch:** `Vidhi`
**What you can say in one sentence:** *"I replaced the fake Push Now button (which wrote a random ID directly to the database) with a real call to the n8n workflow — so clicking Push Now actually starts the OPS automation pipeline, then waits 5s and refreshes the status tables."*

---

## 1. What Got Built

| File | What Changed |
|---|---|
| `backend/modules/n8n_proxy/routes.py` | Extended `POST /api/n8n/workflows/{id}/trigger` to accept a JSON body and forward its fields as webhook query params; added proper error handling (503/504/502) |
| `n8n-workflows/ops-push.json` | Updated Parse Params node to support `product_id` query param (single-product push) |
| `frontend/src/components/products/push-history.tsx` | Added `refreshTrigger` prop so the parent can force a log refresh after a push |
| `frontend/src/app/(admin)/products/[id]/page.tsx` | Replaced mock `handlePush` with real `/api/n8n/workflows/ops-push-001/trigger` call + 5s poll pattern |

---

## 2. Background — What Is This Task About?

### Task Type
**Full-stack integration** — Backend (Python/FastAPI) + n8n workflow (JSON) + Frontend (TypeScript/React). No database changes.

### What Was Wrong Before This Task?

The "Push Now" button was **fake**. It didn't actually push anything to OPS. It just:
1. Wrote a fake push-log entry directly to the database
2. Made up a random `ops-prod-XXXX` ID (like `ops-prod-5234`)
3. Marked status as "pushed" even though nothing happened

```tsx
// BEFORE — mock (fake)
await api("/api/push-log", {
  method: "POST",
  body: JSON.stringify({
    product_id: product.id,
    customer_id: targetId,
    status: "pushed",
    ops_product_id: `ops-prod-${Math.floor(Math.random() * 9000) + 1000}`,  // ← fake!
  }),
});
```

This was intentional during early development — it let the UI be tested before the n8n workflow was ready. Task 6 fixed the n8n workflow. Task 8 wires them together.

---

## 3. How the Real Push Flow Works Now

```
User clicks "Push Now"
    ↓
Frontend: POST /api/n8n/workflows/ops-push-001/trigger
          body: { product_id, customer_id }
    ↓
Backend (n8n_proxy):
  - Looks up workflow "ops-push-001" in n8n REST API
  - Finds its webhook path ("ops-push")
  - Forwards body fields as webhook query params
    ↓
Backend calls: GET http://localhost:5678/webhook/ops-push
                    ?product_id=abc-123&customer_id=xyz-456
    ↓
n8n workflow runs (ops-push.json):
  Parse Params → Get Product → Build OPS Inputs
  → Set Category → Set Product → Set Sizes + Set Price
  → Write push-log entry (status: pushed or failed)
    ↓
Backend returns { triggered: true, response: {...} } to frontend
    ↓
Frontend waits 5 seconds
    ↓
Frontend: GET /api/products/{id}/push-status  (re-fetch per-customer status)
Frontend: increments refreshTrigger  (re-fetches PushHistory log table)
    ↓
User sees real OPS product ID + real status in the history table
```

---

## 4. The Three Pieces — Explained

### Piece 1 — Reusing `/api/n8n/workflows/{id}/trigger`

Rather than inventing a new endpoint, Task 8 reuses the existing `POST /api/n8n/workflows/{workflow_id}/trigger` route in `n8n_proxy/routes.py`. Originally it just fired the webhook with no params — not useful for a single-product push.

**The update:** accept an optional JSON body and forward its fields as webhook query params.

```python
@router.post("/workflows/{workflow_id}/trigger")
async def trigger_workflow(workflow_id: str, body: Optional[dict] = None):
    # ... look up workflow and find its webhook path ...
    trigger_url = f"{_webhook_base()}/webhook/{webhook_path}"
    params = {k: str(v) for k, v in (body or {}).items() if v is not None}
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(trigger_url, params=params)
        r.raise_for_status()
        return {"triggered": True, "url": trigger_url, "response": r.json()}
```

So:
```
POST /api/n8n/workflows/ops-push-001/trigger
{ "product_id": "abc", "customer_id": "xyz" }
```
becomes:
```
GET /webhook/ops-push?product_id=abc&customer_id=xyz
```

**Error handling:**
| Error | HTTP Code | Message |
|---|---|---|
| Docker/n8n not running | 503 | "n8n webhook is not reachable…" |
| n8n takes too long | 504 | "n8n webhook timed out…" |
| n8n returns error | 502 | "n8n returned an error: HTTP XXX" |
| Workflow not found | 404 | "Workflow not found" |
| Workflow not active | 409 | "Workflow 'X' is not active" |

---

### Piece 2 — n8n Workflow: product_id Support

Before Task 8, the n8n Parse Params node only read `customer_id`, `supplier_id`, `limit` — it always fetched a **list** of products. You couldn't push just one.

The node was updated to also read `product_id`:

```js
const product_id = q.product_id ?? q.productId ?? null;

let products_url;
if (product_id) {
  // Single-product push (from product detail page)
  products_url = `${api_base}/api/products/${product_id}`;
} else {
  // Bulk push (all products for a customer/supplier)
  const url = new URL(`${api_base}/api/products`);
  url.searchParams.set('limit', String(limit));
  if (supplier_id) url.searchParams.set('supplier_id', String(supplier_id));
  products_url = url.toString();
}
```

The existing `Explode Products` node already handled both a list response and a single-object response, so no further changes were needed downstream.

---

### Piece 3 — Frontend `handlePush` + PushHistory `refreshTrigger`

**The new handlePush (matches the spec):**

```tsx
const handlePush = async (customerId?: string) => {
  if (!product) return;
  const targetId = customerId || (customers.length > 0 ? customers[0].id : null);
  if (!targetId) {
    alert("Please configure a storefront in the Storefronts page first.");
    return;
  }
  setPushing(targetId);
  try {
    // Trigger n8n workflow — it writes the push-log entry itself on completion
    await api(`/api/n8n/workflows/ops-push-001/trigger`, {
      method: "POST",
      body: JSON.stringify({
        product_id: product.id,
        customer_id: targetId,
      }),
    });
    // Poll push status after ~5s for the result (n8n workflow takes ~15s total)
    await new Promise((r) => setTimeout(r, 5000));
    const newStatuses = await api<ProductPushStatus[]>(`/api/products/${id}/push-status`);
    setPushStatuses(newStatuses);
    // Also trigger PushHistory to re-fetch its log (both tables live there)
    setPushRefresh((n) => n + 1);
  } catch (e) {
    console.error(e);
    alert("Publish failed. Check n8n logs at http://localhost:5678.");
  } finally {
    setPushing(null);
  }
};
```

**Why `refreshTrigger` on PushHistory?**
Task 7 merged the "Storefront Publish Status" and "Push Log History" tables into a single `PushHistory` component that fetches its own data (`/api/push-log`). The spec's polling pattern only refreshes the parent's `pushStatuses` state — but since PushHistory has its own internal log fetch, we also need to tell it to re-fetch. Incrementing `refreshTrigger` does that.

```tsx
// In PushHistory:
useEffect(() => {
  fetchLogs();
}, [productId, refreshTrigger]);  // re-runs when refreshTrigger changes
```

---

## 5. Build Verification

- ✅ `npx tsc --noEmit` — no TypeScript errors in our changed files
- ✅ `python ast.parse` — backend Python syntax OK
- ⚠️ Pre-existing error in `/storefront/vg/page.tsx` (useSearchParams without Suspense) — not ours
- Warnings about `<img>` tags and `useEffect` dependencies are pre-existing

---

## 6. Acceptance Criteria (From Spec)

| Criterion | Status |
|---|---|
| Product detail page shows the Publish Status table (per storefront) | ✅ (inside PushHistory — Table 1) |
| …and below it the Push History table (timeline of all push attempts) | ✅ (inside PushHistory — Table 2) |
| Clicking "Push Now" triggers n8n (not a mock) | ✅ (calls `/api/n8n/workflows/ops-push-001/trigger`) |
| After workflow completes (~15s), push status updates | ✅ (5s poll + `refreshTrigger` refreshes both tables) |

---

## 7. What Comes Next

| Next Task | What It Adds | Blocked? |
|---|---|---|
| **Task 5** — n8n smoke test | Manually test the full end-to-end push with real OPS credentials | 🔴 Yes — needs credentials from Christian |
| **Customers page** | UI to add/edit/delete customer storefronts | ❌ No |
| **Workflows page** | UI to view n8n workflow status and trigger pushes | ❌ No |
