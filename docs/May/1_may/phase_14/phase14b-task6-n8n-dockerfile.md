# Phase 14b — Task 6: Custom n8n Dockerfile

**Date:** 2026-05-05
**Branch:** `dev/phase14b-n8n-decouple`
**File created:** `n8n.Dockerfile`
**Status:** Complete (code done — Docker build verification pending)

---

## What We Did

Created `n8n.Dockerfile` at the repo root. It is a two-stage Docker build that compiles the OnPrintShop TypeScript node and bakes it into the official n8n image using `N8N_CUSTOM_EXTENSIONS`.

## The File

```dockerfile
FROM node:20-alpine AS node-build
WORKDIR /build
COPY n8n-nodes-onprintshop/package.json n8n-nodes-onprintshop/package-lock.json ./
RUN npm ci
COPY n8n-nodes-onprintshop ./
RUN npm run build

FROM n8nio/n8n:latest
USER root
RUN mkdir -p /home/node/.n8n/custom \
 && chown -R node:node /home/node/.n8n/custom
COPY --from=node-build --chown=node:node /build/dist /home/node/.n8n/custom/n8n-nodes-onprintshop/dist
COPY --from=node-build --chown=node:node /build/package.json /home/node/.n8n/custom/n8n-nodes-onprintshop/package.json
USER node
ENV N8N_CUSTOM_EXTENSIONS=/home/node/.n8n/custom
```

## How the Two Stages Work

| Stage | Base image | What it does |
|-------|-----------|-------------|
| `node-build` | `node:20-alpine` | `npm ci` installs deps, `npm run build` compiles TypeScript → `dist/` |
| Final | `n8nio/n8n:latest` | Copies compiled `dist/` + `package.json` into `/home/node/.n8n/custom/` |

`N8N_CUSTOM_EXTENSIONS` tells n8n to scan that directory for extra nodes at startup — no volume mounts, no entrypoint scripts needed.

## Why This Replaces the Volume Mount

The old approach in `docker-compose.yml` mounted `./n8n-nodes-onprintshop` into the container and ran a shell script to copy files at startup. This only worked if:
- You had the repo cloned locally
- The `dist/` folder was already compiled

With the Dockerfile approach the image is self-contained and portable — it works in ECS, Render, Fly, n8n.cloud Pro+, or any Docker host without needing the repo on the host machine.

## To Build and Test

```bash
# Build
docker build -f n8n.Dockerfile -t api-hub-n8n:dev .

# Verify OnPrintShop node loads
docker run --rm -p 5679:5678 -e N8N_HOST=0.0.0.0 api-hub-n8n:dev 2>&1 | grep -i onprintshop
```
