# Phase 14b — Task 1: URL Inventory

**Date:** 2026-05-05
**Branch:** `dev/phase14b-n8n-decouple`
**Status:** Complete

---

## What We Did

Audited the entire codebase for every place that hardcodes n8n or backend URLs, so we know exactly what needs to change before touching any code.

## Command Run

```bash
grep -rn "host.docker.internal\|http://n8n:5678\|N8N_BASE_URL\|N8N_WEBHOOK\|API_BASE_URL" \
  backend/ docker-compose.yml .env.example n8n-workflows/
```

## What We Found

| Location | Issue |
|----------|-------|
| `backend/scripts/ingest_ops_master_options.py:13` | `API_BASE_URL` falls back to `http://localhost:8000` — wrong inside Docker |
| `backend/modules/n8n_proxy/routes.py:28` | Reads `N8N_BASE_URL` — old var name, no dev fallback |
| `docker-compose.yml:27` | `N8N_BASE_URL=http://n8n:5678` — hardcoded, not env-driven |
| `docker-compose.yml:47` | `API_BASE_URL=${API_BASE_URL:-http://host.docker.internal:8000}` — `host.docker.internal` doesn't work on Linux |
| `.env.example:24` | Comment mentions `host.docker.internal` as the default |
| `n8n-workflows/README.md:78` | Doc says `host.docker.internal:8000` is the default |

## What Was Already Clean

All `n8n-workflows/*.json` files already use `{{ $env.API_BASE_URL }}` — no hardcoded URLs in any workflow JSON. Task 9 only needed a README fix.

## Why This Matters

`host.docker.internal` works on macOS and Windows Docker Desktop but silently fails on Linux (bare metal, ECS, CI). Using it as a default means the stack works locally for some developers but breaks in production and on Linux CI runners. The fix is to use Docker Compose service DNS (`http://api:8000`, `http://n8n:5678`) which works everywhere inside Compose networks.
