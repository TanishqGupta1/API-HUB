# Hygiene & Deployment Tasks — Session Log

This document records each task completed in this session, what was done, and why it matters.

---

## Task 1 — Delete `frontend/tailwind.config.js`

**Status:** Done  
**File deleted:** `frontend/tailwind.config.js`

### What was done

The file `tailwind.config.js` (CommonJS format, `module.exports`) was deleted. The live Tailwind config is `tailwind.config.ts` (TypeScript, `export default`).

### Why this was important

The project had two Tailwind config files at the same time:

| File | Format | Status |
|------|--------|--------|
| `tailwind.config.js` | Old CommonJS, no shadcn/ui CSS variables, no `borderRadius` | Dead — was the original config before shadcn was added |
| `tailwind.config.ts` | TypeScript, full shadcn/ui CSS variable colors, `borderRadius` tokens | Live — the one Next.js actually picks up |

Having both files is dangerous because:
- A future developer might edit the `.js` file thinking it's active, and their changes would be silently ignored
- Build tools that scan for config files could pick up the wrong one
- It creates confusion about which config is the source of truth

The `.js` file was not referenced anywhere in the codebase (confirmed by grep). Deleting it makes the project unambiguous — there is now exactly one Tailwind config.

---

## Task 2 — Replace `console.error` with `log.error` in `sanmar-mapping-panel.tsx`

**Status:** Done  
**File changed:** `frontend/src/components/mappings/sanmar-mapping-panel.tsx`

### What was done

- Added `import { log } from "@/lib/log"` at the top of the file
- Replaced `console.error("Polling error", e)` on line 52 with `log.error("Polling error", e)`
- Confirmed zero remaining `console.error` or `console.warn` calls anywhere in `frontend/src`

### Why this was important

The project has a dedicated `log` utility at `frontend/src/lib/log.ts`. It wraps `console.error/warn` but **silences them in production** (`process.env.NODE_ENV === "production"`). Raw `console.error` calls bypass this gate and leak internal error details — stack traces, internal API URLs, data shapes — into the browser console of production users.

The `sanmar-mapping-panel.tsx` was the only file still using a raw `console.error`. It sits inside a polling interval that hits the sync-jobs API every 2 seconds — a frequent, user-facing code path. Any network blip would log raw error objects to the production console. Replacing it with `log.error` means errors are visible in development but silent in production.

---

## Task 3 — Create `n8n-nodes-onprintshop/.npmignore`

**Status:** Done  
**File created:** `n8n-nodes-onprintshop/.npmignore`

### What was done

Created `.npmignore` in the `n8n-nodes-onprintshop/` package that explicitly excludes:
- `nodes/` — TypeScript source files
- `credentials/` — TypeScript source files
- `scripts/` — internal build scripts
- `gulpfile.js`, `tsconfig.json` — build tooling
- `node_modules/` — dev dependencies
- `OPS-NODE-GAP-ANALYSIS.md` — internal planning doc

Ran `npm pack --dry-run` to confirm only `dist/`, `package.json`, `LICENSE`, and `README.md` ship in the tarball.

### Why this was important

The `n8n-nodes-onprintshop` package is installed into n8n directly from GitHub (not npm registry). When installing from a git URL, npm clones the full repository directory — it does not automatically strip source files the way a published npm package would.

The `package.json` already has a `files` whitelist (`["dist", "package.json", "README.md"]`), which works correctly for `npm publish`. But for **GitHub installs**, npm respects `.npmignore` as the primary exclusion mechanism.

Without `.npmignore`:
- Source TypeScript files (`nodes/`, `credentials/`) ship alongside compiled `dist/` — doubling package size
- `node_modules/` (dev deps like TypeScript, gulp) could be included — making the install massive and slow
- `OPS-NODE-GAP-ANALYSIS.md` (an internal gap-tracking doc) would be visible to anyone who installs the package

With `.npmignore`, the install is lean: only the compiled output that n8n actually needs.

---

## Task 4 — Fix `seed_demo.py` category string population

**Status:** Done  
**File changed:** `backend/seed_demo.py`

### What was done

The `Product` model has two category fields:
- `category` — a plain string (e.g. `"Polos"`) used for display on the PDP
- `category_id` — a UUID foreign key linking to the `Category` table

