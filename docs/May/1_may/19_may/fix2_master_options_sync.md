# Fix 2 — Master Options Catalog Page Sync Route

**Date:** 2026-05-19
**Author:** Vidhi
**Branch:** Vidhi
**Status:** Done (uncommitted)

---

## What type of task is this?

**Backend + Frontend — route fix and error handling.**

---

## What was the problem?

The Master Options Catalog page at `/products/configure` had a "Sync from OPS" button. Clicking it returned **405 Method Not Allowed**.

Additionally, when sync failed, the Next.js dev overlay (the full-screen error popup) appeared because the error was being logged with `console.error`.

---

## Root cause

The `POST /api/master-options/sync` route had been deleted in a previous session. Without it, FastAPI tried to match the URL segment `"sync"` as a UUID for `GET /api/master-options/{master_option_id}`. That failed with 405 because GET ≠ POST.

The route ordering in FastAPI matters — a specific route like `/sync` must be registered **before** a wildcard route like `/{id}`, otherwise the wildcard eats it.

---

## What changed and why

### Fix 1 — Restored the sync route

**File:** `backend/modules/master_options/routes.py`

Added back `POST /api/master-options/sync` — placed before `GET /{master_option_id}`:

```python
@router.post("/sync", status_code=202)
async def sync_master_options(db: AsyncSession = Depends(get_db)):
    # 1. Find first active customer with OPS credentials
    # 2. Call OPS GraphQL: getMasterOptions query
    # 3. Upsert MasterOption + MasterOptionAttribute rows
    # 4. Return {"synced": N, "status": "ok"}
```

If OPS is unreachable (e.g. placeholder URL configured), returns **502** with a clear message instead of crashing with 500.

---

### Fix 2 — Stop triggering Next.js error overlay

**File:** `frontend/src/app/(admin)/products/configure/page.tsx`

```typescript
// Before
} catch (e) {
  log.error("Sync failed", e);   // ← triggers Next.js dev overlay
}

// After
} catch (e) {
  log.warn("Sync failed", e);    // ← no overlay
  alert(`Sync failed: ${msg}`);  // ← shows actual error message
}
```

`log.error` calls `console.error`, which Next.js dev mode intercepts and displays as a blocking full-screen overlay. Using `log.warn` prevents that while still logging the error.

---

## Files changed

| File | Change |
|------|--------|
| `backend/modules/master_options/routes.py` | Restored `POST /sync` route with OPS sync logic + 502 error handling |
| `frontend/src/app/(admin)/products/configure/page.tsx` | Changed `log.error` → `log.warn` in catch block |

---

## Manual Test Steps

1. Go to `http://localhost:3000/products/configure`
2. Click "Sync from OPS"
3. If Visual Graphics has placeholder OPS URL → shows alert "Sync failed: Could not connect to OPS storefront"
4. No Next.js error overlay appears
5. If real OPS credentials are configured → master options appear in the grid
