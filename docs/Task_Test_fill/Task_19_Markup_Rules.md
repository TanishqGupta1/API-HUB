# Task 19 — Markup Rules

## What This Task Built

A markup rule defines how much to mark up the wholesale base price before pushing a product into an OnPrintShop storefront. Each customer (storefront) can have one or more rules.

**Example:** If a product's `base_price` is $10.00 and the markup rule says 45%, the final price pushed to OPS is $14.50 (optionally rounded to $14.99 with `nearest_99`).

Rules have a `scope` so you can apply different markups to different products:
- `"all"` — applies to every product for this customer
- `"category:Tees"` — applies only to products in the Tees category
- `"product:PC61"` — applies only to the specific product with that supplier SKU

When multiple rules match, `priority` decides which one wins (higher number = higher priority).

### Files Created

| File | Purpose |
|------|---------|
| `backend/modules/markup/__init__.py` | Marks the directory as a Python module |
| `backend/modules/markup/models.py` | SQLAlchemy model — defines the `markup_rules` table |
| `backend/modules/markup/schemas.py` | Pydantic schemas — what data comes in and goes out |
| `backend/modules/markup/routes.py` | FastAPI router — 3 endpoints |

### Database Table — `markup_rules`

| Column | Type | What it stores |
|--------|------|----------------|
| `id` | UUID | Primary key, auto-generated |
| `customer_id` | UUID (FK) | Which customer (storefront) this rule belongs to. Cascades on delete — delete the customer, rules go too |
| `scope` | String | What the rule applies to: `"all"`, `"category:{name}"`, `"product:{sku}"` |
| `markup_pct` | Numeric(5,2) | Markup percentage, e.g. `45.00` means 45% over base price |
| `min_margin` | Numeric(5,2) | Optional minimum margin floor — if markup result is below this, use this instead |
| `rounding` | String | How to round the final price: `"none"`, `"nearest_99"`, `"nearest_dollar"` |
| `priority` | Integer | Higher number wins when multiple rules match the same product |
| `created_at` | DateTime | Timestamp when created |

### Dependency

This table has a **foreign key** to the `customers` table (Task 18). You must create a customer before you can create a markup rule.

---

## API Endpoints

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/api/markup-rules/{customer_id}` | List all rules for a customer, ordered by priority (highest first) |
| `POST` | `/api/markup-rules` | Create a new markup rule |
| `DELETE` | `/api/markup-rules/{rule_id}` | Delete a specific rule by its own UUID |

---

## How to Test

### Prerequisites

Backend must be running and you need a customer in the database:

```bash
cd /Users/PD/API-HUB
docker compose up -d postgres
cd backend && source .venv/bin/activate
uvicorn main:app --reload --port 8001
```

First create a customer (skip if one already exists):

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

Save the customer `id` — needed for all markup rule tests.

---

### Test 1 — Create a Markup Rule (POST)

**What it tests:** A markup rule is created and linked to the customer. All fields are returned correctly.

```bash
curl -s -X POST http://localhost:8001/api/markup-rules \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "{customer_id}",
    "scope": "all",
    "markup_pct": 45.00,
    "rounding": "nearest_99",
    "priority": 0
  }' | python3 -m json.tool
```

Replace `{customer_id}` with the actual UUID.

**Expected response:**

```json
{
    "id": "c21b3163-645a-4223-9434-8e46e32500c5",
    "customer_id": "e20a2d38-d0d7-4a3c-a3fd-992821b96109",
    "scope": "all",
    "markup_pct": 45.0,
    "min_margin": null,
    "rounding": "nearest_99",
    "priority": 0,
    "created_at": "2026-04-15T08:52:08.575927Z"
}
```

Save the rule `id` — needed for the delete test.

---

### Test 2 — Create a Second Rule with Higher Priority (POST)

**What it tests:** Multiple rules can exist for one customer. The list endpoint returns them ordered by priority (highest first).

```bash
curl -s -X POST http://localhost:8001/api/markup-rules \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "{customer_id}",
    "scope": "product:PC61",
    "markup_pct": 30.00,
    "rounding": "none",
    "priority": 10
  }' | python3 -m json.tool
```

This rule only applies to product SKU `PC61` and overrides the 45% "all" rule due to higher priority.

---

### Test 3 — List Markup Rules for a Customer (GET)

**What it tests:** Returns all rules for the customer, highest priority first. If you created both rules above, the `PC61`-specific rule (priority 10) should appear before the "all" rule (priority 0).

```bash
curl -s http://localhost:8001/api/markup-rules/{customer_id} | python3 -m json.tool
```

**Expected response:** Array of rules ordered by priority descending.

---

### Test 4 — Delete a Markup Rule (DELETE)

**What it tests:** A specific rule is deleted by its own UUID. Returns 404 if not found.

```bash
curl -s -X DELETE http://localhost:8001/api/markup-rules/{rule_id} | python3 -m json.tool
```

Replace `{rule_id}` with the rule's `id` from Test 1.

**Expected response:**

```json
{
    "deleted": true
}
```

Run Test 3 again after deleting — the deleted rule should be gone from the list.

---

### Test 5 — Cascade Delete (Customer Delete Removes Rules)

**What it tests:** When a customer is deleted, all their markup rules are automatically deleted too (CASCADE).

```bash
# Delete the customer
curl -s -X DELETE http://localhost:8001/api/customers/{customer_id} | python3 -m json.tool

# Try to list their markup rules — should return empty array []
curl -s http://localhost:8001/api/markup-rules/{customer_id} | python3 -m json.tool
```

**Expected:** `[]` — no rules remain after the customer is deleted.

---

## Test Results (2026-04-15)

| Test | Result |
|------|--------|
| POST /api/markup-rules — rule created with correct fields | ✅ PASS |
| GET /api/markup-rules/{customer_id} — returns rules for customer | ✅ PASS |
| DELETE /api/markup-rules/{rule_id} — deletes specific rule | not yet run |
| Cascade delete when customer is removed | not yet run |
