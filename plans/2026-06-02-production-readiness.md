# Production-Readiness Plan — Close the Gap to Live

**Date:** 2026-06-02
**Author:** review + exploration pass (Claude), reconciled against actual code
**Inputs:** full-project exploration (suppliers, frontend, plans, tests), open PRs #159/#160, open issues #147–#153 + #29, master-rollout-plan (2026-05-27).

**Goal:** one sequenced plan that lands the in-flight PRs, hardens reliability and tests, and clears the doc/dead-code debt — so the platform is genuinely production-ready for the first live customer, not just feature-complete.

---

## 0. Current state (verified — do NOT redo)

The master-rollout-plan (2026-05-27) Phases A–D have **landed**. Many plan docs still show unticked `- [ ]` boxes, but the work shipped. Confirmed in code:

- **Auth foundation (Phase A)** — merged #144. `require_customer_access` (defined `modules/auth/dependencies.py:149`) genuinely enforced across `markup`, `customer_catalog`, `ops_config`, `decorations`, `customers`, `pricing`, `ops_push`, `push_candidates` (verified used, not just imported). Register mints `vg_admin` **only on zero-users bootstrap** (atomic `~exists(User)` at `auth/routes.py:281`), then closes with 409; post-bootstrap `/users` defaults to `customer_admin` and is `VGAdmin`-gated — safe by design.
- **Redis backplane (Phase E start)** — merged #156. `cache.py`, `limiter.py`, token cache, shared rate-limiter present.
- **Customer portal** — merged #136 → #137.
- **CI gate is blocking** — `deploy-dev.yml` runs `pytest --tb=short -q` (no `|| true`).
- **Migrations** — 9 Alembic revisions exist; `create_all` drift papered-over items resolved.
- **Security remediation (2026-05-29 plan)** — mostly delivered via PR #160 (open): SSRF guard on image preflight, `sanitize_error` redaction, n8n proxy `vg_admin` gate, XFF-aware limiter, Next.js `remotePatterns` tightening, Sentry `maskAllText`+`blockAllMedia`, push-mappings tenant guard.
- **SanMar images = SOAP**, not FTP. `getMediaContent` (MediaService/v110, `adapter.py:296` / `client.py:931`) → `merge_media` (`ps_normalizer_v2.py:185`) populates `ingest.images`; real ingest uses it via `category_import.py:220` when `fetch_images=True`. **Correction (verified):** the `sanmar_ftp.py` + `trigger_lazy_image_fetch` path is NOT dead — it's a **disabled-by-default feature flag** (`ENABLE_LAZY_IMAGES`, default false) wired into the live `GET /api/products/{product_id}` endpoint (`catalog/routes.py:192-204`), and `storage.upload_image` has a real S3 path when configured. The FTP client itself is mocked. See Phase 4 for the decision (finish the flag vs remove the feature) — it is not a trivial dead-code delete.
- **All four supplier adapters** (SanMar SOAP, Alphabroder SOAP, S&S REST, 4Over REST-HMAC) wired: discover → hydrate → persist → record.

**Stale plan docs to mark done after this plan:** `2026-05-27-phase-a-auth-foundation.md`, `2026-05-29-security-leak-remediation.md`.

---

## 1. Phase sequence

Ordered so each phase unblocks the next. Phases 1–2 are production-blockers; 3 gates onboarding real customers; 4 is debt.

### Phase 1 — Land the in-flight PRs (do first) — ✅ COMPLETE 2026-06-02

**P1.1 — Merge #160 (security hardening)** — ✅ merged (squash `c005340`)
- [x] Resolve the 3 non-blocking moderates flagged in review:
  - [x] `FORWARDED_ALLOW_IPS` — fail closed when `ENVIRONMENT=production` instead of defaulting `"*"`. Done in `backend/bootstrap.sh`. (Follow-up: ECS uses the Dockerfile `CMD` directly, not bootstrap.sh — set `FORWARDED_ALLOW_IPS` to the VPC CIDR in `deployment/ecs/api-hub.yaml`. Low risk: `_client_ip` is already spoof-resistant via last-XFF-entry behind the ALB.)
  - [x] Per-email limiter — GC aged-out buckets once the dict grows past `_EMAIL_GC_THRESHOLD`. `backend/limiter.py`.
  - [x] `check_image_urls_reachable` — it IS a blocker (not a warning); fixed by treating 3xx as reachable while keeping `follow_redirects=False` for SSRF. `backend/modules/ops_push/preflight.py`.
- [x] Suite verified locally (140 passed across the affected areas; DB tests deferred to CI); merged.

**P1.2 — Merge #159 (inline product push)** — ✅ merged (squash `e70af31`)
- [x] Landed after #160; resolved the trivial `main.py` conflict (routes/gateway auto-merged); app imports + tests pass.

**P1.3 — Close the security issue backlog** — ✅ 0 open issues
- [x] Closed via #160 + audit: **#147**, **#150**, **#151**, **#152**, **#153**, **#29**.
- [x] **#148** (IDOR cluster): audited — markup guarded (#144), push-mappings GET tenant-scoped + DELETE guard (#160), push-log `VGAdmin`-only, products are shared catalog with the one `customer_id`-filtered list path tenant-checked (`catalog/routes.py:92`). Closed.
- [x] **#149** (orchestrator push-status key-scoping): orchestrator GET enforces `check_key_scope` + returns 404 (`integrations/routes.py:177`); admin mirror is `VGAdmin`-only. Closed.

**Exit:** ✅ #159 + #160 merged, 8 issues closed with evidence, OPS schema fix live on main (canary unblocked).

