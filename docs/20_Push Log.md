# Task 20 — Push Log

A "push log" in API-HUB is a record of every attempt to push a product into an OnPrintShop storefront. This task creates the database table, API schemas, and routes that let n8n write push results and let the frontend query the latest push status for any product.

Last updated: 2026-04-15

---

## Files Created

| File | Purpose |
|------|---------|
| `backend/modules/push_log/__init__.py` | Empty file — marks the directory as a Python module |
| `backend/modules/push_log/models.py` | SQLAlchemy model — defines the `product_push_log` database table |
| `backend/modules/push_log/schemas.py` | Pydantic schemas — PushLogCreate, PushLogRead, ProductPushStatus |
| `backend/modules/push_log/routes.py` | FastAPI router — 2 endpoints for writing and reading push results |

---

## Why This Task Exists

Without a push log there is no visibility into what has happened during a push workflow:

- Did this product get pushed to Acme's storefront successfully?
- When was it last pushed?
- If it failed, what was the error?
- Has it ever been pushed to this storefront at all?

The push log answers all of these questions. n8n writes one log entry per push attempt (success or failure). The frontend Sync Jobs page (Task 15) reads these logs to show the current push state for every product × customer combination.

---

## Database Table — `product_push_log`

Defined in `backend/modules/push_log/models.py`.

| Column | Type | What it stores |
|--------|------|----------------|
| `id` | UUID | Primary key, auto-generated |
| `product_id` | UUID (FK) | Which product was pushed. FK → `products.id`, cascades on delete |
| `customer_id` | UUID (FK) | Which storefront it was pushed to. FK → `customers.id`, cascades on delete |
| `ops_product_id` | String(255) | The product ID assigned by OPS after a successful push. `null` if the push failed |
| `status` | String(50) | Result of the push attempt: `"pushed"`, `"failed"`, or `"skipped"` |
| `error` | Text | Error message when `status` is `"failed"`. `null` on success |
| `pushed_at` | DateTime (UTC) | When the push attempt happened |

### Status Values

| Status | Meaning |
|--------|---------|
| `"pushed"` | Product was successfully created or updated in OPS |
| `"failed"` | Push attempt was made but OPS returned an error |
| `"skipped"` | n8n decided not to push this product (e.g. no price change, product inactive) |

### Why Both FKs CASCADE?

- If a **product** is deleted from the catalog, its push history is no longer meaningful — delete it automatically.
- If a **customer** (storefront) is deleted, their push history goes with them — no orphaned records.

---

## How the Push Status Query Works

The `GET /api/products/{product_id}/push-status` endpoint returns the **latest** push log entry per customer, not every log entry. This is intentional:

```
product_push_log (many entries over time)
  product_id = PC61, customer_id = Acme, status = pushed,  pushed_at = 09:00
  product_id = PC61, customer_id = Acme, status = failed,  pushed_at = 10:00  ← most recent
  product_id = PC61, customer_id = Acme, status = pushed,  pushed_at = 11:00  ← most recent after retry
```

The endpoint queries `.order_by(pushed_at.desc()).limit(1)` per customer, so you always see where things stand right now — not the full history.

If a product has never been pushed to a customer, that customer appears in the response with `"status": "not_pushed"` and `"pushed_at": null`.

---

## API Endpoints

Defined in `backend/modules/push_log/routes.py`.

| Method | Path | What it does |
|--------|------|--------------|
| `POST` | `/api/push-log` | Create a push log entry — called by n8n after each push attempt |
| `GET` | `/api/products/{product_id}/push-status` | Returns the latest push status for a product across all customers |

---

## How It Connects to the Rest of the System

```
products table (Task 4)           customers table (Task 18)
       │                                   │
       └──────────── product_push_log ─────┘
                          (Task 20)
                              │
                    FK: product_id → products.id
                    FK: customer_id → customers.id
```

**n8n workflow (Task 21)** calls `POST /api/push-log` after every push attempt:
- On success: `status = "pushed"`, `ops_product_id = "OPS-1234"`
- On failure: `status = "failed"`, `error = "401 Unauthorized"`

**Frontend Sync Jobs page (Task 15)** calls `GET /api/products/{id}/push-status` to show a grid of which storefronts have the product and which don't.

---

## How to Test

Make sure the backend is running and PostgreSQL is up:

```bash
docker compose up -d postgres
cd backend && source .venv/bin/activate
uvicorn main:app --reload --port 8001
```

You need a customer and a product in the database. Run the seed script if needed:

```bash
python3 seed_demo.py
```

Get a product ID from the database:

```bash
docker exec api-hub-postgres-1 psql -U vg_user -d vg_hub \
  -c "SELECT id, product_name FROM products LIMIT 3;"
```

**Log a successful push:**

```bash
curl -s -X POST http://localhost:8001/api/push-log \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "PRODUCT_ID",
    "customer_id": "CUSTOMER_ID",
    "ops_product_id": "OPS-1001",
    "status": "pushed"
  }' | python3 -m json.tool
```

Expected response:

```json
{
    "id": "...",
    "product_id": "PRODUCT_ID",
    "customer_id": "CUSTOMER_ID",
    "ops_product_id": "OPS-1001",
    "status": "pushed",
    "error": null,
    "pushed_at": "2026-04-15T..."
}
```

**Check push status for the product:**

```bash
curl -s http://localhost:8001/api/products/PRODUCT_ID/push-status | python3 -m json.tool
```

Expected response:

```json
[
    {
        "customer_id": "CUSTOMER_ID",
        "customer_name": "Acme Store",
        "ops_product_id": "OPS-1001",
        "status": "pushed",
        "pushed_at": "2026-04-15T..."
    }
]
```

**Log a failed push:**

```bash
curl -s -X POST http://localhost:8001/api/push-log \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "PRODUCT_ID",
    "customer_id": "CUSTOMER_ID",
    "status": "failed",
    "error": "OAuth token request returned 401 Unauthorized"
  }' | python3 -m json.tool
```

**Check push status again** — should now show `"failed"` since it is the most recent entry:

```bash
curl -s http://localhost:8001/api/products/PRODUCT_ID/push-status | python3 -m json.tool
```

Expected response:

```json
[
    {
        "customer_id": "CUSTOMER_ID",
        "customer_name": "Acme Store",
        "ops_product_id": null,
        "status": "failed",
        "pushed_at": "2026-04-15T..."
    }
]
```
