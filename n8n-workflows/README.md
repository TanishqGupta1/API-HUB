# n8n Workflows

Importable n8n workflow JSON for the API-HUB pipelines.

## `vg-ops-pull.json` — Pull catalog from Visual Graphics OnPrintShop

**What it does**

1. Looks up the VG OPS supplier row in FastAPI by slug `vg-ops`; fails fast if missing or inactive.
2. Pulls all categories from OPS (`product_category` GraphQL query, paginated).
3. Pulls all products from OPS (`products_details` query, paginated with `fetchAllPages=true`).
4. Transforms each shape into the hub's `CategoryIngest` / `ProductIngest` contract.
5. POSTs the normalized batches to `/api/ingest/{vg_sid}/categories` and `/api/ingest/{vg_sid}/products` with the `X-Ingest-Secret` header.

Stock and pricing are **not** in this workflow yet — they're separate OPS queries per product (`productStocks`, `product_price`) and require a fan-out loop. Add in v2 after v1 is green.

**Prerequisites**

- Postgres running: `docker compose up -d postgres`
- FastAPI running on host :8000 (`uvicorn main:app --port 8000` from `backend/`)
- n8n running: `docker compose up -d n8n`
- VG OPS supplier seeded (if your DB is empty): `python backend/seed_demo.py` (or just start FastAPI in development — it auto-creates a `vg-ops` supplier row on boot)
- VG supplier active in DB:
  ```bash
  docker exec api-hub-postgres-1 psql -U vg_user -d vg_hub \
    -c "UPDATE suppliers SET is_active=true WHERE slug='vg-ops';"
  ```
- `INGEST_SHARED_SECRET` set in repo-root `.env` **and** that variable exposed to the n8n container via `docker-compose.yml` (already done — see the `n8n` service `environment:` block). Restart n8n with `docker compose up -d n8n` after changing `.env`.

## Import + configure

1. Open n8n UI at **http://localhost:5678**.
2. **Workflows → Import from File** → select `vg-ops-pull.json`. The workflow loads with 9 nodes and 8 connections.
3. **Credentials → New → OnPrintShop API** (custom node provides this type):
   - **Client ID:** supplied by Christian
   - **Client Secret:** supplied by Christian
   - **Base URL:** e.g. `https://vg.onprintshop.com` (production) or staging URL
   - **Token URL:** e.g. `https://vg.onprintshop.com/oauth/token`
   - Name the credential **`VG OnPrintShop`** (matches the name referenced in the workflow JSON).
4. In the imported workflow, click each OnPrintShop node (`OPS: Get Categories`, `OPS: Get Products Detailed`) and confirm the credential dropdown shows `VG OnPrintShop`. If it's blank, select it manually and save.

## Run

1. Click **Execute Workflow** (top toolbar).
2. Watch each node light up. Click any node to open its input/output panel.
3. Expected output shapes:
   - `Get Suppliers` → array of supplier objects.
   - `Resolve VG SID` → `{ vg_sid, vg_name }`.
   - `OPS: Get Categories` → OPS GraphQL response with `data.product_category.product_category[]`.
   - `Shape Categories` → flat array of `{ external_id, name, parent_external_id, sort_order }`.
   - `POST /ingest/categories` → `{ sync_job_id, records_processed, status: "completed" }`.
   - Same shape for products.
4. Verify hub-side:
   ```bash
   VG_ID=$(curl -s http://localhost:8000/api/suppliers | jq -r '.[] | select(.slug=="vg-ops") | .id')
   curl -s "http://localhost:8000/api/products?supplier_id=$VG_ID" | jq 'length'
   curl -s "http://localhost:8000/api/categories?supplier_id=$VG_ID" | jq 'length'
   curl -s http://localhost:8000/api/sync-jobs | jq '[.[] | select(.supplier_name | contains("Visual Graphics"))]'
   ```
5. Reload **http://localhost:3000/storefront/vg** — the OPS catalog replaces the manual seed placeholders.

## Failure modes

| Node in red | Cause | Fix |
|---|---|---|
| `Resolve VG SID` — "VG OPS supplier not seeded" | seed missing | Start FastAPI in development (auto-creates `vg-ops`) or run `python backend/seed_demo.py` |
| `Resolve VG SID` — "is_active=false" | Supplier gate | SQL UPDATE shown above |
| `OPS: Get Categories` — 401 / 403 | Bad OAuth2 cred | Re-enter client id/secret in n8n credential editor |
| `POST /ingest/*` — 401 "Invalid or missing X-Ingest-Secret" | n8n's `INGEST_SHARED_SECRET` env ≠ FastAPI's | Compare `docker exec api-hub-n8n-1 env \| grep INGEST` to the value in repo `.env`; re-run `docker compose up -d n8n` |
| `POST /ingest/*` — 409 "not active" | Supplier flipped back | SQL UPDATE above |
| `POST /ingest/*` — 500 | Uvicorn crashed — check its log |

## Network / environment

All workflow URLs use `{{ $env.API_BASE_URL }}` so the address is configurable per environment.
Set `API_BASE_URL` in the n8n container's environment (already wired in `docker-compose.yml`):

- **Docker Compose (all platforms):** `http://api:8000` (Compose service DNS — set in `docker-compose.yml`)
- **Production:** your public or internal API hostname (set `API_BASE_URL` in task definition / `.env`)

## Activation

All workflow JSONs ship with `"active": false`. This is intentional — workflows must be
manually imported, credentials bound, and then activated in the n8n UI before any scheduled
or webhook triggers fire. Activating before credentials are set causes every execution to fail.

---

## Removed in M1 (T23)

- `ops-push.json` — OPS push moved to FastAPI (`POST /api/push/{customer_id}/{product_id}` →
  integration gateway → `modules/ops_client`). The legacy webhook + `setProduct`/`setProductPrice`
  + `X-Ingest-Secret` flow is gone.
- `ops-master-options-pull.json` — Master-options ingest is now a direct FastAPI route
  (`POST /api/integrations/v1/master-options/ingest` + the in-process `master_options/routes.py`),
  not an n8n-orchestrated pull.

n8n remains the orchestrator for **inbound supplier sync only** (catalog + pricing + inventory
pulls). The OPS push path is FastAPI-owned end-to-end.

## Workflow index

| File | Schedule | Flow |
|---|---|---|
| `vg-ops-pull.json` | Manual / Daily | OPS categories + products → hub `/api/ingest/{sid}/*` |
| `sanmar-sftp-pull.json` | Daily | SanMar SFTP → hub `/api/ingest/{sid}/*` |
| `sanmar-soap-pull.json` | Daily | SanMar PromoStandards SOAP → hub `/api/ingest/{sid}/*` |
| `inventory-sync-hourly.json` | Hourly | Per-supplier inventory delta → hub `/api/ingest/{sid}/inventory` |
| `pricing-sync-daily.json` | Daily | Per-supplier pricing refresh → hub `/api/ingest/{sid}/pricing` |
| `catalog-sync-weekly.json` | Weekly | Full catalog rebuild |
| `closeouts-monthly.json` | Monthly | Closeouts pull |

## Next additions (not in v1)

- `Get Stock` loop per product → POST `/api/ingest/{sid}/inventory`.
- `Get Prices` loop per product → POST `/api/ingest/{sid}/pricing`.
- Schedule Trigger (cron) parallel to the Manual Trigger for daily 3am runs. Connect it to the same `Get Suppliers` node.
- Error workflow that writes a `push_log` entry on failure.
