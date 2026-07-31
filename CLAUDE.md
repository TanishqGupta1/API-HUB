<!-- GRAPHX-CANONICAL-AUTHORITY -->
# GraphX Connect implementation guide

Product decisions live in `GraphXCPI/graphx-docs`; read
`graphx-docs/_CANONICAL-AUTHORITY.md` and `atomic-specs/connect.md`. Root `AGENTS.md` defines the
mandatory safety and runtime boundary. Verify the implementation/status detail below against code.

**This repo is governed by:** `atomic-specs/connect.md`.

This repository is the extracted FastAPI connector service; it is not yet proven wired to the
canonical Platform Connect floor.

> Do not make or defend an architecture decision from a doc in this repo. Escalate to the spec, not to local docs.
<!-- /GRAPHX-CANONICAL-AUTHORITY -->

<!-- GRAPHX-DOCS-FRESHNESS -->
## ⚠️ Docs must stay current — verify against CODE, not docs

**A stale doc is a DEFECT, not a reference.** Before asserting anything is built / unbuilt / done / migrated / blocked, **verify against the actual code** — `git ls-remote` for branches, the schema, the migrations, the tests — **never from a doc.** **Any change that alters build state, architecture, status, or a count MUST update the doc that describes it, in the same commit.** Reconciliation / status / audit docs are DATED + PROVISIONAL (carry date + commit SHA + repo) and are **STALE until re-verified**. Fix stale docs on sight with a dated note — `CORRECTED (YYYY-MM-DD): … verified against <repo>@<sha>`. Every count/status must be reproducible from the code. Full rule: `graphx-docs/_CANONICAL-AUTHORITY.md` -> "Docs must stay current."

> **The code is truth; docs must chase it; a stale doc is a bug you fix, not a source you trust.**
<!-- /GRAPHX-DOCS-FRESHNESS -->

---

# CLAUDE.md / GEMINI.md

This file provides guidance to AI coding agents (like Gemini CLI or Claude Code) when working with code in this repository.

## Project

API-HUB — middleware platform connecting 994+ PromoStandards wholesale suppliers to OnPrintShop (OPS) storefronts. Modular monolith: FastAPI backend + Next.js frontend + PostgreSQL.

CORRECTED (2026-07-21): n8n is dropped as a built tier (DECISIONS-LOG.md, LOCKED 2026-06-30). FastAPI's own Integration Gateway (`modules/integrations/`) + import/inventory schedulers (`modules/import_jobs/scheduler.py`, in-process asyncio + Redis lock) now own sync scheduling and OPS push directly — there is no live n8n orchestration in this repo. The former `n8n_proxy` module, `n8n-workflows/`, and `n8n-nodes-onprintshop/` were moved to `historical/2026-07/` (preserved, not deleted — they capture real logic per `_CANONICAL-AUTHORITY.md`) and are no longer mounted in `main.py`. n8n is at most a future integration *target* (a system Connect could integrate *to*, if a tenant already runs one) per `atomic-specs/connect.md` §4.1 — never a built engine here.

## Commands

