# API-HUB — Code Review: All Completed Tasks

**Reviewed:** 2026-04-15 | **Scope:** All merged PRs (#1 Urvashi, #2 Sinchana, #3 Vidhi) + initial commits  
**Last updated:** 2026-05-04 | **All 9 issues resolved** ✅

---

## Resolution Status — All Issues

| # | Severity | Issue | Status | Resolved in |
|---|----------|-------|--------|-------------|
| 1 | CRITICAL | PostgreSQL port mismatch | ✅ RESOLVED | `docker-compose.yml` — postgres no longer exposed on host; services use internal network port 5432 |
| 2 | CRITICAL | `load_dotenv` wrong path | ✅ RESOLVED | `backend/database.py:10`, `backend/seed_demo.py:8` — path changed to `parent.parent / ".env"` |
| 3 | CRITICAL | shadcn/ui not installed | ✅ RESOLVED | `frontend/src/components/ui/` — all shadcn components present |
| 4 | MODERATE | N+1 query in push status endpoint | ✅ RESOLVED | `backend/modules/push_log/routes.py:91-126` — GROUP BY subquery, 2 queries total |
| 5 | MODERATE | Inconsistent route prefix | ✅ RESOLVED | `backend/modules/push_log/routes.py:13` — split into two routers with proper prefixes |
| 6 | MODERATE | N+1 query in product list | ✅ RESOLVED | `backend/modules/catalog/routes.py:46-67` — `variant_agg` subquery covers count + price + inventory |
| 7 | MINOR | Imports inside loop body | ✅ RESOLVED | `backend/seed_demo.py` — all imports hoisted to top of file |
| 8 | MINOR | Dashboard hardcoded data | ✅ RESOLVED | `frontend/src/app/(admin)/page.tsx:67` — live `api<Stats>("/api/stats")` call |
| 9 | MINOR | Hardcoded `/Users/PD/API-HUB` in docs | ✅ RESOLVED | `docs/Task_Test_fill/` — paths replaced in all 4 files |

---

## Issues Summary (original)

---

## CRITICAL Issues

### Issue 1: PostgreSQL port mismatch

**Files:** `docker-compose.yml` (line 9), `.env` (line 1)

`docker-compose.yml` maps port **5434** on the host:
```yaml
ports:
  - "5434:5432"
```

But `.env` connects to port **5432**:
```
POSTGRES_URL=postgresql+asyncpg://vg_user:vg_pass@localhost:5432/vg_hub
```

**Impact:** The backend cannot connect to PostgreSQL. Anyone pulling main and running `docker compose up -d postgres` will get connection refused errors.

**Root cause:** Vidhi changed the port to avoid a conflict on her local machine. This shouldn't have been committed.

**Fix:** Either revert `docker-compose.yml` back to `"5432:5432"`, or update `.env` to use port 5434. Reverting docker-compose is preferred — it's the standard port.

**Status (2026-04-27): RESOLVED.** docker-compose.yml no longer exposes postgres on the host; n8n + api hit it on the docker network. Service-internal port stays 5432.

---

### Issue 2: `load_dotenv` points to wrong path

**Files:** `backend/database.py` (line 7), `backend/seed_demo.py` (line 8)

Both files load:
```python
load_dotenv(Path(__file__).parent / ".env")
```

This resolves to `backend/.env` — but that file **does not exist**. The project's `.env` is at the repo root (`api-hub/.env`).

**Impact:** `load_dotenv` silently does nothing. The backend only works if:
- You run it from Docker Compose (which injects env vars), OR
- You happen to have the env vars set in your shell

If you run `uvicorn main:app` directly without Docker, `SECRET_KEY` will be empty (no encryption) and `POSTGRES_URL` falls back to the hardcoded default — which may or may not match your docker-compose port.

**Fix:** Either:
- Change path to `Path(__file__).parent.parent / ".env"` (goes up to repo root), OR
- Remove `load_dotenv` entirely and use `docker compose` or shell env vars (cleaner)

**Status (2026-04-27): RESOLVED.** backend/database.py:10 + backend/seed_demo.py:8 now use Path(__file__).parent.parent / ".env".

---

### Issue 3: shadcn/ui not installed (Task 9)

**Covered in detail in `docs/09_Task9_Review.md`.**

The spec requires `npx shadcn@latest add button card input table badge separator scroll-area`. None are installed. No `components/ui/` directory exists.

**Impact:** All 7 frontend pages (Tasks 10-16) expect shadcn components. This blocks Phase 4.

**Fix:** Run in `frontend/`:
```bash
npx shadcn@latest init -d
npx shadcn@latest add button card input table badge separator scroll-area
```

**Status (2026-04-27): RESOLVED.** frontend/package.json declares the @radix-ui/* primitives and frontend/src/components/ui/ contains the shadcn-generated files.

---

## MODERATE Issues

### Issue 4: N+1 query in push status endpoint (Task 20)

**File:** `backend/modules/push_log/routes.py` lines 27-52

```python
customers_result = await db.execute(select(Customer))
customers = {c.id: c.name for c in customers_result.scalars().all()}

for customer_id, customer_name in customers.items():
    result = await db.execute(
        select(ProductPushLog).where(...).limit(1)
    )
```

Loads ALL customers, then runs a **separate query per customer**. With 100 customers, that's 101 queries.

**Impact:** Acceptable for V0 with a few test customers. Will become a performance problem when real customers are added.

**Fix (later):** Use a single query with `DISTINCT ON` or a window function to get the latest push log per customer in one round-trip.

**Status (2026-04-27): RESOLVED.** backend/modules/push_log/routes.py:91-126 uses a GROUP BY subquery + a single Customer fetch — two queries total.

---

### Issue 5: Inconsistent route prefix pattern (Task 20)

**File:** `backend/modules/push_log/routes.py` line 13

Every other module uses `APIRouter(prefix="/api/...")`:
- suppliers: `prefix="/api/suppliers"`
- customers: `prefix="/api/customers"`
- markup: `prefix="/api/markup-rules"`
- catalog: `prefix="/api/products"`
- ps_directory: `prefix="/api/ps-directory"`

But push_log uses no prefix and hardcodes `/api/` in each route:
```python
router = APIRouter(tags=["push_log"])  # no prefix

@router.post("/api/push-log", ...)
@router.get("/api/products/{product_id}/push-status", ...)
```

**Impact:** Not a bug — it works. But it breaks the pattern, making the code harder to maintain.

**Fix:** The push_log routes span two URL namespaces (`/api/push-log` and `/api/products/{id}/push-status`), so a single prefix doesn't work cleanly. Options:
- Split into two routers (one for `/api/push-log`, one added to the catalog router), OR
- Leave as-is and document why it's different

**Status (2026-04-27): RESOLVED in this plan (Task 3).**

---

### Issue 6: N+1 query in product list (Task 6)

**File:** `backend/modules/catalog/routes.py` lines 48-55

```python
for p in products:
    count = (
        await db.execute(
            select(func.count())
            .select_from(ProductVariant)
            .where(ProductVariant.product_id == p.id)
        )
    ).scalar() or 0
```

Fetches variant count per product in a loop. With 50 products (the default limit), that's 50 extra queries.

**Impact:** Slow on large catalogs. The supplier name lookup above it (lines 39-45) correctly uses a batch query — the variant count should do the same.

**Fix (later):** Use a subquery or `GROUP BY` to get variant counts in a single query:
```python
from sqlalchemy import func, select
variant_counts = (
    select(ProductVariant.product_id, func.count().label("cnt"))
    .group_by(ProductVariant.product_id)
    .subquery()
)
```

**Status (2026-04-27): RESOLVED.** backend/modules/catalog/routes.py:46-67 uses a variant_agg subquery for variant_count + price_min/max + total_inventory.

---

## MINOR Issues

### Issue 7: Imports inside loop body (Task 8)

**File:** `backend/seed_demo.py` lines 102, 127-128

```python
for s_data in SUPPLIERS:
    from sqlalchemy import select      # inside loop
    ...

for p_data in DEMO_PRODUCTS:
    from sqlalchemy import select      # inside loop
    from decimal import Decimal        # inside loop
```

Python caches these so it works, but it's messy. Imports belong at the top of the file.

**Fix:** Move `from sqlalchemy import select` and `from decimal import Decimal` to the top imports section.

**Status (2026-04-27): RESOLVED in this plan (Task 4).**

---

### Issue 8: Dashboard hardcoded data (Task 9)

**File:** `frontend/src/app/page.tsx`

Dashboard shows static sample data (4 vendors, 32.4k SKUs) instead of calling `api<Stats>("/api/stats")`. The API endpoint exists and works.

**Fix:** Replace hardcoded values with a `useEffect` + `api()` call.

**Status (2026-04-27): RESOLVED.** frontend/src/app/(admin)/page.tsx:67 calls api<Stats>("/api/stats") and renders live values.

---

### Issue 9: Hardcoded local path in test docs

**Files:** 4 files in `docs/Task_Test_fill/`

All reference `/Users/PD/API-HUB` — Vidhi's local machine path:
- `docs/Task_Test_fill/README.md` line 19
- `docs/Task_Test_fill/Task_18_Customer_Model.md` line 71
- `docs/Task_Test_fill/Task_19_Markup_Rules.md` line 61
- `docs/Task_Test_fill/Task_20_Push_Log.md` line 60

**Fix:** Replace with relative paths or use `cd api-hub` instead.

**Status (2026-04-27): RESOLVED in this plan (Task 8).**

---

## What's Clean (no issues found)

| Task | Module | Notes |
|------|--------|-------|
| 2 | `database.py` | EncryptedJSON implementation is solid (aside from the dotenv issue added by PR #3) |
| 3 | `suppliers/models.py`, `schemas.py` | Clean model, proper encrypted auth_config |
| 4 | `catalog/models.py` | Product/Variant split is correct, CASCADE delete works |
| 5 | `ps_directory/client.py`, `suppliers/service.py` | 24h cache logic is clean |
| 6 | `ps_directory/routes.py` | Simple, correct |
| 6 | `suppliers/routes.py` | Full CRUD, proper error handling |
| 18 | `customers/routes.py` | Write-only secret pattern is well-implemented |
| 19 | `markup/routes.py` | Priority-based rules, clean CRUD |

---

## Recommended Fix Order

1. **Fix Issues 1 + 2 first** (port + dotenv) — the backend literally won't start without these
2. **Fix Issue 3** (shadcn/ui) — blocks all Phase 4 frontend work
3. Issues 4-9 can be addressed as part of normal development

---

## Session Update — 2026-05-04

Additional hygiene and deployment tasks completed in this session (separate from the original 9 code review issues):

| Task | File(s) changed | What |
|------|----------------|------|
| Delete dead tailwind config | `frontend/tailwind.config.js` (deleted) | Removed old pre-shadcn CommonJS config — `.ts` version is the live one |
| Replace `console.error` with `log` util | `frontend/src/components/mappings/sanmar-mapping-panel.tsx` | Last remaining raw `console.error` — now uses `log.error` which is silenced in production |
| Create `.npmignore` for n8n node | `n8n-nodes-onprintshop/.npmignore` | Ensures only `dist/` ships when installing from GitHub — excludes source TS, dev deps, internal docs |
| Fix `seed_demo.py` category string | `backend/seed_demo.py` | Set `product.category` string alongside `category_id` so PDP category label renders correctly in demo |
| docker-compose env passthrough | `docker-compose.yml`, `.env.example` | Wire `ALLOWED_ORIGINS` to api service; document `API_BASE_URL` used by all n8n workflows |
| AWS App Runner config | `deployment/aws-app-runner.yaml`, `deployment/README.md` | CloudFormation template for one-command production deployment to AWS App Runner |
