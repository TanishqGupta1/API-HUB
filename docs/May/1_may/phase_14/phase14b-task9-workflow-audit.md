# Phase 14b — Task 9: n8n Workflow JSON Audit

**Date:** 2026-05-05
**Branch:** `dev/phase14b-n8n-decouple`
**Files checked:** `n8n-workflows/*.json`, `n8n-workflows/README.md`
**Status:** Complete

---

## What We Did

Audited all n8n workflow JSON files for hardcoded URLs and found they were already clean. Fixed one stale reference in the README.

## Audit Result

```bash
grep -rn "host.docker.internal\|http://n8n:\|http://localhost\|http://127.0.0.1" n8n-workflows/
```

**Result:** No hits in any `.json` file. All 9 workflow JSON files already use `{{ $env.API_BASE_URL }}` for every backend call.

## Only Fix Needed — README.md

`n8n-workflows/README.md` had a stale comment:

```
- **macOS/Windows Docker Desktop (default):** `http://host.docker.internal:8000`
- **Linux / all-Docker stack:** `http://api:8000`
```

**Replaced with:**

```
- **Docker Compose (all platforms):** `http://api:8000` (Compose service DNS — set in docker-compose.yml)
- **Production:** your public or internal API hostname (set `API_BASE_URL` in task definition / `.env`)
```

## Why the JSON Files Were Already Clean

The workflow JSONs use n8n's `{{ $env.VARIABLE_NAME }}` expression syntax which reads from the n8n container's environment at execution time. This was implemented correctly from the start. The `API_BASE_URL` env var is now set via `docker-compose.yml` with proper Compose-DNS defaults instead of `host.docker.internal`.
