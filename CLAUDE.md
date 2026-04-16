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

### Full stack
```bash
docker compose up -d                          # postgres + api
```

## Architecture

**Modular monolith** — NOT microservices. All backend modules live in one FastAPI app. Suppliers are database configuration (protocol adapter pattern), not per-supplier code. Adding a supplier = creating a DB row, not writing code.

**Three systems:**
- `backend/` — FastAPI (Python 3.12). All routes under `/api/`. Async SQLAlchemy + asyncpg.
- `frontend/` — Next.js 14/15 (App Router). Blueprint design system (Outfit + Fira Code fonts, paper palette #f2f0ed, blueprint blue #1e4d92, dot-grid). Uses shadcn/ui + Tailwind.
- n8n (external) — owns all external API calls (PromoStandards SOAP, OPS GraphQL). FastAPI stores data and serves rules.

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

## Plan & Progress

Master plan: `plans/2026-04-14-v0-proof-of-concept.md` — 21 tasks with dependency map, task status, and phase-based execution order. Check the Task Status table at the top for current progress.

Current Status (April 15, 2026): V0 proof of concept is underway. Backend API modules are mostly complete. Frontend pages (`/suppliers`, `/products`, `/customers`, `/markup`) have been scaffolded and are iterating towards functional completeness.