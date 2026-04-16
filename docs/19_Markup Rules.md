# Task 19 — Markup Rules

A "markup rule" in API-HUB defines how much to mark up the wholesale base price before pushing a product into an OnPrintShop storefront. This task creates the database table, API schemas, and CRUD routes that store per-customer pricing rules so n8n can calculate the correct final price for each storefront.

Last updated: 2026-04-15

---

## Files Created

| File | Purpose |
|------|---------|
| `backend/modules/markup/__init__.py` | Empty file — marks the directory as a Python module |
| `backend/modules/markup/models.py` | SQLAlchemy model — defines the `markup_rules` database table |
| `backend/modules/markup/schemas.py` | Pydantic schemas — controls what data comes in and goes out of the API |
| `backend/modules/markup/routes.py` | FastAPI router — 3 endpoints for managing markup rules |

---

## Why This Task Exists

Different OnPrintShop storefronts sell at different price points. One storefront might mark up wholesale prices by 30%, another by 55%. Some storefronts may want a different markup for specific product categories or individual products (e.g. a higher margin on branded polos than basic tees).

When n8n runs the push workflow, it needs to:

1. Look up the markup rules for each storefront (`GET /api/markup-rules/{customer_id}`)
2. Find the rule that matches the product being pushed (by scope and priority)
3. Calculate `final_price = base_price × (1 + markup_pct / 100)`
4. Apply rounding if configured (e.g. round to nearest $.99)
5. Push that final price to OPS via `setProductPrice`

Without markup rules, every storefront would get the raw wholesale price — which is not how retail works.

---

## Database Table — `markup_rules`

Defined in `backend/modules/markup/models.py`.

| Column | Type | What it stores |
|--------|------|----------------|
| `id` | UUID | Primary key, auto-generated |
| `customer_id` | UUID (FK) | Which storefront this rule belongs to. FK → `customers.id`, cascades on delete |
| `scope` | String(50) | What the rule applies to: `"all"`, `"category:Tees"`, `"product:PC61"` |
| `markup_pct` | Numeric(5,2) | Markup percentage — e.g. `45.00` means 45% over base price |
| `min_margin` | Numeric(5,2) | Optional minimum margin floor. If the markup result is too low, use this instead |
| `rounding` | String(20) | How to round the final price: `"none"`, `"nearest_99"`, `"nearest_dollar"` |
| `priority` | Integer | When multiple rules match a product, highest priority wins |
| `created_at` | DateTime (UTC) | Timestamp when the record was created |

### How `scope` Works

| Scope value | What it matches |
|-------------|----------------|
| `"all"` | Every product pushed to this storefront |
| `"category:Tees"` | Only products whose category is "Tees" |
| `"product:PC61"` | Only the product with supplier SKU "PC61" |

When multiple rules match (e.g. an `"all"` rule and a `"product:PC61"` rule both apply), the one with the highest `priority` value wins.

### Why `CASCADE` on Delete?

If a customer (storefront) is deleted, all their markup rules are automatically deleted too. There is no point keeping pricing rules for a storefront that no longer exists in the system.

---

## API Endpoints

Defined in `backend/modules/markup/routes.py`. Router prefix: `/api/markup-rules`.

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/api/markup-rules/{customer_id}` | List all rules for a customer, ordered by priority (highest first) |
| `POST` | `/api/markup-rules` | Create a new markup rule for a customer |
| `DELETE` | `/api/markup-rules/{rule_id}` | Delete a specific rule by its own UUID |

> **Note:** `PUT /api/markup-rules/{id}` (update) is not implemented yet. To change a rule, delete it and create a new one.

---

## How It Connects to the Rest of the System

```
customers table (Task 18)
       │
       └── markup_rules table (Task 19)
             FK: markup_rules.customer_id → customers.id
             Each storefront can have multiple rules with different scopes and priorities
```

**n8n workflow (Task 21)** will:
1. Call `GET /api/markup-rules/{customer_id}` to get the pricing rules for a storefront
2. Find the highest-priority rule that matches the current product
3. Calculate `final_price = base_price × (1 + markup_pct / 100)`
4. Apply rounding as configured
5. Push `final_price` to OPS via `setProductPrice`

---

## How to Test

Make sure the backend is running and PostgreSQL is up:

```bash
docker compose up -d postgres
cd backend && source .venv/bin/activate
uvicorn main:app --reload --port 8001
```

**First create a customer** (markup rules require a customer to attach to):

```bash
curl -s -X POST http://localhost:8001/api/customers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp Store",
    "ops_base_url": "https://acme.onprintshop.com/graphql",
    "ops_token_url": "https://acme.onprintshop.com/oauth/token",
    "ops_client_id": "acme_client_id",
    "ops_client_secret": "super_secret_value"
  }' | python3 -m json.tool
```

Copy the `id` from the response.

**Create a catch-all markup rule (45% on everything):**

```bash
curl -s -X POST http://localhost:8001/api/markup-rules \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUSTOMER_ID",
    "scope": "all",
    "markup_pct": 45.00,
    "rounding": "nearest_99",
    "priority": 0
  }' | python3 -m json.tool
```

Expected response:

```json
{
    "id": "...",
    "customer_id": "CUSTOMER_ID",
    "scope": "all",
    "markup_pct": 45.0,
    "min_margin": null,
    "rounding": "nearest_99",
    "priority": 0,
    "created_at": "2026-04-15T..."
}
```

**Create a higher-priority rule for a specific product (30% on PC61 only):**

```bash
curl -s -X POST http://localhost:8001/api/markup-rules \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUSTOMER_ID",
    "scope": "product:PC61",
    "markup_pct": 30.00,
    "rounding": "none",
    "priority": 10
  }' | python3 -m json.tool
```

**List all rules for the customer** (highest priority first):

```bash
curl -s http://localhost:8001/api/markup-rules/CUSTOMER_ID | python3 -m json.tool
# PC61-specific rule (priority 10) appears before the "all" rule (priority 0)
```

**Delete a rule:**

```bash
curl -s -X DELETE http://localhost:8001/api/markup-rules/RULE_ID | python3 -m json.tool
# Expected: {"deleted": true}
```

**Verify cascade delete — delete the customer and check rules are gone:**

```bash
curl -s -X DELETE http://localhost:8001/api/customers/CUSTOMER_ID | python3 -m json.tool
curl -s http://localhost:8001/api/markup-rules/CUSTOMER_ID | python3 -m json.tool
# Expected: [] — rules deleted automatically with the customer
```
