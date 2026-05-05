# Phase 14b — Task 11: README n8n Hosting Note

**Date:** 2026-05-05
**Branch:** `dev/phase14b-n8n-decouple`
**File changed:** `README.md`
**Status:** Complete

---

## What We Did

Replaced the old 5-line n8n Setup section in `README.md` with a proper section that explains hosting requirements, supported tiers, and links to the integration contract doc.

## Before

```markdown
## n8n Setup

1. Run n8n: `docker compose up -d n8n` (or use existing instance)
2. Install community nodes: `n8n-nodes-onprintshop` (VisualGraphxLLC)
3. Import workflow JSON from `n8n-workflows/`
4. Point HTTP Request nodes at `http://localhost:8000`
5. Configure OnPrintShop credentials per customer via the Customers UI
```

## After

```markdown
## n8n Setup

API-HUB delegates outbound integrations (OPS push, scheduled syncs) to n8n.
The OnPrintShop node is a custom community node baked into our `n8n.Dockerfile`.

**Supported n8n hosts:**
- Self-hosted Docker — `docker build -f n8n.Dockerfile -t api-hub-n8n:latest .`
- ECS Fargate (Phase 14d)
- n8n.cloud Pro+ (manual community-node install)
- Render, Fly, Railway, Hetzner — anywhere Docker runs

**Not supported:** n8n.cloud Starter — community nodes are blocked on that tier.

**Quick start (local dev):**
1. `docker compose --profile dev up -d`
2. Import workflow JSONs from `n8n-workflows/`
3. Set `INGEST_SHARED_SECRET` and `API_BASE_URL` in `.env`
4. Configure OnPrintShop credentials per customer via the Customers UI

See [docs/n8n-integration.md](docs/n8n-integration.md) for the full integration contract.
```

## Why

- The old section told developers to "point HTTP Request nodes at `http://localhost:8000`" — this is wrong, workflows use `$env.API_BASE_URL`
- There was no mention of the custom Dockerfile or what it does
- n8n.cloud Starter being unsupported is a common gotcha — explicitly calling it out saves a support question
- Linking to `docs/n8n-integration.md` gives developers a single place to understand the full setup
