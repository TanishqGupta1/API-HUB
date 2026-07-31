# API-HUB

![API-HUB Dashboard](docs/screenshot-dashboard.png)

Middleware platform connecting 994+ PromoStandards wholesale suppliers to OnPrintShop (OPS) storefronts. Eliminates the $3K/year per-customer API integration fee by automating catalog sync, pricing, and product push through a supplier-agnostic pipeline.

---

## Architecture

```
┌─────────────────────┐         ┌────────────────────────────────────────┐
│  Next.js 15 UI      │◀───────▶│  FastAPI Backend (modular monolith)    │
│  Blueprint design   │         │                                        │
│  shadcn/ui          │         │  /api/suppliers       (CRUD)           │
│  Polymorphic PDP    │         │  /api/products        (browse + PDP)   │
│  (apparel + print)  │         │  /api/customers       (OPS auth)       │
│  Live price quotes  │         │  /api/markup-rules    (pricing rules)  │
└─────────────────────┘         │  /api/pricing/quote   (live quote)     │
                                │  /api/suppliers/{id}/import (trigger)  │
                                │  /api/sync-jobs/health (per-supplier)  │
                                │  /api/push-log        (audit)          │
                                └────────────────┬───────────────────────┘
                                                 │
                                ┌────────────────┴───────────────────────┐
                                │  Adapter registry (DB-config-driven)   │
                                │  ┌───────────────────────────────────┐ │
                                │  │ PromoStandardsAdapter (zeep SOAP) │ │
                                │  │ SanMarAdapter (PS subclass)       │ │
                                │  │ FourOverAdapter (REST + HMAC)     │ │
                                │  │ OPSAdapter (GraphQL inbound)      │ │
                                │  └───────────────────────────────────┘ │
                                └────────────────┬───────────────────────┘
                                                 │
                                ┌────────────────┴───────────────────────┐
                                │  PostgreSQL 16 (asyncpg + JSONB)       │
                                └────────────────┬───────────────────────┘
                                                 │
┌────────────────────────────────────────────────┴────────────────────────┐
│  In-process scheduler (modules/import_jobs/scheduler.py)                 │
│  asyncio + Redis advisory lock — no external orchestrator                │
│                                                                          │
│  catalog-sync-weekly  ──▶ /import?mode=full_sellable                     │
│  pricing-sync-daily   ──▶ /import?mode=delta                             │
│  inventory-sync-hourly──▶ /import?mode=delta                             │
│  closeouts-monthly    ──▶ /import?mode=closeouts                        │
│  ops-push             ──▶ apply markup + push to customer storefront    │
│         via modules/ops_push/ + modules/integrations/ (Integration Gateway) │
└──────────────────────────────────────────────────────────────────────────┘
```

CORRECTED (2026-07-21): n8n is dropped as a built tier (DECISIONS-LOG.md, LOCKED 2026-06-30). FastAPI's own scheduler and Integration Gateway own scheduling and OPS push directly — there is no live n8n orchestration in this repo. The former `n8n-workflows/` and `n8n-nodes-onprintshop/` were moved to `historical/2026-07/` (preserved, not deleted) and are no longer referenced by any running code.

**Key design decisions:**
- **Suppliers are DB rows, not code.** Adding a supplier creates a `suppliers` row with `adapter_class` + encrypted `auth_config`. No per-supplier services.
- **Adapter pattern.** `BaseAdapter` ABC with `discover()`, `hydrate_product()`, `discover_changed()`, `discover_closeouts()`. Adapters self-register via `register_adapter()`.
- **Polymorphic catalog.** `product_type` ∈ {apparel, print}. Apparel uses tiered variant pricing; print uses formula `base × area × area_factor + setup`.
- **All credentials managed through the UI.** Encrypted at rest via `EncryptedJSON` (Fernet AES-128) on `suppliers.auth_config` and `customers.ops_auth_config`.
- **FastAPI owns external API calls end-to-end.** The Integration Gateway (`modules/integrations/`) prepares data, applies markup, and calls OPS directly via `modules/ops_client/` — no external orchestrator in the loop.
- **Modular monolith.** All backend modules in one FastAPI app. Split only if a hotspot demands it.

