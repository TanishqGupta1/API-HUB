# Phase 14a — Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock down container posture, CORS, ingest-secret handling, and add fail-loud startup checks so subsequent subsystems land on safe ground.

**Architecture:** No behaviour change for end users. Tightens config: backend container runs as non-root, ingest-script secret fallback removed, CORS regex disabled in production, n8n editor port gated behind a `dev` Compose profile, startup check refuses to boot in production if required env vars are unset.

**Tech Stack:** Python 3.12, FastAPI, Docker multi-stage build, docker-compose v2 profiles.

**Tracking issue:** [#85](https://github.com/VisualGraphxLLC/API-HUB/issues/85)

**Branch:** `dev/phase14a-security`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/Dockerfile` | Modify | Add non-root user; switch to that user before CMD |
| `backend/scripts/ingest_ops_master_options.py` | Modify | Drop hardcoded `vg-hub-ingest-secret-2026` fallback |
| `backend/main.py` | Modify | Add `_require_prod_env()` check called from lifespan; tighten CORS for production mode |
| `backend/tests/test_startup_checks.py` | Create | Unit tests for `_require_prod_env()` |
| `.env.example` | Modify | Mark required-in-prod vars; remove `host.docker.internal` default for `API_BASE_URL` |
| `docker-compose.yml` | Modify | Move n8n `ports` block under a `dev` profile |

---

## Task 1: Branch + baseline test infrastructure

**Files:**
- Create: `backend/tests/test_startup_checks.py` (placeholder)

- [ ] **Step 1: Create branch**

```bash
git checkout main
git pull --ff-only
git checkout -b dev/phase14a-security
```

- [ ] **Step 2: Create empty test file with skip marker**

```python
# backend/tests/test_startup_checks.py
import pytest

pytestmark = pytest.mark.asyncio


@pytest.mark.skip(reason="implemented in Task 4")
async def test_placeholder():
    pass
```

- [ ] **Step 3: Verify test discovery**

```bash
cd backend && source .venv/bin/activate
pytest tests/test_startup_checks.py -v
```
Expected: 1 skipped.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_startup_checks.py
git commit -m "test(phase14a): scaffold startup-checks test file"
```

---

## Task 2: Drop hardcoded ingest secret fallback

**Files:**
- Modify: `backend/scripts/ingest_ops_master_options.py:12`

- [ ] **Step 1: Replace fallback with required-env read**

Open `backend/scripts/ingest_ops_master_options.py`. Replace line 12:

```python
# OLD
INGEST_SECRET = os.getenv("INGEST_SHARED_SECRET", "vg-hub-ingest-secret-2026")

# NEW
INGEST_SECRET = os.environ["INGEST_SHARED_SECRET"]
```

- [ ] **Step 2: Verify the script fails loudly without env**

```bash
cd backend && source .venv/bin/activate
unset INGEST_SHARED_SECRET
python scripts/ingest_ops_master_options.py 2>&1 | head -3
```
Expected: `KeyError: 'INGEST_SHARED_SECRET'` immediately.

- [ ] **Step 3: Verify with env set**

```bash
INGEST_SHARED_SECRET=test-only python -c "import scripts.ingest_ops_master_options as m; print(m.INGEST_SECRET)"
```
Expected: `test-only` printed.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/ingest_ops_master_options.py
git commit -m "fix(security): drop hardcoded ingest-secret fallback in script

The fallback string was a known public value committed to the repo.
Anyone with repo access could call ingest endpoints. Now the script
requires INGEST_SHARED_SECRET env var and crashes loudly if unset."
```

---

## Task 3: Backend Dockerfile — non-root user

**Files:**
- Modify: `backend/Dockerfile`

- [ ] **Step 1: Read current Dockerfile state**

```bash
cat backend/Dockerfile
```

- [ ] **Step 2: Add user creation + USER directive**

Replace the final `FROM python:3.12-slim` stage block with:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app:/deps \
    PATH="/deps/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# libpq5 needed by asyncpg/psycopg at runtime; keep image lean
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -u 1000 app
COPY --from=builder /deps /deps
COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Build the image**

```bash
docker compose build api 2>&1 | tail -10
```
Expected: build succeeds.

- [ ] **Step 4: Verify the container runs as uid 1000**

```bash
docker compose run --rm api id
```
Expected: `uid=1000(app) gid=1000(app) groups=1000(app)`.

- [ ] **Step 5: Verify the app still boots**

```bash
docker compose up -d api postgres 2>&1 | tail -5
sleep 5
docker compose logs api --tail 20
curl -fsS http://127.0.0.1:8000/health
docker compose down
```
Expected: `{"status":"ok"}` from `/health`. No permission errors in logs.

- [ ] **Step 6: Commit**

```bash
git add backend/Dockerfile
git commit -m "fix(security): backend Dockerfile runs as non-root uid 1000

Container compromise no longer means root inside the container.
Adds 'app' user, sets ownership on COPY, switches USER before CMD."
```

---

## Task 4: Production startup check helper

**Files:**
- Modify: `backend/main.py` — add `_require_prod_env()` function
- Modify: `backend/tests/test_startup_checks.py` — replace skip with real tests

- [ ] **Step 1: Write failing tests**

Replace the entire content of `backend/tests/test_startup_checks.py`:

```python
import os
import pytest

pytestmark = pytest.mark.asyncio


@pytest.fixture
def clean_env(monkeypatch):
    """Clear env vars the check looks for, restore after test."""
    for key in (
        "ENVIRONMENT", "SECRET_KEY", "JWT_SECRET_KEY",
        "INGEST_SHARED_SECRET", "ALLOWED_ORIGINS",
        "POSTGRES_URL", "N8N_WEBHOOK_BASE_URL", "API_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)


async def test_dev_mode_passes_with_no_env(clean_env, monkeypatch):
    """Development mode must not fail on missing prod-only vars."""
    from main import _require_prod_env
    monkeypatch.setenv("ENVIRONMENT", "development")
    _require_prod_env()  # no exception


async def test_production_mode_fails_when_secret_key_missing(clean_env, monkeypatch):
    from main import _require_prod_env
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("INGEST_SHARED_SECRET", "x")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("POSTGRES_URL", "postgresql+asyncpg://u:p@h/d")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _require_prod_env()


async def test_production_mode_passes_when_all_vars_set(clean_env, monkeypatch):
    from main import _require_prod_env
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "k" * 44)
    monkeypatch.setenv("INGEST_SHARED_SECRET", "x")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("POSTGRES_URL", "postgresql+asyncpg://u:p@h/d")
    _require_prod_env()  # no exception
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && source .venv/bin/activate
pytest tests/test_startup_checks.py -v
```
Expected: all 3 FAIL with `ImportError: cannot import name '_require_prod_env' from 'main'`.

- [ ] **Step 3: Implement `_require_prod_env()` in `main.py`**

Open `backend/main.py`. Find the import block at the top of the file (around line 1-30). After the existing imports, insert:

```python
_PROD_REQUIRED_ENV_VARS = (
    "SECRET_KEY",
    "INGEST_SHARED_SECRET",
    "ALLOWED_ORIGINS",
    "POSTGRES_URL",
)


def _require_prod_env() -> None:
    """Refuse to boot in production if required env vars are missing.

    Called at the top of the lifespan handler. In development the check is
    a no-op so local dev still works without a full prod env.
    """
    if os.getenv("ENVIRONMENT", "development").lower() != "production":
        return
    missing = [v for v in _PROD_REQUIRED_ENV_VARS if not os.getenv(v, "").strip()]
    if missing:
        raise RuntimeError(
            "Production startup blocked. Missing required env vars: "
            + ", ".join(missing)
            + ". Set them in the task definition / ECS secrets / Secrets Manager."
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_startup_checks.py -v
```
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_startup_checks.py
git commit -m "feat(security): add _require_prod_env() startup check

Refuses to boot in ENVIRONMENT=production if any required env var is
unset. No-op in development. Tests cover dev pass-through, prod fail
on missing var, prod pass when all set."
```

---

## Task 5: Wire startup check into lifespan

**Files:**
- Modify: `backend/main.py` — call `_require_prod_env()` first thing in `lifespan`

- [ ] **Step 1: Locate the lifespan function**

```bash
grep -n "async def lifespan" backend/main.py
```

- [ ] **Step 2: Add the call**

Open `backend/main.py`. Inside the `lifespan` function body, before any other statement, add:

```python
async def lifespan(app: FastAPI):
    _require_prod_env()
    # ... existing body unchanged
```

- [ ] **Step 3: Verify dev mode still boots**

```bash
docker compose up -d 2>&1 | tail -5
sleep 5
curl -fsS http://127.0.0.1:8000/health
docker compose down
```
Expected: `{"status":"ok"}`.

- [ ] **Step 4: Verify prod mode without secrets refuses to boot**

```bash
docker compose run --rm \
  -e ENVIRONMENT=production \
  -e SECRET_KEY= \
  -e ALLOWED_ORIGINS= \
  -e INGEST_SHARED_SECRET= \
  -e POSTGRES_URL= \
  api python -c "import asyncio; from main import _require_prod_env; _require_prod_env()" 2>&1 | tail -3
```
Expected: `RuntimeError: Production startup blocked. Missing required env vars: SECRET_KEY, INGEST_SHARED_SECRET, ALLOWED_ORIGINS, POSTGRES_URL.`

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat(security): call _require_prod_env() at lifespan startup

App refuses to start in ENVIRONMENT=production if any required env
var is unset. Dev mode unaffected."
```

---

## Task 6: CORS production lock

**Files:**
- Modify: `backend/main.py` — CORS middleware block

- [ ] **Step 1: Locate the CORS middleware block**

```bash
grep -n "CORSMiddleware" backend/main.py
```

- [ ] **Step 2: Replace the block**

Open `backend/main.py`. Find the existing `app.add_middleware(CORSMiddleware, ...)` call (currently around lines 164-171). Replace with:

```python
_IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"
_CORS_METHODS = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
_CORS_HEADERS = ["Authorization", "Content-Type", "X-Ingest-Secret"]

_cors_kwargs: dict = dict(
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=_CORS_METHODS,
    allow_headers=_CORS_HEADERS,
)
if not _IS_PRODUCTION:
    _cors_kwargs["allow_origin_regex"] = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"

app.add_middleware(CORSMiddleware, **_cors_kwargs)
```

- [ ] **Step 3: Verify dev mode still allows localhost ports**

```bash
docker compose up -d 2>&1 | tail -3
sleep 5
curl -i -H "Origin: http://localhost:9999" http://127.0.0.1:8000/health 2>&1 | grep -i access-control
docker compose down
```
Expected: `access-control-allow-origin: http://localhost:9999` in headers.

- [ ] **Step 4: Verify prod mode rejects unknown origin**

```bash
docker compose run --rm \
  -e ENVIRONMENT=production \
  -e SECRET_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  -e INGEST_SHARED_SECRET=test \
  -e ALLOWED_ORIGINS=https://app.example.com \
  -e POSTGRES_URL="postgresql+asyncpg://vg_user:vg_pass@postgres:5432/vg_hub" \
  -p 8001:8000 \
  api python -m uvicorn main:app --host 0.0.0.0 --port 8000 &

sleep 3
curl -i -H "Origin: http://localhost:9999" http://127.0.0.1:8001/health 2>&1 | grep -i access-control || echo "NO CORS HEADER (correct in prod)"
kill %1
```
Expected: no `access-control-allow-origin` header for the unknown origin.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat(security): lock CORS in production

Production mode disables the localhost regex and locks methods +
headers to explicit lists. Dev mode unchanged. Methods now restricted
to [GET, POST, PATCH, DELETE, OPTIONS] in both modes; headers to
[Authorization, Content-Type, X-Ingest-Secret]."
```

---

## Task 7: Gate n8n editor port behind dev profile

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Read current n8n service block**

```bash
grep -n "n8n:" docker-compose.yml
sed -n '36,62p' docker-compose.yml
```

- [ ] **Step 2: Add `profiles: [dev]` to the n8n service**

Open `docker-compose.yml`. Inside the `n8n:` service block (currently lines 36–62), add a `profiles:` key alongside the other top-level service keys (after `image`, before `ports`):

```yaml
  n8n:
    image: n8nio/n8n:latest
    profiles: ["dev"]
    ports:
      - "5678:5678"
    # ... rest unchanged
```

- [ ] **Step 3: Verify default `up` no longer starts n8n**

```bash
docker compose down
docker compose up -d 2>&1 | tail -10
docker compose ps
```
Expected: `n8n` is NOT in the running services list.

- [ ] **Step 4: Verify `--profile dev` starts n8n**

```bash
docker compose --profile dev up -d 2>&1 | tail -5
docker compose ps | grep n8n
```
Expected: `n8n` is running.

- [ ] **Step 5: Tear down**

```bash
docker compose --profile dev down
```

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml
git commit -m "chore(security): gate n8n service behind dev profile

Default 'docker compose up' no longer starts n8n on port 5678.
Use 'docker compose --profile dev up' for local dev. Production
deploys via ECS Fargate (Phase 14d) — never via this Compose file."
```

---

## Task 8: `.env.example` documentation pass

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Read current state**

```bash
cat .env.example
```

- [ ] **Step 2: Update with REQUIRED IN PROD comments**

Replace the entire file content with:

```bash
# ─── REQUIRED IN PRODUCTION ─────────────────────────────────────────────────
# These variables MUST be set when ENVIRONMENT=production. The backend refuses
# to boot if any of them are unset. In ECS Fargate they come from
# Secrets Manager via the task definition.

# Connection string for asyncpg
POSTGRES_URL=postgresql+asyncpg://vg_user:vg_pass@localhost:5432/vg_hub

# Fernet key for EncryptedJSON columns (suppliers.auth_config, customers.ops_auth_config).
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SECRET_KEY=

# Shared secret for n8n → FastAPI ingest endpoints (POST /api/ingest/{sid}/...).
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
INGEST_SHARED_SECRET=

# CORS — comma-separated list of allowed origins for the FastAPI backend.
# In production this list is the only way to allow a browser origin.
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# ─── DEV-ONLY DEFAULTS ─────────────────────────────────────────────────────

POSTGRES_USER=vg_user
POSTGRES_PASSWORD=vg_pass
POSTGRES_DB=vg_hub
ENVIRONMENT=development

# SanMar SFTP Connection (optional — only set if you need SanMar imports locally)
SANMAR_SFTP_HOST=ftp.sanmar.com
SANMAR_SFTP_PORT=2200
SANMAR_SFTP_USER=
SANMAR_SFTP_PASS=

# PromoStandards
PS_DIRECTORY_URL=https://services.promostandards.org/WebServiceRepository/WebServiceRepository.svc/json

# n8n Workflows (used by the frontend)
NEXT_PUBLIC_PUSH_WORKFLOW_ID=vg-ops-push-001
NEXT_PUBLIC_N8N_URL=http://localhost:5678
MASTER_OPTIONS_SYNC_WORKFLOW_ID=ops-master-options-pull-001

# ─── n8n / FastAPI INTER-SERVICE URLs ──────────────────────────────────────
# Phase 14b promotes these to required env vars in production.
# In dev (Docker Compose with --profile dev), use the Compose service DNS.
# Set these per environment; do NOT keep host.docker.internal here.
API_BASE_URL=
N8N_WEBHOOK_BASE_URL=
```

- [ ] **Step 3: Confirm there is no `host.docker.internal` left**

```bash
grep -n host.docker.internal .env.example || echo "OK — no host.docker.internal references"
```
Expected: `OK — no host.docker.internal references`.

- [ ] **Step 4: Commit**

```bash
git add .env.example
git commit -m "docs(security): mark required-in-prod env vars in .env.example

Clear separation between vars that must be set in production (will
fail startup if missing) and dev-only defaults. Drops the
host.docker.internal default for API_BASE_URL — Phase 14b promotes
this to a required env var with no default."
```

---

## Task 9: Sanity test the full flow

**Files:**
- No new files. Verification only.

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && source .venv/bin/activate
pytest -q 2>&1 | tail -10
```
Expected: all green (or pre-existing failures unrelated to phase 14a — note them in PR description if any).

- [ ] **Step 2: Run frontend lint**

```bash
cd frontend && npm run lint 2>&1 | tail -5
```
Expected: no new errors compared to main.

- [ ] **Step 3: Bring stack up dev mode end-to-end**

```bash
cd /Users/tanishq/Documents/project-files/api-hub/api-hub
docker compose --profile dev up -d 2>&1 | tail -10
sleep 8
curl -fsS http://127.0.0.1:8000/health
curl -fsSI http://127.0.0.1:3000 | head -3
curl -fsSI http://127.0.0.1:5678 | head -3
docker compose --profile dev down
```
Expected: backend `{"status":"ok"}`, frontend 200, n8n 200.

- [ ] **Step 4: Confirm default `up` (no profile) does NOT start n8n**

```bash
docker compose up -d 2>&1 | tail -5
docker compose ps | grep -c n8n
docker compose down
```
Expected: `0` n8n containers running.

---

## Task 10: Open PR

- [ ] **Step 1: Push branch**

```bash
git push -u origin dev/phase14a-security
```

- [ ] **Step 2: Open PR**

```bash
gh pr create --title "Phase 14a — security hardening" --body "$(cat <<'EOF'
## Summary
Foundation for Phase 14 production readiness. No behaviour change for end users.

- Backend Dockerfile runs as uid 1000 (non-root)
- Drop hardcoded INGEST_SHARED_SECRET fallback in scripts/ingest_ops_master_options.py
- Production startup check: refuse to boot if SECRET_KEY / INGEST_SHARED_SECRET / ALLOWED_ORIGINS / POSTGRES_URL unset
- CORS production lock: drop localhost regex in prod, lock methods + headers
- docker-compose: gate n8n editor port behind a 'dev' profile
- .env.example: REQUIRED IN PROD section, drop host.docker.internal default

Closes #85.

## Test plan
- [x] backend pytest passes
- [x] docker compose up (no profile) does NOT start n8n
- [x] docker compose --profile dev up starts n8n on :5678
- [x] backend container runs as uid 1000
- [x] prod env without required vars refuses to boot
- [x] CORS preflight from unknown origin rejected in prod env
EOF
)"
```

- [ ] **Step 3: Verify PR opened**

```bash
gh pr view --web
```

---

## Self-review checklist

After completing all tasks:

- [ ] Spec coverage: each acceptance criterion in issue #85 maps to a task
  - Non-root container → Task 3
  - Drop ingest secret fallback → Task 2
  - CORS prod lock → Task 6
  - n8n compose profile → Task 7
  - Startup check → Tasks 4 + 5
  - .env.example documentation → Task 8
- [ ] Placeholder scan: every code block contains real code, no "TBD" / "fill in"
- [ ] Type consistency: `_require_prod_env`, `_PROD_REQUIRED_ENV_VARS`, `_CORS_METHODS`, `_CORS_HEADERS` named the same in tests + main.py
- [ ] Frequent commits: 8 separate commits across 8 functional tasks
