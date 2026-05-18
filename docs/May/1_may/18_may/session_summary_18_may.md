# Session Summary — 18 May 2026

**Developer:** Vidhi
**Branch:** `Vidhi`
**PR:** #127 — [fix: AWS deploy, endpoint health, lint errors, test fixtures](https://github.com/VisualGraphxLLC/API-HUB/pull/127)
**Final commit:** `fad2177`
**Tests:** 507 backend ✅ · 30 frontend ✅ · 0 lint errors ✅

---

## 1. Understanding the App

Started the session by doing a full codebase walkthrough to understand what API-HUB is and how it works.

### What the app is
A B2B middleware platform that connects 994+ PromoStandards wholesale suppliers (SanMar, S&S Activewear, Alphabroder, 4Over) to OnPrintShop (OPS) storefronts. It sits in the middle — fetching products from suppliers, normalizing them, applying markup rules, and pushing them to customer storefronts.

### Stack
| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.12), async SQLAlchemy + asyncpg, PostgreSQL |
| Frontend | Next.js 15 (App Router), shadcn/ui, Tailwind CSS, Blueprint design system |
| Orchestration | n8n (Docker, port 5678) — triggers FastAPI via webhooks |
| Deployment | AWS ECS + ECR, CloudFormation |

### How data flows
```
Supplier (SOAP/REST)
    → Protocol Adapter (SanMar / S&S / Alphabroder / 4Over)
    → Normalize + Upsert into PostgreSQL
    → Admin configures markup rules + OPS field mappings
    → Integration Gateway runs preflight + builds payload
    → OPS GraphQL mutations via OAuth2
    → OnPrintShop Storefront
```

### Key design decisions
- Suppliers are **database rows, not code** — adding a supplier = creating a DB record, not writing code
- All credentials encrypted in DB using `EncryptedJSON` (Fernet/AES-128)
- Schema upgrades are inline `ALTER TABLE IF NOT EXISTS` in `main.py` — no migration tool
- `NEXT_PUBLIC_*` frontend variables are baked into the Next.js bundle **at Docker build time**, not at runtime

---

## 2. AWS Deployment Investigation

### Problem reported
- **User side:** 504 Gateway Timeout on the deployed app
- **Lead side:** Build Error on `dev-apihub.visualgraphx.com`

```
Module parse failed: Unexpected character '@' (1:0)
> @import "@fontsource/outfit/400.css";
```

### Root cause found
`tailwindcss`, `postcss`, and `autoprefixer` were in `devDependencies` in `frontend/package.json`. The AWS server was installing only production packages, so `postcss` was not available. Without `postcss`, Next.js cannot process CSS — webpack tried to parse `globals.css` as JavaScript and choked on the `@` character. The app crashed on startup, which caused the reverse proxy to return a 504 to users.

Verified by fetching the live site — it was returning HTTP 500 on every route.

### Fix applied
Moved `tailwindcss`, `postcss`, `autoprefixer` from `devDependencies` → `dependencies` in `frontend/package.json`.

**Files changed:**
- `frontend/package.json`
- `frontend/package-lock.json`

---

## 3. Full Endpoint Health Check (41 endpoints)

Ran a complete test of every registered API endpoint locally using a real JWT auth cookie and real database IDs.

### How it was done
1. Called `GET /openapi.json` to get all registered routes
2. Logged in via `POST /api/auth/login` to get a session cookie
3. Fetched real IDs (supplier, product, customer, category) from the database
4. Hit every endpoint with real IDs and checked HTTP status codes

### Result: All 41 endpoints healthy

Two responses that look like errors but are correct behaviour:

| Endpoint | Status | Why it's correct |
|---|---|---|
| `GET /api/suppliers/{id}/categories` | 400 | Category browse only works for SOAP/PromoStandards suppliers, not `ops_graphql` protocol |
| `GET /api/push/{customer}/product/{product}/payload` | 401 | Internal endpoint for n8n only — requires `X-Ingest-Secret` header, not a JWT cookie |