---

### Phase 2 — Production reliability infra (highest real leverage)

**P2.1 — Durable push/sync queue (arq)**
- Problem: push + sync execute via in-process `asyncio.Semaphore` + task (`ops_push/task_runner.py`, scheduler). A pod restart / crash mid-push **loses the job silently** — unacceptable for live OPS writes.
- [ ] Add `arq` worker backed by the existing Redis (`cache.py` connection).
- [ ] Move `run_push_task` and the sync scheduler enqueue path to arq jobs (idempotent — the push_log row + idempotency key already exist).
- [ ] Worker process in `docker-compose.yml` + deployment (ECS task / App Runner sidecar).
- [ ] Retry policy + dead-letter handling; surface job state on the existing push-status endpoints.
- [ ] Tests: enqueue → worker executes → push_log terminal state; restart-mid-job replays without duplicate OPS writes.

**P2.2 — M1 ops_client read-back / dedup layer**
- Problem: push path is mutation-only. On retry it can create duplicates in OPS. Memory note `project_m1_ops_client_wrong_schema` is resolved (mutations now match real schema via #160); the missing piece is **reads**.
- [ ] Add OPS query operations (product lookup by SKU) in `modules/ops_client/`.
- [ ] Pre-push dedup: before `setProduct`, look up existing OPS product → update vs create.
- [ ] Post-push read-back verification of the written product (optional, behind a flag).
- [ ] Tests against the OPS Postman collection contract.

**Exit:** a killed worker resumes pushes with no loss and no duplicate OPS rows; retries are idempotent end-to-end.

---

### Phase 3 — Test hardening (gate before live customers)

Coverage is better than a first pass suggests (suppliers/tenant/key-auth have indirect coverage via `test_gateway_*`, `test_supplier_auth_no_leak`, `test_tenant_access_extra`, `test_redis_backplane`). Genuine thin spots, in risk order:

- [ ] **REST adapters** — `fourover_client` + the REST base ARE tested (`test_fourover_client.py`, `test_rest_connector.py`); `ss_normalizer` too. Gap is the **adapter** layer: `fourover_adapter.py` and `ss_adapter.py` have no direct unit tests (discover→hydrate→normalize wiring). `backend/modules/rest_connector/`.
- [ ] **Webhooks** — delivery + retry + payload-shape tests (silent-loss risk). `backend/modules/webhooks/`.
- [ ] **ops_push orchestration** — `task_runner` / `service` / `merge` (critical push path, currently untested). Fold into Phase 2 where the queue is rewritten.
- [ ] **integrations key-scope** — direct unit tests for `check_key_scope` edge cases + Redis-outage fallback in `integrations/auth.py`.
- [ ] **Frontend** — API-client layer (`lib/api`), auth-flow, and error-state tests; E2E is happy-path only today.

**Exit:** every supplier adapter and the push/webhook paths have unit coverage; CI stays green and blocking.

---

### Phase 4 — Hygiene & optimization (debt) — in progress 2026-06-04

- [x] **Decide the lazy-image (SanMar FTP) feature flag** — **chose (a) Remove.** The whole path was mock-only (mock FTP listing + mock `_mock_upload_to_s3`); SOAP `getMediaContent` already covers real images, and finishing it was blocked on SanMar SFTP creds. Deleted `sanmar_ftp.py`, `modules/images/service.py`, `scripts/sync_images.py`, `tests/test_image_pipeline.py`, and the `ENABLE_LAZY_IMAGES`-gated caller + now-unused imports in `catalog/routes.py`. **Kept** the `last_image_fetch_attempt_at` column — it's used by the real `images/mirror.py` pipeline, not just the lazy feature.
- [ ] **REST delta-sync** — S&S + 4Over `discover_changed` fall back to full re-fetch. Optimize once volume justifies (not a blocker). **Deferred** — not part of this pass.
- [x] **4Over frontend sync button** — **chose to wire it.** `print-products/page.tsx` now routes "Sync from 4Over" into the standard supplier import flow (`/suppliers/{id}/import`) for the configured 4Over supplier; disabled only when none exists. Removed the "coming in V1d" stub copy and updated the info banner. The 4Over REST adapter was already wired into the generic import path.
- [x] **Docs** — refreshed `docs/progress.md` with a Current State (2026-06-04) section + corrected the stale "routes missing" module map; marked `phase-a-auth-foundation` + `security-leak-remediation` plans DONE.

**Exit:** no dead mock code on a live path; docs reflect reality. (REST delta-sync intentionally deferred.)

---

## 2. Sequencing & risk

- **Phase 1 before everything** — merging the open PRs first avoids rebasing Phase 2/3 work onto a moving base, and closes the live-exploitable security issues.
- **Phase 2 is the real production gate** — feature-complete but lossy-on-crash is not shippable for OPS writes. Highest leverage.
- **Phase 3 gates the first real customer**, not the merge — can run in parallel with Phase 2 by a second contributor.
- **Reviewer separation** — Phase 2 (push reliability) and any Phase 1 security change need a distinct reviewer pass, not self-approval (per house rule).
- **External dependency** — live end-to-end verification (real OPS push, SanMar pricing) still needs credentials from Christian (OPS `ops_auth_config`, supplier API keys) per `plans/tasks/tanishq-tasks.md`. Phases 1–3 are all testable with `FakeOpsClient` + dry-run without them.

---

## 3. First action

Phase 1.1 — clear #160's three moderates, merge #160 then #159, close the 8 issues. Smallest step, unblocks the rest.
