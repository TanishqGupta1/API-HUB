# Task 18 — Customer Model (OAuth2)

A "customer" in API-HUB is an OnPrintShop (OPS) storefront. This task creates the database table, API schemas, and CRUD routes that store each storefront's OAuth2 credentials — encrypted — so n8n can authenticate and push products into it.

Last updated: 2026-04-15

---

## Files Created

| File | Purpose |
|------|---------|
| `backend/modules/customers/__init__.py` | Empty file — marks the directory as a Python module |
| `backend/modules/customers/models.py` | SQLAlchemy model — defines the `customers` database table |
| `backend/modules/customers/schemas.py` | Pydantic schemas — controls what data comes in and goes out of the API |
| `backend/modules/customers/routes.py` | FastAPI router — 4 CRUD endpoints for managing customers |

---

## Why This Task Exists

The platform's job is to push products from supplier catalogs into OnPrintShop storefronts. Each storefront (customer) is a separate OPS instance with its own OAuth2 credentials. When n8n runs the push workflow, it needs to:

1. Look up the storefront's OAuth2 details
2. Exchange client credentials for an access token
3. Use that token to call `setProduct` and `setProductPrice` on that specific OPS instance

Those credentials (especially the `client_secret`) must never be stored as plain text in the database. This task solves that with the same `EncryptedJSON` pattern used for supplier credentials in Task 3.

---

## Database Table — `customers`

Defined in `backend/modules/customers/models.py`.

| Column | Type | What it stores |
|--------|------|----------------|
| `id` | UUID | Primary key, auto-generated |
| `name` | String(255) | Human-readable storefront name, e.g. "Acme Corp Store" |
| `ops_base_url` | Text | The OPS GraphQL API root URL for this storefront |
| `ops_token_url` | Text | The OAuth2 token endpoint URL — where to exchange credentials for an access token |
| `ops_client_id` | String(255) | OAuth2 client ID — not secret, stored as plain text |
| `ops_auth_config` | EncryptedJSON | Stores `{"client_secret": "..."}` — encrypted at rest using Fernet AES-128 |
| `is_active` | Boolean | Soft toggle — disable a customer without deleting it |
| `created_at` | DateTime (UTC) | Timestamp when the record was created |

### Why `ops_auth_config` instead of a plain `ops_client_secret` column?

The `EncryptedJSON` column type (defined in `backend/database.py`) transparently encrypts any dict before saving and decrypts on read. Storing the secret inside a JSON dict means:

- The same pattern is used across the whole platform (supplier credentials use the same approach)
- The column can hold additional fields in future (e.g. refresh tokens) without a schema migration
- If the `SECRET_KEY` env var is not set in local dev, it falls back to plain JSON — no crash

---

## How the Secret is Protected — Write-Only Flow

The `client_secret` goes in but never comes back out. Here is how:

```
POST /api/customers
  body: { "ops_client_secret": "abc123", ... }
       ↓
CustomerCreate schema (schemas.py)
  accepts ops_client_secret as a plain field
       ↓
routes.py create_customer()
  builds Customer(ops_auth_config={"client_secret": body.ops_client_secret})
  — the secret is now inside an EncryptedJSON column
       ↓
Database stores: gAAAAA... (Fernet-encrypted blob)
       ↓
GET /api/customers or GET /api/customers/{id}
  returns CustomerRead schema
  — CustomerRead has no ops_auth_config or ops_client_secret field
  — the secret is never included in any API response
```

This means the secret is **write-only**. Once saved, even an admin reading the API cannot retrieve it — they would need direct DB access plus the `SECRET_KEY`.

---

## API Endpoints

Defined in `backend/modules/customers/routes.py`. Router prefix: `/api/customers`.

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/api/customers` | List all customers, ordered by creation date (newest first) |
| `POST` | `/api/customers` | Create a new customer — encrypts the client secret before saving |
| `GET` | `/api/customers/{customer_id}` | Get one customer by UUID — returns 404 if not found |
| `DELETE` | `/api/customers/{customer_id}` | Delete a customer — returns 404 if not found |

> **Note:** `PUT /api/customers/{id}` (update) is not implemented yet. It will be added when the Customers frontend page (Task 13) is built.

---

## How It Connects to the Rest of the System

```
customers table (Task 18)
       │
       ├── markup_rules table (Task 19)
       │     FK: markup_rules.customer_id → customers.id
       │     Each storefront can have its own markup percentage and pricing rules
       │
       └── product_push_log table (Task 20)
             FK: product_push_log.customer_id → customers.id
             Every OPS push attempt is logged per product per customer
```

**n8n workflow (Task 21)** will query `GET /api/customers` to get the list of storefronts to push into, then for each one:
1. Read `ops_token_url` and `ops_client_id` from the API response
2. Read `ops_auth_config.client_secret` directly from the database (n8n has DB access, or a dedicated internal endpoint will be added)
3. Authenticate and push products

---

## How to Test

Make sure the backend is running and PostgreSQL is up:

```bash
docker compose up -d postgres
cd backend && source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

**Create a customer:**

```bash
curl -s -X POST http://localhost:8000/api/customers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp Store",
    "ops_base_url": "https://acme.onprintshop.com/graphql",
    "ops_token_url": "https://acme.onprintshop.com/oauth/token",
    "ops_client_id": "acme_client_id",
    "ops_client_secret": "super_secret_value"
  }' | python3 -m json.tool
```

Expected response — note `ops_client_secret` is absent:

```json
{
  "id": "...",
  "name": "Acme Corp Store",
  "ops_base_url": "https://acme.onprintshop.com/graphql",
  "ops_token_url": "https://acme.onprintshop.com/oauth/token",
  "ops_client_id": "acme_client_id",
  "is_active": true,
  "created_at": "2026-04-15T..."
}
```

**List all customers:**

```bash
curl -s http://localhost:8000/api/customers | python3 -m json.tool
```

**Verify secret is encrypted in the database (not plain text):**

```bash
docker exec $(docker ps -qf "name=postgres") \
  psql -U vg_user -d vg_hub \
  -c "SELECT name, ops_client_id, ops_auth_config FROM customers;"
# ops_auth_config column should show a Fernet blob (gAAAAA...), not plain JSON
```
