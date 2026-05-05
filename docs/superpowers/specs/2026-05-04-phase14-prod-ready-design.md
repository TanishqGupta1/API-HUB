# Phase 14 — Production Readiness Design

**Date:** 2026-05-04
**Status:** Spec
**Tracking issues:** [#89 parent](https://github.com/VisualGraphxLLC/API-HUB/issues/89), [#85](https://github.com/VisualGraphxLLC/API-HUB/issues/85), [#86](https://github.com/VisualGraphxLLC/API-HUB/issues/86), [#87](https://github.com/VisualGraphxLLC/API-HUB/issues/87), [#88](https://github.com/VisualGraphxLLC/API-HUB/issues/88)

## Goal

Make API-HUB deployable to AWS ECS Fargate with no `host.docker.internal` defaults, real authentication, locked-down configuration, and a decoupled n8n that can run on any host that supports community nodes.

## Why now

Current state:
- All admin endpoints unauthenticated (30+ POST/PATCH/DELETE routes accept anonymous calls)
- `host.docker.internal` and `http://n8n:5678` baked into defaults — incompatible with any non-Docker-Desktop deploy target
- Custom OnPrintShop n8n node distributed via volume mount — won't work on managed n8n
- Backend container runs as root
- CORS regex allows any localhost port with credentials
- Hardcoded fallback for `INGEST_SHARED_SECRET` in a script
- PR #79 attempted phase 13 hardening but committed merge conflict markers in the CFN template; cannot be merged as-is

Phase 14 ships the production posture without those liabilities.

## Scope

### In scope

- Auth: JWT-backed login flow with httpOnly cookies, RBAC (`vg_admin` / `customer_admin`), audit log
- Container hardening: non-root runtime, locked CORS, fail-loud startup checks
- n8n decoupling: env-driven URLs, custom node baked into a custom n8n Docker image, formal integration contract
- ECS Fargate infrastructure: single CFN stack with backend + frontend + n8n services, RDS Postgres, EFS, Secrets Manager, ALB, Cloud Map
- CI deploy pipeline (GitHub Actions → ECR → CloudFormation update)

### Out of scope

- Multi-region / DR (single region, RDS automated backups only)
- Per-tenant isolation beyond JWT RBAC (V1 is single-tenant)
- Replacing n8n with native FastAPI orchestration (kept as the workflow engine)
- Storefront subdomain split (kept as `/storefront/*` path on the same Next.js app)
- Stripe / billing
- SAML / SSO (basic JWT only)

## Architecture

### Production deploy target

```
Internet
  │
  ├─ Route 53
  │   ├─ api.example.com  ──┐
  │   ├─ app.example.com  ──┼──► ALB (HTTPS, ACM cert)
  │   └─ n8n.example.com  ──┘
  │
  ├─ ECS Fargate cluster
  │   ├─ backend.api-hub.local:8000   (Service: api-hub-backend, 1–5 tasks)
  │   ├─ frontend.api-hub.local:3000  (Service: api-hub-frontend, 1–3 tasks)
  │   └─ n8n.api-hub.local:5678       (Service: api-hub-n8n, pinned at 1)
  │
  ├─ RDS PostgreSQL 16, Multi-AZ in production, private subnets
  ├─ EFS for n8n persistent state, mounted at /home/node/.n8n
  ├─ Secrets Manager: SECRET_KEY, JWT_SECRET_KEY, INGEST_SHARED_SECRET, POSTGRES_URL, OPS_*
  └─ CloudWatch Logs
```

### Inter-service communication contract

| From | To | URL (in container) | Auth |
|------|------|--------------------|------|
| Frontend | Backend | `https://api.example.com` | JWT cookie |
| Backend | n8n webhooks | `http://n8n.api-hub.local:5678` (Cloud Map) | per-workflow webhook secret |
| Backend | n8n REST API | `http://n8n.api-hub.local:5678` | `N8N_API_KEY` |
| n8n | Backend (ingest) | `http://backend.api-hub.local:8000` | `X-Ingest-Secret` |
| n8n | Backend (callback) | `http://backend.api-hub.local:8000` | `X-Ingest-Secret` |

No `host.docker.internal`. No `http://n8n:5678` (Docker Compose DNS). All resolved via Cloud Map private DNS in prod, or explicit env vars in dev.

### Auth model

- One JWT per session, stored in httpOnly Secure SameSite=Lax cookie, 8-hour expiry
- No refresh-token rotation in V1 (re-login on expiry); flagged as V2 follow-up
- JWT signed with `JWT_SECRET_KEY`, separate from Fernet `SECRET_KEY`
- Roles: `vg_admin` (sees all customers), `customer_admin` (scoped to own storefront)
- Storefront `/storefront/*` paths public (whitelisted in middleware)
- Admin routers wrapped with `Depends(get_current_user)` at registration time
- Audit log middleware records every write request with user email, route, status

### Container posture

- Backend: multi-stage Dockerfile, runs as uid 1000 user `app`, non-root
- Frontend: existing `nextjs` user (uid 1001) — already correct
- n8n: custom image `FROM n8nio/n8n:latest`, OnPrintShop node baked in via `N8N_CUSTOM_EXTENSIONS`
- All images pushed to ECR per merge to main with SHA tag

### Startup checks (backend)

If `ENVIRONMENT=production` and any of these missing/invalid → RuntimeError at boot:
- `SECRET_KEY` (Fernet) — must be a real Fernet key
- `JWT_SECRET_KEY` — must be set (no fallback to `SECRET_KEY` in prod)
- `INGEST_SHARED_SECRET`
- `ALLOWED_ORIGINS`
- `POSTGRES_URL`
- `N8N_WEBHOOK_BASE_URL`
- `API_BASE_URL`

Dev mode (`ENVIRONMENT=development` default): warns on missing values, falls back where safe (Fernet derived from arbitrary string, etc.) per existing `database.py` pattern.

### CORS posture

- `ENVIRONMENT=production` → `ALLOWED_ORIGINS` must be set; no localhost regex
- Dev → existing regex `^http://(localhost|127\.0\.0\.1)(:\d+)?$` retained
- Methods locked to `["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` always
- Headers locked to explicit list (`Authorization`, `Content-Type`, `X-Ingest-Secret`)

## Subsystems

The work is split into four subsystems landing in this order. Each is a separate branch + PR. No mega-PR.

### A — Security Hardening — issue #85

Foundation. No behaviour change for end users. Tightens config + container posture so later subsystems land on safe ground.

Files: `backend/Dockerfile`, `backend/main.py`, `backend/scripts/ingest_ops_master_options.py`, `.env.example`, `docker-compose.yml`.

Changes:
- Add non-root `USER app` to backend Dockerfile
- Drop hardcoded `vg-hub-ingest-secret-2026` fallback from script
- CORS production lock (env-driven, explicit methods + headers)
- Gate `n8n` `ports: 5678:5678` in compose behind a `dev` profile
- Add the production startup-check function called from `lifespan`

Size: ~50 LOC, 1 PR.

### B — n8n Decoupling — issue #86

Treat n8n as an external service. No more Docker-network DNS. Custom node baked into a Docker image, not volume-mounted.

Files: `backend/main.py`, `backend/modules/n8n_proxy/*`, `backend/modules/ops_push/service.py`, `n8n-workflows/*.json`, `docker-compose.yml`, `.env.example`, new `n8n.Dockerfile`, new `docs/n8n-integration.md`.

Changes:
- Promote `N8N_WEBHOOK_BASE_URL`, `N8N_API_BASE_URL`, `API_BASE_URL`, `N8N_PUSH_WEBHOOK_URL` to required env vars in prod
- Drop `host.docker.internal` and `http://n8n:5678` defaults
- Build a custom n8n image with OnPrintShop node baked in (replaces volume mount)
- Document outbound webhook spec, ingest spec, callback spec, self-host setup checklist
- README clarifies: custom n8n required (n8n.cloud Pro+, Render, Fly, ECS Fargate, self-hosted Docker — n8n.cloud Starter blocks community nodes)

Size: ~150 LOC + 1 Dockerfile + 1 doc. 1–2 PRs.

### C — Auth — issue #87

Cherry-pick auth subset of PR #79 into a clean branch. Fix the criticals that blocked #79 from merging.

Files cherry-picked from PR #79:
- `backend/modules/auth/*`
- `backend/modules/audit_log/*`
- `backend/alembic/*`
- `requirements.txt` deps (jose, passlib, alembic, slowapi, bcrypt<4.0.0)
- `backend/main.py` lifespan + router registration
- `frontend/src/app/(auth)/*`, `frontend/src/app/(admin)/settings/page.tsx`, `audit-log/page.tsx`, `error.tsx`, `not-found.tsx`, `forbidden/page.tsx`
- `frontend/src/components/SidebarNav.tsx` user info + sign-out
- `frontend/src/middleware.ts` (with `/storefront` whitelist)

Fixes layered on top:
1. httpOnly cookie set by backend, no localStorage tokens, no `Authorization` header injection in `api.ts`
2. Drop `SECRET_KEY` fallback string from `auth/security.py`
3. `JWT_SECRET_KEY` required in prod (no fallback)
4. Drop default-admin auto-seed; first-run flow via `/api/auth/setup` + frontend `/setup` redirect
5. `trigger_n8n_push` calls `.raise_for_status()` so n8n 5xx propagates to failure handler
6. `LoginRequest.email: EmailStr`, `User.email` lowercased on insert/lookup
7. `customer_admin` cannot update `ops_base_url` / `ops_token_url` — vg_admin only

Size: ~750 LOC (mostly cherry-picked). 1 PR.

### D — ECS Fargate Infrastructure — issue #88

Replace the App Runner CFN template (`deployment/aws-app-runner.yaml`) with a single ECS Fargate stack that provisions the full architecture above.

Files: new `deployment/ecs/api-hub.yaml`, rewritten `deployment/README.md`, new `.github/workflows/deploy.yml`.

Includes:
- 1 cluster, 3 services, 1 ALB, 3 target groups, 3 task definitions
- 1 RDS instance, subnet group, parameter group, security group
- 1 EFS file system + mount targets + access point for n8n
- Cloud Map private DNS namespace `api-hub.local`
- Secrets Manager resources (auto-generated where possible)
- IAM: task execution role + per-service task roles (least privilege)
- Auto-scaling: backend 1–5 (CPU 60% target), frontend 1–3, n8n pinned at 1
- Health checks: backend `/health`, frontend `/`, n8n `/healthz`
- CI: build + push three images to ECR per merge, run Alembic migration via one-off Fargate task, update services with new image URIs
- Document Route 53 hosted zone + ACM cert as one-time manual prerequisites
- n8n workflow + credential migration procedure from current install

Size: ~500 LOC infra (1 CFN file) + GH Actions workflow + README rewrite. 1 PR.

## Branching strategy

```
main
 ├─ dev/phase14a-security        →  PR → main  (lands first)
 ├─ dev/phase14b-n8n-decouple    →  PR → main  (after A)
 ├─ dev/phase14c-auth            →  PR → main  (after A; can land in parallel with B)
 └─ dev/phase14d-ecs             →  PR → main  (after A + B + C)
```

No long-running parent branch. Each sub-branch is short-lived (target: <1 week each). Phase 14 closes when all four PRs merge + a staging ECS deploy succeeds end-to-end.

## Risks

| Risk | Mitigation |
|------|------------|
| `@visualgraphx` npm scope blocks B | Use custom n8n Docker image (current plan) — no npm publish needed |
| Auth migration locks out existing users | Existing dev DBs have no users; first-run setup creates the first admin via `/api/auth/setup`. Production DB does not exist yet. |
| Rotating `SECRET_KEY` invalidates `EncryptedJSON` rows | Document in deploy README. Rotation requires `ALLOW_UNENCRYPTED_LEGACY` flag + re-save flow. Treat `SECRET_KEY` as semi-permanent. |
| n8n single-task downtime during deploy | Acceptable for V1. Deploys outside business hours. Schedule via EventBridge (V2) if downtime becomes painful. |
| ALB + Cloud Map cost (~$130/mo per env) | Acceptable. Single env to start (staging). Production env added when product ready. |
| Domain + ACM cert is a manual prerequisite | Documented in `deployment/README.md`. Ops handles before D ships. |
| n8n credential export/import is manual | Documented. One-time pain during cutover from current Docker n8n to ECS-hosted n8n. |
| Conflict markers in PR #79's CFN template | PR #79 stays open as cherry-pick source for #87 (auth files only). D writes a fresh CFN, ignores #79's deployment artifacts. |

## Acceptance criteria

Phase 14 is done when:

- All 4 sub-issues (#85–#88) closed
- All admin endpoints 401 without a valid auth cookie
- Storefront `/storefront/*` paths reachable without auth
- Backend boots in `ENVIRONMENT=production` mode without ephemeral fallbacks
- `grep -r host.docker.internal backend/ frontend/ docker-compose.yml .env.example` returns 0 hits (or only dev-comment context)
- A staging ECS environment is deployable from scratch via a single CFN command + CI pipeline in <30 min
- Custom n8n image with OnPrintShop node runs in ECS Fargate
- Backend can resolve `http://n8n.api-hub.local:5678` from inside the cluster (verified via ECS Exec)
- A test product push: UI click → push_log "pending" → n8n webhook fires → callback flips to "success" with real OPS product ID

## Open questions for product / ops

Resolve before D ships:

- Domain ownership: who registers and manages Route 53?
- ACM cert: wildcard `*.example.com` or per-subdomain?
- n8n basic-auth: shared admin login, or per-user?
- Production AWS account: shared with staging, or separate?
- Existing OPS OAuth credentials in current n8n: who handles the export-import procedure?

## Discussion log + decisions

This section records the decisions made during the brainstorm so future readers (and team members joining the work) can see the tradeoffs and pick up the thread without re-litigating.

### D1 — Why is `host.docker.internal` a problem?

**Discussion:** It works in dev (Docker Desktop on macOS) and gets baked into `.env.example` as the default for `API_BASE_URL`. The string then leaks into every config file that's copied from the example. It's a Docker-Desktop-only DNS name; doesn't resolve on Linux Docker without `--add-host`, doesn't exist on ECS, k8s, App Runner, n8n.cloud, etc.

**Decision:** Promote inter-service URLs from "defaults with localhost values" to "required env vars per environment, no defaults in production." Local dev sets values in `.env`. Cloud envs set values per task definition. Subsystem B implements.

**Alternative considered:** Conditional defaults based on `ENVIRONMENT` flag. Rejected — config that depends on a flag-of-a-flag is hard to debug. Fail-loud is clearer.

### D2 — Do we even need n8n?

**Discussion:** n8n owns OPS push, scheduling, OAuth2 token mgmt for OPS, and the OnPrintShop custom node. All are replaceable with FastAPI + `httpx` + `tenacity` + EventBridge. We considered ripping it out.

What we'd lose: visual workflow editor (non-engineers can tweak), drag-drop node ecosystem for future suppliers, sales-narrative value ("we have a workflow engine").

What we'd gain: one less service, no shared-secret boundary inside our own stack, simpler deploy.

**Decision:** Keep n8n in V1. Treat it as a *pluggable* outbound webhook target — backend POSTs payload to a configurable URL, n8n is just one possible consumer. This decoupling (subsystem B) keeps the option open to swap later (Lambda, Render worker, native Python queue) without rewriting the backend.

**Tradeoff accepted:** ~$30–50/mo running cost + the operational complexity of an extra service, in exchange for the workflow editor and node ecosystem.

### D3 — n8n.cloud Starter doesn't support community nodes

**Discussion:** "Any cloud n8n" was the original ask. Reality: n8n.cloud Starter blocks community nodes; OnPrintShop node won't load. n8n.cloud Pro+ allows them but costs more.

**Decision:** Phase 14 supports any n8n that allows community nodes — n8n.cloud Pro+, Render, Fly, ECS Fargate, self-hosted Docker. Documented as a constraint in the README. n8n.cloud Starter explicitly unsupported.

### D4 — Custom node distribution: npm vs Docker image

**Discussion:** Three options for shipping the OnPrintShop n8n node:
- Publish `@visualgraphx/n8n-nodes-onprintshop` to npm — clean, standard, but requires the npm scope to be registered (slow ops process) and n8n.cloud nodes-via-npm flow varies by tier
- GitHub Packages — works, but requires n8n config to authenticate with a GH token
- Build a custom n8n Docker image with the node baked in via `N8N_CUSTOM_EXTENSIONS` — works everywhere we control the Docker host

**Decision:** Custom Docker image. Subsystem B builds `n8n.Dockerfile` (or `n8n-nodes-onprintshop/Dockerfile.n8n`), pushed to ECR alongside backend + frontend. Used in dev compose and ECS Fargate.

**Alternative kept open:** Publish to npm later if/when we want non-Docker n8n hosts to install the node.

### D5 — Deploy target: EC2 vs App Runner vs ECS Fargate

**Discussion:** Three real options:

| Target | Cost (rough) | Pros | Cons |
|--------|--------------|------|------|
| Single EC2 + docker-compose | ~$20/mo | Cheapest, fastest to ship | No HA, manual TLS, manual backups, n8n exposed unless firewalled |
| App Runner | ~$50/mo | Managed compute, auto-HTTPS, simple | No persistent volumes for n8n, no Cloud Map service discovery |
| ECS Fargate | ~$130/mo | Real prod posture, EFS for n8n, Cloud Map, IAM per task | Most complex CFN, ALB cost adds floor |

**Decision:** ECS Fargate. App Runner can't host n8n (no volumes). EC2 is fine for hobby projects but lacks HA + TLS + service discovery out of the box. Subsystem D writes the ECS CFN.

**Cost accepted:** ~$130/mo per environment. Single staging env to start; production env added when product-ready.

### D6 — Subsystem ordering

**Discussion:** Three orderings considered:
- A → B → C → D: foundation, contracts, surface, infra
- B → A → C → D: contracts first, then container hardening
- C parallel to B: auth surface independent of n8n contract changes

**Decision:** A → B → C(parallel-eligible) → D. A is foundation (startup checks live in the code paths B + C extend). B before D so D's task definitions inject the env vars B introduces. C is auth-surface-only; doesn't depend on B. If two devs work concurrently, C can land alongside B. D last because it needs A + B + C in main to reflect real prod posture.

### D7 — Single mega-PR vs four separate PRs

**Discussion:** All four subsystems on one `dev/phase14-prod-ready` branch is appealing for "ship in one shot." Reality: ~1500 LOC of spread across auth + infra + config + Dockerfiles is unreviewable, and a single rollback would lose unrelated work.

**Decision:** Four separate branches off main, each with its own PR. Phase 14 closes when all four PRs merge + a staging ECS deploy succeeds. No long-running parent branch.

### D8 — PR #79 fate

**Discussion:** PR #79 contains ~80% of the auth code we want for subsystem C, plus audit log, plus alembic, plus a (broken) CFN template. Latest commit on #79 introduced unresolved git conflict markers in the CFN file — `aws cloudformation validate-template` would fail. Merging it ships broken YAML to main.

**Decision:** Don't merge #79. Leave it open as the cherry-pick source for subsystem C (auth + audit + alembic files only). Subsystem D writes a fresh CFN; ignores #79's deployment artifacts. Net waste: ~20% of #79's diff (CFN template + a few config tweaks).

### D9 — Token storage: localStorage vs httpOnly cookie

**Discussion:** PR #79 stores JWT in `localStorage` and additionally writes a non-httpOnly cookie for the Next.js middleware to read. Comment in code acknowledges the XSS exposure. Project also server-renders DOMPurify for storefront descriptions — XSS surface is non-trivial.

**Decision:** Backend `/api/auth/login` sets the JWT as httpOnly + Secure + SameSite=Lax cookie. Body returns user info only, no token. Frontend `lib/auth.ts` drops localStorage usage. `api.ts` drops `Authorization: Bearer` injection (cookie auto-sends). Subsystem C implements.

**V2 follow-up:** Refresh-token rotation. V1 ships 8-hour access token + re-login on expiry.

### D10 — `SECRET_KEY` reused for JWT signing vs separate

**Discussion:** PR #79 uses `SECRET_KEY` (Fernet) as the JWT HMAC key. Mixing key purposes means rotating one rotates the other. Fernet rotation invalidates all `EncryptedJSON` rows; JWT rotation just invalidates active sessions — these have very different operational profiles.

**Decision:** Separate `JWT_SECRET_KEY` env var. Falls back to `SECRET_KEY` only in dev, with a startup warning. In prod, must be explicitly set.

### D11 — Default admin auto-seed

**Discussion:** PR #79 (after fixes) auto-creates `admin@localhost` with a random password when DB has 0 users and `ENVIRONMENT=development`. Mitigates the original `admin/admin` risk but still creates a known user account.

**Decision:** Drop the auto-seed entirely. First-run flow: empty DB → frontend redirects to `/setup` → user creates first admin via `POST /api/auth/setup` (which 409s if any user already exists). No magic admin account.

### D12 — Storefront subdomain split

**Discussion:** Frontend Next.js app serves both admin (`/(admin)/...`) and public storefront (`/storefront/...`). Two options:
- Keep on one host, whitelist `/storefront/*` in middleware (cheap)
- Split into two Next.js apps on `app.example.com` (admin) and `shop.example.com` (storefront) — clean boundaries, easier Cloudflare cache rules, separate deploy cadence

**Decision:** Keep on one host for V1. Whitelist `/storefront/*` in `middleware.ts`. Split is V2 if needed.

### D13 — n8n single-task on Fargate = downtime during deploys

**Discussion:** EFS supports multi-task mounts but n8n is single-writer (workflow execution state in `~/.n8n`). Task count must stay at 1. Rolling deploys briefly stop the n8n editor and any running workflow executions.

**Decision:** Accept 30-second downtime windows during deploys. Schedule deploys outside business hours. If downtime becomes painful, V2 explores moving cron schedules to EventBridge + FastAPI cron, leaving n8n only for on-demand workflows.

### D14 — Multi-region / DR

**Discussion:** Cross-region RDS replicas, multi-region ALB, etc. — out of scope for V1.

**Decision:** Single region (us-east-1 default). RDS automated backups (7 days staging, 14 days production). RPO ~1 hour, RTO ~30 min. Documented in deploy README.

### D15 — `client_secret` in n8n webhook payload

**Discussion:** Backend currently sends `customer.ops_auth_config.client_secret` in the JSON payload to the n8n webhook so n8n can call OPS. This is plaintext over HTTP.

**Decision (V1):** Webhook URL must point inside the VPC (Cloud Map private DNS). Documented constraint. Subsystem B's contract doc spells it out.

**V2 follow-up:** Move OPS credentials to AWS Secrets Manager and have n8n read them directly via IAM-based access. Backend stops shipping secrets in payloads.

### D16 — Storefront cookie auth

**Discussion:** Storefront is buyer-facing. Should it have its own auth (customer login) or stay anonymous?

**Decision:** Stay anonymous in V1. Storefront serves catalog + product detail + cart-as-localStorage. Phase 15+ adds buyer accounts if the product needs order history etc.

## Sources

- PR #79: https://github.com/VisualGraphxLLC/API-HUB/pull/79 (cherry-pick source for C)
- Re-review of #79: https://github.com/VisualGraphxLLC/API-HUB/pull/79#issuecomment-4373367309
- Issue #83: ops_push follow-up (some overlap with C)
- CLAUDE.md project constraints (modular monolith, n8n owns OPS push, EncryptedJSON for credentials)
