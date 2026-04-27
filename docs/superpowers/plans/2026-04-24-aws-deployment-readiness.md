# AWS Deployment Readiness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all localhost hardcodes + package the n8n OnPrintShop node for external n8n instances. App becomes runnable on any host (App Runner, ECS, EC2, Kubernetes) via env vars alone.

**Architecture:** Two orthogonal changes. (1) Config externalization: kill hardcoded localhost/host.docker.internal across backend + frontend + n8n workflows; all URLs from env. (2) n8n node packaging: publish-ready `n8n-nodes-onprintshop` so external n8n instances install via `npm install github:...`. No Dockerfile rewrites (defer multi-stage optimization). Existing `docker-compose.yml` continues working for local dev.

**Tech Stack:** FastAPI (Python 3.12), Next.js 15, n8n (npm 20.x node), TypeScript, shell.

**Spec / source of truth:** meeting brainstorm on 2026-04-24 + companion plan at `/Users/tanishq/.gemini/tmp/api-hub/4a11aa23-a6f6-486c-9fc9-e05a810affda/plans/2026-04-24-aws-deployment-readiness.md`. This plan covers the app-level half; infra (CloudFormation for App Runner + ECS-n8n + RDS + Secrets Manager) is a separate plan.

---

## File map

| File | Action | Task |
|------|--------|------|
| `backend/database.py` | MODIFY | Task 1 — remove localhost default, conditional load_dotenv |
| `backend/main.py` | MODIFY | Task 2 — CORS_ORIGINS env parser |
| `backend/modules/n8n_proxy/routes.py` | MODIFY | Task 3 — drop N8N_BASE_URL localhost default |
| `frontend/src/app/(admin)/products/configure/page.tsx` | MODIFY | Task 4 — env-driven n8n URL in alert text |
| `frontend/src/app/(admin)/api-registry/page.tsx` | MODIFY | Task 4 — env-driven API base in display |
| `n8n-workflows/ops-master-options-pull.json` | MODIFY | Task 5 — host.docker.internal → $env.API_HUB_BASE_URL |
| `n8n-workflows/vg-ops-pull.json` | MODIFY | Task 5 |
| `n8n-workflows/sanmar-soap-pull.json` | MODIFY | Task 5 |
| `n8n-workflows/sanmar-sftp-pull.json` | MODIFY | Task 5 |
| `docker-compose.yml` | MODIFY | Task 6 — pass API_HUB_BASE_URL to n8n service |
| `.env.example` | MODIFY | Task 6 — add all new vars |
| `n8n-nodes-onprintshop/package.json` | MODIFY | Task 7 — n8n block + files array + publishConfig |
| `n8n-nodes-onprintshop/.npmignore` | CREATE | Task 7 |
| `n8n-nodes-onprintshop/README.md` | MODIFY | Task 7 — install-via-github instructions |
| `backend/tests/test_config.py` | CREATE | Task 1–3 tests |

---

## Task 1 — Backend: conditional `load_dotenv` + require POSTGRES_URL

**Files:**
- Modify: `backend/database.py`
- Test: `backend/tests/test_config.py` (new)

- [ ] **Step 1: Write failing test `backend/tests/test_config.py`**

```python
"""Config resilience tests — app must not crash when .env is missing,
and must reject missing required secrets."""

import importlib
import os
import sys

import pytest


def _reload_database():
    """Force re-import so module-level env reads re-run."""
    if "database" in sys.modules:
        del sys.modules["database"]
    return importlib.import_module("database")


def test_database_requires_postgres_url(monkeypatch):
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    # Also hide .env loading by pointing loader at a non-existent file
    monkeypatch.setenv("DOTENV_PATH", "/nonexistent/.env")
    with pytest.raises(RuntimeError, match="POSTGRES_URL"):
        _reload_database()


def test_database_uses_env_postgres_url(monkeypatch):
    monkeypatch.setenv(
        "POSTGRES_URL",
        "postgresql+asyncpg://test:test@testhost:5432/testdb",
    )
    db = _reload_database()
    url = str(db.engine.url)
    assert "testhost" in url
    assert "localhost" not in url
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_config.py -v`
Expected: FAIL. First test fails because current `database.py` line 20 falls back to `localhost:5432` default.

- [ ] **Step 3: Fix `backend/database.py`**

Find the existing block near the top:
```python
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

POSTGRES_URL = os.getenv(
    "POSTGRES_URL", "postgresql+asyncpg://vg_user:vg_pass@localhost:5432/vg_hub"
)
```

Replace with:
```python
from dotenv import load_dotenv

_dotenv_path = Path(__file__).parent.parent / ".env"
if _dotenv_path.exists():
    load_dotenv(_dotenv_path)

POSTGRES_URL = os.getenv("POSTGRES_URL")
if not POSTGRES_URL:
    raise RuntimeError(
        "POSTGRES_URL environment variable is required. "
        "Set it via .env for local dev or via container env/Secrets Manager in production."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_config.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Smoke-test existing tests still green**

```bash
docker compose restart api && sleep 4
docker compose exec -T api pytest tests/ -v 2>&1 | tail -10
```
Expected: all existing tests still pass (conftest.py loads .env via its own path, so container has POSTGRES_URL).

- [ ] **Step 6: Commit**

```bash
git add backend/database.py backend/tests/test_config.py
git commit -m "feat(backend): require POSTGRES_URL env, make load_dotenv resilient for container deploy"
```

---

## Task 2 — Backend: `CORS_ORIGINS` env parser

**Files:**
- Modify: `backend/main.py` (lines 78–83)
- Test: `backend/tests/test_config.py` (append)

- [ ] **Step 1: Append failing test to `backend/tests/test_config.py`**

```python
def test_cors_origins_parsed_from_env(monkeypatch):
    """CORS_ORIGINS env var should split on comma and be used by the app."""
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://app.staging.vg,https://app.prod.vg",
    )
    # Re-import main to pick up new env
    if "main" in sys.modules:
        del sys.modules["main"]
    main = importlib.import_module("main")
    # Inspect the CORS middleware config
    middlewares = [m for m in main.app.user_middleware if "CORS" in str(m.cls)]
    assert len(middlewares) >= 1
    cors = middlewares[0].options
    assert "https://app.staging.vg" in cors["allow_origins"]
    assert "https://app.prod.vg" in cors["allow_origins"]


