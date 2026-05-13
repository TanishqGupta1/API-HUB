# Stage 3: n8n Backend Reference Enumeration

## Objective
Enumerate every n8n reference in `/api-hub/backend/` Python code to size the "remove n8n from backend" PR exactly.

## Scope
Backend code only: `/backend/` (skip frontend, n8n-workflows/, n8n-nodes-onprintshop/, n8n.Dockerfile).

## Search Strategy
- Token matches: "n8n" (case-insensitive)
- Environment variables: N8N_API_BASE_URL, N8N_WEBHOOK_BASE_URL, N8N_PUSH_WEBHOOK_URL, N8N_API_KEY, N8N_BASE_URL
- Function/module names: trigger_n8n_push, n8n_proxy, trigger_workflow_by_id, etc.
- Route paths: /api/n8n
- Docstrings/comments describing n8n behavior

## Comprehensive Reference Table

| File | Line | Kind | Snippet | Classification | Notes |
|------|------|------|---------|-----------------|-------|
| **main.py** | 35 | import | `from modules.n8n_proxy.routes import router as n8n_proxy_router` | **DELETE** | Router import — delete line |
| main.py | 55 | env-var | `"N8N_WEBHOOK_BASE_URL"` in _PROD_REQUIRED_ENV_VARS tuple | **DELETE** | Remove from required env vars list (line 49-57) |
| main.py | 189 | import-cleanup | `from modules.n8n_proxy import routes as _n8n_proxy` | **DELETE** | Lifespan cleanup import (lines 189-191) |
| main.py | 190 | function-call | `if _n8n_proxy._http_client is not None:` | **DELETE** | HTTP client cleanup code |
| main.py | 191 | function-call | `await _n8n_proxy._http_client.aclose()` | **DELETE** | HTTP client cleanup code |
| main.py | 234 | router-register | `app.include_router(n8n_proxy_router, dependencies=_auth)` | **DELETE** | Router registration — delete line |
| **modules/n8n_proxy/routes.py** | 1-172 | module-entire | Entire file: proxy endpoints for n8n | **DELETE** | **Entire file (172 LOC)** — no dependencies outside this module |
| **modules/n8n_proxy/__init__.py** | N/A | module-entire | Empty module | **DELETE** | Can delete entire directory `modules/n8n_proxy/` |
| **modules/ops_push/service.py** | 24 | function-def | `async def trigger_n8n_push(payload: dict[str, Any]) -> None:` | **DELETE** | Function definition (lines 24-37, 14 LOC) |
| modules/ops_push/service.py | 25 | docstring | `"""POST payload to N8N_PUSH_WEBHOOK_URL...` | **DELETE** | Docstring explaining n8n push |
| modules/ops_push/service.py | 30 | env-read | `webhook_url = os.getenv("N8N_PUSH_WEBHOOK_URL", "").strip()` | **DELETE** | Env var read (lines 30-34, 5 LOC — error check) |
| modules/ops_push/service.py | 33 | error-check | `raise RuntimeError("N8N_PUSH_WEBHOOK_URL is required in production")` | **DELETE** | Env var validation |
| modules/ops_push/service.py | 120-123 | function-call | `await trigger_n8n_push({...})` | **DELETE** | Call to trigger_n8n_push (lines 120-134, 15 LOC) — will be REPLACED with direct OPS API call |
| modules/ops_push/service.py | 102 | comment | `# In production, n8n owns the actual OPS API call.` | **RENAME** | Update comment — "FastAPI now owns the OPS API call" |
| modules/ops_push/service.py | 113 | comment | `# Real ID will be back-filled by n8n callback.` | **RENAME** | Update comment — "Real ID will be set synchronously" |
| modules/ops_push/service.py | 139 | response-msg | `"Product payload prepared and queued for n8n push."` | **RENAME** | Update message — "Product pushed to OPS" |
| modules/ops_push/service.py | 144 | error-msg | `f"n8n trigger failed: {e}"` | **RENAME** | Update error — "OPS push failed" |
| **modules/master_options/routes.py** | 11 | import | `from modules.n8n_proxy.routes import trigger_workflow_by_id` | **DELETE** | Import removed function (lines 11 & 131-132) |
| modules/master_options/routes.py | 126 | docstring | `"""Trigger the n8n master options pull workflow."""` | **RENAME** | Update docstring — describe manual trigger behavior |
| modules/master_options/routes.py | 131 | error-msg | `"Warning: n8n trigger failed ({e})..."` | **RENAME** | Update message — "Please run the master options import manually" |
| modules/master_options/routes.py | 132 | error-msg | `"Please execute workflow '{workflow_id}' manually in n8n."` | **RENAME** | Update message — reference internal task or manual process |
| **modules/markup/routes.py** | 41 | docstring | `n8n calls this before invoking OPS...` | **RENAME** | Update docstring — "This endpoint prepares OPS variants" |
| modules/markup/routes.py | 57 | docstring | `"""Return sizes + prices aligned by index for n8n OPS push loop."""` | **RENAME** | Update docstring — "for OPS mutation loop" |
| **modules/markup/schemas.py** | 67 | comment | `# -------- OPS variant bundle (n8n setProductSize...)..` | **RENAME** | Update comment — remove n8n reference |
| **modules/ops_push/routes.py** | 27 | docstring | `n8n calls this when pushing a product to OPS...` | **RENAME** | Update docstring — "FastAPI calls this when pushing a product to OPS" |
| **modules/promostandards/routes.py** | 3 | docstring | `n8n calls these endpoints to kick off SOAP syncs...` | **RENAME** | Update docstring — "Internal endpoints to kick off SOAP syncs" |
| modules/promostandards/routes.py | 5 | docstring | `as a FastAPI BackgroundTask. n8n polls GET /api/sync_jobs/{job_id}` | **RENAME** | Update docstring — "Caller polls GET /api/sync_jobs/{job_id}" |
| modules/promostandards/routes.py | 140 | comment | `# clear message... until n8n times out.` | **RENAME** | Update comment — remove n8n timeout reference |
| **modules/catalog/ingest.py** | 1 | docstring | `"""Write-side (n8n-facing) catalog endpoints.` | **RENAME** | Update docstring — "Write-side catalog endpoints" |
| **modules/pricing/routes.py** | 13 | comment | `all n8n → FastAPI internal calls.` | **RENAME** | Update comment — remove n8n reference |
| modules/pricing/routes.py | 62 | docstring | `customer. Only n8n workflows should call this.` | **RENAME** | Update docstring — "Only internal workflows should call this" |
| **modules/import_jobs/scheduler.py** | 3 | comment | `NOTE: PR #71 shipped n8n cron workflows...` | **KEEP** | Informational history comment — OK to keep for context |
| modules/import_jobs/scheduler.py | 5 | comment | `job. If those n8n workflows are active...` | **KEEP** | Informational history comment |
| modules/import_jobs/scheduler.py | 49 | comment | `Respects the DISABLE_SCHEDULER env var...` | **KEEP** | References scheduler behavior (not n8n-specific) |
| modules/import_jobs/scheduler.py | 53 | log-msg | `log.info('Import scheduler disabled... (n8n handles cron).')` | **KEEP** | Informational log (not critical) |
| **modules/master_options/schemas.py** | 36 | comment | `# ---- Ingest (for POST... n8n payload) ----` | **KEEP** | Describes payload format (not n8n-specific) |
| **modules/suppliers/demo_seed.py** | 16 | field | `"n8n_credential_id": "PLACEHOLDER_CREDENTIAL_ID"` | **KEEP** | Database schema field — intentional coupling to supplier auth config |
| **modules/suppliers/demo_seed.py** | 19 | comment | `# The n8n workflows treat inactive suppliers as a "gate"...` | **KEEP** | Historical context comment — OK to keep |
| **seed_demo.py** | 63 | field | `"n8n_credential_id": "PLACEHOLDER_CREDENTIAL_ID"` | **KEEP** | Demo data — same as suppliers/demo_seed.py |
| **tests/conftest.py** | 153 | field | `auth_config={"n8n_credential_id": "test", ...}` | **KEEP** | Test fixture — same as seed data |
| **tests/test_n8n_url_config.py** | 14 | test-function | `def test_dev_mode_does_not_require_n8n_urls(...)` | **DELETE** | Entire test file (test_n8n_url_config.py, ~50 LOC) — env var checks no longer needed |
| tests/test_n8n_url_config.py | 21 | test-function | `def test_production_mode_fails_when_n8n_webhook_base_url_missing(...)` | **DELETE** | Test function #2 |
| tests/test_n8n_url_config.py | 41 | test-config | `monkeypatch.setenv("N8N_WEBHOOK_BASE_URL", ...)` | **DELETE** | Test setup |
| tests/test_n8n_url_config.py | 54 | test-config | `monkeypatch.setenv("N8N_WEBHOOK_BASE_URL", ...)` | **DELETE** | Test setup |
| **tests/test_ops_push_failure.py** | 15 | test-function | `async def test_push_product_n8n_failure(...)` | **DELETE** | Entire test function (lines 15-58, ~44 LOC) — tests n8n webhook failure, not relevant post-removal |
| tests/test_ops_push_failure.py | 16 | docstring | `"""Test that n8n webhook failure results...` | **DELETE** | Test docstring |
| tests/test_ops_push_failure.py | 53 | test-config | `monkeypatch.setenv("N8N_PUSH_WEBHOOK_URL", ...)` | **DELETE** | Test setup |
| tests/test_ops_push_failure.py | 58 | assertion | `assert "n8n trigger failed" in result["message"]` | **DELETE** | Test assertion |

