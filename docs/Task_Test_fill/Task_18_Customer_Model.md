# Task 18 — Customer Model (OAuth2)

## What This Task Built

A "customer" in API-HUB is an OnPrintShop (OPS) storefront — the destination where products get pushed into.
This task created the database table and API endpoints to store each storefront's OAuth2 credentials **encrypted**.

When n8n runs a push workflow, it needs to:
1. Look up the storefront's OAuth2 details (token URL, client ID)
2. Use the encrypted `client_secret` to get an access token
3. Push products into that specific OPS storefront

### Files Created

| File | Purpose |
|------|---------|
| `backend/modules/customers/__init__.py` | Marks the directory as a Python module |
| `backend/modules/customers/models.py` | SQLAlchemy model — defines the `customers` table |
| `backend/modules/customers/schemas.py` | Pydantic schemas — what data comes in and goes out |
| `backend/modules/customers/routes.py` | FastAPI router — 4 CRUD endpoints |

### Database Table — `customers`

| Column | Type | What it stores |
|--------|------|----------------|
| `id` | UUID | Primary key, auto-generated |
| `name` | String | Human-readable storefront name, e.g. "Acme Corp Store" |
| `ops_base_url` | Text | OPS GraphQL API URL for this storefront |
| `ops_token_url` | Text | OAuth2 token endpoint URL |
| `ops_client_id` | String | OAuth2 client ID — not secret, stored plain |
| `ops_auth_config` | EncryptedJSON | Stores `{"client_secret": "..."}` — encrypted with Fernet AES-128 |
| `is_active` | Boolean | Soft toggle — disable without deleting |
| `created_at` | DateTime | Timestamp when created |

### Why the Secret Is Never Returned

The `client_secret` is **write-only**:

```
POST /api/customers  →  body includes ops_client_secret (plain text)
                    ↓
        routes.py saves it as ops_auth_config={"client_secret": "..."}
                    ↓
        Database stores: gAAAAA... (Fernet-encrypted blob)
                    ↓
GET /api/customers  →  response has NO ops_client_secret or ops_auth_config
```

Once saved, the secret cannot be retrieved through the API. Only someone with direct DB access AND the `SECRET_KEY` env var can read it.

---

## API Endpoints

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/api/customers` | List all customers |
| `POST` | `/api/customers` | Create a new customer — encrypts the client secret |
| `GET` | `/api/customers/{id}` | Get one customer by UUID |
| `DELETE` | `/api/customers/{id}` | Delete a customer |

---

## How to Test

### Prerequisites

Backend must be running:

```bash
cd "$(git rev-parse --show-toplevel)"
docker compose up -d postgres
cd backend && source .venv/bin/activate
uvicorn main:app --reload --port 8001
```

---

### Test 1 — Create a Customer (POST)

**What it tests:** Customer is created successfully. The `ops_client_secret` you send is NOT returned in the response — it has been encrypted and stored in `ops_auth_config`.

```bash
curl -s -X POST http://localhost:8001/api/customers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Store",
    "ops_base_url": "https://test.onprintshop.com/graphql",
    "ops_token_url": "https://test.onprintshop.com/oauth/token",
    "ops_client_id": "test_client",
    "ops_client_secret": "test_secret"
  }' | python3 -m json.tool
```

**Expected response** — notice `ops_client_secret` is absent:

```json
{
    "id": "e20a2d38-d0d7-4a3c-a3fd-992821b96109",
    "name": "Test Store",
    "ops_base_url": "https://test.onprintshop.com/graphql",
    "ops_token_url": "https://test.onprintshop.com/oauth/token",
    "ops_client_id": "test_client",
    "is_active": true,
    "created_at": "2026-04-15T08:47:35.767757Z"
}
```

Save the `id` — you will need it for the next tests.

---

### Test 2 — List All Customers (GET)

**What it tests:** The list endpoint returns all customers. The secret is still not exposed.

```bash
curl -s http://localhost:8001/api/customers | python3 -m json.tool
```

**Expected response:** Array containing the customer you just created.

---

### Test 3 — Get One Customer (GET by ID)

**What it tests:** Fetch a single customer by UUID. Returns 404 if the ID does not exist.

```bash
curl -s http://localhost:8001/api/customers/{id} | python3 -m json.tool
```

Replace `{id}` with the actual UUID from Test 1.

**Expected response:** Same fields as the list — no secret exposed.

---

### Test 4 — Delete a Customer (DELETE)

**What it tests:** Customer is deleted. Returns `{"deleted": true}`. Returns 404 if not found.

```bash
curl -s -X DELETE http://localhost:8001/api/customers/{id} | python3 -m json.tool
```

**Expected response:**

```json
{
    "deleted": true
}
```

After deleting, run Test 2 again — the list should be empty.

---

### Test 5 — Verify Secret Is Encrypted in the Database

**What it tests:** Confirms the `ops_auth_config` column stores a Fernet blob (starting with `gAAAAA...`), not plain JSON.

```bash
docker exec $(docker ps -qf "name=postgres") \
  psql -U vg_user -d vg_hub \
  -c "SELECT name, ops_client_id, ops_auth_config FROM customers;"
```

**Expected:** The `ops_auth_config` column shows `gAAAAA...`, not `{"client_secret": "test_secret"}`.

---

## Test Results (2026-04-15)

| Test | Result |
|------|--------|
| POST /api/customers — secret not in response | ✅ PASS |
| GET /api/customers — lists all customers | ✅ PASS |
| GET /api/customers/{id} — returns single customer | ✅ PASS |
| DELETE /api/customers/{id} — deletes customer | ✅ PASS |
