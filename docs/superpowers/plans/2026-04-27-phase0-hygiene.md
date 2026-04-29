# Phase 0 — Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop tests polluting dev DB, drop dead config, normalize one router, replace dev-only console logging with a tiny prod-safe logger, and close out stale code-review items already silently resolved by later commits.

**Architecture:** Eight independent low-risk patches that share a theme (cleanup) but no runtime dependency on each other. Each ships its own commit and is reversible. No new modules introduced.

**Tech Stack:** FastAPI · async SQLAlchemy · pytest-asyncio · Next.js 15 · TypeScript.

**Background context (read before starting):**
- Repo root: `/Users/tanishq/Documents/project-files/api-hub/api-hub`
- Backend lives in `backend/`, frontend in `frontend/`, n8n stuff in `n8n-nodes-onprintshop/` + `n8n-workflows/`.
- Modular monolith — every backend module under `backend/modules/` exports `models.py`, `schemas.py`, `routes.py`. **Do not** create per-supplier code; suppliers are DB rows.
- Backend is async SQLAlchemy 2.0 with the `Mapped` typed attribute pattern. Use `select(...)` not legacy Query API. Test fixtures use `pytest-asyncio` style (`@pytest_asyncio.fixture`).
- `INGEST_SHARED_SECRET` is required on POST routes that n8n calls; tests set it via `conftest.py`.
- Commit policy: **never** add `Co-Authored-By` lines (see CLAUDE.md). Frequent commits, conventional-commits format (`fix(scope): subject`).
- Stack is up locally on the user's machine: api :8000, frontend :3000, n8n :5678, postgres healthy. Don't bring it down without warning the user.
- Live data exists in the dev DB (5 SanMar products, 2 VG OPS products, 13 customers — 12 of which are sentinel `Test Customer*` rows the tests leaked). **Never `DELETE` from `vg_hub` without an explicit user OK** — the user already denied one such request this session.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/tests/conftest.py` | Modify | Wire `TEST_DATABASE_URL`; extend cleanup to purge leaked customers / products / mappings created by tests |
| `backend/tests/test_conftest_isolation.py` | Create | Regression test: customer rows created in a test do not survive cleanup |
| `backend/modules/push_log/routes.py` | Modify | Convert `APIRouter(tags=...)` → `APIRouter(prefix="/api", tags=...)`; strip `/api` from each route decorator (CR #5) |
| `backend/seed_demo.py` | Modify | Hoist `from sqlalchemy import select, delete` to module top (CR #7) |
| `frontend/tailwind.config.js` | Delete | Dead — `tailwind.config.ts` is the live config |
| `frontend/next.config.ts` | Modify | Add `images.remotePatterns` for OPS + SanMar + Visual Graphics CDNs |
| `frontend/src/lib/log.ts` | Create | Tiny logger: console in dev, no-op in prod |
| `frontend/src/app/(admin)/**/page.tsx` + `frontend/src/components/suppliers/reveal-form.tsx` | Modify | Replace 17 `console.error`/`console.warn` calls with `log.error`/`log.warn` |
| `docs/code_review_all_tasks.md` | Modify | Mark CR #1, #2, #3, #4, #6, #8 as RESOLVED with commit refs |
| `docs/Task_Test_fill/*.md` (4 files) | Modify | Replace hardcoded `/Users/PD/API-HUB` paths with relative paths (CR #9) |

---

## Task 1: Extend test cleanup fixture to also nuke leaked customers

**Files:**
- Modify: `backend/tests/conftest.py:37-81`
- Create: `backend/tests/test_conftest_isolation.py`

**Why:** `test_push_mappings.py` creates `Customer(name="Test Customer{,2,3}", ops_base_url="https://test{,2,3}.ops.com", …)` rows. Current cleanup fixture only deletes test SUPPLIERS (slugs `vg-ops-test`, `vg-ops-inactive`). Each pytest run leaks 3 customer rows; 4 runs left 12 in dev DB. Customers cascade to `push_mappings`, `markup_rules`, `push_log` via `ON DELETE CASCADE` (verified in `push_log/models.py:15-16`, `markup/models.py:15`, `push_mappings/models.py:25,32`).

**Sentinel:** all leaked customer rows have `ops_base_url` matching `https://test%.ops.com` — safe to filter on.

- [x] **Step 1: Write the failing regression test**

Create `backend/tests/test_conftest_isolation.py`:

```python
"""Regression test: tests must not leak customer rows into the DB."""
import pytest
from sqlalchemy import func, select

from database import async_session
from modules.customers.models import Customer


TEST_OPS_BASE_URLS = (
    "https://test.ops.com",
    "https://test2.ops.com",
    "https://test3.ops.com",
)


@pytest.mark.asyncio
async def test_test_customers_do_not_survive_cleanup():
    """If a previous test created a Test Customer, it must have been purged.

    This test runs after the autouse `_cleanup_around_test` fixture, so any
    sentinel rows visible here mean the cleanup is incomplete.
    """
    async with async_session() as s:
        count = (
            await s.execute(
                select(func.count())
                .select_from(Customer)
                .where(Customer.ops_base_url.in_(TEST_OPS_BASE_URLS))
            )
        ).scalar_one()
    assert count == 0, (
        f"Cleanup leak: {count} sentinel Test Customer rows still in DB. "
        "Update conftest._cleanup_test_customers."
    )
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_conftest_isolation.py -v`
Expected: FAIL — `AssertionError: Cleanup leak: 12 sentinel Test Customer rows still in DB.`

- [x] **Step 3: Modify `backend/tests/conftest.py`**

Replace the section from `TEST_SUPPLIER_SLUGS = ...` through the end of `_cleanup_around_test` with this:

```python
TEST_SUPPLIER_SLUGS = ("vg-ops-test", "vg-ops-inactive")
TEST_CUSTOMER_OPS_URLS = (
    "https://test.ops.com",
    "https://test2.ops.com",
    "https://test3.ops.com",
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


async def _cleanup_test_customers() -> None:
    """Delete sentinel Customer rows + everything that cascades from them.

    `customers.id` has ON DELETE CASCADE FKs from push_mappings, markup_rules,
    and push_log, so a single DELETE on customers cleans the whole tree.
    """
    from modules.customers.models import Customer

    async with async_session() as s:
        await s.execute(
            delete(Customer).where(
                Customer.ops_base_url.in_(TEST_CUSTOMER_OPS_URLS)
            )
        )
        await s.commit()


async def _cleanup_test_suppliers() -> None:
    """Delete any lingering supplier rows + their owned products / variants /
    images / categories / sync_jobs."""
    from modules.catalog.models import Category, Product, ProductImage, ProductVariant
    from modules.suppliers.models import Supplier
    from modules.sync_jobs.models import SyncJob

    async with async_session() as s:
        supplier_ids = (
            await s.execute(
                select(Supplier.id).where(Supplier.slug.in_(TEST_SUPPLIER_SLUGS))
            )
        ).scalars().all()
        if not supplier_ids:
            await s.commit()
            return

        product_ids = (
            await s.execute(
                select(Product.id).where(Product.supplier_id.in_(supplier_ids))
            )
        ).scalars().all()

        if product_ids:
            await s.execute(
                delete(ProductVariant).where(ProductVariant.product_id.in_(product_ids))
            )
            await s.execute(
                delete(ProductImage).where(ProductImage.product_id.in_(product_ids))
            )
        await s.execute(delete(Product).where(Product.supplier_id.in_(supplier_ids)))
        await s.execute(delete(Category).where(Category.supplier_id.in_(supplier_ids)))
        await s.execute(delete(SyncJob).where(SyncJob.supplier_id.in_(supplier_ids)))
        await s.execute(delete(Supplier).where(Supplier.id.in_(supplier_ids)))
        await s.commit()


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_around_test():
    await _cleanup_test_customers()
    await _cleanup_test_suppliers()
    yield
    await _cleanup_test_customers()
    await _cleanup_test_suppliers()
```

Leave `seed_supplier`, `inactive_supplier`, `db`, and `client` fixtures unchanged.

- [x] **Step 4: Run the new test + the full push_mappings suite to verify**

Run: `cd backend && pytest tests/test_conftest_isolation.py tests/test_push_mappings.py -v`
Expected: ALL PASS. The isolation test confirms no leaked rows; push_mappings tests still pass because their own customer rows get cleaned between tests.

- [x] **Step 5: Commit**

```bash
git add backend/tests/conftest.py backend/tests/test_conftest_isolation.py
git commit -m "test(conftest): purge leaked Test Customer rows in cleanup fixture

Tests created Customer rows with sentinel ops_base_url 'https://test*.ops.com'
that the cleanup fixture wasn't removing. Cascades via ON DELETE CASCADE on
push_mappings / markup_rules / push_log, so a single DELETE on customers
clears the full tree. Regression test asserts no sentinel rows survive."
```

---

## Task 2: Wire TEST_DATABASE_URL in conftest

**Files:**
- Modify: `backend/tests/conftest.py:1-25` (top of file)

**Why:** Tests currently load the dev `.env` (`Path(__file__).parent.parent.parent / ".env"`), so `pytest` runs against `vg_hub` — a real dev database with live data. Even with Task 1's cleanup, an interrupted test still has a window where it's writing to the dev DB. Make the URL overridable so CI / local devs can point at a throwaway DB.

- [x] **Step 1: Modify the top of `backend/tests/conftest.py`**

Replace lines 1-25 (everything before `TEST_SUPPLIER_SLUGS`) with:

```python
"""Shared pytest fixtures for the backend test suite.

Strategy: each fixture/session is short-lived. Test data is inserted with
a fresh session, committed, and then cleaned up by the autouse cleanup
fixture after each test. This avoids asyncpg "another operation in progress"
errors that occur when the same session is shared between the test and the
FastAPI app's request handler.

Database selection: by default we load the dev .env so engineers can run the
suite locally against the same Postgres they're already running. Set
TEST_DATABASE_URL to point pytest at a separate database (recommended for CI).
"""
import os
from pathlib import Path

import pytest_asyncio
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# If TEST_DATABASE_URL is set, override POSTGRES_URL before `database` is imported
# so the engine is built against the test DB.
_test_db_url = os.environ.get("TEST_DATABASE_URL")
if _test_db_url:
    os.environ["POSTGRES_URL"] = _test_db_url

os.environ["INGEST_SHARED_SECRET"] = "test-secret-do-not-use-in-prod"

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from database import Base, async_session, engine  # noqa: E402
from main import app  # noqa: E402
```

(The constants and fixtures from Task 1 remain below.)

- [x] **Step 2: Verify default-path tests still pass**

Run: `cd backend && pytest tests/ -q`
Expected: all green. (No `TEST_DATABASE_URL` set → falls through to `.env`'s `POSTGRES_URL`.)

- [x] **Step 3: Verify TEST_DATABASE_URL override works**

Set up a throwaway db once:
```bash
docker compose exec -T postgres psql -U vg_user -d postgres -c "CREATE DATABASE vg_hub_test OWNER vg_user;" 2>/dev/null || true
```

Run: `cd backend && TEST_DATABASE_URL='postgresql+asyncpg://vg_user:vg_pass@localhost:5432/vg_hub_test' pytest tests/ -q`
Expected: all green; tables auto-created in `vg_hub_test`; dev DB row counts unchanged.

- [x] **Step 4: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test(conftest): support TEST_DATABASE_URL override

CI and engineers who want full isolation can now run pytest against a
throwaway database without touching the dev vg_hub. Default behaviour is
unchanged — when the env var isn't set we still load the dev .env."
```

---

## Task 3: Normalize push_log router prefix

**Files:**
- Modify: `backend/modules/push_log/routes.py:13` and the four `@router.<verb>("/api/...")` decorators

**Why:** Every other router declares `APIRouter(prefix="/api/...", tags=...)` and uses bare paths in decorators (e.g. `@router.get("")`). `push_log` is the lone exception (`APIRouter(tags=["push_log"])` + `@router.get("/api/push-log")` + `@router.post("/api/push-log")` + `@router.get("/api/products/{product_id}/push-status")`). CR #5. The push-status route lives under a different namespace (`/api/products/...`) so the cleanest fix is two routers.

- [x] **Step 1: Add a regression test that pins the route paths**

Append to `backend/tests/test_route.py` (create the file if it does not exist; if it exists, just append):

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_push_log_routes_are_registered_under_api(client: AsyncClient):
    """Pin the public path of push_log endpoints — a refactor must not move them."""
    # GET /api/push-log returns 200 (possibly empty list)
    r = await client.get("/api/push-log?limit=1")
    assert r.status_code == 200, r.text

    # POST /api/push-log requires a body, so without one we expect 422 (not 404)
    r = await client.post("/api/push-log", json={})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_push_status_route_is_registered_under_products(client: AsyncClient):
    import uuid
    # Random UUID — endpoint should respond 200 with empty list, not 404
    r = await client.get(f"/api/products/{uuid.uuid4()}/push-status")
    assert r.status_code == 200, r.text
```

- [x] **Step 2: Run the new tests to verify they pass against the current code**

Run: `cd backend && pytest tests/test_route.py -v`
Expected: PASS. They pin current behaviour so the refactor can't move paths.

- [x] **Step 3: Replace `backend/modules/push_log/routes.py:13` and decorators**

Edit `backend/modules/push_log/routes.py`:

1. Change line 13 from:
```python
router = APIRouter(tags=["push_log"])
```
to:
```python
router = APIRouter(prefix="/api/push-log", tags=["push_log"])
push_status_router = APIRouter(prefix="/api/products", tags=["push_log"])
```

2. Change line 16 from `@router.get("/api/push-log", response_model=list[PushLogRead])` to `@router.get("", response_model=list[PushLogRead])`.

3. Change line 57 from `@router.post("/api/push-log", response_model=PushLogRead, status_code=201)` to `@router.post("", response_model=PushLogRead, status_code=201)`.

4. Change line 91 from `@router.get("/api/products/{product_id}/push-status", response_model=list[ProductPushStatus])` to `@push_status_router.get("/{product_id}/push-status", response_model=list[ProductPushStatus])`.

- [x] **Step 4: Wire the second router in `backend/main.py`**

In `backend/main.py:26`, change:
```python
from modules.push_log.routes import router as push_log_router
```
to:
```python
from modules.push_log.routes import router as push_log_router, push_status_router
```

In the routers section (~line 110), after `app.include_router(push_log_router)` add:
```python
app.include_router(push_status_router)
```

- [x] **Step 5: Re-run the regression tests**

Run: `cd backend && pytest tests/test_route.py -v`
Expected: PASS. Same paths, no behaviour change for callers.

- [x] **Step 6: Verify against the live stack**

Run: `curl -sf http://127.0.0.1:8000/api/push-log?limit=1 | head -c 80 && echo`
Expected: JSON array (possibly empty), no 404.

- [x] **Step 7: Commit**

```bash
git add backend/modules/push_log/routes.py backend/main.py backend/tests/test_route.py
git commit -m "refactor(push_log): use APIRouter prefix like every other module

Was the only router that hardcoded /api/ in decorators instead of declaring
it on APIRouter. Splits push-status (which lives under /api/products/...)
into a second router so each router has a single namespace."
```

---

## Task 4: Hoist `from sqlalchemy import` out of seed_demo loops

**Files:**
- Modify: `backend/seed_demo.py:143` (and any other in-loop import found)

**Why:** Cosmetic but caught by CR #7. Imports are cheap on repeat (Python caches `sys.modules`) but reading the import inside a loop body suggests the import is conditional, which it isn't.

- [x] **Step 1: Find every in-loop import in seed_demo.py**

Run: `grep -n '    from sqlalchemy' backend/seed_demo.py`
Expected: at least line 143 prints. Note the line numbers.

- [x] **Step 2: Move every match to the top imports block**

Open `backend/seed_demo.py:1-12` and ensure the top imports include:
```python
from sqlalchemy import delete, select
```

Then delete each in-body `from sqlalchemy import …` line found in step 1.

- [x] **Step 3: Re-run the script to confirm no behaviour change**

Run: `cd backend && python seed_demo.py`
Expected: same output as before (idempotent seed).

- [x] **Step 4: Commit**

```bash
git add backend/seed_demo.py
git commit -m "chore(seed): hoist sqlalchemy imports to module top"
```

---

## Task 5: Delete dead `frontend/tailwind.config.js`

**Files:**
- Delete: `frontend/tailwind.config.js`

**Why:** Both `tailwind.config.js` (36 loc, minimal) and `tailwind.config.ts` (77 loc, full Blueprint tokens) exist. Tailwind picks the `.ts` first, so the `.js` file is dead. Confusing for newcomers reading the repo.

- [ ] **Step 1: Confirm the TS config is the live one**

Run: `cd frontend && grep -n 'theme\|extend\|content' tailwind.config.ts | head -10`
Expected: shows `content`, `theme.extend`, `colors`, etc. — confirms it is the real config.

- [ ] **Step 2: Confirm the JS config is unreferenced**

Run: `cd frontend && grep -rn 'tailwind.config.js' --include='*.json' --include='*.ts' --include='*.tsx' --include='*.mjs' .`
Expected: only `package-lock.json` matches (irrelevant). Nothing in app code depends on it.

- [ ] **Step 3: Delete the file**

Run: `rm frontend/tailwind.config.js`

- [ ] **Step 4: Verify the build still works**

Run: `cd frontend && npm run lint && npm run build`
Expected: build succeeds; CSS output identical.

- [ ] **Step 5: Commit**

```bash
git add -A frontend/tailwind.config.js  # records the deletion
git commit -m "chore(frontend): remove dead tailwind.config.js

tailwind.config.ts is the live config (full Blueprint tokens). The .js file
was a 36-line stub that never got the theme extension and no code referenced it."
```

---

## Task 6: Add `images.remotePatterns` to next.config.ts

**Files:**
- Modify: `frontend/next.config.ts`

**Why:** Next.js refuses external images in `<Image>` components unless the host is allow-listed. SanMar product images are served from `*.sanmar.com`, OPS images from `*.onprintshop.com`, and VG product images from a couple of hosts. Without this, prod-mode storefront PDPs render broken images.

- [ ] **Step 1: Replace `frontend/next.config.ts` contents**

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "*.sanmar.com" },
      { protocol: "https", hostname: "*.sanmarstatic.com" },
      { protocol: "https", hostname: "cdnl.sanmar.com" },
      { protocol: "https", hostname: "*.onprintshop.com" },
      { protocol: "https", hostname: "*.visualgraphx.com" },
      { protocol: "https", hostname: "images.ssactivewear.com" },
      { protocol: "https", hostname: "*.4over.com" },
    ],
  },
};

export default nextConfig;
```

- [ ] **Step 2: Verify dev server still serves**

Run: `cd frontend && curl -sI http://127.0.0.1:3000 | head -1`
Expected: `HTTP/1.1 200 OK` (frontend has hot-reload, no manual restart needed).

- [ ] **Step 3: Confirm a SanMar image renders**

Open `http://localhost:3000/products` in a browser and confirm at least one SanMar product card shows an image without a Next.js error overlay.

- [ ] **Step 4: Commit**

```bash
git add frontend/next.config.ts
git commit -m "feat(frontend): allow SanMar / OPS / 4Over / S&S CDN images

Next.js requires explicit allow-listing for next/image hosts. Adds wildcards
for the four supplier CDNs we actually serve images from in prod-mode."
```

---

## Task 7: Add a tiny `log` util and replace `console.error/warn`

**Files:**
- Create: `frontend/src/lib/log.ts`
- Modify: ~13 files under `frontend/src/app/(admin)/**/page.tsx` + `frontend/src/components/suppliers/reveal-form.tsx`

**Why:** 17 raw `console.error`/`console.warn` calls ship to production. Some only fire when the API is down so they're not noisy, but they'll surface in customer browser dev tools. Centralizing makes future "replace with toast / Sentry" a one-file change.

- [ ] **Step 1: Create `frontend/src/lib/log.ts`**

```typescript
/**
 * Tiny logger. console in dev, no-op in prod. Replace with toast / Sentry later
 * by editing only this file.
 */