## Summary Statistics

### DELETE (Remove entirely)
- **modules/n8n_proxy/routes.py** — 172 LOC (entire file)
- **modules/n8n_proxy/__init__.py** — 0 LOC (empty)
- **modules/ops_push/service.py** — 37 LOC (trigger_n8n_push function + call site)
- **main.py** — 6 LOC (import + router registration + lifespan cleanup)
- **modules/master_options/routes.py** — 2 LOC (import statement)
- **tests/test_n8n_url_config.py** — ~50 LOC (entire file)
- **tests/test_ops_push_failure.py** — ~44 LOC (one test function)

**Total DELETE: ~311 LOC**

### RENAME (Update docstrings/comments)
- **modules/ops_push/service.py** — 4 lines (3 comments, 1 error message)
- **modules/master_options/routes.py** — 2 lines (2 error messages)
- **modules/markup/routes.py** — 2 lines (2 docstrings)
- **modules/markup/schemas.py** — 1 line (1 comment)
- **modules/ops_push/routes.py** — 1 line (1 docstring)
- **modules/promostandards/routes.py** — 3 lines (3 docstring/comment)
- **modules/catalog/ingest.py** — 1 line (1 docstring)
- **modules/pricing/routes.py** — 2 lines (2 docstrings)

**Total RENAME: ~16 lines (non-functional changes; safe to batch)**