### Backend
```bash
# Start PostgreSQL
docker compose up -d postgres

# Run backend (from api-hub/ root)
cd backend && source .venv/bin/activate
uvicorn main:app --reload --port 8000

# Seed demo data (1 supplier, 1 product, 12 variants)
cd backend && source .venv/bin/activate && python seed_demo.py

# Install Python deps
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### Frontend
```bash
cd frontend && npm install && npm run dev    # runs on :3000
cd frontend && npm run build                  # production build
cd frontend && npm run lint                   # ESLint
```

### Full stack (Docker)
```bash
docker compose up -d                          # postgres only
```

## Architecture

**Modular monolith** — NOT microservices. All backend modules live in one FastAPI app. Suppliers are database configuration (protocol adapter pattern), not per-supplier code. Adding a supplier = creating a DB row, not writing code.

**Three systems:**
- `backend/` — FastAPI (Python 3.12). All routes under `/api/`. Async SQLAlchemy + asyncpg. Handles SOAP/REST fetch, normalization, storage, markup rules. Owns its own scheduling (`modules/import_jobs/scheduler.py`, in-process asyncio + Redis lock) and OPS push (`modules/ops_push/` + `modules/integrations/`) directly — no external orchestrator.
- `frontend/` — Next.js 15 (App Router). Blueprint design system (Outfit + Fira Code fonts, paper palette #f2f0ed, blueprint blue #1e4d92, dot-grid). Uses shadcn/ui + Tailwind.
- `historical/2026-07/n8n-nodes-onprintshop/` — the former TypeScript custom n8n node for OnPrintShop GraphQL API. Preserved for reference only (dropped as a built tier, DECISIONS-LOG.md 2026-06-30); not mounted or run.

**Backend module pattern:** Each module in `backend/modules/` has `models.py`, `schemas.py`, `routes.py`, `__init__.py`. Some have `service.py`. Modules: `suppliers`, `catalog`, `customers`, `markup`, `push_log`, `ps_directory`, `sync_jobs`.

**Encryption:** `EncryptedJSON` type decorator in `database.py` — transparently encrypts/decrypts JSONB columns using Fernet (AES-128). Used for `suppliers.auth_config` and `customers.ops_auth_config`. Key from `SECRET_KEY` env var.

**All routers registered in:** `backend/main.py`. Tables auto-created on startup via `Base.metadata.create_all` in the lifespan handler.

## Key Constraints

- **Never create per-supplier services or code.** The system is dynamic — suppliers are DB config with protocol adapters (SOAP/REST), not separate codebases.
- **All credentials via UI, encrypted in DB.** No credential .env files. Use the `EncryptedJSON` column type.
- **VARCHAR for DB type columns, not PG ENUMs.** Pydantic validates at the app layer.
- **Frontend must look professional, not AI-generated.** Use shadcn/ui + Tailwind. Clean, minimal, functional. No decorative gradients or generic hero sections. Follow the Blueprint design system in `globals.css`.
- **Never add Co-Authored-By lines to git commits.**
- **PostgreSQL upserts** — use `ON CONFLICT DO UPDATE` for all sync operations.

## Environment

`.env` at repo root (development defaults):
```
POSTGRES_URL=postgresql+asyncpg://vg_user:vg_pass@localhost:5432/vg_hub
SECRET_KEY=<fernet-key>
INGEST_SHARED_SECRET=<random-32>    # trusted service-to-service ingest auth header (X-Ingest-Secret)
```

`frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

- **FastAPI owns OPS push (M1) end-to-end.** Integration Gateway in `modules/integrations/` + `modules/ops_push/` runs preflight + payload build + mutation plan, then executes via `modules/ops_client/` (OPS GraphQL with OAuth2). No external orchestrator is involved — the former n8n OnPrintShop node is historical only (`historical/2026-07/n8n-nodes-onprintshop/`), not mounted or run.

## Plan & Progress

- **V0 plan:** `plans/2026-04-14-v0-proof-of-concept.md` — 21 tasks, 19 done. Backend complete. Remaining: Customers page, Workflows page, E2E verification.
- **V1 plan:** `plans/2026-04-16-v1-integration-pipeline.md` — 6 phases, 23 tasks:
  - V0 Cleanup (3 critical bug fixes + 2 frontend pages)
  - V1a: SanMar SOAP inbound (fetch → normalize → store)
  - V1b: S&S Activewear + Alphabroder
  - V1c: OPS Push (n8n node mutations + markup engine + push workflow)
  - V1d: 4Over (REST + HMAC)
  - V1e: Scheduled sync + inventory + dashboard
  - V1f: Frontend UX overhaul (simplified supplier form, OPS product config, terminology)
- **Code review:** `docs/code_review_all_tasks.md` — 3 critical, 3 moderate, 3 minor issues

CORRECTED (2026-07-12): the former April completion counts, live n8n state, credential blocker, and
V1 approval statement were not reverified against `graphx-connect@5afa7b82`. Treat the plan list
as historical scope only; use root `RESTART.md` and rederive current status from code, tests, open
work, and inspected live state before acting.
