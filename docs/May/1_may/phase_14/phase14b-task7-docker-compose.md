# Phase 14b — Task 7: docker-compose URL Cleanup

**Date:** 2026-05-05
**Branch:** `dev/phase14b-n8n-decouple`
**File changed:** `docker-compose.yml`
**Status:** Complete

---

## What We Did

Replaced hardcoded and `host.docker.internal` URL defaults in `docker-compose.yml` with proper env-var-driven values using Docker Compose service DNS.

## Changes

### api service — before

```yaml
- N8N_BASE_URL=http://n8n:5678
```

### api service — after

```yaml
- N8N_API_BASE_URL=${N8N_API_BASE_URL:-http://n8n:5678}
- N8N_WEBHOOK_BASE_URL=${N8N_WEBHOOK_BASE_URL:-http://n8n:5678}
- N8N_PUSH_WEBHOOK_URL=${N8N_PUSH_WEBHOOK_URL:-}
- API_BASE_URL=${API_BASE_URL:-http://api:8000}
```

### n8n service `API_BASE_URL` — before

```yaml
- API_BASE_URL=${API_BASE_URL:-http://host.docker.internal:8000}
```

### n8n service `API_BASE_URL` — after

```yaml
- API_BASE_URL=${API_BASE_URL:-http://api:8000}
```

## Why

| Old value | Problem |
|-----------|---------|
| `host.docker.internal:8000` | macOS/Windows only — breaks on Linux, ECS, CI |
| `N8N_BASE_URL` | Old var name — not consistent with the new `N8N_API_BASE_URL` |

**Docker Compose service DNS** (`http://api:8000`, `http://n8n:5678`) works on all platforms because it's resolved inside the Docker bridge network — not the host. The `${VAR:-default}` syntax means you can override per-environment by setting the var in `.env` without touching the compose file.

## What the Compose-DNS Fallbacks Mean

In local dev you don't need to set these vars at all — the defaults wire everything up correctly. In production (ECS) the task definition sets the real values and the fallbacks are never used. This gives us one compose file that works for both local dev and acts as documentation for what production needs.
