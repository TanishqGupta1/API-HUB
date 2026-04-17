# CLAUDE.md / GEMINI.md

This file provides guidance to AI coding agents (like Gemini CLI or Claude Code) when working with code in this repository.

## Project

API-HUB — middleware platform connecting 994+ PromoStandards wholesale suppliers to OnPrintShop (OPS) storefronts. Modular monolith: FastAPI backend + Next.js frontend + PostgreSQL, orchestrated by n8n.

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
docker compose up -d                          # postgres + n8n (with OPS node)
```

### n8n
```bash
docker compose up -d n8n                      # n8n editor on :5678
# OnPrintShop custom node auto-installed from ./n8n-nodes-onprintshop/
```

## Architecture

**Modular monolith** — NOT microservices. All backend modules live in one FastAPI app. Suppliers are database configuration (protocol adapter pattern), not per-supplier code. Adding a supplier = creating a DB row, not writing code.

**Four systems:**
- `backend/` — FastAPI (Python 3.12). All routes under `/api/`. Async SQLAlchemy + asyncpg. Handles SOAP/REST fetch, normalization, storage, markup rules.
- `frontend/` — Next.js 15 (App Router). Blueprint design system (Outfit + Fira Code fonts, paper palette #f2f0ed, blueprint blue #1e4d92, dot-grid). Uses shadcn/ui + Tailwind.
- n8n (Docker, port 5678) — orchestrates sync schedules via HTTP triggers to FastAPI. Owns all OPS push calls via the OnPrintShop custom node.
- `n8n-nodes-onprintshop/` — TypeScript custom n8n node for OnPrintShop GraphQL API. OAuth2 auth. 22 operations implemented, 33 mutations missing (see `OPS-NODE-GAP-ANALYSIS.md`).

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
```

`frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

- **n8n owns OPS push.** FastAPI prepares data + applies markup. n8n calls OPS via the OnPrintShop node.

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

Current Status (April 16, 2026): V0 is 19/21 done. n8n running in Docker with OnPrintShop node loaded. V1 pipeline plan approved. Waiting on Christian for SanMar API credentials and OPS Postman collection export.