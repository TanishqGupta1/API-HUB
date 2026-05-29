# Timesheet — 2026-05-18

**Developer:** Vidhi
**Branch:** `Vidhi`
**Commit pushed:** `a650dd2`
**Test suite:** 507 / 507 backend passed · 30 / 30 frontend passed · 0 lint errors

---

## Tasks Completed

### Task 1: Investigate & Fix AWS Deployment Failure

**Problem:** The deployed app at `dev-apihub.visualgraphx.com` was broken in two different ways depending on who accessed it:
- User side: **504 Gateway Timeout** (reverse proxy got no response)
- Lead side: **Build Error — Module parse failed: Unexpected character '@' (1:0)** pointing to `globals.css` line 1 (`@import "@fontsource/outfit/400.css"`)

**Root cause:** `tailwindcss`, `postcss`, and `autoprefixer` were in `devDependencies`. The AWS server was installing only production packages, so `postcss` was missing at build/run time. Without `postcss`, Next.js cannot process CSS — webpack fell back to parsing `globals.css` as JavaScript and failed on the `@` character. The app crashed on startup, causing the 504.

**Fix:** Moved `tailwindcss`, `postcss`, and `autoprefixer` from `devDependencies` → `dependencies` in `frontend/package.json`. Updated `package-lock.json`.

**Status:** ✅ Done

---

### Task 2: Full Endpoint Health Check (41 endpoints)

Ran a complete check of all registered API endpoints locally with a real auth cookie and real DB IDs.

**Results:** All 41 endpoints healthy. Two non-bug behaviours confirmed:
- `GET /api/suppliers/{id}/categories` → 400 — correct, category browse only works for SOAP suppliers, not `ops_graphql`
- `GET /api/push/{customer}/product/{product}/payload` → 401 — correct, this is an internal n8n endpoint requiring `X-Ingest-Secret`, not JWT

**Status:** ✅ Done

---

### Task 3: Fix CI/CD Pipeline — Hardcoded Placeholder URLs

**Problem:** `deploy.yml` had hardcoded placeholder URLs that would make every API call fail in the deployed frontend:
```yaml
--build-arg NEXT_PUBLIC_API_URL=https://api.staging.example.com
--build-arg NEXT_PUBLIC_N8N_URL=https://n8n.staging.example.com
```
`NEXT_PUBLIC_*` variables are baked into the Next.js bundle at Docker build time, so wrong values at build time = broken app at runtime.

**Fix:** Replaced hardcoded URLs with GitHub secrets references:
```yaml
--build-arg NEXT_PUBLIC_API_URL=${{ secrets.NEXT_PUBLIC_API_URL }}
--build-arg NEXT_PUBLIC_N8N_URL=${{ secrets.NEXT_PUBLIC_N8N_URL }}
```
Lead needs to add `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_N8N_URL` as repository secrets in GitHub → Settings → Secrets and variables → Actions.

**Status:** ✅ Done (lead action required to set secrets)

---

## Bugs Fixed

### Bug 1: `GET /api/audit-log` — 422 with `args` and `kwargs` required

**Where:** `backend/modules/audit_log/routes.py`

**What happened:** The audit-log GET endpoint was returning 422 with:
```json
{"detail": [{"msg": "Field required", "loc": ["query", "args"]}, {"msg": "Field required", "loc": ["query", "kwargs"]}]}
```
`args` and `kwargs` were appearing as required query parameters in the OpenAPI spec even though the route handler had no such parameters.

**Root cause:** The route used `dependencies=[Depends(VGAdmin)]` where `VGAdmin = Annotated[User, Depends(_require_vg_admin)]`. Wrapping an already-annotated type in another `Depends()` confused FastAPI's dependency introspection, which leaked `args` and `kwargs` into the spec as required query params.

**Fix:** Changed from `dependencies=[Depends(VGAdmin)]` to injecting it as a typed parameter `_: VGAdmin` in the function signature.