### KEEP (Intentional data fields / informational)
- **modules/suppliers/demo_seed.py** — `n8n_credential_id` field in Supplier schema (intentional)
- **seed_demo.py** — demo seed data
- **tests/conftest.py** — test fixture data
- **modules/import_jobs/scheduler.py** — historical comments (4 lines, OK to keep)
- **modules/suppliers/demo_seed.py** — historical comment (1 line, OK to keep)
- **modules/master_options/schemas.py** — payload description (1 line, OK to keep)

**Total KEEP: ~11 LOC (all safe; no functional impact)**

## Environment Variables Inventory

### Required in Production (before removal)
```
N8N_API_BASE_URL      # Read in: modules/n8n_proxy/routes.py:29 (_base())
N8N_WEBHOOK_BASE_URL  # Read in: modules/n8n_proxy/routes.py:41 (_webhook_base())
N8N_WEBHOOK_BASE      # Fallback for N8N_WEBHOOK_BASE_URL (backward compat)
N8N_API_KEY           # Read in: modules/n8n_proxy/routes.py:21 (_key())
N8N_PUSH_WEBHOOK_URL  # Read in: modules/ops_push/service.py:30 (trigger_n8n_push)
```

### Required in _PROD_REQUIRED_ENV_VARS (main.py:49-57)
```
N8N_WEBHOOK_BASE_URL  # Line 55 of main.py
```

