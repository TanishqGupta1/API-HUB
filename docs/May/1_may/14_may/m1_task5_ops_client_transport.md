# M1 — Task 5: OPS GraphQL Client Transport

**Owner:** Vidhi
**Status:** Done (2026-05-14)
**Plan:** `docs/superpowers/plans/2026-05-14-centralized-fastapi-ops-m1.md`
**Phase:** M1.1 — `ops_client` Module (Task 5 of 25)

---

## What is this task?

Task 5 creates the **foundational transport layer** for talking directly to OnPrintShop's GraphQL API from Python. It's the first file in the new `backend/modules/ops_client/` module.

Before this task, there was **zero Python code** in the project that could call OPS GraphQL mutations. All OPS communication went through n8n workflows (JSON files). This task builds the "phone line" — the next tasks (T6–T9) will use it to make the actual calls.

---

## Why is it important?

### 1. It's the foundation for the entire M1 migration

Every task in M1.1 builds on top of this:

| Task | What it needs from T5 |
|------|-----------------------|
| **T6** — `set_product_category` | Uses `OpsGraphQLClient.execute()` to send the mutation |
| **T7** — `set_product` | Same — sends mutation via `execute()` |
| **T8** — `set_product_size` | Same |
| **T9** — `set_product_price` | Same |
| **T11** — orchestrator | Calls all four wrappers, which all go through this client |

Without T5, none of those tasks can be built.

### 2. It replaces n8n's OPS connection

Today the OPS connection lives inside n8n's custom `n8n-nodes-onprintshop` node. After T5, Python owns the connection. This means:
- Push logic becomes **testable** (unit tests, not n8n execution logs)
- Push logic becomes **debuggable** (Python stack traces, not workflow JSON)
- Push logic becomes **reusable** (any endpoint can push, not just n8n webhooks)

### 3. Security: frozen credentials

`OpsAuth` is a frozen dataclass — once created, credentials can't be accidentally overwritten. This prevents a class of bugs where middleware or logging accidentally mutates the auth object.

---

## How does it connect to the existing codebase?

The customer's OPS credentials are **already stored** in the database (from Phase 3):

```
customers.ops_base_url      → OpsAuth.base_url
customers.ops_token_url     → OpsAuth.token_url
customers.ops_client_id     → OpsAuth.client_id
customers.ops_auth_config   → {"client_secret": "..."} (encrypted via Fernet)
```

See: `backend/modules/customers/models.py` — the `Customer` model already has these columns.

The new client **reads** these credentials and uses them to get an OAuth token and call GraphQL. It doesn't modify the database at all.

---

## What was done

### Files created

#### `backend/modules/ops_client/__init__.py`

Package marker. One line — tells Python this folder is an importable module.

#### `backend/modules/ops_client/client.py`

Three pieces inside:

| Piece | Type | Purpose |
|-------|------|---------|
| `OpsAuth` | Frozen dataclass | Holds the 4 OAuth credentials. Immutable after creation. |
| `OpsResult` | Frozen dataclass | Holds every response: `ok` (bool), `data` (dict), `ops_error_code`, `ops_error_message`, `raw`. Never raises exceptions. |
| `OpsGraphQLClient` | Class | The transport. Two methods: `_get_token()` (OAuth login + cache) and `execute(query, variables)` (send GraphQL, return `OpsResult`). |

##### Why `OpsResult` never raises exceptions

The push orchestrator (T11) needs to check each mutation step:
```python
# In push.py (T11), the orchestrator does:
result = await client.execute(set_category_query, variables={...})
if not result.ok:
    return {"status": "failed", "error": result.ops_error_message}
# Otherwise, thread the category_id to the next step
category_id = result.data["setProductCategory"]["category_id"]
```

If `execute()` raised exceptions, this would become messy `try/except` blocks. Returning `OpsResult` keeps the control flow clean.

##### How OAuth token caching works

```
First call to _get_token():
  → POST client_id + client_secret to token_url
  → Get back access_token (valid ~1 hour)
  → Cache token + expiry time in memory

Subsequent calls to _get_token():
  → Check: is cached token still valid (>30s before expiry)?
  → YES → return cached token (no HTTP call)
  → NO  → fetch new token, update cache
```

The 30-second buffer prevents edge cases where a token expires mid-request.

#### `backend/tests/test_ops_client_transport.py`

6 unit tests following TDD (written before implementation):

| Test | What it verifies |
|------|-----------------|
| `test_ops_auth_is_frozen_dataclass` | Cannot modify credentials after creation |
| `test_ops_result_success` | Success result carries data correctly |
| `test_ops_result_error` | Error result carries error code + message |
| `test_ops_result_is_frozen` | Cannot modify results after creation |
| `test_client_constructable` | Client can be created with an OpsAuth |
| `test_client_has_graphql_path` | GraphQL path is `/graphql` |

---

## Verification

```bash
# Test run — all 6 pass
cd backend && source .venv/bin/activate && pytest tests/test_ops_client_transport.py -v

# Output:
# test_ops_auth_is_frozen_dataclass PASSED
# test_ops_result_success PASSED
# test_ops_result_error PASSED
# test_ops_result_is_frozen PASSED
# test_client_constructable PASSED
# test_client_has_graphql_path PASSED
# ========================= 6 passed in 0.77s =========================

# Import check — module is loadable
python -c "from modules.ops_client.client import OpsAuth, OpsResult, OpsGraphQLClient; print('✅ Import works')"
# → ✅ Import works
```

**Note:** The IDE may show a red squiggle on `import httpx` (Pyrefly `missing-import`). This is an IDE config issue — httpx 0.28.1 is installed in the project venv at `backend/.venv/`. Fix by pointing VS Code interpreter to `backend/.venv/bin/python`.

---

## How it can change in the future

- **Retry logic** — Add automatic retry on HTTP 429 (rate limited) or 503 (OPS down)
- **Connection pooling** — Reuse `httpx.AsyncClient` across multiple `execute()` calls instead of creating a new one each time
- **Multiple API versions** — If OPS introduces `/graphql/v2`, add version selection to `OpsAuth`
- **Standalone package** — Could be extracted into a `pip install ops-client` package if other services need OPS access

---

## What's next

T5 unblocks the mutation wrappers. Execution order:

| Task | Owner | Status | Blocked by |
|------|-------|--------|-----------|
| T5 — OpsGraphQLClient transport | Vidhi | ✅ Done | — |
| T6 — `set_product_category` wrapper | Vidhi | ⬜ Next | T5 |
| T7 — `set_product` wrapper | Vidhi | ⬜ Queued | T5 |
| T8 — `set_product_size` wrapper | Vidhi | ⬜ Queued | T5 |
| T9 — `set_product_price` wrapper | Vidhi | ⬜ Queued | T5 |
| T11 — push orchestrator | Vidhi | ⬜ Queued | T6–T9 + T10 (Shinchna) |

---

## Reference

- **M1 Plan:** `docs/superpowers/plans/2026-05-14-centralized-fastapi-ops-m1.md` (Tasks 5, lines 327–452)
- **Phase 8 Task 1 (DB schema for gateway):** `docs/May/1_may/13_may/phase8_task1_done.md`
- **Customer model (where OPS creds live):** `backend/modules/customers/models.py`
- **Existing n8n OPS push (being replaced):** `backend/modules/ops_push/service.py`
