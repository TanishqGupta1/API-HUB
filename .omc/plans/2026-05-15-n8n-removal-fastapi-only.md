# Plan: n8n Removal + FastAPI-only API Surface

- **Status:** pending approval — consensus reached (Architect APPROVE, Critic APPROVE after 2 review rounds); awaiting user execution approval. RALPLAN-DR short mode.
- **Date:** 2026-05-15
- **Author:** ralplan consensus (Planner draft v1)
- **Owner:** Tanishq (PM + tech lead)

## Requirements Summary

Remove n8n entirely from api-hub. Migrate every flow currently owned by n8n (cron-scheduled supplier syncs, master-options sync trigger, ops_push webhook receiver, the `n8n_proxy` admin helper, the custom OnPrintShop n8n node, the workflow JSONs, and all `N8N_*` env vars) to direct FastAPI endpoints. Add `APScheduler` for cron-style scheduling. Strengthen FastAPI OpenAPI docs (summary, description, request/response field descriptions, example payload) so the public API surface is the single self-documenting contract. n8n must be re-addable later as a thin webhook caller without code changes.

## RALPLAN-DR Summary

### Principles
1. **Modular monolith** — state + logic stay in FastAPI; no new sidecar services.
2. **Public-API surface is self-documenting** — OpenAPI is the only contract source.
3. **Reversible removal** — n8n can be re-added as a thin webhook caller without code changes.
4. **No functional regression** — every scheduled sync (catalog/inventory/pricing/master-options) keeps firing.
5. **Database-tracked job state** — every scheduled run lands in `sync_jobs` for ops visibility.

### Decision Drivers (top 3)
1. **Operational simplicity** — one Python process beats `n8n service + custom node build + EFS mount + secrets`.
2. **Lower deployment cost** — drop n8n ECS task, EFS volume, secrets, ALB routing.
3. **Self-contained tests** — n8n workflow JSONs aren't testable in CI; APScheduler jobs are.

### Viable Options

**Option A — APScheduler in backend (recommended)**
- *Approach:* `apscheduler.schedulers.asyncio.AsyncIOScheduler` runs inside the FastAPI process with `SQLAlchemyJobStore` pointed at Postgres (sync URL `postgresql://...` for the jobstore engine; async `postgresql+asyncpg://...` stays the app default). Each job handler acquires `pg_try_advisory_lock(hashtext(job_id))` before running — multi-worker safe from day 1.
- *Pros:* zero new containers; DB-backed jobstore survives restarts; same auth/settings context as routes; testable with pytest; matches the `Modular monolith` principle; advisory lock means no operator-toggle landmine.
- *Cons:* requires a second SQLAlchemy engine (sync) just for `SQLAlchemyJobStore`; no visual UI for non-devs; long jobs must be awaited carefully or pushed to a thread pool.

**Option B — External cron container (Linux crontab + curl)**
- *Approach:* tiny sidecar with `cron` + `curl` that POSTs to FastAPI ingest endpoints on schedule.
- *Pros:* stupid simple; survives backend restarts; auth via env-loaded `X-Orchestrator-Key`.
- *Cons:* re-adds a sidecar (violates Principle 1); secrets still wired into a second container; no backend visibility into runs.

**Option C — AWS EventBridge → FastAPI**
- *Approach:* EventBridge schedules fire HTTPS requests at FastAPI integration endpoints.
- *Pros:* zero ops cost in cloud; fits ECS deployment.
- *Cons:* cloud lock-in (api-hub also runs locally — dev parity breaks); requires AWS creds in deploy; local dev still needs APScheduler-or-equivalent, so the second tool earns its keep only in prod.