```python
# Before
@router.get("", dependencies=[Depends(VGAdmin)])
async def list_audit_logs(limit: int = ..., ...):

# After
@router.get("")
async def list_audit_logs(_: VGAdmin, limit: int = ..., ...):
```

---

### Bug 2: `useDebouncedQuote` test returning `undefined` for `quote.total`

**Where:** `frontend/src/lib/__tests__/use-debounced-quote.test.ts`

**What happened:** The test expected `result.current.quote?.total` to be `"625.00"` but got `undefined`.

**Root cause:** The test mock only had a `json()` method, but `api.ts` reads the response body via `res.text()` then `JSON.parse()`s it manually — it never calls `res.json()`. Since `text()` was undefined on the mock, `api.ts` got an empty string, returned `{}`, and `quote.total` was `undefined`.

**Fix:** Added `text()` and `status: 200` to the fetch mock:
```ts
text: async () => JSON.stringify(body),
status: 200,
```

---

### Bug 3: `test_markup_engine.py` — 12 tests failing with `AttributeError`

**Where:** `backend/test_markup_engine.py`

**What happened:** All 12 `apply_markup` and `resolve_rule` tests failed with:
```
AttributeError: 'types.SimpleNamespace' object has no attribute 'markup_amount'
```
And subsequently `min_price`, `max_price`, `is_active`, `effective_from`, `effective_until`.

**Root cause:** The `rule()` helper function in the test file used `SimpleNamespace` to build fake rule objects. After pricing enhancements were added to `markup/engine.py` (flat-dollar markup, date-range activation, price floor/ceiling), the engine now reads these new fields — but the test helper hadn't been updated to include them.

**Fix:** Added all missing fields with `None`/`True` defaults to the `rule()` helper:
```python
def rule(scope, markup_pct=None, *, priority=0, min_margin=None, rounding="none",
         markup_amount=None, min_price=None, max_price=None,
         is_active=True, effective_from=None, effective_until=None):
```

---

### Bug 4: ESLint errors in `customers/[id]/catalog/page.tsx` — hooks called conditionally

**Where:** `frontend/src/app/(admin)/customers/[id]/catalog/page.tsx`

**What happened:** ESLint reported 3 errors:
```
98:20  Error: React Hook "useMemo" is called conditionally
112:18  Error: React Hook "useMemo" is called conditionally
130:32  Error: React Hook "useMemo" is called conditionally
```

**Root cause:** Three `useMemo` calls (for `filtered`, `counts`, `needsDecorationCount`) appeared **after** an early return guard `if (!isValidId) { return (...) }`. React requires hooks to be called in the same order on every render — an early return before a hook violates this.

**Fix:** Moved all three `useMemo` calls to **before** the `if (!isValidId)` early return. Safe to do because all three depend only on state variables (`selections`, `search`, `statusFilter`) which are always initialized.

---

### Bug 5: ESLint error in `BrandingPanel.tsx` — unescaped `"` in JSX

**Where:** `frontend/src/components/products/BrandingPanel.tsx` line 211

**What happened:**
```
211:51  Error: `"` can be escaped with `&quot;`
211:57  Error: `"` can be escaped with `&quot;`
```

**Root cause:** JSX text contained raw `"` quote characters:
```jsx
Logo positioning is relative to the "Front" view of the {product.product_type}.
```
Raw `"` in JSX text must be escaped.

**Fix:** Replaced with HTML named entities:
```jsx
Logo positioning is relative to the &ldquo;Front&rdquo; view of the {product.product_type}.
```

---

## Summary

| Item | Detail |
|------|--------|
| Tasks completed | 3 |
| Bugs fixed | 5 |
| Files modified | 50 |
| Backend tests | 507 / 507 ✅ |
| Frontend tests | 30 / 30 ✅ |
| Lint errors | 0 ✅ |
| Commit | `a650dd2` pushed to `Vidhi` |
| Pending (lead action) | Set `NEXT_PUBLIC_API_URL` + `NEXT_PUBLIC_N8N_URL` as GitHub secrets, then merge `Vidhi` → `dev` and trigger pipeline |