### Bug discovered during this check
`GET /api/audit-log` was returning 422 with `args` and `kwargs` as required query params — even though the route handler had neither. Fixed (see Bug #1 below).

---

## 4. Bugs Found and Fixed

### Bug 1 — `GET /api/audit-log` returning 422 (args/kwargs required)

**File:** `backend/modules/audit_log/routes.py`

**What was happening:**
```json
{
  "detail": [
    {"msg": "Field required", "loc": ["query", "args"]},
    {"msg": "Field required", "loc": ["query", "kwargs"]}
  ]
}
```
The endpoint was completely broken — no admin could access audit logs.

**Root cause:**
The route used `dependencies=[Depends(VGAdmin)]` where `VGAdmin = Annotated[User, Depends(_require_vg_admin)]`. Wrapping an already-annotated type inside another `Depends()` confused FastAPI's parameter introspection, which leaked internal `args` and `kwargs` into the OpenAPI spec as required query parameters.

**Fix:**
Changed from using `dependencies=[Depends(VGAdmin)]` to injecting it as a typed function parameter:
```python
# Before — broken
@router.get("", dependencies=[Depends(VGAdmin)])
async def list_audit_logs(limit: int = ..., db = ...):

# After — correct
@router.get("")
async def list_audit_logs(_: VGAdmin, limit: int = ..., db = ...):
```

---

### Bug 2 — `useDebouncedQuote` test returning `undefined`

**File:** `frontend/src/lib/__tests__/use-debounced-quote.test.ts`

**What was happening:**
Test expected `result.current.quote?.total` to be `"625.00"` but got `undefined`. The test was failing in CI.

**Root cause:**
The test mock only had a `json()` method on the fake fetch response. But `api.ts` reads the body using `res.text()` then `JSON.parse()`s it manually — it never calls `res.json()`. Since `text()` was missing on the mock, `api.ts` got an empty result and returned `{}`.

**Fix:**
Added `text()` and `status: 200` to the fetch mock:
```ts
// Before
const fakeFetch = vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ total: "625.00", ... }),
  headers: new Headers({ "content-type": "application/json" }),
});

// After
const body = { unit_price: "12.50", total: "625.00", ... };
const fakeFetch = vi.fn().mockResolvedValue({
  ok: true,
  status: 200,
  json: async () => body,
  text: async () => JSON.stringify(body),   // ← this is what api.ts actually calls
  headers: new Headers({ "content-type": "application/json" }),
});
```

---

### Bug 3 — 12 backend tests failing with `AttributeError`

**File:** `backend/test_markup_engine.py`

**What was happening:**
```
AttributeError: 'types.SimpleNamespace' object has no attribute 'markup_amount'
```
12 out of 15 tests in the markup engine test file were failing.

**Root cause:**
The `rule()` helper function built fake rule objects using `SimpleNamespace`. Pricing enhancements had been added to `markup/engine.py` (flat-dollar markup, date-range activation, price floor/ceiling) that read new fields: `markup_amount`, `min_price`, `max_price`, `is_active`, `effective_from`, `effective_until`. The test helper was never updated to include these fields.

**Fix:**
Added all missing fields with safe defaults to the `rule()` helper:
```python
# Before
def rule(scope, markup_pct, *, priority=0, min_margin=None, rounding="none"):
    return SimpleNamespace(
        id=uuid4(), scope=scope, markup_pct=markup_pct,
        priority=priority, min_margin=min_margin, rounding=rounding,
    )

# After
def rule(scope, markup_pct=None, *, priority=0, min_margin=None, rounding="none",
         markup_amount=None, min_price=None, max_price=None,
         is_active=True, effective_from=None, effective_until=None):
    return SimpleNamespace(
        id=uuid4(), scope=scope, markup_pct=markup_pct, markup_amount=markup_amount,
        priority=priority, min_margin=min_margin, min_price=min_price,
        max_price=max_price, rounding=rounding, is_active=is_active,
        effective_from=effective_from, effective_until=effective_until,
    )
```

---

### Bug 4 — React hooks called after early return (ESLint error)

**File:** `frontend/src/app/(admin)/customers/[id]/catalog/page.tsx`

**What was happening:**
ESLint was reporting 3 errors — these would cause the CI build to fail:
```
98:20  Error: React Hook "useMemo" is called conditionally
112:18  Error: React Hook "useMemo" is called conditionally
130:32  Error: React Hook "useMemo" is called conditionally
```

**Root cause:**
Three `useMemo` hooks (`filtered`, `counts`, `needsDecorationCount`) were placed **after** an early return guard:
```tsx
if (!isValidId) {
  return <ErrorPage />;   // ← early return here
}

const filtered = useMemo(...);   // ← hooks after early return = Rules of Hooks violation
const counts = useMemo(...);
const needsDecorationCount = useMemo(...);
```
React requires hooks to run in the exact same order on every render. An early return before a hook breaks this rule.

**Fix:**
Moved all three `useMemo` calls to before the `if (!isValidId)` guard. Safe because they only depend on state variables (`selections`, `search`, `statusFilter`) which are always initialized at the top of the component.

---

### Bug 5 — Unescaped quotes in JSX (ESLint error)

**File:** `frontend/src/components/products/BrandingPanel.tsx` line 211

**What was happening:**
```
211:51  Error: `"` can be escaped with `&quot;`
211:57  Error: `"` can be escaped with `&quot;`
```

**Root cause:**
JSX text content had raw `"` double-quote characters which are not allowed unescaped in JSX:
```tsx
Logo positioning is relative to the "Front" view of the {product.product_type}.
```

**Fix:**
Replaced with HTML named entities:
```tsx
Logo positioning is relative to the &ldquo;Front&rdquo; view of the {product.product_type}.
```

---

## 5. ECS Deployment Fix

### Problem
Even after fixing the CSS build error, the deployed app would still have broken API calls because `NEXT_PUBLIC_API_URL` was never being set correctly.

**Why this happens with Next.js:**
`NEXT_PUBLIC_*` variables are baked into the JavaScript bundle at **Docker build time** — they are not runtime environment variables. Setting them in ECS task definition environment variables has no effect on the frontend bundle.

### Two-part fix

**Part 1 — Dockerfile was not accepting build args:**

The `frontend/Dockerfile` builder stage had no `ARG` declarations, so even if someone passed `--build-arg NEXT_PUBLIC_API_URL=...`, Next.js would never see it.

```dockerfile
# Before — build args ignored
FROM deps AS builder
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# After — build args properly declared and passed to Next.js
FROM deps AS builder
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_N8N_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_N8N_URL=$NEXT_PUBLIC_N8N_URL
RUN npm run build
```

**Part 2 — Created `scripts/build-and-push.sh`:**

A ready-to-run script for the team to use when deploying to ECS. Handles ECR login, Docker build with correct args, and push of both frontend and backend images.

**Usage:**
```bash
AWS_REGION=us-east-1 \
AWS_ACCOUNT_ID=<account-id> \
NEXT_PUBLIC_API_URL=https://<real-backend-url> \
NEXT_PUBLIC_N8N_URL=https://<real-n8n-url> \
./scripts/build-and-push.sh
```

After running, go to **ECS → service → Update** and set the new image tag shown in the script output.

---

## 6. CI/CD Pipeline Update

Updated `.github/workflows/deploy.yml` to replace hardcoded placeholder URLs with GitHub secrets:
```yaml
# Before
--build-arg NEXT_PUBLIC_API_URL=https://api.staging.example.com

# After
--build-arg NEXT_PUBLIC_API_URL=${{ secrets.NEXT_PUBLIC_API_URL }}
```

Lead needs to add `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_N8N_URL` as repository secrets in GitHub → Settings → Secrets and variables → Actions.

---

## 7. Files Changed

| File | What changed |
|---|---|
| `frontend/package.json` | Moved tailwindcss/postcss/autoprefixer to dependencies |
| `frontend/package-lock.json` | Updated lockfile |
| `frontend/Dockerfile` | Added ARG/ENV for NEXT_PUBLIC build args |
| `scripts/build-and-push.sh` | New ECS deployment script |
| `.github/workflows/deploy.yml` | Replaced hardcoded URLs with GitHub secrets |
| `backend/modules/audit_log/routes.py` | Fixed VGAdmin double-wrap bug |
| `backend/test_markup_engine.py` | Fixed rule() helper missing new pricing fields |
| `frontend/src/lib/__tests__/use-debounced-quote.test.ts` | Fixed fetch mock missing text() |
| `frontend/src/app/(admin)/customers/[id]/catalog/page.tsx` | Moved useMemo before early return |
| `frontend/src/components/products/BrandingPanel.tsx` | Fixed unescaped quotes |

Plus all other pre-existing changes on the Vidhi branch (supplier schema audit, push status UI, live mode push, SanMar OPS smoke test, etc.).

---

## 8. Final Test Results

| Suite | Before | After |
|---|---|---|
| Backend `pytest` | 495 passed / 12 failed | **507 / 507 passed** ✅ |
| Frontend `vitest` | 29 passed / 1 failed | **30 / 30 passed** ✅ |
| ESLint | 5 errors | **0 errors** ✅ |

---

## 9. What Lead Needs to Do

1. **Set GitHub secrets** — `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_N8N_URL` in repo settings (for pipeline use)
2. **Run `scripts/build-and-push.sh`** with the real backend URL to build and push correct Docker images to ECR
3. **Update ECS service** with the new image tag
4. **Merge `Vidhi` → `dev`** to deploy all fixes to the dev environment

---

## 10. PR

All changes are in **[PR #127](https://github.com/VisualGraphxLLC/API-HUB/pull/127)** — open and ready for review.
