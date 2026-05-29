# Bug — `is_synthetic` Column Missing from Schema Migration

**Date found:** 2026-05-15
**Severity:** Blocking (all integration key lookups failed in tests)
**Status:** ✅ Fixed
**Commit:** `29b7308`
**File fixed:** `backend/main.py`

---

## What was the bug?

When running the test suite after setting up the database from scratch, every test that tried to look up an `IntegrationKey` by its hash crashed with:

```
sqlalchemy.exc.ProgrammingError:
column integration_keys.is_synthetic does not exist
[SQL: SELECT integration_keys.id, ..., integration_keys.is_synthetic, ...
 FROM integration_keys
 WHERE integration_keys.key_hash = $1 AND integration_keys.is_synthetic = false]
```

The `integration_keys` table existed (it was created by `Base.metadata.create_all`), but it was missing the `is_synthetic` column. The query was trying to filter by a column that didn't exist in the database.

---

## Why did this happen?

### Two ways schema changes happen in this project

This project uses two mechanisms to update the database schema:

1. **`Base.metadata.create_all`** — creates tables that don't exist yet. If the table already exists, it does nothing. This runs at startup.

2. **`_SCHEMA_UPGRADES` list in `main.py`** — a list of raw SQL statements that run at startup. Each statement must be idempotent (safe to run multiple times, like using `IF NOT EXISTS`). This is how you add columns to existing tables.

The second mechanism is needed because `create_all` only creates, it doesn't alter. Once the `integration_keys` table exists (from a previous deployment), `create_all` won't add new columns to it.

### What went wrong

When the `IntegrationKey` model was first written (Task 1, 2026-05-13), it had these columns:
```python
id, key_hash, name, allowed_customer_ids, allowed_supplier_slugs,
rate_limit_per_minute, is_active, last_used_at, created_at, revoked_at
```

Later, the `is_synthetic` column was added to the model:
```python
is_synthetic: Mapped[bool] = mapped_column(
    Boolean, default=False, server_default="false"
)
```

Someone added the column to the Python model but **forgot to add the corresponding `ALTER TABLE` statement to `_SCHEMA_UPGRADES`**. 

For a brand-new database, `create_all` creates the table with `is_synthetic` included — no problem. But for a database that was created before `is_synthetic` was added (like a test database, or a production database), the column is missing. SQLAlchemy generates queries that reference `is_synthetic` (because it's in the model), and the database rejects them.

### Why it showed up in tests

The test runner uses a PostgreSQL database. On the developer's machine, the test database had been created before `is_synthetic` was added to the model. The `_create_schema` fixture in `conftest.py` calls:
```python
await conn.run_sync(Base.metadata.create_all)
for stmt in _SCHEMA_UPGRADES:
    await conn.execute(text(stmt))
```

`create_all` saw the `integration_keys` table already existed and did nothing. The `_SCHEMA_UPGRADES` loop ran but had no statement for `is_synthetic`. Result: column missing, query fails.

---

## How does this connect to the existing codebase?

The `is_synthetic` column exists for a specific security reason.

The Integration Gateway routes need to look up an `IntegrationKey` by the hash of the `X-Orchestrator-Key` header. The auth query looks like:
```sql
SELECT * FROM integration_keys
WHERE key_hash = $1
AND is_synthetic = FALSE
```

The `is_synthetic = FALSE` filter is critical. There is a special synthetic key called `_admin_ui_proxy` that the admin UI uses internally. This key's hash is a hardcoded string that is never derived from a real `token_urlsafe` value. If external orchestrators could forge this key, they could bypass the scope checks that normally restrict keys to specific customers and suppliers.

By filtering `WHERE is_synthetic = FALSE`, the external key lookup path completely ignores the synthetic key. An external caller who somehow knew the admin proxy key's stored hash couldn't use it to get an `OrchestratorKey` object.

This means: if `is_synthetic` is missing from the DB, no integration key lookup works at all. Every `POST /api/integrations/v1/push-requests` call returns a database error before it even reaches the auth check.

See `backend/modules/integrations/models.py` for the column definition, and `backend/modules/integrations/auth.py` for where the filter is applied.

---

## The fix

Added one line to `_SCHEMA_UPGRADES` in `backend/main.py`:

```python
"ALTER TABLE integration_keys ADD COLUMN IF NOT EXISTS is_synthetic BOOLEAN NOT NULL DEFAULT FALSE",
```

`IF NOT EXISTS` means this statement is safe to run on any database:
- If the column already exists (new database created by `create_all`): no-op
- If the column is missing (older database): adds it with a default of `FALSE`

The `DEFAULT FALSE` is important — existing rows in the table should not be treated as synthetic. All real orchestrator keys have `is_synthetic=False`.

---

## How can this be prevented in the future?

The root cause is that there's no automated check to verify that every column in the Python model has a corresponding migration in `_SCHEMA_UPGRADES`. 

A few ways to reduce the chance of this happening again:

1. **Team practice:** When adding a column to a SQLAlchemy model, immediately check if there's a corresponding migration. Make it part of the PR checklist.

2. **Test database reset:** If the test DB is always created fresh (drop and recreate before tests), `create_all` handles everything and the migration gap only affects existing databases. The downside is slower test startup.

3. **Alembic:** The project could adopt Alembic (a proper migration tool for SQLAlchemy). Alembic generates versioned migration files and tracks which ones have run. This makes it impossible to add a column without generating a migration. The trade-off is more tooling overhead.

For now, the `_SCHEMA_UPGRADES` approach works well — it just requires discipline to add a migration for every model change.
