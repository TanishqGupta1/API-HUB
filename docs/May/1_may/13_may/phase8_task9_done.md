# Phase 8 — Task 9: Gateway Routes + n8n Path Retirement

**Owner:** Vidhi
**Status:** Done
**Date completed:** 2026-05-15 (initial: 2026-05-13, finalized: 2026-05-15)
**Spec:** `docs/superpowers/specs/2026-05-11-integration-gateway-design.md`
**Commit:** `29b7308`

---

## What is this task?

Task 9 exposes the Integration Gateway to the outside world and fully retires the old n8n-based push path. It covers two things:

1. **New API layer** — HTTP endpoints under `/api/integrations/v1/` that any orchestrator can call with an `X-Orchestrator-Key`
2. **n8n path removal** — delete the legacy push code, remove the n8n proxy router, mark the old route deprecated, archive the n8n workflow JSON

---

## Why is it important?

### 1. Any orchestrator can now trigger a push

The old push path was tied to n8n via a private webhook. The new gateway endpoints are fully documented, key-authenticated, and callable by any system — n8n, curl, cron, Lambda.

### 2. It introduces proper machine-to-machine auth

`X-Orchestrator-Key` with SHA-256 hashing, per-key scope, revocation, and `last_used_at` tracking replaces the old "POST to n8n webhook with no auth" pattern.

### 3. It fully removes the n8n dependency from the push path

The spec constraint was: **No n8n in the OPS push path for beta.** This task enforces that — the n8n proxy is removed, `trigger_n8n_push()` is deleted, and the old route is marked deprecated.

---

## What was done

### Gateway HTTP layer (initial — 2026-05-13)

#### `backend/modules/integrations/auth.py`

`get_orchestrator_key()` FastAPI dependency:
- Reads `X-Orchestrator-Key` header
- SHA-256 hashes it, looks up `integration_keys` table (`WHERE is_synthetic = FALSE`)
- Returns 401 `BAD_SIGNATURE` if not found
- Returns 403 `KEY_REVOKED` if revoked or inactive
- `check_key_scope()` — validates key is allowed for the requested customer + supplier

#### `backend/modules/integrations/routes.py`

**Gateway endpoints (X-Orchestrator-Key auth):**

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/integrations/v1/push-requests` | Push a product to OPS |
| `GET` | `/api/integrations/v1/push-requests/{id}` | Poll push status |
| `POST` | `/api/integrations/v1/suppliers/{slug}/products` | Catalog upsert batch |
| `GET` | `/api/integrations/v1/suppliers/{slug}/schema` | Discover required fields |
| `POST` | `/api/integrations/v1/push-mappings` | Upsert OPS↔hub product mapping |
| `POST` | `/api/integrations/v1/customers/{id}/ops/connection-test` | OAuth2 probe against OPS |

**Admin endpoints (JWT + vg_admin):**

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/integrations/keys` | List all integration keys |
| `POST` | `/api/integrations/keys` | Create key — returns `raw_key` once |
| `POST` | `/api/integrations/keys/{id}/revoke` | Revoke a key |
| `GET` | `/api/integrations/admin/push-requests/{id}` | Admin status poll (JWT auth) |
| `POST` | `/api/integrations/admin/push-requests` | Admin push proxy |

---

### n8n path retirement (finalized — 2026-05-15)

#### `backend/modules/ops_push/service.py`
- Removed `trigger_n8n_push()` function
- Removed `N8N_PUSH_WEBHOOK_URL` env var usage
- Removed unused imports: `os`, `httpx`, `Any`

#### `backend/main.py`
- Removed `from modules.n8n_proxy.routes import router as n8n_proxy_router`
- Removed `app.include_router(n8n_proxy_router, ...)` registration
- Removed n8n_proxy HTTP client cleanup from lifespan shutdown handler
- Removed `N8N_WEBHOOK_BASE_URL` from `_PROD_REQUIRED_ENV_VARS`

#### `backend/modules/ops_push/routes.py`
- Marked `POST /{customer_id}/{product_id}` as `deprecated=True` in OpenAPI — still works, but Swagger UI shows it as deprecated

#### `n8n-workflows/`
- Moved `ops-push.json` → `deprecated/ops-push.json`
- Created `deprecated/README.md` tombstone explaining the workflow is superseded by the Integration Gateway

---

## Error codes implemented

| Code | HTTP | When |
|------|------|------|
| `BAD_SIGNATURE` | 401 | Invalid or missing `X-Orchestrator-Key` |
| `KEY_REVOKED` | 403 | Key is revoked or inactive |
| `KEY_NOT_ALLOWED` | 403 | Key scoped away from requested customer/supplier |
| `UNKNOWN_REF` | 404 | Customer, supplier, or product not found |
| `SUPPLIER_MISMATCH` | 409 | Product UUID belongs to a different supplier |
| `IDEMPOTENCY_CONFLICT` | 409 | Same Idempotency-Key with different payload |
| `IN_FLIGHT` | 409 | Another push for same (customer, product) is processing |
| `PREFLIGHT_BLOCKER` | 422 | Validation failed before any OPS write |

---

## Test file changes

- **`test_gateway_push_request.py`** — added autouse `_mock_preflight_ok` fixture; added tests for IN_FLIGHT, PREFLIGHT_BLOCKER, partial_failure, callback
- **`test_admin_route_preserved.py`** — added autouse `_mock_preflight_ok`; removed `test_admin_route_no_n8n_webhook_trigger` (tests a deleted function)
- **`test_ops_push.py`** — added autouse `_mock_gateway_deps` (mocks both preflight and build_push_payload)
- **`test_ops_push_failure.py`** — added autouse `_mock_preflight_ok`
- **`test_n8n_url_config.py`** — removed test for `N8N_WEBHOOK_BASE_URL` being required in production (it no longer is)

**Suite result: 418/418 pass**

---

## What's next

Vidhi's Phase 8 tasks (1, 8, 9) are all complete. Waiting on:
- Urvashi: Task 4 (OpsClient mutations) + Task 5 (FakeOpsClient) → swap 2 stubs in `gateway.py`
- Urvashi: Task 11 E2E test against VG OPS staging
- Shinchana: Task 10 (Admin UI — push log detail, integration keys page)
