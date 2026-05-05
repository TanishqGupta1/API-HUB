# Phase 14b — Task 3: Add n8n URLs to _PROD_REQUIRED_ENV_VARS

**Date:** 2026-05-05
**Branch:** `Vidhi`
**File changed:** `backend/main.py`
**Status:** Complete

---

## What We Did

Extended `_PROD_REQUIRED_ENV_VARS` in `main.py` to include the two n8n inter-service URL variables that are required in production.

## Before

```python
_PROD_REQUIRED_ENV_VARS = (
    "SECRET_KEY",
    "INGEST_SHARED_SECRET",
    "ALLOWED_ORIGINS",
    "POSTGRES_URL",
)
```

## After

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

## Why These Two Vars

| Var | Why Required |
|-----|-------------|
| `N8N_WEBHOOK_BASE_URL` | FastAPI uses this to call n8n webhooks (OPS push trigger). Without it the push pipeline silently does nothing in prod. |
| `API_BASE_URL` | n8n uses this to call FastAPI ingest endpoints. Without it, syncs fail inside n8n workflows. |

## What Happens if They Are Missing in Production

The `_require_prod_env()` function (added in Phase 14a) is called at lifespan startup. If either var is unset when `ENVIRONMENT=production`, the app raises:

```
RuntimeError: Production startup blocked. Missing required env vars:
N8N_WEBHOOK_BASE_URL. Set them in the task definition / ECS secrets / Secrets Manager.
```

This is intentional — a misconfigured deploy fails immediately at startup rather than silently failing at first push/sync hours later.

## Dependency

This task required Phase 14a to be merged first because `_require_prod_env()` and `_PROD_REQUIRED_ENV_VARS` were introduced by Phase 14a. That's why Tasks 2 and 3 were done after the teammate merged Phase 14a.