---

## Build Phases

| Phase | What | Status |
|-------|------|--------|
| **V0** | FastAPI + PostgreSQL + Next.js scaffold. Supplier CRUD with encryption. PS directory search. Product catalog grid. | ✅ Done |
| **Phase 2** | OPS inbound adapter (`OPSAdapter`), `BaseAdapter` ABC, adapter registry, `/api/suppliers/{id}/import`. | ✅ Done |
| **Phase 3** | SanMar / PromoStandards adapter (zeep SOAP). `PromoStandardsAdapter` + `SanMarAdapter` subclass. WSDL caching. SOAP fault classifier. Retry with exponential backoff. | ✅ Done |
| **Phase 4** | Pricing engine. Apparel `TieredVariantResolver` (Net > Sale > MSRP > Case). Print `FormulaResolver` with bounds. Customer markup + storefront overrides. `POST /api/pricing/quote`. | ✅ Done |
| **Phase 5** | Polymorphic PDP. `ApparelDetailPanel` / `PrintDetailPanel` dispatch on `product_type`. `DimensionInput` with bounds, debounced live quote, breakdown disclosure. | ✅ Done |
| **Phase 6** | Sync pipeline. `discovery_mode` + per-job counters (`total_products` / `success_count` / `failed_count`). `CustomerProductSelection` stale detection. `/api/sync-jobs/health` per supplier. | ✅ Done |
| **Phase 7** | OPS push (FastAPI's own Integration Gateway owns the mutation + applies markup — see 2026-07-21 correction below). | In progress |
| **Phase 9** | Scheduled sync: weekly catalog, daily pricing, hourly inventory, monthly closeouts. | ✅ Done — originally shipped as n8n cron workflows; re-homed onto the in-process scheduler (`modules/import_jobs/scheduler.py`) per the 2026-06-30 LOCKED decision dropping n8n as a built tier |
| **Phase 10** | `FourOverAdapter` (REST + HMAC). | Skeleton merged — sandbox creds pending |

---

## Features

- **994+ supplier support** — PromoStandards Directory auto-discovers all registered suppliers; no hardcoded vendor lists.
- **Adapter framework** — `BaseAdapter` ABC + registry. New supplier types are subclasses + a DB row, not new services.
- **Polymorphic catalog & pricing** — apparel (tiered variants) and print (formula) share one product API; resolver dispatches by `product_type`.
- **Live price quotes** — debounced `/api/pricing/quote` returns unit price + total + breakdown (base, area factor, tier match, setup).
- **Customer markup engine** — per-customer rules (scope, markup %, min margin, rounding, priority) + storefront overrides (`fixed_unit_price`, `extra_markup_pct`, `nearest_99` / `nearest_dollar` rounding).
- **SOAP fault classification** — auth codes (`100/104/110`) → `AuthError` (fatal); other faults → `SupplierError` (per-product, retried/skipped).
- **Retry with exponential backoff** — `TransientError` retries 3× with `2 ** (2 - retries)` second delay; transport errors (timeouts, DNS) wrapped to `TransientError`.
- **WSDL caching** — `PromoStandardsClient` caches the zeep service per instance; resolver returns highest-version endpoint from PS Directory.
- **Stale detection** — when a product is re-synced after being pushed to a customer, `customer_product_selections.status` flips to `"stale"`.
- **Per-supplier sync health** — `/api/sync-jobs/health` reports last sync time, recent error count, consecutive failures.
- **Scheduled sync** — the in-process scheduler polls `/api/sync-jobs/{id}` until terminal, then Slack-alerts on failure.
- **Fernet encryption** — all credentials encrypted transparently at the DB layer.
- **Blueprint design system** — Outfit + Fira Code, paper palette `#f2f0ed`, blueprint blue `#1e4d92`, dot-grid background.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router), shadcn/ui, Tailwind CSS, Vitest + Playwright |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async), asyncpg |
| SOAP | `zeep` + `lxml` (hardened parser: `resolve_entities=False`, `no_network=True`) |
| Encryption | `cryptography` — Fernet symmetric encryption (AES-128) |
| Database | PostgreSQL 16, JSONB for endpoint cache + JSONB error logs |
| Pipeline | In-process scheduler (`modules/import_jobs/scheduler.py`), custom PromoStandards adapter loaded at runtime |
| OPS push | `modules/ops_push/` + `modules/integrations/` — GraphQL mutations via `modules/ops_client/` |
| Infrastructure | Docker Compose |

