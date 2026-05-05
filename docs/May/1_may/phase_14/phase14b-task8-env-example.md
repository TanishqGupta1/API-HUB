# Phase 14b — Task 8: .env.example Update

**Date:** 2026-05-05
**Branch:** `dev/phase14b-n8n-decouple`
**File changed:** `.env.example`
**Status:** Complete

---

## What We Did

Updated `.env.example` to document all the new n8n inter-service URL variables, remove the `host.docker.internal` reference, and explain which vars are required in production.

## New Section Added

```bash
# ─── n8n / FastAPI INTER-SERVICE URLs ──────────────────────────────────────
# REQUIRED IN PRODUCTION. Backend refuses to boot if these are unset when
# ENVIRONMENT=production (enforced after Phase 14a merges).
# In local dev with Docker Compose the values below are the correct defaults.

# n8n → FastAPI: base URL used by all n8n workflows via $env.API_BASE_URL
API_BASE_URL=http://api:8000

# FastAPI → n8n REST API (workflow listing, trigger-by-id)
N8N_API_BASE_URL=http://n8n:5678

# n8n REST API key — generate from n8n editor → Settings → API
N8N_API_KEY=

# FastAPI → n8n webhooks (used by ops_push and any webhook trigger)
N8N_WEBHOOK_BASE_URL=http://n8n:5678

# Full URL of the OPS push webhook in n8n.
# Example dev:  http://n8n:5678/webhook/vg-ops-push-001
# Example prod: http://n8n.api-hub.local:5678/webhook/vg-ops-push-001
N8N_PUSH_WEBHOOK_URL=
```

## What Changed vs Before

| Before | After |
|--------|-------|
| `API_BASE_URL=` with comment "use `host.docker.internal:8000`" | `API_BASE_URL=http://api:8000` with Compose DNS default |
| No `N8N_API_BASE_URL` | Added with explanation |
| No `N8N_API_KEY` | Added |
| No `N8N_WEBHOOK_BASE_URL` | Added |
| No `N8N_PUSH_WEBHOOK_URL` | Added with examples |

## Why the Defaults Are `http://api:8000` and `http://n8n:5678`

These are Docker Compose service DNS names. They resolve inside the Compose network on all platforms (macOS, Windows, Linux, CI). A new developer can copy `.env.example` to `.env` and `docker compose up` will work immediately without any manual URL editing.
