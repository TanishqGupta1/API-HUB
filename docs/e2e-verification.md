# API-HUB — End-to-End Verification (V0)

This is the manual checklist for **Task 17 — End-to-End Verification**.

## Prereqs

- Docker running
- Repo-root `.env` created from `.env.example`
- Services:
  - Postgres: `docker compose up -d postgres`
  - n8n: `docker compose up -d n8n`
  - Backend: `cd backend && uvicorn main:app --reload --port 8000`
  - Frontend: `cd frontend && npm install && npm run dev`

## 1) Backend sanity

- `GET /health` returns `{ "status": "ok" }`
- `GET /api/stats` returns counts (no 500s)
- Seed demo data:
  - `cd backend && python seed_demo.py`
  - Verify:
    - `GET /api/suppliers` returns at least 1 supplier
    - `GET /api/products` returns products + variant aggregates

## 2) Frontend pages (admin)

Open `http://localhost:3000`:

- Dashboard loads and stats render
- Suppliers page:
  - Create supplier
  - Test directory lookup (PromoStandards directory page)
- Products page:
  - List products
  - Click into product detail
- Customers page:
  - Create storefront (customer)
  - Ensure secrets do not render after save
- Markup page:
  - Create markup rule for the customer
  - Verify the rule shows in list
- Workflows page:
  - Loads without crashing when n8n is down (should show an error banner)
  - When n8n is up and `N8N_API_KEY` is set, it lists workflows
- Sync jobs page:
  - Shows ingest runs after running the VG pull workflow

## 3) n8n workflows

### Import

- In n8n UI (`http://localhost:5678`):
  - Import `n8n-workflows/vg-ops-pull.json`
  - Import `n8n-workflows/ops-push.json`

### VG pull workflow

- Run `VG OPS → Hub (Categories + Products)` once
- Verify hub-side:
  - Categories appear: `GET /api/categories`
  - Sync jobs logged: `GET /api/sync-jobs`

### OPS push workflow (minimal)

Pre-req: Create a customer in the hub that corresponds to the OPS credential you’ll select in n8n.

- Activate the workflow in n8n (required for webhook)
- Trigger:
  - `GET http://localhost:5678/webhook/ops-push?customer_id=<uuid>&limit=5`
- Verify:
  - Push logs exist: `GET /api/push-log`
  - Per-product push status renders on product detail page

## Expected failure modes

- `401 Invalid or missing X-Ingest-Secret`:
  - Ensure `INGEST_SHARED_SECRET` is set in repo-root `.env`
  - Restart n8n after changing `.env`: `docker compose up -d n8n`
- n8n proxy APIs fail from frontend:
  - Set `N8N_API_KEY` so FastAPI can call n8n’s REST API
- OPS mutations fail:
  - Validate OPS OAuth2 creds in the `n8n-nodes-onprintshop` credential
  - Some OPS instances require valid `category_id` / `size_id`; adjust the workflow’s input builder node if needed