---

## Project Structure

```
api-hub/
├── backend/
│   ├── main.py                        # FastAPI app — routers, lifespan, scheduler task
│   ├── database.py                    # Async engine + EncryptedJSON type decorator
│   ├── requirements.txt
│   ├── Dockerfile
│   └── modules/
│       ├── suppliers/                 # Supplier CRUD, endpoint caching, category import
│       ├── ps_directory/              # PromoStandards directory client (994+ suppliers)
│       ├── catalog/                   # Product / Variant / Image / Apparel/PrintDetails / Selection
│       ├── customers/                 # OPS storefront OAuth2 configs
│       ├── markup/                    # Per-customer pricing rules + engine
│       ├── pricing/                   # Quote resolvers (apparel tiered + print formula)
│       ├── promostandards/            # PromoStandardsAdapter, SanMarAdapter, ps_normalizer_v2
│       ├── rest_connector/            # FourOverAdapter (REST + HMAC)
│       ├── ops_inbound/               # OPSAdapter (GraphQL inbound)
│       ├── ops_config/                # Per-customer storefront overrides
│       ├── ops_push/                  # OPS push pipeline (markup → mutation prep)
│       ├── push_mappings/             # Master option → OPS option mapping
│       ├── master_options/            # Canonical option vocabulary
│       ├── push_candidates/           # Customer product selections / push queue
│       ├── push_log/                  # OPS push audit trail
│       ├── import_jobs/               # BaseAdapter, registry, service, scheduler
│       ├── sync_jobs/                 # Job records + /health endpoint
│       └── auth/                      # Ingest secret, customer scoping
├── frontend/                          # Next.js 15 app
│   ├── src/app/(admin)/               # Admin: suppliers, customers, sync, workflows
│   ├── src/app/storefront/vg/         # Polymorphic storefront PDP
│   ├── src/components/storefront/     # ApparelDetailPanel, PrintDetailPanel, DimensionInput, LivePriceQuote
│   ├── src/lib/use-debounced-quote.ts # 250ms debounced /api/pricing/quote
│   ├── e2e/                           # Playwright specs (apparel + print PDP, catalog filter)
│   └── docs/pdp-runbook.md            # Polymorphic PDP runbook
├── historical/2026-07/                # Preserved, not run — see 2026-07-21 correction above
│   ├── n8n_proxy/                     # former n8n workflow trigger pass-through
│   ├── n8n-workflows/                 # former n8n cron workflow JSONs
│   ├── n8n-nodes-onprintshop/         # former OnPrintShop GraphQL custom node (TypeScript)
│   └── n8n.Dockerfile
├── docs/
│   └── superpowers/plans/             # Phase plans (status banners updated)
├── plans/
│   ├── 2026-04-14-v0-proof-of-concept.md
│   └── 2026-04-16-v1-integration-pipeline.md
├── docker-compose.yml
└── .env                               # Not committed — see .env.example
```

---

## Database Schema