The seed script was setting `category_id` correctly but never setting the `category` string field. Fixed in two places:

1. **New products** — added `category=category_name` alongside `category_id=category_id` when constructing the `Product` object
2. **Existing products** — added `existing_product.category = category_name` when backfilling the category FK on an existing row

Also fixed a **duplicate `print + engine.dispose()`** at the end of the `seed()` function — it was calling both lines twice, meaning the engine was disposed twice on every run.

### Why this was important

The product detail page (PDP) reads `product.category` to display which category a product belongs to (e.g. "Polos", "Outerwear"). Because the seed never set this field, running `seed_demo.py` and then opening a VG product on the storefront would show a blank category — making the demo look broken even though the data was correct in the database.

The `category` string field exists as a denormalized display value so the PDP does not need to join through the `Category` table just to show a label. Keeping both `category_id` (for relational integrity) and `category` (for display) in sync is important for the demo to work end-to-end.

---

## Task 5 — `docker-compose.yml` env passthrough + `.env.example`

**Status:** Done  
**Files changed:** `docker-compose.yml`, `.env.example`

### What was done

**`docker-compose.yml`** — added `ALLOWED_ORIGINS` to the `api` service environment:
```yaml
- ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173}
```

**`.env.example`** — added `API_BASE_URL` with explanation of what it controls and two example values (local dev vs production), and added a comment to the existing `ALLOWED_ORIGINS` entry.

### Why this was important

**`ALLOWED_ORIGINS` was never wired into docker-compose.**  
`backend/main.py` reads `ALLOWED_ORIGINS` from the environment to configure FastAPI's CORS middleware. Without the passthrough in `docker-compose.yml`, the env var you set in `.env` was silently ignored when running in Docker — the backend always fell back to the hardcoded default (`localhost:3000, localhost:5173`). In production, where the frontend runs on a real domain, CORS would fail for every browser request because the production origin was not in the allowed list.

**`API_BASE_URL` was undocumented.**  
Every n8n workflow uses `$env.API_BASE_URL` to call the FastAPI backend. The variable was already in `docker-compose.yml` for the n8n service, but was missing from `.env.example` — so a developer setting up a new environment or deploying to production would have no way to know this variable existed or what value to give it.

---

## Task 6 — Create `deployment/aws-app-runner.yaml` + `deployment/README.md`

**Status:** Done  
**Files created:** `deployment/aws-app-runner.yaml`, `deployment/README.md`

### What was done

Created a CloudFormation template that deploys two AWS App Runner services:

| Service | Image | Port | CPU | Memory |
|---------|-------|------|-----|--------|
| `api-hub-backend` | ECR (FastAPI) | 8000 | 1 vCPU | 2 GB |
| `api-hub-frontend` | ECR (Next.js standalone) | 3000 | 0.25 vCPU | 0.5 GB |

The template includes:
- **IAM role** — `AppRunnerECRAccessRole` so App Runner can pull from ECR
- **Parameters** — all secrets (`PostgresUrl`, `SecretKey`, `IngestSharedSecret`) marked `NoEcho: true` so they never appear in CloudFormation logs
- **Environment variables** — all required env vars passed to each service (`POSTGRES_URL`, `SECRET_KEY`, `INGEST_SHARED_SECRET`, `ALLOWED_ORIGINS`, `N8N_BASE_URL` for backend; `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_N8N_URL` for frontend)
- **Health checks** — backend checks `GET /api/health`, frontend checks `GET /`
- **Auto-scaling** — backend scales 1→5 instances, frontend scales 1→3

Also created `deployment/README.md` with step-by-step instructions: build + push ECR images, deploy the stack, get service URLs, and update after code changes.

### Why this was important

Without this file, deploying to AWS required manually clicking through the console or writing commands from scratch each time. The CloudFormation template makes deployment:

- **Repeatable** — run one command to create or update the full stack
- **Auditable** — the entire infrastructure is defined in version-controlled code
- **Safe** — secrets are passed as parameters (`NoEcho: true`), never hardcoded in the template
- **Consistent** — the same template creates identical environments for staging and production

