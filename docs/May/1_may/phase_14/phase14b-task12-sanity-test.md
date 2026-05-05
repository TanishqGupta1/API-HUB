# Phase 14b — Task 12: Full Stack Sanity Test

**Date:** 2026-05-05
**Branch:** `Vidhi`
**Status:** Complete ✅

---

## What We Did

Ran a full-stack integration sanity check after all Phase 14b code changes were in place. This validated that:
1. All Docker images build cleanly with the new configuration
2. All four services start and respond correctly
3. The OnPrintShop node is properly baked into the n8n image (not volume-mounted)
4. No `host.docker.internal` references remain in live code

---

## Bug Found and Fixed During This Task

### Dockerfile path shadowed by volume mount

**Problem:** The original `n8n.Dockerfile` copied the OnPrintShop node to `/home/node/.n8n/custom/`. The `docker-compose.yml` mounts `n8n_data:/home/node/.n8n` — which completely shadows the `custom/` directory baked into the image. On a fresh install the node would be missing.

**Root cause:** `N8N_CUSTOM_EXTENSIONS` was set to `/home/node/.n8n/custom`, inside the volume mount point.

**Fix:** Changed Dockerfile to use `/opt/custom-nodes` (outside the volume):

```dockerfile
# Before
RUN mkdir -p /home/node/.n8n/custom ...
COPY ... /home/node/.n8n/custom/n8n-nodes-onprintshop/...
ENV N8N_CUSTOM_EXTENSIONS=/home/node/.n8n/custom

# After
RUN mkdir -p /opt/custom-nodes/n8n-nodes-onprintshop ...
COPY ... /opt/custom-nodes/n8n-nodes-onprintshop/...
ENV N8N_CUSTOM_EXTENSIONS=/opt/custom-nodes
```

---

## Verification Results

### Build
```
docker compose --profile dev build --no-cache
```
| Image | Result |
|-------|--------|
| `api-hub-n8n:dev` | ✅ Built |
| `api_hub_send-api` | ✅ Built |
| `api_hub_send-frontend` | ✅ Built |

### Service startup
```
docker compose --profile dev up -d
```
All 4 services running:
- `api_hub_send-postgres-1` — Up (healthy)
- `api_hub_send-api-1` — Up
- `api_hub_send-n8n-1` — Up (image: `api-hub-n8n:dev`)
- `api_hub_send-frontend-1` — Up

### Health endpoints
| Endpoint | Response |
|----------|----------|
| `GET http://127.0.0.1:8000/health` | `{"status":"ok","service":"api-hub"}` ✅ |
| `GET http://127.0.0.1:3000` | HTTP 200 ✅ |
| `GET http://127.0.0.1:5678` | HTTP 200 ✅ |

### OnPrintShop node in n8n image
```
docker exec api_hub_send-n8n-1 printenv N8N_CUSTOM_EXTENSIONS
# /opt/custom-nodes

docker exec api_hub_send-n8n-1 ls /opt/custom-nodes/n8n-nodes-onprintshop/dist/nodes/OnPrintShop/
# GenericFunctions.d.ts  GenericFunctions.js  descriptions  execute  graphql  types.d.ts  types.js
```
✅ Node present at `/opt/custom-nodes` — outside the `n8n_data` volume mount

### host.docker.internal scan
```
grep -r "host.docker.internal" ... --include="*.py" --include="*.yml" --include="*.ts" ...
```
✅ Zero matches in live code — only in historical docs/plans (expected)

---

## Commands Used

```bash
# Build
docker compose --profile dev build --no-cache

# Start
docker compose --profile dev up -d

# Verify endpoints
curl -fsS http://127.0.0.1:8000/health
curl -fsSI http://127.0.0.1:3000 | head -3
curl -fsSI http://127.0.0.1:5678 | head -3

# Verify node
docker exec api_hub_send-n8n-1 printenv N8N_CUSTOM_EXTENSIONS
docker exec api_hub_send-n8n-1 ls /opt/custom-nodes/n8n-nodes-onprintshop/dist/nodes/OnPrintShop/

# Scan for host.docker.internal
grep -r "host.docker.internal" . --include="*.py" --include="*.yml" -l

# Tear down
docker compose --profile dev down
```