| Table | Purpose |
|---|---|
| `suppliers` | Adapter class + protocol + `auth_config` (Encrypted JSONB) + `endpoint_cache` + `protocol_config` + `last_full_sync` / `last_delta_sync`. |
| `products` | Canonical product. `product_type` ∈ {apparel, print}. `last_synced` drives stale detection. |
| `product_variants` | Apparel color × size matrix with `base_price`. |
| `variant_prices` | Tiered pricing (`price_type`, `quantity_min`, `quantity_max`, `price`). |
| `product_images` | URL + type (front/back/swatch/detail) + colour. |
| `apparel_details` | Apparel-specific (`apparel_style`, `is_closeout`, `is_caution`, `fabric_specs`, `fob_points`). |
| `print_details` | Print-specific (`min_width` / `max_width` / `min_height` / `max_height`, `base_price_per_sq_unit`, formula in `raw_payload`). |
| `product_options` / `product_option_attributes` | Configurable options + multipliers. |
| `product_sizes` | Print preset sizes. |
| `customers` | OPS storefront OAuth2 (encrypted `client_secret`). |
| `customer_product_selections` | Customer's curated product list. Status: `selected` / `pushed` / `stale`. |
| `markup_rules` | Per-customer pricing rules — scope, markup %, min margin, rounding, priority. |
| `product_storefront_configs` | Per-customer-per-product overrides (`pricing_overrides`, `option_mappings`, `ops_category_id`). |
| `sync_jobs` | Job records: `status`, `discovery_mode`, `total_products`, `success_count`, `failed_count`, `errors` (JSONB), `started_at`, `completed_at`. |
| `product_push_log` | OPS push audit — `ops_product_id`, status, error per product per customer. |
| `master_options` / `master_option_attributes` | Canonical option vocabulary (synced from OPS). |
| `push_mappings` | Master option → OPS option mapping. |

---

## API Reference (selected)

| Method + Path | Purpose |
|---|---|
| `POST /api/suppliers/{id}/import` | Trigger import. Body: `{ "mode": "first_n" \| "delta" \| "full_sellable" \| "explicit_list" \| "closeouts", "limit": int? }`. Returns `sync_job_id`. |
| `GET /api/suppliers/{id}/sync-jobs` | Recent sync jobs for a supplier (default limit 50). |
| `GET /api/sync-jobs/{id}` | Job status, counts, errors. |
| `GET /api/sync-jobs/health` | Per-supplier health: last sync, recent error count, consecutive failures. |
| `POST /api/pricing/quote` | Public quote (base price, no markup). Body: `{ product_id, variant_id?, width?, height?, qty, selected_attribute_ids? }`. |
| `POST /api/customers/{id}/pricing/quote` | Internal-only (gated by `X-Ingest-Secret`): marked-up + storefront-override price. |
| `GET/POST /api/integrations/v1/products[/{id}]` | Scoped catalog read via the Integration Gateway (`X-Orchestrator-Key`, per-key `allowed_supplier_slugs`). |

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

# 3. Frontend
cd frontend
npm install
npm run dev
```

### Seed demo data

```bash
cd backend && source .venv/bin/activate
python seed_demo.py
```

### Run tests

```bash
# Backend
cd backend && source .venv/bin/activate && pytest

# Frontend unit + component
cd frontend && npm test

# Frontend e2e (Playwright)
cd frontend && npm run test:e2e
```

### Environment variables

Copy `.env.example` to `.env` and fill in:

```
POSTGRES_URL=postgresql+asyncpg://vg_user:vg_pass@localhost:5432/vg_hub
SECRET_KEY=<python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
INGEST_SHARED_SECRET=<random-32-char-string>      # trusted service-to-service ingest auth header
API_BASE_URL=http://localhost:8000                # this service's own base URL, used by ops_push/merge.py + scripts/ingest_ops_master_options.py
```

`frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

> **Never** prefix server-only secrets with `NEXT_PUBLIC_` — those are bundled into the browser JS by Next.js.

---

## n8n (historical, 2026-07-21)

n8n was originally used to delegate outbound integrations (OPS push, scheduled syncs). It has been
dropped as a built tier (`DECISIONS-LOG.md`, LOCKED 2026-06-30) — API-HUB's own scheduler and
Integration Gateway now own that work directly, in-process. The former n8n workflows, the custom
OnPrintShop node, and `n8n.Dockerfile` are preserved at `historical/2026-07/` for reference (they
capture real logic per `_CANONICAL-AUTHORITY.md`) but are not run, built, or referenced by any live
code path. n8n remains, at most, a possible future *integration target* — a system Connect could
integrate *to* if a tenant already runs one — never a built engine in this repo
(`atomic-specs/connect.md` §4.1).

---

**Status:** V0 + Phases 2–6 + Phase 9 shipped (Phase 9's scheduling re-homed off n8n onto the in-process scheduler, 2026-07-21). Phase 7 (OPS push) in progress. Phase 10 (4Over) skeleton merged, awaiting sandbox credentials.

**Maintained by:** VisualGraphx
