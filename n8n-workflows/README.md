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
- VG OPS supplier seeded: `python backend/seed_demo.py`
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
| `Resolve VG SID` — "VG OPS supplier not seeded" | seed_demo not run | `python backend/seed_demo.py` |
| `Resolve VG SID` — "is_active=false" | Supplier gate | SQL UPDATE shown above |
| `OPS: Get Categories` — 401 / 403 | Bad OAuth2 cred | Re-enter client id/secret in n8n credential editor |
| `POST /ingest/*` — 401 "Invalid or missing X-Ingest-Secret" | n8n's `INGEST_SHARED_SECRET` env ≠ FastAPI's | Compare `docker exec api-hub-n8n-1 env \| grep INGEST` to the value in repo `.env`; re-run `docker compose up -d n8n` |
| `POST /ingest/*` — 409 "not active" | Supplier flipped back | SQL UPDATE above |
| `POST /ingest/*` — 500 | Uvicorn crashed — check its log |

## Network assumption

Workflow URLs use `http://host.docker.internal:8000` because FastAPI runs on the host (uvicorn) while n8n runs in Docker. If FastAPI later runs inside Docker (`docker compose up -d api`), replace every `host.docker.internal:8000` with `api:8000` across the workflow JSON (9 lines), save, re-import.

---

## `ops-push.json` — Push products from Hub → OnPrintShop (minimal)

**What it does**

1. Trigger via webhook with a `customer_id`.
2. Lists hub products via `GET /api/products`.
3. For each product, calls `GET /api/push/{customer_id}/product/{product_id}/payload` (requires `X-Ingest-Secret`) to apply markup rules.
4. Calls OPS GraphQL mutations via the custom node:
   - `setProduct` (creates/updates a product shell)
   - `setProductPrice` (creates a simple 1..999999 price band)
5. Writes an audit row to `POST /api/push-log`.

**Prerequisites**

- FastAPI running on host :8000
- n8n running: `docker compose up -d n8n`
- `INGEST_SHARED_SECRET` set in repo-root `.env` and exposed to n8n (compose already includes it)
- Create a hub customer (Storefront) in the UI and note its UUID
- In n8n, create an OnPrintShop credential named **`OPS Storefront`** (matches the workflow JSON)

**Activate + run**

1. Import `ops-push.json` in n8n.
2. Set the `OPS Storefront` credential on both OPS nodes if it didn’t auto-bind.
3. Activate the workflow (required for webhooks).
4. Trigger:
   ```bash
   curl "http://localhost:5678/webhook/ops-push?customer_id=<UUID>&limit=5"
   ```
5. Verify:
   - `GET /api/push-log` shows new rows
   - Product detail push-status shows latest per-customer status

**Notes / limitations**

- The workflow pushes to a *single* OPS credential; it does not dynamically select credentials per customer.
- It uses default `category_id=0` and `size_id=0`. If your OPS instance requires valid IDs, update the `Build OPS Inputs` code node accordingly.

---

## `ops-master-options-pull.json` — Pull master options catalog from OnPrintShop

**What it does**

1. Calls the OnPrintShop custom node `getManyMasterOptions` operation (paginated, all master-option fields + nested `attributes`).
2. Normalizes each record into the hub's `MasterOptionIngest` contract (casts IDs to int, coerces pricing fields, unwraps the `attributes[]` array).
3. POSTs the batch to `/api/ingest/master-options` with the `X-Ingest-Secret` header.
4. On HTTP error, routes the failure through a `Format Error` code node for downstream logging.

**Prerequisites**

- FastAPI running on host :8000 with the master-options ingest endpoint live.
- n8n running with the `OnPrintShop` credential configured (same cred type used by `vg-ops-pull`).
- `INGEST_SHARED_SECRET` exposed to the n8n container.

**Import**

```bash
docker cp n8n-workflows/ops-master-options-pull.json api-hub-n8n-1:/tmp/mo.json
docker exec api-hub-n8n-1 n8n import:workflow --input=/tmp/mo.json
```

## Workflow index

| File | Schedule | Flow |
|---|---|---|
| `vg-ops-pull.json` | Manual / Daily | OPS categories + products → hub `/api/ingest/{sid}/*` |
| `sanmar-sftp-pull.json` | Daily | SanMar SFTP → hub `/api/ingest/{sid}/*` |
| `ops-push.json` | Webhook | Hub `/api/push/...` → OPS `setProduct` + `setProductPrice` |
| `ops-master-options-pull.json` | Daily | OPS `getManyMasterOptions` → hub `/api/ingest/master-options` |

## Next additions (not in v1)

- `Get Stock` loop per product → POST `/api/ingest/{sid}/inventory`.
- `Get Prices` loop per product → POST `/api/ingest/{sid}/pricing`.
- Schedule Trigger (cron) parallel to the Manual Trigger for daily 3am runs. Connect it to the same `Get Suppliers` node.
- Error workflow that writes a `push_log` entry on failure.
