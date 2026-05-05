# Phase 14b — n8n Decoupling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Treat n8n as an external service. Kill `host.docker.internal` and Docker-Compose-only DNS defaults. Bake the OnPrintShop custom node into a Docker image so it ships with any n8n host that supports community nodes.

**Architecture:** All inter-service URLs become required env vars in production. Backend resolves `N8N_WEBHOOK_BASE_URL` / `N8N_API_BASE_URL`; n8n resolves `API_BASE_URL`. A custom n8n Dockerfile copies the compiled OnPrintShop node into `N8N_CUSTOM_EXTENSIONS` so installing it requires no volume mount. Production failure mode: backend refuses to boot if either n8n URL is unset.

**Tech Stack:** Python 3.12, FastAPI, n8n, Docker, n8n's `N8N_CUSTOM_EXTENSIONS` directory loading.

**Tracking issue:** [#86](https://github.com/VisualGraphxLLC/API-HUB/issues/86)

**Branch:** `dev/phase14b-n8n-decouple`

**Depends on:** Phase 14a merged (uses `_require_prod_env` infrastructure).

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/main.py` | Modify | Add `N8N_WEBHOOK_BASE_URL`, `API_BASE_URL` to required prod env list |
| `backend/modules/n8n_proxy/client.py` | Modify | Read `N8N_API_BASE_URL` instead of hardcoded fallback |
| `backend/modules/ops_push/service.py` | Modify | Read `N8N_PUSH_WEBHOOK_URL` from env; no `host.docker.internal` fallback |
| `backend/tests/test_n8n_url_config.py` | Create | Verify env-var reads + production fail-loud behaviour |
| `n8n.Dockerfile` | Create | Custom n8n image with OnPrintShop node baked in via `N8N_CUSTOM_EXTENSIONS` |
| `docker-compose.yml` | Modify | Use the custom image; drop volume mount for the node; replace `http://n8n:5678` defaults with explicit env |
| `.env.example` | Modify | Promote `N8N_WEBHOOK_BASE_URL`, `API_BASE_URL`, `N8N_PUSH_WEBHOOK_URL` to documented required vars |
| `docs/n8n-integration.md` | Create | Outbound webhook spec, ingest spec, callback spec, self-host setup checklist |
| `n8n-workflows/*.json` | Modify | Audit + ensure all references use `$env.API_BASE_URL` consistently |
| `README.md` | Modify | Note: n8n.cloud Starter unsupported (community-node restriction) |

---

## Task 1: Branch + read current n8n entry points

**Files:** none (read-only)

- [ ] **Step 1: Create branch**

```bash
git checkout main
git pull --ff-only
git checkout -b dev/phase14b-n8n-decouple
```

- [ ] **Step 2: Inventory every place the codebase mentions n8n URLs**

```bash
grep -rn "host.docker.internal\|http://n8n:5678\|N8N_BASE_URL\|N8N_WEBHOOK\|API_BASE_URL" \
  backend/ frontend/ docker-compose.yml .env.example n8n-workflows/ 2>&1 | tee /tmp/phase14b-inventory.txt
wc -l /tmp/phase14b-inventory.txt
```
Expected: ~15–25 lines. Save the file — Task 7 references it.

- [ ] **Step 3: No commit — inventory only**

---

## Task 2: Backend N8N URL config — failing tests

**Files:**
- Create: `backend/tests/test_n8n_url_config.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_n8n_url_config.py
import os
import pytest

pytestmark = pytest.mark.asyncio


@pytest.fixture
def clean_env(monkeypatch):
    for key in (
        "ENVIRONMENT", "N8N_WEBHOOK_BASE_URL", "N8N_API_BASE_URL",
        "API_BASE_URL", "N8N_PUSH_WEBHOOK_URL",
        "SECRET_KEY", "INGEST_SHARED_SECRET", "ALLOWED_ORIGINS", "POSTGRES_URL",
    ):
        monkeypatch.delenv(key, raising=False)


async def test_dev_mode_does_not_require_n8n_urls(clean_env, monkeypatch):
    """Dev mode must boot without N8N_WEBHOOK_BASE_URL or API_BASE_URL set."""
    from main import _require_prod_env
    monkeypatch.setenv("ENVIRONMENT", "development")
    _require_prod_env()  # no exception


async def test_production_mode_fails_when_n8n_webhook_base_url_missing(clean_env, monkeypatch):
    from main import _require_prod_env
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "k" * 44)
    monkeypatch.setenv("INGEST_SHARED_SECRET", "x")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("POSTGRES_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("API_BASE_URL", "https://api.example.com")
    with pytest.raises(RuntimeError, match="N8N_WEBHOOK_BASE_URL"):
        _require_prod_env()


async def test_production_mode_fails_when_api_base_url_missing(clean_env, monkeypatch):
    from main import _require_prod_env
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "k" * 44)
    monkeypatch.setenv("INGEST_SHARED_SECRET", "x")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("POSTGRES_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("N8N_WEBHOOK_BASE_URL", "http://n8n.api-hub.local:5678")
    with pytest.raises(RuntimeError, match="API_BASE_URL"):
        _require_prod_env()


async def test_production_mode_passes_when_all_set(clean_env, monkeypatch):
    from main import _require_prod_env
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "k" * 44)
    monkeypatch.setenv("INGEST_SHARED_SECRET", "x")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("POSTGRES_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("N8N_WEBHOOK_BASE_URL", "http://n8n.api-hub.local:5678")
    monkeypatch.setenv("API_BASE_URL", "http://backend.api-hub.local:8000")
    _require_prod_env()  # no exception
```

- [ ] **Step 2: Run tests, expect 2 failures**

```bash
cd backend && source .venv/bin/activate
pytest tests/test_n8n_url_config.py -v
```
Expected: `test_dev_mode_does_not_require_n8n_urls` and `test_production_mode_passes_when_all_set` PASS (already covered by 14a). The two `_fails_when_*_missing` tests FAIL because phase 14a's `_PROD_REQUIRED_ENV_VARS` doesn't yet list these vars.

---

## Task 3: Add n8n URLs to `_PROD_REQUIRED_ENV_VARS`

**Files:**
- Modify: `backend/main.py` — extend the tuple defined in phase 14a

- [ ] **Step 1: Update the constant**

Open `backend/main.py`. Find the line:

```python
_PROD_REQUIRED_ENV_VARS = (
    "SECRET_KEY",
    "INGEST_SHARED_SECRET",
    "ALLOWED_ORIGINS",
    "POSTGRES_URL",
)
```

Replace with:

```python
_PROD_REQUIRED_ENV_VARS = (
    "SECRET_KEY",
    "INGEST_SHARED_SECRET",
    "ALLOWED_ORIGINS",
    "POSTGRES_URL",
    "N8N_WEBHOOK_BASE_URL",
    "API_BASE_URL",
)
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
pytest tests/test_n8n_url_config.py -v
```
Expected: 4 PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/main.py backend/tests/test_n8n_url_config.py
git commit -m "feat(n8n-decouple): require N8N_WEBHOOK_BASE_URL + API_BASE_URL in prod

Extends the production startup check (added in 14a) to enforce that
backend → n8n and n8n → backend URLs are explicitly configured per
environment. Dev mode unchanged."
```

---

## Task 4: n8n_proxy client reads env, no localhost fallback

**Files:**
- Modify: `backend/modules/n8n_proxy/client.py`

- [ ] **Step 1: Read the current client**

```bash
cat backend/modules/n8n_proxy/client.py
```

Look for the line that defines the n8n base URL — typically `N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://n8n:5678")` or similar.

- [ ] **Step 2: Replace fallback with explicit env read**

Open `backend/modules/n8n_proxy/client.py`. Find the URL constant block at the top of the file. Replace whatever you find with:

```python
N8N_API_BASE_URL = os.getenv("N8N_API_BASE_URL") or os.getenv("N8N_BASE_URL")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")

if N8N_API_BASE_URL is None and os.getenv("ENVIRONMENT", "development").lower() == "production":
    raise RuntimeError(
        "N8N_API_BASE_URL must be set in production. "
        "In ECS this comes from the task definition; in dev set it in .env."
    )

# Fallback for dev only — local Compose service DNS
N8N_API_BASE_URL = N8N_API_BASE_URL or "http://n8n:5678"
```

(Keep `N8N_BASE_URL` as a backward-compatible alias since older code may still read it.)

- [ ] **Step 3: Verify no other module hard-codes the URL**

```bash
grep -rn "http://n8n:5678\|host.docker.internal" backend/ | grep -v ".env.example\|docker-compose"
```
Expected: 0 hits in code (only docker-compose.yml + .env.example may still contain dev fallbacks — addressed in later tasks).

- [ ] **Step 4: Run backend tests**

```bash
pytest -q 2>&1 | tail -10
```
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/n8n_proxy/client.py
git commit -m "feat(n8n-decouple): n8n_proxy client reads N8N_API_BASE_URL from env

Production fails loud if unset. Dev falls back to Compose service DNS
(http://n8n:5678) so existing local workflows still work."
```

---

## Task 5: ops_push.service reads N8N_PUSH_WEBHOOK_URL from env

**Files:**
- Modify: `backend/modules/ops_push/service.py`

- [ ] **Step 1: Locate the trigger function**

```bash
grep -n "N8N_PUSH_WEBHOOK_URL\|trigger_n8n\|webhook_url" backend/modules/ops_push/service.py
```

- [ ] **Step 2: Replace with strict env read**

Open `backend/modules/ops_push/service.py`. Find the `trigger_n8n_push` function (added in PR #82 / #84). Replace the env read with:

```python
async def trigger_n8n_push(payload: dict[str, Any]) -> None:
    """POST payload to N8N_PUSH_WEBHOOK_URL.

    Returns silently if the env var is unset (dev convenience). Raises if the
    request fails so the caller can flip push_log status to 'failed'.
    """
    webhook_url = os.getenv("N8N_PUSH_WEBHOOK_URL", "").strip()
    if not webhook_url:
        if os.getenv("ENVIRONMENT", "development").lower() == "production":
            raise RuntimeError("N8N_PUSH_WEBHOOK_URL is required in production")
        return  # dev: silently skip
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(webhook_url, json=payload)
        response.raise_for_status()
```

- [ ] **Step 3: Run ops_push tests**

```bash
pytest tests/test_ops_push.py -v
```
Expected: green (tests don't set the env var, so they hit the dev silent-skip path).

- [ ] **Step 4: Commit**

```bash
git add backend/modules/ops_push/service.py
git commit -m "feat(n8n-decouple): ops_push reads N8N_PUSH_WEBHOOK_URL from env

Dev silently skips when unset. Prod fails loud. raise_for_status()
ensures n8n 5xx responses propagate to the failure handler so
push_log.status flips to 'failed' (not stuck at 'pending')."
```

---

## Task 6: Custom n8n Dockerfile

**Files:**
- Create: `n8n.Dockerfile` at repo root

- [ ] **Step 1: Create the Dockerfile**

```dockerfile
# Custom n8n image with the OnPrintShop community node baked in.
# Replaces the volume-mount install pattern so this image is portable
# (ECS, n8n.cloud Pro+, Render, Fly, self-hosted Docker).
#
# Build from repo root:
#   docker build -f n8n.Dockerfile -t api-hub-n8n:latest .
FROM node:20-alpine AS node-build
WORKDIR /build
COPY n8n-nodes-onprintshop/package.json n8n-nodes-onprintshop/package-lock.json ./
RUN npm ci
COPY n8n-nodes-onprintshop ./
RUN npm run build

FROM n8nio/n8n:latest
USER root
RUN mkdir -p /home/node/.n8n/custom \
 && chown -R node:node /home/node/.n8n/custom
COPY --from=node-build --chown=node:node /build/dist /home/node/.n8n/custom/n8n-nodes-onprintshop/dist
COPY --from=node-build --chown=node:node /build/package.json /home/node/.n8n/custom/n8n-nodes-onprintshop/package.json
USER node
ENV N8N_CUSTOM_EXTENSIONS=/home/node/.n8n/custom
```

- [ ] **Step 2: Build the image**

```bash
docker build -f n8n.Dockerfile -t api-hub-n8n:dev .
```
Expected: build succeeds, final image tagged `api-hub-n8n:dev`.

- [ ] **Step 3: Verify the OnPrintShop node loads**

```bash
docker run --rm -p 5679:5678 -e N8N_HOST=0.0.0.0 api-hub-n8n:dev 2>&1 | tee /tmp/n8n-boot.log &
sleep 15
grep -i "loaded.*onprintshop\|n8n-nodes-onprintshop" /tmp/n8n-boot.log || echo "Node not loaded — investigate"
docker ps -q --filter ancestor=api-hub-n8n:dev | xargs -r docker stop
```
Expected: log line confirming `n8n-nodes-onprintshop` loaded.

- [ ] **Step 4: Commit**

```bash
git add n8n.Dockerfile
git commit -m "feat(n8n-decouple): custom n8n Dockerfile with OnPrintShop node

Two-stage build: stage 1 compiles the TypeScript node, stage 2 bakes
dist/ into the official n8n image at /home/node/.n8n/custom (the path
N8N_CUSTOM_EXTENSIONS reads). Replaces the volume-mount install
pattern so this image works in ECS, Render, Fly, n8n.cloud Pro+, etc."
```

---

## Task 7: docker-compose uses custom n8n image, no localhost defaults

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Read current state**

```bash
cat docker-compose.yml
```

- [ ] **Step 2: Replace the n8n service block**

Open `docker-compose.yml`. Find the `n8n:` service (after Phase 14a it has `profiles: ["dev"]`). Replace its body with:

```yaml
  n8n:
    build:
      context: .
      dockerfile: n8n.Dockerfile
    image: api-hub-n8n:dev
    profiles: ["dev"]
    ports:
      - "5678:5678"
    environment:
      - N8N_HOST=0.0.0.0
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - NODE_FUNCTION_ALLOW_EXTERNAL=*
      - N8N_BLOCK_ENV_ACCESS_IN_NODE=false
      - INGEST_SHARED_SECRET=${INGEST_SHARED_SECRET}
      - API_BASE_URL=${API_BASE_URL}
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on:
      postgres:
        condition: service_healthy
```

(Drop the volume mount + entrypoint script for the OnPrintShop node — the custom image bakes it in.)

- [ ] **Step 3: Update the api service env to drop the localhost defaults**

In the `api:` block, replace the `N8N_BASE_URL` line:

```yaml
# OLD
- N8N_BASE_URL=http://n8n:5678

# NEW (no fallback — must be set in .env or task definition)
- N8N_API_BASE_URL=${N8N_API_BASE_URL:-http://n8n:5678}
- N8N_WEBHOOK_BASE_URL=${N8N_WEBHOOK_BASE_URL:-http://n8n:5678}
- N8N_PUSH_WEBHOOK_URL=${N8N_PUSH_WEBHOOK_URL:-}
- API_BASE_URL=${API_BASE_URL:-http://api:8000}
```

(Compose-only fallback to service DNS is fine — `_require_prod_env` enforces explicit values in production via the task definition.)

- [ ] **Step 4: Verify dev compose still works**

```bash
docker compose --profile dev up -d --build 2>&1 | tail -10
sleep 8
curl -fsS http://127.0.0.1:8000/health
curl -fsSI http://127.0.0.1:5678 | head -3
docker compose --profile dev down
```
Expected: backend `{"status":"ok"}`, n8n 200.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "chore(n8n-decouple): compose uses custom n8n image, env-driven URLs

n8n service builds from n8n.Dockerfile (OnPrintShop node baked in).
Volume-mount install removed. api service reads N8N_API_BASE_URL,
N8N_WEBHOOK_BASE_URL, N8N_PUSH_WEBHOOK_URL, API_BASE_URL from .env
with Compose-DNS fallbacks for dev only."
```

---

## Task 8: `.env.example` for the new vars

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add the n8n decoupling section**

Open `.env.example`. Find the section added in Phase 14a:

```
# ─── n8n / FastAPI INTER-SERVICE URLs ──────────────────────────────────────
# Phase 14b promotes these to required env vars in production.
# In dev (Docker Compose with --profile dev), use the Compose service DNS.
# Set these per environment; do NOT keep host.docker.internal here.
API_BASE_URL=
N8N_WEBHOOK_BASE_URL=
```

Replace with:

```
# ─── n8n / FastAPI INTER-SERVICE URLs ──────────────────────────────────────
# REQUIRED IN PRODUCTION. Backend refuses to boot if these are unset when
# ENVIRONMENT=production. In ECS Fargate they resolve via Cloud Map private
# DNS. In local dev with --profile dev, fall back to Docker Compose service
# DNS (already wired in docker-compose.yml).

# n8n → FastAPI ingest endpoints
API_BASE_URL=http://api:8000

# FastAPI → n8n webhooks (used by ops_push and any other webhook trigger)
N8N_WEBHOOK_BASE_URL=http://n8n:5678

# FastAPI → n8n REST API (workflow-trigger-by-id, etc.)
N8N_API_BASE_URL=http://n8n:5678

# n8n REST API key (generate from n8n editor → Settings → API)
N8N_API_KEY=

# Full URL of the OPS push webhook in n8n.
# Example dev: http://n8n:5678/webhook/vg-ops-push-001
# Example prod: http://n8n.api-hub.local:5678/webhook/vg-ops-push-001
N8N_PUSH_WEBHOOK_URL=
```

- [ ] **Step 2: Confirm no `host.docker.internal` left**

```bash
grep -n host.docker.internal .env.example || echo "OK"
```

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "docs(n8n-decouple): document required n8n URLs in .env.example"
```

---

## Task 9: Audit n8n workflow JSONs

**Files:**
- Modify: any `n8n-workflows/*.json` that hardcodes URLs

- [ ] **Step 1: Inventory hardcoded URLs in workflows**

```bash
grep -rn "host.docker.internal\|http://n8n:\|http://localhost\|http://127.0.0.1" n8n-workflows/ || echo "OK — workflows already use \$env"
```

- [ ] **Step 2: For each hit, replace with `{{$env.API_BASE_URL}}` or `{{$env.N8N_WEBHOOK_BASE_URL}}`**

If grep returned hits, edit each file in `n8n-workflows/` so URLs reference env vars. Example before:

```json
"url": "http://host.docker.internal:8000/api/ingest/..."
```

Example after:

```json
"url": "={{ $env.API_BASE_URL }}/api/ingest/..."
```

- [ ] **Step 3: Re-run grep to confirm**

```bash
grep -rn "host.docker.internal\|http://n8n:\|http://localhost\|http://127.0.0.1" n8n-workflows/ || echo "OK"
```
Expected: `OK`.

- [ ] **Step 4: Commit (skip if no changes)**

```bash
git diff --quiet n8n-workflows/ || (git add n8n-workflows/ && git commit -m "chore(n8n-decouple): workflow JSONs reference \$env.API_BASE_URL")
```

---

## Task 10: Integration contract documentation

**Files:**
- Create: `docs/n8n-integration.md`

- [ ] **Step 1: Write the document**

```markdown
# n8n Integration Contract

API-HUB treats n8n as an external workflow engine. This document is the
formal interface between the FastAPI backend and any n8n instance.

## 1. Environment requirements

n8n must be a host that supports community nodes:
- Self-hosted Docker (recommended; use `n8n.Dockerfile` from this repo)
- ECS Fargate (Phase 14d)
- n8n.cloud Pro+ (manual community-node install)
- Render, Fly, Railway, etc.

**Not supported:** n8n.cloud Starter — community nodes are blocked on that
tier and the OnPrintShop node will not load.

## 2. Required env vars on the n8n side

| Var | Purpose |
|-----|---------|
| `API_BASE_URL` | Base URL of the FastAPI backend (e.g. `http://backend.api-hub.local:8000`) |
| `INGEST_SHARED_SECRET` | Header value for `X-Ingest-Secret` on inbound calls to `/api/ingest/...` |
| `N8N_BASIC_AUTH_USER` / `N8N_BASIC_AUTH_PASSWORD` | Editor login (production) |

## 3. Outbound: backend → n8n webhooks

**Trigger:** FastAPI POSTs to a webhook URL configured per workflow.

**Headers:**
- `Content-Type: application/json`

**Body:** JSON payload defined per workflow. The OPS push payload (defined in
`backend/modules/ops_push/service.py`) is:

```json
{
  "push_log_id": "uuid",
  "customer_id": "uuid",
  "product_id": "uuid",
  "payload": {
    "external_id": "supplier-sku",
    "name": "Product Name",
    "variants": [...],
    "options": [...]
  },
  "ops_auth": {
    "base_url": "https://customer-ops.example.com",
    "token_url": "https://customer-ops.example.com/oauth/token",
    "client_id": "...",
    "client_secret": "..."
  }
}
```

**Response:**
- `2xx` — workflow accepted the trigger; backend leaves `push_log.status = "pending"`
- `4xx`/`5xx` — `httpx` raises; backend flips `push_log.status = "failed"` with `error = str(exc)`

**Security:** `ops_auth.client_secret` is shipped in the request body. The
webhook URL **must** point inside a private network (Cloud Map DNS in ECS,
VPC peering, or a dedicated VPN). Public-internet n8n hosts must terminate
TLS before this URL.

## 4. Inbound: n8n → backend ingest

**Endpoints:** `POST /api/ingest/{supplier_id}/products`, `categories`,
`inventory`, `pricing`, `master-options`.

**Headers:**
- `Content-Type: application/json`
- `X-Ingest-Secret: <INGEST_SHARED_SECRET>` (rejected with 401 if missing or wrong)

**Body shapes:** see `backend/modules/catalog/ingest.py` (Pydantic models).

## 5. Inbound: n8n → backend push callback (V1 future task)

After n8n calls OPS GraphQL and receives the real `ops_product_id`, it must
call back into FastAPI to flip the push log:

```
POST /api/push/{push_log_id}/callback
Headers:
  X-Ingest-Secret: <INGEST_SHARED_SECRET>
Body:
  {
    "status": "success" | "failed",
    "ops_product_id": "12345" | null,
    "error": null | "OPS error message"
  }
```

(Endpoint to be added in a follow-up — see issue #83.)

## 6. Self-host setup checklist

For a fresh n8n install (Docker, Render, Fly, etc.):

1. Run the custom image built from `n8n.Dockerfile` (or pull from your ECR
   if Phase 14d's CI is wired up). The OnPrintShop community node is
   pre-baked.
2. Visit the n8n editor; create the basic-auth admin account.
3. Settings → API → generate an API key. Copy.
4. Set env vars on the n8n container: `API_BASE_URL`, `INGEST_SHARED_SECRET`.
5. Set env vars on the FastAPI backend: `N8N_API_BASE_URL`,
   `N8N_API_KEY`, `N8N_WEBHOOK_BASE_URL`, `N8N_PUSH_WEBHOOK_URL`.
6. Import the workflow JSONs from `n8n-workflows/` via the n8n editor's
   Workflow → Import from File menu.
7. For each imported workflow, open it once and click "Save" so the
   workflow_id is stable.
8. Activate the workflows you need (cron syncs, OPS push).
9. Smoke test: POST `http://api:8000/api/ingest/{sid}/products` with the
   `X-Ingest-Secret` header — verify n8n executes the linked workflow.

## 7. Existing-install migration

Migrating from the current Docker Compose n8n install to a new ECS-hosted
n8n:

1. In the source n8n: Workflows → Export All → save the bundle.
2. In the source n8n: Credentials → for each credential, use the n8n CLI
   `n8n export:credentials --backup --output=...` (credentials are AES-256
   encrypted with `N8N_ENCRYPTION_KEY` — preserve this env var across hosts
   or re-create credentials manually).
3. In the destination n8n: Workflows → Import bundle. Credentials → CLI
   `n8n import:credentials --input=...`.
4. Re-activate workflows.
```

- [ ] **Step 2: Verify file written**

```bash
wc -l docs/n8n-integration.md
```
Expected: 100+ lines.

- [ ] **Step 3: Commit**

```bash
git add docs/n8n-integration.md
git commit -m "docs(n8n-decouple): formal n8n integration contract

Outbound webhook spec, inbound ingest spec, callback spec, self-host
setup checklist, existing-install migration procedure."
```

---

## Task 11: README update

**Files:**
- Modify: `README.md` (or top-level project doc)

- [ ] **Step 1: Find the README**

```bash
ls README.md 2>/dev/null && head -20 README.md || echo "Use api-hub/README.md or top-level note"
```

- [ ] **Step 2: Add n8n hosting note**

Append (or insert into the deployment section) the following block:

```markdown
## n8n hosting requirements

API-HUB delegates outbound integrations (OPS push, scheduled syncs) to n8n.
The OnPrintShop node is a custom community node baked into our `n8n.Dockerfile`.

Supported n8n hosts:
- Self-hosted Docker (use `n8n.Dockerfile` from this repo, or any image with
  `N8N_CUSTOM_EXTENSIONS` configured for the OnPrintShop node)
- ECS Fargate (Phase 14d)
- n8n.cloud Pro+ (manual community-node install)
- Render, Fly, Railway, Hetzner — anywhere Docker runs

**Not supported:** n8n.cloud Starter — community nodes are blocked on that
tier. The OnPrintShop node cannot be installed.

See [docs/n8n-integration.md](docs/n8n-integration.md) for the full contract
between FastAPI backend and n8n.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(n8n-decouple): README — n8n hosting requirements"
```

---

## Task 12: Sanity test the full stack

**Files:** none (verification)

- [ ] **Step 1: Build everything fresh**

```bash
docker compose --profile dev down -v
docker compose --profile dev build --no-cache
docker compose --profile dev up -d
sleep 12
docker compose ps
```

- [ ] **Step 2: Hit health endpoints**

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsSI http://127.0.0.1:3000 | head -3
curl -fsSI http://127.0.0.1:5678 | head -3
```
Expected: backend ok, frontend 200, n8n 200.

- [ ] **Step 3: Confirm OnPrintShop node visible in n8n**

```bash
docker compose logs n8n 2>&1 | grep -i onprintshop | head -3
```
Expected: at least one line confirming the node loaded.

- [ ] **Step 4: Confirm grep `host.docker.internal` is clean**

```bash
grep -rn host.docker.internal backend/ frontend/ docker-compose.yml .env.example | grep -v "^Binary" || echo "OK"
```
Expected: `OK` or only inside dev-comment context.

- [ ] **Step 5: Tear down**

```bash
docker compose --profile dev down
```

---

## Task 13: Open PR

- [ ] **Step 1: Push branch + open PR**

```bash
git push -u origin dev/phase14b-n8n-decouple
gh pr create --title "Phase 14b — n8n decoupling" --body "$(cat <<'EOF'
## Summary
Treats n8n as an external service. Removes Docker-Compose-DNS and host.docker.internal defaults from production paths.

- Backend startup check requires N8N_WEBHOOK_BASE_URL + API_BASE_URL in production
- ops_push trigger reads N8N_PUSH_WEBHOOK_URL from env; raises on n8n 5xx
- n8n_proxy client reads N8N_API_BASE_URL, falls back to N8N_BASE_URL for compat
- Custom n8n.Dockerfile bakes OnPrintShop node via N8N_CUSTOM_EXTENSIONS
- docker-compose.yml uses custom image, drops volume-mount install
- .env.example documents required vars
- docs/n8n-integration.md formal contract
- README clarifies: n8n.cloud Starter unsupported

Closes #86. Depends on #85 merged.

## Test plan
- [x] backend pytest passes (test_n8n_url_config covers prod fail-loud)
- [x] custom n8n image builds + loads OnPrintShop node
- [x] dev compose --profile dev up still works end-to-end
- [x] grep host.docker.internal returns 0 hits in code
EOF
)"
```

---

## Self-review checklist

- [ ] Spec coverage: every change in issue #86 maps to a task
  - Required env vars → Tasks 2, 3
  - n8n_proxy client env-read → Task 4
  - ops_push trigger env-read + raise_for_status → Task 5
  - Custom Docker image → Task 6
  - Compose update → Task 7
  - .env.example → Task 8
  - Workflow JSONs → Task 9
  - Integration doc → Task 10
  - README → Task 11
  - n8n.cloud Starter caveat → Task 11
- [ ] Placeholder scan: every code block contains real code
- [ ] Type consistency: `N8N_API_BASE_URL`, `N8N_WEBHOOK_BASE_URL`, `N8N_PUSH_WEBHOOK_URL` used consistently across files
- [ ] Frequent commits: 9 commits across 13 tasks (some doc-only tasks combine)