const isProd = process.env.NODE_ENV === "production";

export const log = {
  error(message: string, ...rest: unknown[]) {
    if (isProd) return;
    // eslint-disable-next-line no-console
    console.error(message, ...rest);
  },
  warn(message: string, ...rest: unknown[]) {
    if (isProd) return;
    // eslint-disable-next-line no-console
    console.warn(message, ...rest);
  },
  info(message: string, ...rest: unknown[]) {
    if (isProd) return;
    // eslint-disable-next-line no-console
    console.info(message, ...rest);
  },
};
```

- [ ] **Step 2: Find every callsite**

Run: `cd frontend && grep -rn 'console\.\(error\|warn\)' src/`
Expected: ~17 matches across these files (current count, may have grown):
- `src/app/(admin)/page.tsx`
- `src/app/(admin)/products/page.tsx`
- `src/app/(admin)/products/setup/page.tsx`
- `src/app/(admin)/products/[id]/page.tsx`
- `src/app/(admin)/products/configure/page.tsx`
- `src/app/(admin)/products/archived/page.tsx`
- `src/app/(admin)/customers/page.tsx`
- `src/app/(admin)/suppliers/page.tsx`
- `src/app/(admin)/suppliers/[id]/page.tsx`
- `src/app/(admin)/suppliers/[id]/import/page.tsx`
- `src/app/(admin)/mappings/[supplierId]/page.tsx`
- `src/app/(admin)/api-registry/page.tsx`
- `src/components/suppliers/reveal-form.tsx`

- [ ] **Step 3: For each file: add the import and replace the calls**

In each file from step 2:

1. Add to the imports near the top: `import { log } from "@/lib/log";`
2. Replace `console.error(` → `log.error(`
3. Replace `console.warn(` → `log.warn(`

Do not touch `console.info`, `console.log`, `console.debug` if any exist — only `error` and `warn`.

- [ ] **Step 4: Verify**

Run: `cd frontend && grep -rn 'console\.\(error\|warn\)' src/ | grep -v 'src/lib/log.ts'`
Expected: zero matches.

Run: `cd frontend && npm run lint`
Expected: PASS, no new errors.

- [ ] **Step 5: Smoke-test the dashboard page**

Open `http://localhost:3000/` in a browser. With dev tools open, verify the page renders normally and any log calls show up (because dev mode).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/log.ts frontend/src/app frontend/src/components/suppliers/reveal-form.tsx
git commit -m "refactor(frontend): centralize error logging via lib/log

Replaces 17 raw console.error/warn calls with a single log util. No-op in
production so customers no longer see hub error trace in their dev tools.
Future swap to toast / Sentry is a one-file change."
```

---

## Task 8: Hardcoded local paths in 4 task-fill docs

**Files:**
- Modify: every file under `docs/Task_Test_fill/` that contains `/Users/PD/API-HUB`

**Why:** CR #9. The path was Vidhi's laptop — anyone else copying commands from those docs gets `cd: no such file or directory`.

- [ ] **Step 1: List the offending files**

Run: `grep -rln '/Users/PD/API-HUB' docs/`
Expected: ~4 files in `docs/Task_Test_fill/`.

- [ ] **Step 2: For each file, replace the absolute path**

Edit each match. Replace `cd /Users/PD/API-HUB` → `cd "$(git rev-parse --show-toplevel)"` and any reference to `/Users/PD/API-HUB/` (with trailing slash) → empty (so paths become repo-relative).

- [ ] **Step 3: Verify no remaining matches**

Run: `grep -rln '/Users/PD/API-HUB' docs/`
Expected: zero matches.

- [ ] **Step 4: Commit**

```bash
git add docs/Task_Test_fill
git commit -m "docs(task-fill): drop hardcoded /Users/PD/API-HUB paths

cd into the git toplevel instead so the runbook works on any laptop."
```

---

## Task 9: Update `code_review_all_tasks.md` with current resolution state

**Files:**
- Modify: `docs/code_review_all_tasks.md`

**Why:** Five of the nine code-review items are silently fixed by later commits (CR #1, #2, #3, #4, #6, #8 — verified on 2026-04-27 against `main`). Without updating the doc, anyone triaging will keep re-investigating closed items.

- [ ] **Step 1: For each item, append a status line referencing the file that closes it**

Edit `docs/code_review_all_tasks.md`. Under each issue heading, append a `**Status:**` line. Use these exact strings:

- CR #1 (Postgres port mismatch) → `**Status (2026-04-27): RESOLVED.** docker-compose.yml no longer exposes postgres on the host; n8n + api hit it on the docker network. Service-internal port stays 5432.`
- CR #2 (load_dotenv path) → `**Status (2026-04-27): RESOLVED.** backend/database.py:10 + backend/seed_demo.py:8 now use Path(__file__).parent.parent / ".env".`
- CR #3 (shadcn/ui not installed) → `**Status (2026-04-27): RESOLVED.** frontend/package.json declares the @radix-ui/* primitives and frontend/src/components/ui/ contains the shadcn-generated files.`
- CR #4 (push_log N+1) → `**Status (2026-04-27): RESOLVED.** backend/modules/push_log/routes.py:91-126 uses a GROUP BY subquery + a single Customer fetch — two queries total.`
- CR #5 (push_log route prefix) → `**Status (2026-04-27): RESOLVED in this plan (Task 3).**`
- CR #6 (catalog product list N+1) → `**Status (2026-04-27): RESOLVED.** backend/modules/catalog/routes.py:46-67 uses a variant_agg subquery for variant_count + price_min/max + total_inventory.`
- CR #7 (imports inside loops) → `**Status (2026-04-27): RESOLVED in this plan (Task 4).**`
- CR #8 (dashboard hardcoded data) → `**Status (2026-04-27): RESOLVED.** frontend/src/app/(admin)/page.tsx:67 calls api<Stats>("/api/stats") and renders live values.`
- CR #9 (hardcoded /Users/PD/API-HUB) → `**Status (2026-04-27): RESOLVED in this plan (Task 8).**`

- [ ] **Step 2: Commit**

```bash
git add docs/code_review_all_tasks.md
git commit -m "docs(code-review): annotate resolution status for each finding"
```

---

## Task 10: Purge stale Test Customer rows from dev DB (REQUIRES USER OK)

**Files:**
- No code changes. One-shot DB cleanup.

**Why:** Twelve sentinel `Test Customer*` rows leaked into `vg_hub` before Task 1's cleanup fix. They show up in `/api/customers` (`count == 13`, only 1 real). They cascade-delete via FKs.

**Important:** A previous attempt to do this without explicit permission was denied by the user this session. **Do not run the DELETE without asking. Show the preview first; wait for OK.**

- [ ] **Step 1: Show the user exactly what will be deleted**

Run:
```bash
docker compose exec -T postgres psql -U vg_user -d vg_hub -c \
  "SELECT id, name, ops_base_url FROM customers WHERE ops_base_url IN ('https://test.ops.com','https://test2.ops.com','https://test3.ops.com');"
```
Expected: 12 rows print.

- [ ] **Step 2: Ask the user for explicit OK to run the DELETE**

Display the row list and ask: "OK to delete these 12 rows? push_log / push_mappings / markup_rules cascade automatically."

- [ ] **Step 3: ONLY IF the user replies yes — run the DELETE**

```bash
docker compose exec -T postgres psql -U vg_user -d vg_hub -c \
  "DELETE FROM customers WHERE ops_base_url IN ('https://test.ops.com','https://test2.ops.com','https://test3.ops.com');"
```
Expected: `DELETE 12`.

- [ ] **Step 4: Verify**

```bash
curl -s http://127.0.0.1:8000/api/customers | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))'
```
Expected: `1` (only `vg-ops` real customer remains).

- [ ] **Step 5: No commit needed**

Database state change only — nothing tracked in git.

---

## Task 11: Verify the full Phase 0 stack still works

**Files:** none.

- [ ] **Step 1: Run the backend test suite**

Run: `cd backend && pytest -q`
Expected: all green. The new isolation test (`test_conftest_isolation.py`) is among them.

- [ ] **Step 2: Run frontend lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: PASS for both.

- [ ] **Step 3: Smoke the live stack**

Run:
```bash
curl -sf http://127.0.0.1:8000/health
curl -sI http://127.0.0.1:3000 | head -1
curl -sf http://127.0.0.1:8000/api/push-log?limit=1 >/dev/null && echo "push-log OK"
curl -sf "http://127.0.0.1:8000/api/products/$(curl -s http://127.0.0.1:8000/api/products | python3 -c 'import sys,json;print(json.load(sys.stdin)[0][\"id\"])')/push-status" >/dev/null && echo "push-status OK"
```
Expected: all four print success.

- [ ] **Step 4: Confirm no console.error/warn left in shipped frontend**

Run: `cd frontend && grep -rn 'console\.\(error\|warn\)' src/ | grep -v 'src/lib/log.ts'`
Expected: zero matches.

- [ ] **Step 5: Push the branch and open a PR**

```bash
git push origin tanishq
gh pr create --base main --head tanishq --title "phase0: hygiene — test isolation, push_log prefix, image patterns, log util" --body "Implements Phase 0 of the master backlog (docs/superpowers/plans/2026-04-27-phase0-hygiene.md). Each task has its own commit; review by walking the commit list."
```

---

## Self-review checklist

- ✅ Spec coverage: every Phase 0 item from `now-explore-entire-project-linear-gadget.md` §10 maps to a task above (test isolation → 1+2; tailwind → 5; image domains → 6; N+1 fixes already closed → 9; push_log prefix → 3; console cleanup → 7; CR doc update → 9; stale customer purge → 10). The `auth/` module decision and the `n8n_proxy` 404 are intentionally **excluded** — they need user input or belong to Phase 1.
- ✅ Placeholder scan: no "TBD" / "implement later" / "add appropriate error handling" — every code block is concrete.
- ✅ Type/symbol consistency: `_cleanup_test_customers` referenced consistently across Task 1 + the regression test; `push_status_router` declared in Task 3 step 3, exported in step 4, no rename. `log` util signature matches the call sites in Task 7 step 3.
- ✅ Bite-sized: every task ≤ 7 steps, every step ≤ 5 minutes' work.
- ✅ Frequent commits: 9 commits across the plan (Tasks 1-9), each independently reviewable.
