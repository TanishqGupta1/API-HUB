# Task 20 — Push Log

## What This Task Built

Every time n8n pushes a product into an OnPrintShop storefront, the result is logged in the `product_push_log` table. This gives you a full audit trail of what was pushed, when, and whether it succeeded or failed.

**Why this matters:** Without a push log, there's no way to know:
- Which products have been successfully pushed to which storefronts
- Which pushes failed and why (e.g. OAuth error, API timeout)
- Whether a product is out of date in a storefront and needs re-pushing

The push-status endpoint lets the frontend (and n8n) query the latest push result for any product across all customers in one call.

### Files Created

| File | Purpose |
|------|---------|
| `backend/modules/push_log/__init__.py` | Marks the directory as a Python module |
| `backend/modules/push_log/models.py` | SQLAlchemy model — defines the `product_push_log` table |
| `backend/modules/push_log/schemas.py` | Pydantic schemas — PushLogCreate, PushLogRead, ProductPushStatus |
| `backend/modules/push_log/routes.py` | FastAPI router — 2 endpoints |

### Database Table — `product_push_log`

| Column | Type | What it stores |
|--------|------|----------------|
| `id` | UUID | Primary key, auto-generated |
| `product_id` | UUID (FK) | Which product was pushed. FK → `products.id`, CASCADE on delete |
| `customer_id` | UUID (FK) | Which storefront it was pushed to. FK → `customers.id`, CASCADE on delete |
| `ops_product_id` | String | The product ID assigned by OPS after a successful push. Null if push failed |
| `status` | String | Result: `"pushed"`, `"failed"`, or `"skipped"` |
| `error` | Text | Error message if status is `"failed"`. Null on success |
| `pushed_at` | DateTime | When the push attempt happened |

### How It Connects to the Rest of the System

- **FK → products** (Task 4): Each log entry is tied to a specific product
- **FK → customers** (Task 18): Each log entry is tied to a specific storefront
- **n8n (Task 21)** calls `POST /api/push-log` after every push attempt to record the result
- **Frontend (Task 15 — Sync Jobs)** calls `GET /api/products/{id}/push-status` to show push state per storefront

---

## API Endpoints

| Method | Path | What it does |
|--------|------|--------------|
| `POST` | `/api/push-log` | Create a new log entry — called by n8n after each push attempt |
| `GET` | `/api/products/{product_id}/push-status` | Returns the latest push status for a product across all customers |

---

## How to Test

### Prerequisites

Backend running, at least one customer and one product in the database:

```bash
cd /Users/PD/API-HUB/backend && source .venv/bin/activate
uvicorn main:app --reload --port 8001
```

Get a customer ID:

```bash
curl -s http://localhost:8001/api/customers | python3 -m json.tool
```

Get a product ID from the database:

```bash
docker exec api-hub-postgres-1 psql -U vg_user -d vg_hub \
  -c "SELECT id, product_name FROM products LIMIT 3;"
```

Or run the seed script if no products exist:

```bash
python3 seed_demo.py
```

---

### Test 1 — Log a Successful Push (POST)

**What it tests:** n8n successfully pushed a product to OPS and logs the result. `ops_product_id` is the ID assigned by OPS.

```bash
curl -s -X POST http://localhost:8001/api/push-log \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "{product_id}",
    "customer_id": "{customer_id}",
    "ops_product_id": "OPS-1001",
    "status": "pushed"
  }' | python3 -m json.tool
```

**Expected response:**

```json
{
    "id": "1d3cb94e-09bf-407e-a106-02c740f96470",
    "product_id": "4ff584d1-cfef-4a42-a7d0-9e4246dfd4bd",
    "customer_id": "0bfc26ef-7e74-418c-9da6-152393abbc44",
    "ops_product_id": "OPS-1001",
    "status": "pushed",
    "error": null,
    "pushed_at": "2026-04-15T09:27:17.950361Z"
}
```

---

### Test 2 — Check Push Status (GET)

**What it tests:** Returns the latest push log entry per customer for the given product. If a product has never been pushed to a customer, that customer shows `"status": "not_pushed"`.

```bash
curl -s http://localhost:8001/api/products/{product_id}/push-status | python3 -m json.tool
```

**Expected response** after Test 1:

```json
[
    {
        "customer_id": "0bfc26ef-7e74-418c-9da6-152393abbc44",
        "customer_name": "Acme Store",
        "ops_product_id": "OPS-1001",
        "status": "pushed",
        "pushed_at": "2026-04-15T09:27:17.950361Z"
    }
]
```

---

### Test 3 — Log a Failed Push (POST)

**What it tests:** Push failed (e.g. OAuth error). The `error` field captures the reason. `ops_product_id` is null since OPS never received the product.

```bash
curl -s -X POST http://localhost:8001/api/push-log \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "{product_id}",
    "customer_id": "{customer_id}",
    "status": "failed",
    "error": "OAuth token request returned 401 Unauthorized"
  }' | python3 -m json.tool
```

**Expected response:**

```json
{
    "id": "c7984b27-4872-43f0-bdcb-3372f79f2169",
    "product_id": "4ff584d1-cfef-4a42-a7d0-9e4246dfd4bd",
    "customer_id": "0bfc26ef-7e74-418c-9da6-152393abbc44",
    "ops_product_id": null,
    "status": "failed",
    "error": "OAuth token request returned 401 Unauthorized",
    "pushed_at": "2026-04-15T09:27:55.993361Z"
}
```

---

### Test 4 — Push Status Shows Most Recent Entry (GET)

**What it tests:** The push-status endpoint always returns the **latest** log entry per customer, not all of them. After logging a failure in Test 3, the status should now show `"failed"` — not the earlier `"pushed"`.

```bash
curl -s http://localhost:8001/api/products/{product_id}/push-status | python3 -m json.tool
```

**Expected response** — status updated to `failed`:

```json
[
    {
        "customer_id": "0bfc26ef-7e74-418c-9da6-152393abbc44",
        "customer_name": "Acme Store",
        "ops_product_id": null,
        "status": "failed",
        "pushed_at": "2026-04-15T09:27:55.993361Z"
    }
]
```

---

## Test Results (2026-04-15)

| Test | Result |
|------|--------|
| POST /api/push-log — log successful push | ✅ PASS |
| GET /api/products/{id}/push-status — shows pushed status | ✅ PASS |
| POST /api/push-log — log failed push with error message | ✅ PASS |
| GET /api/products/{id}/push-status — updated to failed | ✅ PASS |
