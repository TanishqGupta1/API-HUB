# VG Integration Hub

![VG Integration Hub Dashboard](docs/screenshot-dashboard.png)

A middleware platform connecting 994+ PromoStandards wholesale suppliers to OnPrintShop (OPS) storefronts. Eliminates the $3K/year per-customer API integration fee by automating catalog sync, pricing, and product push through a supplier-agnostic pipeline.

---

## Architecture

```
┌─────────────────┐       ┌──────────────────────────────┐
│  Next.js UI     │◀─────▶│  FastAPI Backend              │
│  Blueprint UI   │       │  Modular Monolith             │
│  shadcn/ui      │       │                               │
│  All config +   │       │  /api/suppliers    (CRUD)     │
│  credentials    │       │  /api/products     (browse)   │
│  via UI only    │       │  /api/customers    (OPS auth) │
└─────────────────┘       │  /api/markup-rules (pricing)  │
                          │  /api/push-log     (audit)    │
                          └──────────────┬────────────────┘
                                         │
                          ┌──────────────┴────────────────┐
                          │  PostgreSQL 16                 │
                          └──────────────┬────────────────┘
                                         │
┌────────────────────────────────────────┴───────────────────────┐
│  n8n Pipeline                                                   │
│                                                                 │
│  PromoStandards custom node  ──▶  normalize  ──▶  push to OPS  │
│  (TypeScript + node-soap)         (FastAPI)       (OPS node)   │
│                                                                 │
│  n8n-nodes-onprintshop (VisualGraphxLLC)                        │
│  OAuth2 GraphQL client for OnPrintShop — setProduct,            │
│  setProductPrice, order management, inventory                   │
└─────────────────────────────────────────────────────────────────┘
```

**Key design decisions:**
- Suppliers are database configuration — no per-supplier code
- All credentials managed through the UI, encrypted at rest (Fernet AES-128)
- n8n owns all external API calls; FastAPI stores data and serves rules
- No microservices — modular monolith for V0/V1, split only if needed later

---

## Build Phases

| Phase | What | Status |
|-------|------|--------|
| **V0** | FastAPI + PostgreSQL + Next.js scaffold. Supplier CRUD with encryption. PS directory search. Product catalog grid. | In progress |
| **V1a** | n8n custom PromoStandards node (TypeScript + node-soap). Auto-discovers WSDL endpoints per supplier. | Planned |
| **V1b** | Normalization engine. PS SOAP response → canonical Product/Variant schema. Data source indicators in UI. | Planned |
| **V1c** | OPS push via `n8n-nodes-onprintshop`. Per-customer markup rules. Push audit log. | Planned |
| **V1d** | Field mapping UI for non-PS suppliers (e.g. 4Over FTP/REST). | Planned |

---

## Features

- **994+ supplier support** — PromoStandards Directory API auto-discovers all registered suppliers; no hardcoded vendor lists
- **Fernet encryption** — all supplier OAuth2/API credentials encrypted transparently at the database layer
- **Endpoint caching** — 24h TTL on PS directory responses to avoid rate limits
- **Progressive reveal UI** — supplier setup form unlocks step-by-step (protocol → supplier → credentials → test → schedule)
- **Blueprint design system** — Outfit + Fira Code, paper palette, dot-grid background; built for technical operators
- **OPS push workflow** — n8n loops over customers, applies markup rules, calls `setProduct` + `setProductPrice` per storefront
- **Push audit trail** — every OPS mutation logged with `ops_product_id`, status, timestamp, and error if failed

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), shadcn/ui, Tailwind CSS |
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), asyncpg |
| Encryption | `cryptography` — Fernet symmetric encryption |
| Database | PostgreSQL 16, JSONB for endpoint cache |
| Pipeline | n8n, custom PromoStandards node (TypeScript + node-soap) |
| OPS push | `n8n-nodes-onprintshop` (VisualGraphxLLC) — GraphQL mutations |
| Infrastructure | Docker Compose |

---

## Project Structure

```
vg-integration-hub/
├── backend/
│   ├── main.py                        # FastAPI app — registers all routers
│   ├── database.py                    # Async engine + EncryptedJSON type decorator
│   ├── requirements.txt
│   ├── Dockerfile
│   └── modules/
│       ├── suppliers/                 # Supplier CRUD, endpoint caching
│       ├── ps_directory/              # PromoStandards directory client
│       ├── catalog/                   # Product + ProductVariant models
│       ├── customers/                 # OPS storefront OAuth2 configs
│       ├── markup/                    # Per-customer pricing rules
│       └── push_log/                  # OPS push audit trail
├── frontend/                          # Next.js Blueprint UI (V0 task 9–17)
├── frontend-prototype/
│   └── index.html                     # Full interactive prototype — 10 screens
├── n8n-workflows/                     # n8n workflow JSON definitions
├── plans/
│   ├── 2026-04-14-v0-proof-of-concept.md   # 21-task implementation plan (V0 + V1c)
│   └── README-draft.md
├── docker-compose.yml
└── .env                               # Not committed — see .env.example
```

---

## Database Schema

| Table | Purpose |
|---|---|
| `suppliers` | Dynamic config — protocol, `auth_config` (Encrypted JSONB), `endpoint_cache` |
| `products` | Canonical product data |
| `product_variants` | Color/size combos with price and inventory |
| `product_images` | Image URLs with type (front/back/swatch/detail) |
| `customers` | OPS storefront OAuth2 credentials (client_id, client_secret encrypted) |
| `markup_rules` | Per-customer pricing rules — scope, markup %, min margin, rounding, priority |
| `sync_jobs` | n8n workflow run history |
| `product_push_log` | OPS push audit trail — ops_product_id, status, error per product per customer |

---

## Getting Started

### Prerequisites

- Docker Desktop
- Python 3.12 + venv
- Node.js 20+

### Run locally

```bash
# 1. Start PostgreSQL
docker compose up -d postgres

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 3. Frontend (once scaffolded in V0 Task 9)
cd frontend
npm install
npm run dev
```

### Seed demo data

```bash
cd backend && source .venv/bin/activate
python seed_demo.py
# Expected: Seeded: 1 supplier, 1 product, 12 variants
```

### Environment variables

Copy `.env.example` to `.env` and fill in:

```
POSTGRES_URL=postgresql+asyncpg://vg_user:vg_pass@localhost:5432/vg_hub
SECRET_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
```

---

## n8n Setup

1. Run n8n: `docker compose up -d n8n` (or use existing instance)
2. Install community nodes: `n8n-nodes-onprintshop` (VisualGraphxLLC)
3. Import workflow JSON from `n8n-workflows/`
4. Point HTTP Request nodes at `http://localhost:8000`
5. Configure OnPrintShop credentials per customer via the Customers UI

---

**Status:** V0 in progress — backend modules complete, frontend scaffold next  
**Maintained by:** VisualGraphx
