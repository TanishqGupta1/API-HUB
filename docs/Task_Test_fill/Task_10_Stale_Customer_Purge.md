# Task 10 — Purge Stale Test Customer Rows from Dev DB

## What This Task Did

Checked the live development database (`vg_hub`) for leaked "Test Customer" rows that previous test runs had left behind, and verified they were already gone.

**No DELETE was needed — the database was already clean.**

---

## Why This Task Exists

Every time the backend test suite runs `test_push_mappings.py`, it creates real rows in the database:

```python
Customer(name="Test Customer",  ops_base_url="https://test.ops.com",  ...)
Customer(name="Test Customer2", ops_base_url="https://test2.ops.com", ...)
Customer(name="Test Customer3", ops_base_url="https://test3.ops.com", ...)
```

Before Task 1 (Urvashi's cleanup fixture fix), the test suite had **no cleanup for customer rows** — it only cleaned up suppliers. So every pytest run leaked 3 customer rows into the dev DB. After 4 runs, that's 12 leaked rows sitting in `vg_hub` alongside real data.

This is a problem because:
- `GET /api/customers` returned 13 results instead of 1 — 12 fake, 1 real
- The frontend customer dropdown was polluted with "Test Customer" entries
- Anyone looking at the DB couldn't tell which customers were real

**The sentinel:** All leaked rows have `ops_base_url` matching `https://test.ops.com`, `https://test2.ops.com`, or `https://test3.ops.com` — a safe, unique pattern to filter on without touching real data.

---

## The Cascading Delete Rule

Customer rows have `ON DELETE CASCADE` foreign keys from three other tables:

| Table | FK Column | What cascades |
|-------|-----------|---------------|
| `push_mappings` | `customer_id` | All push mapping records for that customer |
| `markup_rules` | `customer_id` | All markup rules configured for that customer |
| `push_log` | `customer_id` | All push history for that customer |

So deleting from `customers` automatically cleans all related data. One DELETE, four tables cleaned.

---

## What Was Found

```sql
SELECT id, name, ops_base_url
FROM customers
WHERE ops_base_url IN (
  'https://test.ops.com',
  'https://test2.ops.com',
  'https://test3.ops.com'
);
```

**Result: 0 rows** — database was already clean.

### Current Customer Table (2026-04-28)

| name | ops_base_url |
|------|-------------|
| delta_product_ingest | https://demo.ops.com |
| full_catalog_push | https://demo.ops.com |
| inventory_sync_v2 | https://demo.ops.com |
| pricing_update | https://demo.ops.com |

4 real customers, zero leaked test rows. No delete required.

---

## If Rows Had Existed — The DELETE Command

> This is documented for reference. It was NOT run because 0 rows were found.

```bash
# Step 1 — always preview first
docker compose exec -T postgres psql -U vg_user -d vg_hub -c \
  "SELECT id, name, ops_base_url FROM customers
   WHERE ops_base_url IN (
     'https://test.ops.com',
     'https://test2.ops.com',
     'https://test3.ops.com'
   );"

# Step 2 — only after user confirms the row list
docker compose exec -T postgres psql -U vg_user -d vg_hub -c \
  "DELETE FROM customers
   WHERE ops_base_url IN (
     'https://test.ops.com',
     'https://test2.ops.com',
     'https://test3.ops.com'
   );"
# Expected: DELETE 12
```

**Rule:** Never run Step 2 without showing Step 1 output to the user first and getting explicit OK. This is a destructive operation on the live dev database — there is no undo.

---

## How to Verify

Prerequisites — Postgres must be running:

```bash
cd "$(git rev-parse --show-toplevel)"
docker compose up -d postgres
```

Run the check:

```bash
docker compose exec -T postgres psql -U vg_user -d vg_hub -c \
  "SELECT id, name, ops_base_url FROM customers
   WHERE ops_base_url IN (
     'https://test.ops.com',
     'https://test2.ops.com',
     'https://test3.ops.com'
   );"
```

**Expected output:**
```
 id | name | ops_base_url
----+------+--------------
(0 rows)
```

---

## Verification Result (2026-04-28)

| Check | Result |
|-------|--------|
| Sentinel rows with `ops_base_url` matching `https://test*.ops.com` | 0 found |
| Real customer rows untouched | ✅ 4 rows intact |
| No DELETE needed | ✅ DB already clean |