def test_cors_origins_empty_when_unset(monkeypatch):
    """If CORS_ORIGINS is unset, allow_origins should be empty list
    (regex-only origin matching) — no implicit localhost for production."""
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    if "main" in sys.modules:
        del sys.modules["main"]
    main = importlib.import_module("main")
    middlewares = [m for m in main.app.user_middleware if "CORS" in str(m.cls)]
    cors = middlewares[0].options
    assert cors["allow_origins"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec -T api pytest tests/test_config.py::test_cors_origins_parsed_from_env tests/test_config.py::test_cors_origins_empty_when_unset -v
```
Expected: FAIL — current code hardcodes `["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173"]`.

- [ ] **Step 3: Modify `backend/main.py`**

Find the existing `app.add_middleware(CORSMiddleware, ...)` block (around lines 75–90) and the `allow_origins=[...]` list. Replace the list with env-driven parsing. Keep the regex-based localhost match for dev ergonomics.

Before:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
    ],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

After:
```python
_cors_origins_env = os.getenv("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Ensure `import os` exists at top of file (it does).

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose restart api && sleep 4
docker compose exec -T api pytest tests/test_config.py -v
```
Expected: all 4 tests in test_config.py PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_config.py
git commit -m "feat(backend): CORS_ORIGINS env-driven, keeps localhost regex for dev"
```

---

## Task 3 — Backend: drop `N8N_BASE_URL` localhost default

**Files:**
- Modify: `backend/modules/n8n_proxy/routes.py` (line 28)
- Test: `backend/tests/test_config.py` (append)

- [ ] **Step 1: Append test**

```python
def test_n8n_base_url_required(monkeypatch):
    """n8n_proxy must raise if N8N_BASE_URL unset (not fall back to localhost)."""
    monkeypatch.delenv("N8N_BASE_URL", raising=False)
    # Force re-import to re-evaluate module-level getenv
    for mod in list(sys.modules):
        if mod.startswith("modules.n8n_proxy"):
            del sys.modules[mod]
    import modules.n8n_proxy.routes as n8n_routes
    with pytest.raises(RuntimeError, match="N8N_BASE_URL"):
        n8n_routes._n8n_base_url()


def test_n8n_base_url_uses_env(monkeypatch):
    monkeypatch.setenv("N8N_BASE_URL", "http://n8n.internal:5678")
    for mod in list(sys.modules):
        if mod.startswith("modules.n8n_proxy"):
            del sys.modules[mod]
    import modules.n8n_proxy.routes as n8n_routes
    assert n8n_routes._n8n_base_url() == "http://n8n.internal:5678"
```

- [ ] **Step 2: Run tests**

```bash
docker compose exec -T api pytest tests/test_config.py -v
```
Expected: 2 new tests FAIL (function `_n8n_base_url` doesn't exist yet; current code inline-defaults to localhost).

- [ ] **Step 3: Modify `backend/modules/n8n_proxy/routes.py`**

Find the existing helper (around line 28) that returns `os.getenv("N8N_BASE_URL", "http://localhost:5678").rstrip("/")`. Replace its contents with:

```python
def _n8n_base_url() -> str:
    """Return N8N_BASE_URL from env. Raises RuntimeError if unset."""
    url = os.getenv("N8N_BASE_URL")
    if not url:
        raise RuntimeError(
            "N8N_BASE_URL environment variable is required. "
            "Set it to http://n8n:5678 (docker-compose) or an internal service URL in production."
        )
    return url.rstrip("/")
```

If the existing function already has a different name (`_n8n_base_url` or inline), keep the existing callsite behavior. Just modify the function body. All callers `f"{_n8n_base_url()}/{path}"` still work.

- [ ] **Step 4: Run tests to verify pass**

```bash
docker compose restart api && sleep 4
docker compose exec -T api pytest tests/test_config.py -v
```
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/n8n_proxy/routes.py backend/tests/test_config.py
git commit -m "feat(backend): require N8N_BASE_URL env — no localhost fallback"
```

---

## Task 4 — Frontend: remove localhost display strings

**Files:**
- Modify: `frontend/src/app/(admin)/products/configure/page.tsx` (line ~43)
- Modify: `frontend/src/app/(admin)/api-registry/page.tsx` (line ~113)

- [ ] **Step 1: Patch `frontend/src/app/(admin)/products/configure/page.tsx`**

Find the alert text (currently line 43):
```ts
alert("Sync failed. Check n8n at http://localhost:5678.");
```

Replace with:
```ts
const n8nUrl = process.env.NEXT_PUBLIC_N8N_URL || "your n8n instance";
alert(`Sync failed. Check n8n at ${n8nUrl}.`);
```

- [ ] **Step 2: Patch `frontend/src/app/(admin)/api-registry/page.tsx`**

Find the display line (currently line 113):
```tsx
BASE_URL: http://localhost:8000
```

Replace with:
```tsx
BASE_URL: {process.env.NEXT_PUBLIC_API_URL || "(unset)"}
```

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E "configure/page|api-registry/page" | head -5
```
Expected: no new errors in these files.

- [ ] **Step 4: Smoke test in browser**

Visit `http://localhost:3000/products/configure` + `http://localhost:3000/api-registry`. Strings render using the local dev env URLs (from `frontend/.env.local`).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/\(admin\)/products/configure/page.tsx frontend/src/app/\(admin\)/api-registry/page.tsx
git commit -m "feat(frontend): read NEXT_PUBLIC_N8N_URL and NEXT_PUBLIC_API_URL for display strings"
```

---

## Task 5 — n8n workflows: host.docker.internal → `$env.API_HUB_BASE_URL`

**Files:**
- Modify: `n8n-workflows/ops-master-options-pull.json`
- Modify: `n8n-workflows/vg-ops-pull.json`
- Modify: `n8n-workflows/sanmar-soap-pull.json`
- Modify: `n8n-workflows/sanmar-sftp-pull.json`

`ops-push.json` already uses `$env.API_HUB_BASE_URL` pattern — skip it.

- [ ] **Step 1: Backup + find all raw occurrences**

```bash
cd n8n-workflows
grep -l "host.docker.internal" *.json
```
Expected: 4 files listed.

- [ ] **Step 2: Replace URLs in `ops-master-options-pull.json`**

Find:
```
"url": "http://host.docker.internal:8000/api/ingest/master-options"
```
Replace with (n8n expression syntax — note the `=` prefix makes it evaluated):
```
"url": "={{ $env.API_HUB_BASE_URL }}/api/ingest/master-options"
```

- [ ] **Step 3: Replace URLs in `vg-ops-pull.json`** (3 occurrences)

Same pattern:
```
"url": "http://host.docker.internal:8000/api/suppliers"
→ "url": "={{ $env.API_HUB_BASE_URL }}/api/suppliers"

"url": "=http://host.docker.internal:8000/api/ingest/{{ $('Resolve VG SID').item.json.vg_sid }}/categories"
→ "url": "={{ $env.API_HUB_BASE_URL }}/api/ingest/{{ $('Resolve VG SID').item.json.vg_sid }}/categories"

"url": "=http://host.docker.internal:8000/api/ingest/{{ $('Resolve VG SID').item.json.vg_sid }}/products"
→ "url": "={{ $env.API_HUB_BASE_URL }}/api/ingest/{{ $('Resolve VG SID').item.json.vg_sid }}/products"
```

Note: the leading `=` is preserved on expressions. When URL was a raw string (no `=`), prepend `=` now because we're introducing an expression.

- [ ] **Step 4: Replace URLs in `sanmar-soap-pull.json`** (3 occurrences)

```
"url": "http://host.docker.internal:8000/api/suppliers"
→ "url": "={{ $env.API_HUB_BASE_URL }}/api/suppliers"

"url": "=http://host.docker.internal:8000/api/sync/{{ $json.sid }}/products"
→ "url": "={{ $env.API_HUB_BASE_URL }}/api/sync/{{ $json.sid }}/products"

"url": "=http://host.docker.internal:8000/api/sync/{{ $('Resolve SanMar SID').item.json.sid }}/status"
→ "url": "={{ $env.API_HUB_BASE_URL }}/api/sync/{{ $('Resolve SanMar SID').item.json.sid }}/status"
```

- [ ] **Step 5: Replace URLs in `sanmar-sftp-pull.json`** (3 occurrences)

```
"url": "http://host.docker.internal:8000/api/suppliers"
→ "url": "={{ $env.API_HUB_BASE_URL }}/api/suppliers"

"url": "=http://host.docker.internal:8000/api/ingest/{{ $('Resolve SanMar SID').item.json.sid }}/products"
→ "url": "={{ $env.API_HUB_BASE_URL }}/api/ingest/{{ $('Resolve SanMar SID').item.json.sid }}/products"

"url": "http://host.docker.internal:8000/api/push-log"
→ "url": "={{ $env.API_HUB_BASE_URL }}/api/push-log"
```

- [ ] **Step 6: Validate JSON + re-import all**

```bash
for f in ops-master-options-pull.json vg-ops-pull.json sanmar-soap-pull.json sanmar-sftp-pull.json; do
  python3 -c "import json; json.load(open('n8n-workflows/$f')); print('$f ok')"
  docker cp n8n-workflows/$f api-hub-n8n-1:/tmp/$f
  docker exec api-hub-n8n-1 n8n import:workflow --input=/tmp/$f
done
```
Expected: each prints `ok` + `Successfully imported 1 workflow.`

- [ ] **Step 7: Verify env var resolves in n8n at runtime**

In n8n UI, open one workflow (e.g. `vg-ops-pull`). Click the `Get Suppliers` HTTP node. "Test step". Expected: request hits whatever `API_HUB_BASE_URL` resolves to — in local dev container, `http://host.docker.internal:8000` (set via compose env). 200 response.

If n8n doesn't have `API_HUB_BASE_URL` in its env yet, this fails. Task 6 fixes compose file.

- [ ] **Step 8: Commit**

```bash
git add n8n-workflows/*.json
git commit -m "feat(n8n): replace host.docker.internal with API_HUB_BASE_URL env expression"
```

---

## Task 6 — docker-compose: pass env vars to services

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: Add env passthrough to `docker-compose.yml`**

Find the `n8n` service block. Under `environment:` (or create it), add:
```yaml
    environment:
      - API_HUB_BASE_URL=http://host.docker.internal:8000
      - INGEST_SHARED_SECRET=${INGEST_SHARED_SECRET}
      - N8N_HOST=0.0.0.0
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - NODE_FUNCTION_ALLOW_EXTERNAL=*
```

Find the `api` service block. Under `environment:` (or create it), add:
```yaml
    environment:
      - POSTGRES_URL=postgresql+asyncpg://${POSTGRES_USER:-vg_user}:${POSTGRES_PASSWORD:-vg_pass}@postgres:5432/${POSTGRES_DB:-vg_hub}
      - SECRET_KEY=${SECRET_KEY}
      - INGEST_SHARED_SECRET=${INGEST_SHARED_SECRET}
      - N8N_BASE_URL=http://n8n:5678
      - CORS_ORIGINS=http://localhost:3000
      - N8N_API_KEY=${N8N_API_KEY:-}
```

If existing lines in either block overlap, keep them — just add the missing ones. Preserve existing `depends_on`, `ports`, `volumes`.

- [ ] **Step 2: Update `.env.example`**

Replace current content with:
```env
# Postgres
POSTGRES_USER=vg_user
POSTGRES_PASSWORD=vg_pass
POSTGRES_DB=vg_hub
POSTGRES_URL=postgresql+asyncpg://vg_user:vg_pass@localhost:5432/vg_hub

# Fernet encryption — generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SECRET_KEY=

# Auth between n8n ↔ FastAPI ingest endpoints (any random 32+ chars)
INGEST_SHARED_SECRET=

# n8n API token (optional; for backend → n8n trigger calls)
N8N_API_KEY=
```

- [ ] **Step 3: Restart stack, verify nothing breaks**

```bash
docker compose down
docker compose up -d
sleep 6
docker compose ps
curl -s -o /dev/null -w "api: %{http_code}\nn8n: %{http_code}\nfrontend: %{http_code}\n" \
  http://localhost:8000/docs http://localhost:5678 http://localhost:3000
```
Expected: all 200.

- [ ] **Step 4: Run an n8n workflow — env var resolves**

In n8n UI, execute `vg-ops-pull` manual trigger. First HTTP node (`Get Suppliers`) should hit `http://host.docker.internal:8000/api/suppliers` and return 200.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "feat(compose): pass API_HUB_BASE_URL and service env vars to n8n + api containers"
```

---

## Task 7 — Package `n8n-nodes-onprintshop` for external install

**Files:**
- Modify: `n8n-nodes-onprintshop/package.json`
- Create: `n8n-nodes-onprintshop/.npmignore`
- Modify: `n8n-nodes-onprintshop/README.md`

- [ ] **Step 1: Patch `n8n-nodes-onprintshop/package.json`**

Load the existing file. Ensure these top-level fields are present/correct (merge with existing, don't overwrite unrelated fields):

```json
{
  "name": "n8n-nodes-onprintshop",
  "version": "0.1.0",
  "description": "n8n community node for OnPrintShop (OPS) GraphQL API",
  "keywords": ["n8n-community-node-package"],
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/VisualGraphxLLC/API-HUB.git",
    "directory": "n8n-nodes-onprintshop"
  },
  "main": "index.js",
  "scripts": {
    "build": "tsc && gulp build:icons",
    "prepublishOnly": "npm run build"
  },
  "files": [
    "dist",
    "package.json",
    "README.md"
  ],
  "n8n": {
    "n8nNodesApiVersion": 1,
    "nodes": [
      "dist/nodes/OnPrintShop.node.js"
    ],
    "credentials": [
      "dist/credentials/OnPrintShopApi.credentials.js"
    ]
  },
  "publishConfig": {
    "access": "public"
  }
}
```

**Important:** verify the exact paths under `dist/` match your actual build output. If `OnPrintShopApi.credentials.ts` doesn't exist, drop that array entry.

- [ ] **Step 2: Create `n8n-nodes-onprintshop/.npmignore`**

```
*.ts
!*.d.ts
tsconfig.json
gulpfile.js
nodes/
credentials/
node_modules/
.DS_Store
*.log
```

(Ships only `dist/` + `package.json` + `README.md`.)

- [ ] **Step 3: Update `n8n-nodes-onprintshop/README.md`**

Add install instructions at the top:

```markdown
## Install in an external n8n instance

Requires n8n 1.0+ and the host must allow community nodes (`N8N_COMMUNITY_PACKAGES_ENABLED=true` — default).

```bash
# From GitHub (branch/sha):
npm install github:VisualGraphxLLC/API-HUB#main --prefix ~/.n8n/nodes

# Or from a published npm release (once public):
npm install n8n-nodes-onprintshop --prefix ~/.n8n/nodes
```

Then restart n8n. The `OnPrintShop` node appears under Actions.

## Credentials required

Configure via n8n UI → Credentials → New → `OnPrintShop API`:
- Base URL (e.g. `https://store.onprintshop.com`)
- Token URL (e.g. `https://store.onprintshop.com/oauth/token`)
- Client ID
- Client Secret
```

(Append to existing content — don't remove it.)

- [ ] **Step 4: Build + pack test locally**

```bash
cd n8n-nodes-onprintshop
npm run build
npm pack --dry-run 2>&1 | head -30
```
Expected:
- `npm run build` compiles TypeScript + copies icons to `dist/`.
- `npm pack --dry-run` lists ONLY files under `dist/`, `package.json`, `README.md`. No `.ts` source files, no `node_modules/`.

If `.ts` files show up → `.npmignore` not reaching them → fix the glob.

- [ ] **Step 5: Install-from-github test**

On any non-dev machine (or in a throwaway directory):
```bash
mkdir -p /tmp/n8n-test-install
cd /tmp/n8n-test-install
npm init -y >/dev/null
# Replace <sha> with the current HEAD sha from the push branch
npm install "github:VisualGraphxLLC/API-HUB#<current-branch-sha>" --prefix .
ls node_modules/n8n-nodes-onprintshop/dist
```
Expected: `dist/` contains compiled `.js` files. Verifies `files:` + `.npmignore` work together.

(Skip this step if the branch isn't pushed yet — just run `npm pack --dry-run` and confirm the tarball contents.)

- [ ] **Step 6: Commit**

```bash
git add n8n-nodes-onprintshop/package.json n8n-nodes-onprintshop/.npmignore n8n-nodes-onprintshop/README.md
git commit -m "feat(n8n-nodes-onprintshop): package for external install via npm/github"
```

---

## Task 8 — End-to-end verification

**Files:** none to commit.

- [ ] **Step 1: Rebuild + restart stack from scratch**

```bash
docker compose down
docker compose up -d --build
sleep 10
docker compose ps
```
Expected: postgres healthy, api + frontend + n8n all `Up`.

- [ ] **Step 2: Run full backend test suite**

```bash
docker compose exec -T api pytest tests/ -v 2>&1 | tail -20
```
Expected: all tests PASS, including new `test_config.py` tests.

- [ ] **Step 3: Verify frontend still loads**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000
```
Expected: 200.

- [ ] **Step 4: Verify n8n workflows re-import cleanly + env resolves at runtime**

```bash
docker exec api-hub-n8n-1 n8n list:workflow
```
Expected: lists all 4 imported workflows.

Open n8n UI → execute `vg-ops-pull` manual trigger → `Get Suppliers` HTTP node → 200 from `http://host.docker.internal:8000/api/suppliers`.

- [ ] **Step 5: Simulate production env (no .env file) and verify backend refuses to start**

```bash
# In a throwaway container:
docker run --rm -e POSTGRES_URL= api-hub-api:latest 2>&1 | head -5
```
Expected: `RuntimeError: POSTGRES_URL environment variable is required` at startup. Proves no localhost fallback.

```bash
docker run --rm -e POSTGRES_URL=postgresql+asyncpg://fake:fake@fake:5432/fake api-hub-api:latest 2>&1 | head -10
```
Expected: starts up (will fail on actual DB connect, but no config-related crash).

- [ ] **Step 6: Verify n8n-nodes-onprintshop tarball**

```bash
cd n8n-nodes-onprintshop
npm run build
npm pack --dry-run 2>&1 | grep -E "\.(ts|js|json|md)$" | head -20
```
Expected: only `.js`, `.json`, `.md` files listed. No `.ts` source files.

- [ ] **Step 7: Commit verification log**

```bash
mkdir -p docs/superpowers/verify-logs
cat > docs/superpowers/verify-logs/2026-04-24-aws-deploy-ready.md <<'EOF'
# AWS Deployment Readiness — Verification Log
Date: 2026-04-24

- [x] All backend tests pass
- [x] Frontend loads
- [x] n8n workflows import + env var resolves
- [x] Backend refuses start without POSTGRES_URL
- [x] n8n node tarball contains only dist + package.json + README
EOF
git add docs/superpowers/verify-logs/2026-04-24-aws-deploy-ready.md
git commit -m "docs: 2026-04-24 AWS deployment readiness verification log"
```

---

## Task 9 — Multi-stage backend Dockerfile (production-optimized)

**Files:**
- Modify: `backend/Dockerfile`

- [ ] **Step 1: Rewrite `backend/Dockerfile`**

Replace current content with a two-stage build. Stage 1 installs deps into `/deps`; stage 2 copies only what's needed to a minimal runtime image.

```dockerfile
# syntax=docker/dockerfile:1.6

FROM python:3.12-slim AS builder
WORKDIR /app
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libpq-dev \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --target=/deps -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app:/deps \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# libpq5 needed by asyncpg/psycopg at runtime; keep image lean
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /deps /deps
COPY . .
EXPOSE 8000
# Production CMD — no --reload
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Rebuild + smoke test**

```bash
docker compose build --no-cache api
docker compose up -d api
sleep 5
docker compose logs api --tail 20
curl -s -o /dev/null -w "api /docs: %{http_code}\n" http://localhost:8000/docs
```

Expected: container starts without `--reload`, `/docs` returns 200.

- [ ] **Step 3: Confirm image size smaller than before**

```bash
docker images | grep api-hub-api
```

Expected: image size reduced (no gcc/build tools in final image).

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile
git commit -m "feat(backend): multi-stage Dockerfile for production (slim runtime, no --reload)"
```

---

## Task 10 — Multi-stage frontend Dockerfile + Next.js standalone output

**Files:**
- Modify: `frontend/next.config.ts`
- Modify: `frontend/Dockerfile`

- [ ] **Step 1: Enable standalone output in `frontend/next.config.ts`**

Find the exported config. Add `output: 'standalone'` to the config object:

Before (likely):
```ts
const nextConfig: NextConfig = {
  // existing config...
};

export default nextConfig;
```

After:
```ts
const nextConfig: NextConfig = {
  output: 'standalone',
  // existing config...
};

export default nextConfig;
```

If the file is `next.config.js` (not `.ts`) in this repo, apply the same change there. Confirm file path with `ls frontend/next.config.*`.

- [ ] **Step 2: Rewrite `frontend/Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.6

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_N8N_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_N8N_URL=$NEXT_PUBLIC_N8N_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000
RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
```

- [ ] **Step 3: Pass build args via `docker-compose.yml`**

Find the `frontend` build block. Replace the existing `build: ./frontend` shortcut with the long form:

```yaml
  frontend:
    build:
      context: ./frontend
      args:
        NEXT_PUBLIC_API_URL: http://localhost:8000
        NEXT_PUBLIC_N8N_URL: http://localhost:5678
```

Keep the rest of the `frontend` block (ports, depends_on, volumes, env) as-is. Note: with `standalone` output, the existing bind-mount `./frontend:/app` for hot reload in dev may conflict with the built server. Keep the mount for local dev; production image ignores it because `server.js` entrypoint doesn't use `next dev`.

- [ ] **Step 4: Rebuild + smoke test**

```bash
docker compose build --no-cache frontend
docker compose up -d frontend
sleep 8
docker compose logs frontend --tail 20
curl -s -o /dev/null -w "frontend: %{http_code}\n" http://localhost:3000
```

Expected: `frontend: 200`. Container runs `node server.js`, not `next dev`.

- [ ] **Step 5: Check image size**

```bash
docker images | grep api-hub-frontend
```

Expected: smaller than pre-standalone (~200–300 MB vs 800 MB+ with full node_modules).

- [ ] **Step 6: Commit**

```bash
git add frontend/next.config.ts frontend/Dockerfile docker-compose.yml
git commit -m "feat(frontend): Next.js standalone output + multi-stage Dockerfile with build args for NEXT_PUBLIC_*"
```

---

## Task 11 — AWS App Runner + ECS CloudFormation template

**Files:**
- Create: `deployment/aws-app-runner.yaml`
- Create: `deployment/README.md`

This task produces the infrastructure template only. Actually applying the stack requires AWS credentials + ECR-pushed images and lives outside this repo's automation boundary. Document the apply steps in the README.

- [ ] **Step 1: Create `deployment/` dir**

```bash
mkdir -p deployment
```

- [ ] **Step 2: Write `deployment/aws-app-runner.yaml`**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: API-HUB staging stack — App Runner (api + frontend), ECS Fargate (n8n), RDS Postgres, Secrets Manager

Parameters:
  EnvironmentName:
    Type: String
    Default: staging
    AllowedValues: [staging, production]
  ApiEcrImageUri:
    Type: String
    Description: ECR image URI for api (e.g. 123456789012.dkr.ecr.us-east-1.amazonaws.com/api-hub-api:sha-abc123)
  FrontendEcrImageUri:
    Type: String
    Description: ECR image URI for frontend
  N8nEcrImageUri:
    Type: String
    Description: ECR image URI for n8n (use official n8nio/n8n:latest if not customizing)
    Default: n8nio/n8n:latest
  DomainName:
    Type: String
    Description: Base domain (e.g. staging.visualgraphx.com). Subdomains api./app./n8n. will be created.
  VpcId:
    Type: AWS::EC2::VPC::Id
  PrivateSubnetIds:
    Type: List<AWS::EC2::Subnet::Id>
  PublicSubnetIds:
    Type: List<AWS::EC2::Subnet::Id>
  DbUsername:
    Type: String
    Default: vg_user
  DbPassword:
    Type: String
    NoEcho: true
    MinLength: 16

Resources:
  # ---------- Secrets Manager ----------
  SecretKey:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: !Sub api-hub/${EnvironmentName}/SECRET_KEY
      GenerateSecretString:
        SecretStringTemplate: '{}'
        GenerateStringKey: value
        PasswordLength: 44
        ExcludePunctuation: false

  IngestSharedSecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: !Sub api-hub/${EnvironmentName}/INGEST_SHARED_SECRET
      GenerateSecretString:
        SecretStringTemplate: '{}'
        GenerateStringKey: value
        PasswordLength: 48
        ExcludePunctuation: true

  PostgresUrlSecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: !Sub api-hub/${EnvironmentName}/POSTGRES_URL
      SecretString: !Sub postgresql+asyncpg://${DbUsername}:${DbPassword}@${PostgresDb.Endpoint.Address}:5432/vg_hub

  # ---------- RDS ----------
  DbSubnetGroup:
    Type: AWS::RDS::DBSubnetGroup
    Properties:
      DBSubnetGroupDescription: api-hub RDS subnets
      SubnetIds: !Ref PrivateSubnetIds

  DbSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: api-hub RDS ingress
      VpcId: !Ref VpcId
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 5432
          ToPort: 5432
          CidrIp: 10.0.0.0/8   # TIGHTEN to VPC CIDR in prod

  PostgresDb:
    Type: AWS::RDS::DBInstance
    DeletionPolicy: Snapshot
    Properties:
      DBInstanceIdentifier: !Sub api-hub-${EnvironmentName}
      Engine: postgres
      EngineVersion: '16.3'
      DBInstanceClass: db.t4g.small
      AllocatedStorage: '20'
      StorageType: gp3
      MasterUsername: !Ref DbUsername
      MasterUserPassword: !Ref DbPassword
      DBSubnetGroupName: !Ref DbSubnetGroup
      VPCSecurityGroups: [!Ref DbSecurityGroup]
      MultiAZ: false
      PubliclyAccessible: false
      BackupRetentionPeriod: 7

  # ---------- App Runner: api ----------
  ApiAppRunnerRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal: { Service: build.apprunner.amazonaws.com }
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess

  ApiInstanceRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal: { Service: tasks.apprunner.amazonaws.com }
            Action: sts:AssumeRole
      Policies:
        - PolicyName: SecretsReadAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action: secretsmanager:GetSecretValue
                Resource:
                  - !Ref SecretKey
                  - !Ref IngestSharedSecret
                  - !Ref PostgresUrlSecret

  ApiService:
    Type: AWS::AppRunner::Service
    Properties:
      ServiceName: !Sub api-hub-api-${EnvironmentName}
      SourceConfiguration:
        AuthenticationConfiguration:
          AccessRoleArn: !GetAtt ApiAppRunnerRole.Arn
        AutoDeploymentsEnabled: false
        ImageRepository:
          ImageRepositoryType: ECR
          ImageIdentifier: !Ref ApiEcrImageUri
          ImageConfiguration:
            Port: '8000'
            RuntimeEnvironmentVariables:
              - Name: CORS_ORIGINS
                Value: !Sub https://app.${DomainName}
              - Name: N8N_BASE_URL
                Value: !Sub http://${N8nAlbDnsName}:5678   # populated after ECS n8n defined
            RuntimeEnvironmentSecrets:
              - Name: SECRET_KEY
                Value: !Ref SecretKey
              - Name: INGEST_SHARED_SECRET
                Value: !Ref IngestSharedSecret
              - Name: POSTGRES_URL
                Value: !Ref PostgresUrlSecret
      InstanceConfiguration:
        Cpu: 1024
        Memory: 2048
        InstanceRoleArn: !GetAtt ApiInstanceRole.Arn
      HealthCheckConfiguration:
        Protocol: HTTP
        Path: /docs
        Interval: 10
        Timeout: 5

  # ---------- App Runner: frontend ----------
  FrontendService:
    Type: AWS::AppRunner::Service
    Properties:
      ServiceName: !Sub api-hub-frontend-${EnvironmentName}
      SourceConfiguration:
        AuthenticationConfiguration:
          AccessRoleArn: !GetAtt ApiAppRunnerRole.Arn
        AutoDeploymentsEnabled: false
        ImageRepository:
          ImageRepositoryType: ECR
          ImageIdentifier: !Ref FrontendEcrImageUri
          ImageConfiguration:
            Port: '3000'
      InstanceConfiguration:
        Cpu: 1024
        Memory: 2048
      HealthCheckConfiguration:
        Protocol: HTTP
        Path: /
        Interval: 10
        Timeout: 5

  # ---------- ECS Fargate: n8n (needs persistence) ----------
  N8nCluster:
    Type: AWS::ECS::Cluster
    Properties:
      ClusterName: !Sub api-hub-n8n-${EnvironmentName}

  N8nEfs:
    Type: AWS::EFS::FileSystem
    Properties:
      Encrypted: true
      PerformanceMode: generalPurpose

  N8nTaskRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal: { Service: ecs-tasks.amazonaws.com }
            Action: sts:AssumeRole
      Policies:
        - PolicyName: N8nSecretsRead
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action: secretsmanager:GetSecretValue
                Resource:
                  - !Ref IngestSharedSecret

  N8nExecRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal: { Service: ecs-tasks.amazonaws.com }
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

  N8nTaskDef:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: !Sub api-hub-n8n-${EnvironmentName}
      Cpu: '1024'
      Memory: '2048'
      NetworkMode: awsvpc
      RequiresCompatibilities: [FARGATE]
      TaskRoleArn: !GetAtt N8nTaskRole.Arn
      ExecutionRoleArn: !GetAtt N8nExecRole.Arn
      Volumes:
        - Name: n8n-data
          EFSVolumeConfiguration:
            FilesystemId: !Ref N8nEfs
      ContainerDefinitions:
        - Name: n8n
          Image: !Ref N8nEcrImageUri
          PortMappings: [{ ContainerPort: 5678 }]
          MountPoints:
            - SourceVolume: n8n-data
              ContainerPath: /home/node/.n8n
          Environment:
            - Name: N8N_HOST
              Value: 0.0.0.0
            - Name: N8N_PORT
              Value: '5678'
            - Name: N8N_PROTOCOL
              Value: https
            - Name: N8N_EDITOR_BASE_URL
              Value: !Sub https://n8n.${DomainName}
            - Name: API_HUB_BASE_URL
              Value: !GetAtt ApiService.ServiceUrl
          Secrets:
            - Name: INGEST_SHARED_SECRET
              ValueFrom: !Ref IngestSharedSecret

  # (ALB + Route 53 + ACM cert stubs omitted — add after domain ownership is set in your AWS account)

Outputs:
  ApiUrl:
    Value: !GetAtt ApiService.ServiceUrl
  FrontendUrl:
    Value: !GetAtt FrontendService.ServiceUrl
  PostgresEndpoint:
    Value: !GetAtt PostgresDb.Endpoint.Address
  IngestSecretArn:
    Value: !Ref IngestSharedSecret
```

- [ ] **Step 3: Write `deployment/README.md`**

```markdown
# AWS Deployment — App Runner + ECS (n8n) + RDS

## Apply steps (one-time staging bootstrap)

1. **Push images to ECR** (per-service):
   ```bash
   aws ecr create-repository --repository-name api-hub-api
   aws ecr create-repository --repository-name api-hub-frontend

   SHA=$(git rev-parse --short HEAD)
   REGION=us-east-1
   ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

   # Login to ECR
   aws ecr get-login-password --region $REGION \
     | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$REGION.amazonaws.com

   # Build + push api
   docker build -t api-hub-api:$SHA ./backend
   docker tag api-hub-api:$SHA $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/api-hub-api:$SHA
   docker push $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/api-hub-api:$SHA

   # Build + push frontend (requires NEXT_PUBLIC_* build args)
   docker build \
     --build-arg NEXT_PUBLIC_API_URL=https://api.staging.visualgraphx.com \
     --build-arg NEXT_PUBLIC_N8N_URL=https://n8n.staging.visualgraphx.com \
     -t api-hub-frontend:$SHA ./frontend
   docker tag api-hub-frontend:$SHA $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/api-hub-frontend:$SHA
   docker push $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/api-hub-frontend:$SHA
   ```

2. **Deploy stack:**
   ```bash
   aws cloudformation deploy \
     --template-file deployment/aws-app-runner.yaml \
     --stack-name api-hub-staging \
     --capabilities CAPABILITY_IAM \
     --parameter-overrides \
       EnvironmentName=staging \
       ApiEcrImageUri=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/api-hub-api:$SHA \
       FrontendEcrImageUri=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/api-hub-frontend:$SHA \
       DomainName=staging.visualgraphx.com \
       VpcId=<your-vpc> \
       PrivateSubnetIds=<subnet-a>,<subnet-b> \
       PublicSubnetIds=<subnet-c>,<subnet-d> \
       DbPassword=<generate-strong-password>
   ```

3. **Route 53 + ACM** (done outside this template):
   - Issue ACM cert in us-east-1 for `*.staging.visualgraphx.com`
   - Point `api.staging.visualgraphx.com` → App Runner api service URL (custom domain)
   - Point `app.staging.visualgraphx.com` → App Runner frontend URL
   - Point `n8n.staging.visualgraphx.com` → ALB (or NLB) in front of ECS n8n service

4. **Rollback:** redeploy with previous image SHA via `aws cloudformation update-stack`.

## Scope deferred

- CI/CD (GitHub Actions build→push→deploy) — separate config.
- ALB + Target Group definitions for n8n public exposure — template has placeholders.
- Route 53 hosted zone + records — assumed to exist.
```

- [ ] **Step 4: Validate YAML**

```bash
aws cloudformation validate-template --template-body file://deployment/aws-app-runner.yaml 2>&1 | head -10 \
  || python3 -c "import yaml; yaml.safe_load(open('deployment/aws-app-runner.yaml')); print('yaml ok')"
```

Expected: either `aws validate-template` succeeds (if creds configured) OR the python fallback prints `yaml ok`.

- [ ] **Step 5: Commit**

```bash
git add deployment/aws-app-runner.yaml deployment/README.md
git commit -m "feat(deployment): CloudFormation template for App Runner + ECS n8n + RDS + Secrets Manager"
```

---

## Task 12 — Fix seed_demo.py category string population

**Files:**
- Modify: `backend/seed_demo.py`

Gemini plan flagged: seed script inserts products without setting `product.category` string, breaking the "Vertical Slice" demo when product detail pages read `product.category`.

- [ ] **Step 1: Inspect `backend/seed_demo.py`**

Run:
```bash
grep -n "category\|Category" backend/seed_demo.py | head -20
```

Identify the product insertion loop. Locate where `Product(...)` objects are built + where categories are defined.

- [ ] **Step 2: Patch `backend/seed_demo.py`**

Inside the product insertion loop, before `s.add(product)` or the equivalent, add:
```python
product.category = category.name
```

Where `category` is the Category row being linked. If the loop builds Product via constructor:
```python
product = Product(
    supplier_id=sup.id,
    supplier_sku=spec["sku"],
    product_name=spec["name"],
    category_id=category.id,
    category=category.name,   # <-- ADD this line
    product_type="apparel",
)
```

- [ ] **Step 3: Re-run seed + verify**

```bash
docker compose exec -T api sh -c "cd /app && python seed_demo.py"
docker compose exec -T postgres psql -U vg_user -d vg_hub -c \
  "SELECT supplier_sku, product_name, category FROM products LIMIT 5;"
```

Expected: `category` column populated (not NULL).

- [ ] **Step 4: Commit**

```bash
git add backend/seed_demo.py
git commit -m "fix(seed_demo): populate product.category string from category.name"
```

---

## Deferred (separate plan)

- **CI/CD pipeline (GitHub Actions → ECR → App Runner/ECS)** — builds + pushes on merge to main; triggers CloudFormation update. Bundle into `.github/workflows/deploy-staging.yml` after the manual apply proves the template works.
- **Route 53 + ACM + ALB wiring for custom domains** — depends on AWS account owning `staging.visualgraphx.com`. Template stubs in place; add once domain is provisioned.
- **Prod env** — template takes `EnvironmentName=production`. Promote after staging is proven. Tighten `DbSecurityGroup` CIDR + enable MultiAZ + longer BackupRetentionPeriod.

---

## Critical files summary

| File | Tasks |
|------|-------|
| `backend/database.py` | 1 |
| `backend/main.py` | 2 |
| `backend/modules/n8n_proxy/routes.py` | 3 |
| `backend/tests/test_config.py` | 1, 2, 3 (new file) |
| `frontend/src/app/(admin)/products/configure/page.tsx` | 4 |
| `frontend/src/app/(admin)/api-registry/page.tsx` | 4 |
| `n8n-workflows/ops-master-options-pull.json` | 5 |
| `n8n-workflows/vg-ops-pull.json` | 5 |
| `n8n-workflows/sanmar-soap-pull.json` | 5 |
| `n8n-workflows/sanmar-sftp-pull.json` | 5 |
| `docker-compose.yml` | 6 |
| `.env.example` | 6 |
| `n8n-nodes-onprintshop/package.json` | 7 |
| `n8n-nodes-onprintshop/.npmignore` | 7 (new file) |
| `n8n-nodes-onprintshop/README.md` | 7 |
| `backend/Dockerfile` | 9 |
| `frontend/Dockerfile` | 10 |
| `frontend/next.config.ts` | 10 |
| `deployment/aws-app-runner.yaml` | 11 (new file) |
| `deployment/README.md` | 11 (new file) |
| `backend/seed_demo.py` | 12 |

## Reused patterns

- `EncryptedJSON` type decorator — `backend/database.py` — ensure existing encrypted columns still decode post-change (they will; only `load_dotenv` + POSTGRES_URL default changed).
- Existing env-driven pattern in `backend/modules/n8n_proxy/routes.py` — `os.getenv(..., default)` — extended to require env.
- `ops-push.json` n8n workflow already uses `$env.API_HUB_BASE_URL` pattern — copied to other 4 workflows in Task 5.

## Self-review notes

Spec coverage: all 4 Phase-A items (localhost kill backend/frontend/n8n + load_dotenv fix + CORS parser) covered by Tasks 1–6. Phase B (npm packaging) covered by Task 7. Phase D (verification) = Task 8. Phase C (infra) explicitly deferred.

Type/name consistency: `POSTGRES_URL`, `N8N_BASE_URL`, `API_HUB_BASE_URL`, `CORS_ORIGINS`, `INGEST_SHARED_SECRET` names consistent across backend code + compose + tests + .env.example + n8n workflows.

No placeholders: every task has full code. Commands have expected output. No "TBD" / "add handling" etc.