App Runner was chosen over ECS/EC2 because it handles container orchestration, HTTPS, and auto-scaling automatically — no VPC, load balancer, or task definition configuration needed. For a monolith like API-HUB this is the right tradeoff.

---

## Task 7 — Update `docs/code_review_all_tasks.md`

**Status:** Done  
**File changed:** `docs/code_review_all_tasks.md`

### What was done

Two additions to the existing code review document:

1. **New resolution summary table at the top** — replaces the original issues-only summary with a full table showing each issue's resolution status, exact file, and line numbers where the fix lives. Every issue is marked ✅ RESOLVED with a specific reference.

2. **Session update section at the bottom** — documents the 6 tasks completed in this session (2026-05-04) that were separate from the original 9 code review issues: deleting the dead tailwind config, replacing the last `console.error`, creating `.npmignore`, fixing seed_demo categories, docker-compose env passthrough, and the AWS App Runner config.

### Why this was important

The original document tracked issues but had no single place to confirm all were resolved. A future developer reading it would have to hunt through status lines buried under each issue section to understand the overall health of the codebase. The new summary table answers "are we clean?" in one glance.

The session update section matters because the work done today (hygiene fixes, deployment config) was not tracked in any plan file — the plan checkboxes were stale. Without adding it here, this work would be invisible to anyone reviewing the project history.

---

## Task 8 — Final lint + build verification

**Status:** Done  
**Files changed:** `frontend/next.config.ts` (build fix discovered during this step)

### What was done

**Lint (`npm run lint`)** — passed with warnings only, zero errors. All warnings are pre-existing patterns unrelated to this session's changes:
- `react-hooks/exhaustive-deps` — missing `useEffect` dependencies in 3 files
- `@next/next/no-img-element` — raw `<img>` instead of `<Image />` in 5 files

**Build (`npm run build`)** — initially failed with:
```
Error: ENOENT: no such file or directory, open '.../frontend/browser/default-stylesheet.css'
Error occurred prerendering page "/products/configure"
```

**Root cause:** `isomorphic-dompurify` (used in `configure/page.tsx`) depends on `jsdom` for server-side sanitisation. `jsdom` reads `browser/default-stylesheet.css` using `__dirname` at runtime. When webpack bundles `jsdom` into the Next.js server bundle, it loses the real `__dirname`, so the path resolves to the wrong location (`frontend/browser/` instead of inside `node_modules`).

**Fix applied:** Added `serverExternalPackages` to `frontend/next.config.ts`:
```ts
serverExternalPackages: ["isomorphic-dompurify", "jsdom"],
```

This tells Next.js not to bundle these two packages — they stay as external `require()` calls resolved from `node_modules` at runtime, so `jsdom`'s `__dirname` remains correct.

**After fix:** Build passed cleanly — all 19 pages generated, standalone output produced.

### Why this was important

The build failure was a latent bug that would have broken any production deployment. The `"use client"` directive on `configure/page.tsx` does not prevent Next.js from running the page's module graph on the server during static generation — it only affects hydration. Any server-side import of `jsdom` without the external package flag will silently work in dev (webpack dev mode handles `__dirname` differently) but fail in production builds.

Catching this in the build step — rather than during a live deployment — is exactly what final verification is for.


2026-04-27-phase0-hygiene.md

Task	File	What
Task 5	|| frontend/tailwind.config.js	|| Delete it — dead file, .ts version is live

Task 7	|| frontend/src/components/mappings/sanmar-mapping-panel.tsx:52	|| Replace console.error("Polling error", e) with log.error(...)

Task 9 ||	docs/code_review_all_tasks.md	|| Update resolution state for each item

Task 11	—	|| Final lint + build + PR


2026-04-24-aws-deployment-readiness.md

Task	File	What
Task 6	||  docker-compose.yml + .env.example	 ||   Add API_HUB_BASE_URL + CORS_ORIGINS env passthrough to services

Task 7	 || n8n-nodes-onprintshop/.npmignore	  || Create it so package installs cleanly from GitHub

Task 11	||deployment/aws-app-runner.yaml + deployment/README.md	|| AWS App Runner config — only file truly missing

Task 12	|| backend/seed_demo.py	|| Set product.category string field (currently not set, breaks PDP demo)