### Post-Removal Action
After removing n8n backend code:
- **Delete from required env vars tuple** (main.py:49-57)
- **Delete from ECS task definition** (if using ECS)
- **Delete from .env** (if using local .env)
- **Delete from Secrets Manager** (if using AWS)
- **Backend will NOT read any N8N_* env vars after removal**

## Implementation Checklist

- [ ] Delete `modules/n8n_proxy/` directory (entire module, 0 LOC + 172 LOC routes.py)
- [ ] Delete `tests/test_n8n_url_config.py` (~50 LOC)
- [ ] Delete `tests/test_ops_push_failure.py::test_push_product_n8n_failure` (~44 LOC)
- [ ] Remove `trigger_n8n_push()` function from `modules/ops_push/service.py` (37 LOC)
- [ ] Replace n8n webhook call in `modules/ops_push/service.py` with direct OPS GraphQL call (~15 LOC change)
- [ ] Remove n8n_proxy import from `main.py` (1 line)
- [ ] Remove n8n_proxy router registration from `main.py` (1 line)
- [ ] Remove n8n_proxy cleanup from lifespan handler in `main.py` (3 lines)
- [ ] Remove `N8N_WEBHOOK_BASE_URL` from required env vars in `main.py` (1 line change)
- [ ] Remove `trigger_workflow_by_id` import from `modules/master_options/routes.py` (1 line)
- [ ] Replace `trigger_workflow_by_id()` call in `modules/master_options/routes.py` with internal workflow queue or manual note
- [ ] Update docstrings/comments in 8 files (~16 line changes, non-functional)
- [ ] Update tests to reflect new OPS push behavior (add tests for direct OPS call instead of n8n webhook)

## Findings

[FINDING:F3.1] **Total LOC to delete: 311 lines**
- modules/n8n_proxy/ (172) + trigger_n8n_push in ops_push (37) + main.py edits (6) + imports/registrations (5) + test files (~94)

[FINDING:F3.2] **Total docstring/comment renames: ~16 lines**
- Non-functional changes; can batch in same PR or as follow-up cleanup

[FINDING:F3.3] **Kept references: 11 LOC**
- `n8n_credential_id` field remains in Supplier schema (intentional OPS OAuth coupling)
- Historical comments in scheduler and seed code (informational, safe)
- Rationale: These fields represent the supplier's OAuth credential, not n8n-specific logic

[FINDING:F3.4] **Env var inventory**
| Env Var | Read From | Action |
|---------|-----------|--------|
| N8N_API_BASE_URL | modules/n8n_proxy/routes.py:29 | DELETE (n8n_proxy removed) |
| N8N_WEBHOOK_BASE_URL | modules/n8n_proxy/routes.py:41 | DELETE (n8n_proxy removed) + remove from required vars (main.py:55) |
| N8N_WEBHOOK_BASE | modules/n8n_proxy/routes.py:41 (fallback) | DELETE |
| N8N_API_KEY | modules/n8n_proxy/routes.py:21 | DELETE (n8n_proxy removed) |
| N8N_PUSH_WEBHOOK_URL | modules/ops_push/service.py:30 | DELETE (trigger_n8n_push removed) |

**Production deploy impact:**
- Remove all 5 N8N_* env vars from ECS task definition / Secrets Manager
- Remove N8N_WEBHOOK_BASE_URL from required vars check (main.py)
- No other env var changes needed

---

[STAGE_COMPLETE:3]