**Chosen: Option A.** Option B fails Principle 1. Option C fails the local/cloud parity sub-principle of "reversible removal" (you'd have to swap schedulers per environment).

## Acceptance Criteria (testable)
1. `docker compose up -d` brings up exactly postgres + api + frontend; no n8n container.
2. `grep -rE "N8N_|n8n_proxy|MASTER_OPTIONS_SYNC_WORKFLOW_ID|NEXT_PUBLIC_PUSH_WORKFLOW_ID" backend/ frontend/ docker-compose*.yml .env.example` returns 0 matches (excluding plan/docs files).
3. `backend/modules/n8n_proxy/` does not exist on disk.
4. `n8n-workflows/` and `n8n.Dockerfile` do not exist in the repo; no path in `backend/`, `frontend/`, or `docker-compose*.yml` references `n8n-nodes-onprintshop/` (which lives outside this repo and is untouched).
5. `GET /openapi.json` — every operation has a non-empty `summary` AND a `description` (the OpenAPI operation `description` field, NOT the Python docstring) whose length ≥ 50 characters; every router carries a `tags=[...]` entry; every **protected route** declares `responses={401: ErrorEnvelope, 403: ErrorEnvelope, 404: ErrorEnvelope}`. "Protected route" means every router registered in `backend/main.py` with `dependencies=_auth` — concretely: `suppliers`, `customers`, `markup`, `markup_push`, `push_log`, `push_status`, `ps`, `catalog`, `categories`, `master_options`, `master_options_product_config`, `sync_jobs`, `ops_push`, `push_candidates`, `push_mappings`, `ops_config`, `category_import`, `promostandards_sync`, `import_jobs`, `pricing`, `pricing_customer`, `decorations`, `audit_log`, `customer_catalog`, `integrations_admin`, plus the new `scheduler` router (and `n8n_proxy` once Phase 3 deletes it). Excludes `auth_router` itself. New scheduler endpoints additionally include at least one `examples=[...]` payload (deep field-level docs across legacy endpoints are deferred to the sister OpenAPI plan).
6. `POST /api/master-options/sync` runs the upsert inline (or via APScheduler `run_job(...)`); no outbound HTTP to an n8n URL.
7. APScheduler runs `catalog-sync-weekly`, `inventory-sync-hourly`, `pricing-sync-daily`, `master-options-pull` jobs from a DB jobstore; each invocation writes a `sync_jobs` row with `started_at` + `completed_at` + `status`.
8. Existing pytest suite stays green; new tests added: `test_apscheduler_jobstore.py`, `test_master_options_sync_inline.py`.
9. `npm run build` in `frontend/` succeeds with no `NEXT_PUBLIC_N8N_*` / `NEXT_PUBLIC_PUSH_WORKFLOW_ID` references.
10. `/workflows` admin page replaced with `/sync-jobs` page driven by APScheduler + existing `sync_jobs` API.
11. `CLAUDE.md` no longer claims "n8n owns OPS push" or "n8n orchestrates sync".

## Implementation Steps

### Phase 1 — Backend scheduling foundation (additive, no deletion)
- Add `apscheduler[sqlalchemy]>=3.10` and `psycopg2-binary>=2.9` to `backend/requirements.txt`. (`psycopg2-binary` powers the sync SQLAlchemy engine that `SQLAlchemyJobStore` requires; app queries continue on `asyncpg`.)
- Add `POSTGRES_SYNC_URL` to `backend/database.py` / settings: `postgresql://...` (psycopg2 driver) derived from the existing async URL. Jobstore-only — application queries stay on the async engine.
- APScheduler auto-creates an `apscheduler_jobs` table on first scheduler start; do not add an Alembic migration. Confirm the auto-create completes idempotently on subsequent boots and document in `backend/modules/scheduler/README.md`. The README also documents the R7 boot-timestamp semantics: single-worker boot is clean; rolling deploys with overlapping worker boots may emit at most one spurious "cutover orphan" row per overlapping in-flight job, which the next scheduled tick re-runs (idempotent upserts make this safe).
- Create `backend/modules/scheduler/{__init__.py, scheduler.py, jobs.py, routes.py, advisory_lock.py}`:
  - `scheduler.py`: `AsyncIOScheduler(jobstores={"default": SQLAlchemyJobStore(url=settings.POSTGRES_SYNC_URL)})`.
  - `advisory_lock.py`: async context manager `with_job_lock(job_id)` that opens a dedicated SQLAlchemy transaction (`async with engine.begin() as conn:`) and runs `SELECT pg_try_advisory_xact_lock(hashtext($job_id))`. Transaction-scoped — Postgres auto-releases on COMMIT/ROLLBACK when the `async with` exits, so there is no leaked session lock surviving across handler invocations. Yields `True` if acquired, `False` if another worker holds it. Every registered job wraps its body in this lock so multi-worker deploys never duplicate-run.
  - `jobs.py`: register `catalog-sync-weekly`, `inventory-sync-hourly`, `pricing-sync-daily`, `master-options-pull`. Each handler calls the existing supplier-adapter function inside `with_job_lock(job_id)` and writes a `sync_jobs` row.
  - `routes.py`: `GET /api/scheduler/jobs` (list), `POST /api/scheduler/jobs/{job_id}/run-now` (trigger), both admin-JWT-authed.
- Create `backend/tests/test_apscheduler_jobstore.py` covering: (a) startup creates `apscheduler_jobs` table; (b) registered jobs appear in `/api/scheduler/jobs`; (c) `test_advisory_lock_prevents_double_run` — spawn two parallel calls to the same job handler, assert only one completes the body, the other observes `pg_try_advisory_xact_lock=false` and exits.
- Create `backend/tests/test_master_options_sync_inline.py` covering the inline scheduler dispatch path replacing `_trigger_n8n_workflow` (assert a `sync_jobs` row is created and the workflow is queued through the scheduler — no outbound HTTP).
- `backend/main.py` lifespan: `scheduler.start()` on startup, `scheduler.shutdown(wait=False)` on shutdown. No env flag — advisory lock makes multi-worker safe by default.

### Phase 2 — Inline current n8n callouts
- `backend/modules/master_options/routes.py`: replace `_trigger_n8n_workflow` body with a direct call to `scheduler.run_job("master-options-pull")`. The route returns immediately with the new `sync_jobs.id` (202 Accepted) once the scheduler has accepted the trigger.
- `backend/modules/ops_push/service.py`: delete `trigger_n8n_push` and any caller — ops_push already routes through the M1 admin proxy + gateway (`/api/integrations/admin/push-requests`).
- `backend/main.py`: drop the `N8N_WEBHOOK_BASE_URL` startup check; refactor `_required_in_production` list.

### Phase 3 — Delete n8n surface
- Delete `backend/modules/n8n_proxy/` (4 endpoints + helper).
- Delete `backend/tests/test_n8n_url_config.py`.
- Rewrite `backend/tests/test_master_options_sync.py` to assert inline scheduler invocation (drop the `_trigger_n8n_workflow` mock; assert a `sync_jobs` row appears + `scheduler.run_job` is invoked).
- Edit `backend/tests/test_startup_checks.py` to drop the `N8N_WEBHOOK_BASE_URL` env-var assertions from the `_required_in_production` test (n8n env vars no longer required).
- Edit `backend/tests/test_admin_route_preserved.py` to drop the `trigger_n8n_push` spy; assert push goes through the M1 admin proxy + `modules/ops_push/gateway.execute_push` path instead.
- Delete `n8n-workflows/` directory entirely.
- Delete `n8n.Dockerfile`.
- `n8n-nodes-onprintshop/` lives as a *sibling* of `api-hub/` (outside this repo) — `/Users/tanishq/Documents/project-files/api-hub/n8n-nodes-onprintshop/`. The monorepo copy at `api-hub/n8n-nodes-onprintshop/` referenced by older docs does **not** exist on disk today. Action in PR-A: only ensure `n8n.Dockerfile` and `docker-compose*.yml` no longer reference `../n8n-nodes-onprintshop/` so the sibling tree can be extracted to its own repo independently. The sibling tree stays untouched in this PR; a docs/legacy/ archive is unnecessary because the source is already external to this repo.
- `docker-compose.yml`: remove the `n8n:` service block + `N8N_*` env passthrough on `api:`.
- `docker-compose.override.yml`: drop the n8n override hunk.
- `.env` + `.env.example`: remove `N8N_API_KEY`, `N8N_API_BASE_URL`, `N8N_WEBHOOK_BASE_URL`, `N8N_PUSH_WEBHOOK_URL`, `MASTER_OPTIONS_SYNC_WORKFLOW_ID`, `NEXT_PUBLIC_PUSH_WORKFLOW_ID`, `NEXT_PUBLIC_N8N_URL`.
- **ECS removal deferred to PR-B (separate deliverable).** `deployment/ecs/api-hub.yaml` still references the n8n task, ALB rule for `n8n.api-hub.local`, EFS mount, and `N8N_BASIC_AUTH_PASSWORD` secret. Code merge (this PR) lands first with idempotent upserts so any in-flight n8n cron runs are safe duplicates; PR-B removes the n8n ECS task + ALB rule + EFS mount + secret after staging verifies APScheduler is healthy for one full cycle of the slowest cron (weekly catalog sync).

### Phase 4 — Frontend cleanup
- Replace `frontend/src/app/(admin)/workflows/page.tsx` with `frontend/src/app/(admin)/sync-jobs/page.tsx` that calls `GET /api/scheduler/jobs` + `GET /api/sync-jobs`.
- `frontend/src/components/products/publish-button.tsx`: drop `NEXT_PUBLIC_PUSH_WORKFLOW_ID` and the n8n editor link; route through the M1 admin proxy endpoint (already wired since #112).
- `frontend/src/app/(admin)/products/configure/page.tsx`: replace the `NEXT_PUBLIC_N8N_URL` error message with a link to `/sync-jobs`.
- Update `SidebarNav.tsx` Workflows link → Sync Jobs.

### Phase 5 — OpenAPI documentation skeleton (deep pass deferred)
Scope kept narrow so this PR stays reviewable. Deep field-level descriptions + examples land in a follow-up plan: `2026-05-15-openapi-deep-docs.md` (sister plan, drafted but executed separately).

In this PR:
- Every router gets explicit `tags=["<module>"]` (suppliers, catalog, customers, markup, push_log, ps_directory, sync_jobs, master_options, integrations, ops_push, scheduler).
- Every protected route declares `responses={401: ErrorEnvelope, 403: ErrorEnvelope, 404: ErrorEnvelope}` via a shared FastAPI `responses` constant.
- Every route already missing `response_model` gets one (no field-level edits to existing models).
- New scheduler routes ship with full docstrings + `Field(description=...)` + at least one `examples=[...]` — they set the template the deep pass will follow.
- Add an OpenAPI module-level description on `FastAPI(title=..., description=..., version=...)` in `backend/main.py`.

Deferred to the sister plan: per-field `Field(description=..., examples=[...])` rewrites across 60+ existing endpoints, response-envelope normalization, request-body example payloads.

### Phase 6 — Docs + plan updates
- Update `CLAUDE.md`: replace "n8n orchestrates sync schedules…" + "n8n owns OPS push" with the APScheduler section + the FastAPI-only push pipeline.
- Update `plans/2026-04-16-v1-integration-pipeline.md` — mark n8n-related tasks superseded; cross-link this plan.
- Add a short `docs/migrations/2026-05-15-n8n-removal.md` for ops, covering: (a) the new `/api/scheduler/jobs` admin surface, (b) the dual auth picture (`X-Orchestrator-Key` for M1 gateway vs `X-Ingest-Secret` for legacy ingest), (c) PR-B teardown schedule.
- Draft two follow-up plan stubs in `.omc/plans/`:
  - `2026-05-15-openapi-deep-docs.md` — sister plan for the field-level OpenAPI rewrite (Requirements + ACs only; full plan filled out post-merge).
  - `2026-05-15-n8n-ecs-teardown.md` — PR-B plan stub listing ECS task / ALB rule / EFS mount / secret deletions + the 48h bake gate.

## Risks and Mitigations
- **R1: APScheduler in every worker fires duplicate runs.** *Mitigation in this PR:* `pg_try_advisory_lock(hashtext(job_id))` per-job inside the handler — only the worker that gets the lock executes the body. Lock auto-released on session end / handler exit. No operator-toggle landmine.
- **R2: Long-running supplier sync blocks event loop.** *Mitigation:* chunk fetches; route blocking IO via `loop.run_in_executor`; existing `sync_jobs` chunk-level progress survives.
- **R3: ECS deployment regression — n8n task removal must coordinate with backend deploy.** *Mitigation:* this plan ships code in PR-A (APScheduler + n8n callouts removed, n8n container untouched, dupes are safe upserts). PR-B deletes the ECS n8n task, ALB rule, EFS mount, and secret only after staging verifies APScheduler runs healthy. **Bake target = 48 hours of healthy runs + one manual `run-now` on each registered job (catalog/inventory/pricing/master-options).** Weekly-catalog-sync verification is satisfied by the manual run-now plus the 48h heartbeat; PR-B lands ~2 days after PR-A merges, not 7.
- **R4: Custom OnPrintShop n8n node has standalone value (22 operations, 33 todo) but lives outside this repo.** *Mitigation in this PR:* drop every reference to `../n8n-nodes-onprintshop/` from `n8n.Dockerfile` (deleted whole) and `docker-compose*.yml` (n8n service block deleted whole) — the sibling source tree stays where it is, untouched. Sibling-repo extraction (publish under VisualGraphxLLC GitHub org) is a tracked follow-up.
- **R5: Reintroduction cost (n8n later).** *Mitigation:* keep `/api/integrations/v1/...` shapes and idempotency keys exactly as today; n8n re-adopt = one workflow JSON, no code changes.
- **R6: OpenAPI rewrite breaks generated TypeScript clients (if any).** *Mitigation:* no generated clients in this repo today (frontend uses `fetch` directly); flag for future client-gen step.
- **R7: `sync_jobs` rows created by n8n workflows mid-cutover hang in `status=running`.** *Mitigation:* PR-A reads `APP_BOOT_TIMESTAMP` from `backend/main.py` lifespan start time and adds a one-shot startup task that marks every `sync_jobs` row with `status IN ('running','queued') AND started_at < APP_BOOT_TIMESTAMP` as `status='failed'` with `errors='cutover orphan: n8n removed at <APP_BOOT_TIMESTAMP>'`. Cutover-scoped — only sweeps pre-deploy rows, never kills legitimate long-running jobs (weekly catalog sync against 994 suppliers can exceed 1h). Idempotent on subsequent boots: every later run starts with an `APP_BOOT_TIMESTAMP` greater than all surviving orphans, so the sweep continues to no-op.
- **R8: `INGEST_SHARED_SECRET` lifecycle ambiguous after n8n removal.** Currently auths the legacy `/api/ingest/*` routes used by n8n. *Mitigation:* keep `INGEST_SHARED_SECRET` for the legacy ingest endpoints — they are still useful for direct `curl`/scripted ingest. Document the dual auth surface in `docs/migrations/2026-05-15-n8n-removal.md`: orchestrators should prefer the M1 gateway path with `X-Orchestrator-Key`; the X-Ingest-Secret path remains for `n8n_proxy`-free scripted use cases.

## Verification Steps
- `docker compose up -d` → 3 containers (`postgres`, `api`, `frontend`); `docker compose ps` confirms.
- `docker compose logs api | grep -i 'AsyncIOScheduler started'` → present within 5s of api startup.
- `curl -sf http://localhost:8000/api/scheduler/jobs | jq 'length'` → 4 (or whatever the registered count is).
- `curl -sf -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/scheduler/jobs/catalog-sync-weekly/run-now` → 202; new `sync_jobs` row visible within 30s on demo data.
- `curl -sf http://localhost:8000/openapi.json | jq '.paths | to_entries[] | .value | to_entries[] | select(.value.summary == null or .value.summary == "") | .key'` → empty.
- Multi-worker advisory-lock smoke test: `pytest backend/tests/test_apscheduler_jobstore.py::test_advisory_lock_prevents_double_run` — spawns two scheduler instances in the same process, asserts only one runs the job per tick.
- `npm run build` in `frontend/` exits 0 with no `NEXT_PUBLIC_N8N_*` references.
- `pytest backend/` → green.
- `grep -rE "n8n|N8N_" backend frontend docker-compose*.yml deployment/ .env.example` → only docs/migration mentions left.

## ADR

**Decision:** Remove n8n; adopt APScheduler in the FastAPI process for cron-style scheduling; harden every direct FastAPI endpoint with rigorous OpenAPI docs as the single integration surface.

**Drivers:**
1. Operational simplicity (one less service, one less Dockerfile, one less ALB rule).
2. Self-contained test coverage (n8n JSONs are not testable in CI).
3. Lower deployment + secret surface (drop `N8N_BASIC_AUTH_PASSWORD`, `N8N_API_KEY`, EFS mount).

**Alternatives considered:**
- External cron container (rejected — violates "no new sidecar").
- AWS EventBridge (rejected — breaks local/cloud parity, requires a second scheduler for dev).
- Keep n8n only for cron (rejected — 90% of n8n's operational cost remains for ~10% of its value).

**Why chosen:** APScheduler is a single Python dependency, runs in-process, shares the existing DB connection, and produces the same `sync_jobs` audit trail today's workflows aim for. Re-adding n8n later is cheap because integration endpoints are already idempotent upserts gated by `X-Orchestrator-Key`.

**Consequences:**
- Backend gets a startup task that owns scheduled jobs; jobstore lives in postgres (sync engine alongside the async app engine).
- `pg_try_advisory_lock(hashtext(job_id))` makes multi-worker deploys safe by default — no operator flag.
- Loss of the visual workflow editor (acceptable today; revisit if a non-dev workflow user emerges).
- ECS deploy yaml shrinks in a follow-up PR-B (n8n task + ALB + EFS + secret removed only after PR-A bakes in staging).
- Deep OpenAPI doc rewrite is a sister plan (`2026-05-15-openapi-deep-docs.md`); this PR ships the skeleton (tags, response models, response codes) only.

**Follow-ups:**
- Land sister plan `2026-05-15-openapi-deep-docs.md` (field-level descriptions + example payloads across legacy endpoints).
- PR-B `2026-05-15-n8n-ecs-teardown.md` — remove ECS n8n task, ALB rule, EFS mount, secret after one healthy weekly-cycle in staging.
- Extract `n8n-nodes-onprintshop/` from archive to its own GitHub repo (snapshot lives at `docs/legacy/n8n-nodes-onprintshop-snapshot.tar.gz` until then).
- Surface `/sync-jobs` admin page (already in Phase 4).

## Changelog
- v1 (2026-05-15): initial planner draft.
- v5 (2026-05-15): Critic APPROVE on v4. Consensus reached. Applied Critic's minor improvement — `backend/modules/scheduler/README.md` to document R7 rolling-deploy semantics (spurious cutover-orphan row possible during overlapping worker boots; self-healing via idempotent upserts). Plan status moved to "pending user execution approval."
- v4 (2026-05-15): Architect ITERATE round 2 absorbed —
  - AC #5 protected-router list expanded from 16 to 25 routers based on the actual `dependencies=_auth` registrations in `backend/main.py:257-284`.
  - R7 orphan cleanup re-scoped from "older than 1 hour" to "`started_at < APP_BOOT_TIMESTAMP`" so the sweep only touches pre-deploy rows and cannot kill a legitimate long-running weekly catalog sync.
- v3 (2026-05-15): Critic ITERATE round 1 absorbed —
  - Advisory lock spec switched to `pg_try_advisory_xact_lock` inside an explicit `async with engine.begin()` transaction so the lock is released by COMMIT/ROLLBACK and never leaks across handler invocations (Critic fix #1).
  - Phase 3 archive path corrected: `n8n-nodes-onprintshop/` is a sibling of api-hub, not inside it. R4 + AC #4 rewritten — no archive, just drop in-repo references (Critic fix #2).
  - Phase 3 now explicitly edits `backend/tests/test_startup_checks.py` (drop N8N env-var assertions) and `backend/tests/test_admin_route_preserved.py` (drop the `trigger_n8n_push` spy) (Critic fix #3).
  - Phase 1 now explicitly creates `backend/tests/test_apscheduler_jobstore.py` + `backend/tests/test_master_options_sync_inline.py` so AC #8 + the verification step reference artifacts the plan actually produces (Critic fix #4).
  - Added `psycopg2-binary>=2.9` to Phase 1's requirements addition (Critic fix #5).
  - AC #5 now defines "protected route" by enumerating the routers `backend/main.py` registers with `dependencies=_auth` (Critic fix #6).
  - Phase 2 stale `SCHEDULER_ENABLED=0` reference removed (Critic fix #7).
  - Phase 1 jobstore note added: APScheduler auto-creates `apscheduler_jobs`; no Alembic migration; document in `backend/modules/scheduler/README.md` (Critic fix #8).
  - R3 bake target tightened to 48 hours + manual run-now per job; PR-B lands ~2 days after PR-A (Critic fix #9).
  - R7 added for in-flight `sync_jobs` cutover orphans (Critic gap fix).
  - R8 added for `INGEST_SHARED_SECRET` lifecycle (Critic gap fix).
  - Phase 6 now drafts `2026-05-15-openapi-deep-docs.md` and `2026-05-15-n8n-ecs-teardown.md` stubs in-PR so sister-plan paths are pinned (Critic gap fix).
- v2 (2026-05-15): Architect ITERATE round 1 absorbed —
  - Replaced `SCHEDULER_ENABLED` env flag with `pg_try_advisory_lock` per-job inside handlers (blocker #2).
  - Split deep OpenAPI doc pass into sister plan `2026-05-15-openapi-deep-docs.md`; this PR ships skeleton (tags + response models + protected-route response codes + new-scheduler-routes example) only (blocker #3).
  - Split ECS n8n teardown into follow-up PR-B `2026-05-15-n8n-ecs-teardown.md`; PR-A ships code-only (blocker #5).
  - Added Phase-1 task: introduce `POSTGRES_SYNC_URL` setting for the `SQLAlchemyJobStore` engine (nice-to-have #3).
  - Pinned `n8n-nodes-onprintshop/` destination: `docs/legacy/n8n-nodes-onprintshop-snapshot.tar.gz` + a README capturing scope (nice-to-have #4).
  - Strengthened AC #5: require `description.length >= 50` + `tags` on every router + typed `ErrorEnvelope` 401/403/404 + at least one `examples=[...]` on each new scheduler endpoint (nice-to-have #6).
  - Added advisory-lock unit test to verification steps.
