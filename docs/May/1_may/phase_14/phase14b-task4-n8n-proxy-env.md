# Phase 14b — Task 4: n8n Proxy Client Reads Env

**Date:** 2026-05-05
**Branch:** `dev/phase14b-n8n-decouple`
**File changed:** `backend/modules/n8n_proxy/routes.py`
**Status:** Complete

---

## What We Did

Updated the `_base()` and `_webhook_base()` helper functions in `n8n_proxy/routes.py` to read the new canonical env var names, with backward-compatible fallbacks and a fail-loud behaviour in production.

## Before

```python
def _base() -> str:
    url = os.getenv("N8N_BASE_URL")
    if not url:
        raise RuntimeError("N8N_BASE_URL environment variable is required...")
    return url.rstrip("/")

def _webhook_base() -> str:
    return os.getenv("N8N_WEBHOOK_BASE", _base()).rstrip("/")
```

**Problems:**
- Only reads `N8N_BASE_URL` — no `N8N_API_BASE_URL` (the new canonical name)
- No dev fallback — raises immediately even in local dev if the var isn't set
- `N8N_WEBHOOK_BASE` is not documented anywhere

## After

```python
def _base() -> str:
    # N8N_API_BASE_URL is the canonical var; N8N_BASE_URL kept for backward compat
    url = os.getenv("N8N_API_BASE_URL") or os.getenv("N8N_BASE_URL")
    if url:
        return url.rstrip("/")
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        raise RuntimeError(
            "N8N_API_BASE_URL must be set in production. ..."
        )
    return "http://n8n:5678"

def _webhook_base() -> str:
    return (os.getenv("N8N_WEBHOOK_BASE_URL") or os.getenv("N8N_WEBHOOK_BASE") or _base()).rstrip("/")
```

## Why

- `N8N_API_BASE_URL` is the standardised name used in `.env.example` and docker-compose (Phase 14b)
- Old `N8N_BASE_URL` still works so existing dev setups don't break
- Dev fallback to `http://n8n:5678` (Compose service DNS) means the var doesn't need to be set locally
- Production fails loud — this is intentional so a misconfigured deploy is caught at startup not at first webhook call
- `N8N_WEBHOOK_BASE_URL` replaces the undocumented `N8N_WEBHOOK_BASE`
