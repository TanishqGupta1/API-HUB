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
│  n8n cron pipeline                                                       │
│                                                                          │
│  catalog-sync-weekly  ──▶ trigger /import?mode=full_sellable             │
│  pricing-sync-daily   ──▶ trigger /import?mode=delta                     │
│  inventory-sync-hourly──▶ trigger /import?mode=delta                     │
│  closeouts-monthly    ──▶ trigger /import?mode=closeouts                 │
│  ops-push             ──▶ apply markup + push to customer storefront    │
│                                                                          │
│  n8n-nodes-onprintshop (VisualGraphxLLC)                                 │
│  OAuth2 GraphQL client for OnPrintShop — setProduct, setProductPrice    │
└──────────────────────────────────────────────────────────────────────────┘
```

**Key design decisions:**
- **Suppliers are DB rows, not code.** Adding a supplier creates a `suppliers` row with `adapter_class` + encrypted `auth_config`. No per-supplier services.
- **Adapter pattern.** `BaseAdapter` ABC with `discover()`, `hydrate_product()`, `discover_changed()`, `discover_closeouts()`. Adapters self-register via `register_adapter()`.
- **Polymorphic catalog.** `product_type` ∈ {apparel, print}. Apparel uses tiered variant pricing; print uses formula `base × area × area_factor + setup`.
- **All credentials managed through the UI.** Encrypted at rest via `EncryptedJSON` (Fernet AES-128) on `suppliers.auth_config` and `customers.ops_auth_config`.
- **n8n owns external API calls.** FastAPI prepares data + applies markup; n8n calls OPS via `n8n-nodes-onprintshop`.
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
| **Phase 7** | OPS push (n8n owns mutation; FastAPI applies markup). | In progress |
| **Phase 9** | Scheduled n8n cron workflows: weekly catalog, daily pricing, hourly inventory, monthly closeouts. | ✅ Done (workflows ship `active: false`; activate manually after credential bind) |
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
- **Scheduled sync** — n8n cron workflows poll `/api/sync-jobs/{id}` until terminal, then Slack-alert on failure.
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
| Pipeline | n8n (Docker), custom PromoStandards adapter loaded at runtime |
| OPS push | `n8n-nodes-onprintshop` (VisualGraphxLLC) — GraphQL mutations |
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
│       ├── n8n_proxy/                 # n8n workflow trigger pass-through
│       └── auth/                      # Ingest secret, customer scoping
├── frontend/                          # Next.js 15 app
│   ├── src/app/(admin)/               # Admin: suppliers, customers, sync, workflows
│   ├── src/app/storefront/vg/         # Polymorphic storefront PDP
│   ├── src/components/storefront/     # ApparelDetailPanel, PrintDetailPanel, DimensionInput, LivePriceQuote
│   ├── src/lib/use-debounced-quote.ts # 250ms debounced /api/pricing/quote
│   ├── e2e/                           # Playwright specs (apparel + print PDP, catalog filter)
│   └── docs/pdp-runbook.md            # Polymorphic PDP runbook
├── n8n-workflows/
│   ├── catalog-sync-weekly.json       # Sun 1 AM — full_sellable per supplier
│   ├── pricing-sync-daily.json        # Daily — delta
│   ├── inventory-sync-hourly.json     # Hourly — delta
│   ├── closeouts-monthly.json         # 1st of month — closeouts mode
│   ├── ops-push.json                  # Triggered: apply markup + push to customer
│   ├── ops-master-options-pull.json   # Pull canonical option list from OPS
│   └── README.md                      # Activation flow + env vars
├── n8n-nodes-onprintshop/             # OnPrintShop GraphQL custom node (TypeScript)
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
| `POST /api/n8n/workflows/{id}/trigger` | Trigger an n8n workflow from the admin UI. |

---

## Getting Started

### Prerequisites

- Docker Desktop
- Python 3.12 + venv
- Node.js 20+

### Run locally

```bash
# 1. Start PostgreSQL + n8n
docker compose up -d postgres n8n

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
INGEST_SHARED_SECRET=<random-32-char-string>      # n8n → FastAPI auth header
API_BASE_URL=http://host.docker.internal:8000     # n8n container → FastAPI host
```

`frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

> **Never** prefix server-only secrets with `NEXT_PUBLIC_` — those are bundled into the browser JS by Next.js.

---

## n8n Setup

1. Run n8n: `docker compose up -d n8n` (OnPrintShop custom node auto-mounted from `./n8n-nodes-onprintshop/`).
2. Open http://localhost:5678 — first-run prompts for owner account.
3. Import workflows from `n8n-workflows/` (Settings → Import).
4. Bind credentials in n8n UI: OnPrintShop OAuth2, Slack webhook, etc.
5. **Set `API_BASE_URL` env var** on the n8n container (already wired in `docker-compose.yml`).
6. Activate workflows in the n8n UI. They ship `"active": false` — activating before credentials are bound causes every execution to fail.

See `n8n-workflows/README.md` for activation flow + per-workflow env requirements.

---

**Status:** V0 + Phases 2–6 + Phase 9 shipped. Phase 7 (OPS push) in progress. Phase 10 (4Over) skeleton merged, awaiting sandbox credentials.

**Maintained by:** VisualGraphx
