# Phase 8 — Task 9: Gateway Routes + Auth

**Owner:** Vidhi
**Status:** Done
**Date completed:** 2026-05-13
**Spec:** `docs/superpowers/specs/2026-05-11-integration-gateway-design.md`
**Commit:** `f72b932`

---

## What is this task?

Task 9 exposes the Integration Gateway to the outside world — it creates the HTTP layer that any orchestrator (n8n, curl, cron, Lambda) can call to push products to OPS. It also wires up the `X-Orchestrator-Key` authentication system and provides admin endpoints for managing API keys.

---

## Why is it important?

### 1. It makes the gateway callable by anything

The old push path was tied to n8n — only n8n could trigger a push via a private webhook. This task creates public, documented endpoints under `/api/integrations/v1/` that any system can call using an API key. n8n becomes one consumer, not the only one.

### 2. It introduces proper API key auth

The JWT cookie auth used by the admin UI is not appropriate for machine-to-machine calls from orchestrators. This task adds `X-Orchestrator-Key` header auth with:
- Per-key scope (`allowed_customer_ids`, `allowed_supplier_slugs`)
- Revocation support
- `last_used_at` tracking
- SHA-256 key hashing — raw key shown once at creation, never stored

### 3. It deprecates the old n8n push path

The old `POST /api/push/{cid}/{pid}` route and `trigger_n8n_push()` are marked deprecated. The n8n workflow JSON is moved to `deprecated/`. n8n is documented as one consumer of the new gateway, not the gatekeeper.

---

## What was done

### File created: `backend/modules/integrations/auth.py`

`get_orchestrator_key()` FastAPI dependency:
- Reads `X-Orchestrator-Key` header
- SHA-256 hashes it, looks up `integration_keys` table
- Returns 401 `BAD_SIGNATURE` if not found
- Returns 403 `KEY_REVOKED` if revoked or inactive
- `check_key_scope()` — validates key is allowed for the requested customer + supplier. Returns 403 `KEY_NOT_ALLOWED` if out of scope

### File created: `backend/modules/integrations/schemas.py`

Full Pydantic models for the gateway:

| Model | Purpose |
|-------|---------|
| `PushRequest` | Request body for `POST /push-requests` — target, source, product_ref, decorations, dry_run, callback |
| `PushRequestAccepted` | 202 response — push_log_id, status, links |
| `PushStatusOut` | GET status response — full push state, step_results, cleanup_targets |
| `StepResultOut` | One entry in step_results |
| `GatewayError` | Standard error envelope — code, message, details, trace_id |
| `IntegrationKeyCreate` | Admin: create key request |
| `IntegrationKeyOut` | Admin: key list response |
| `IntegrationKeyCreated` | Admin: create response with `raw_key` (shown once only) |

### File created: `backend/modules/integrations/routes.py`

#### Gateway endpoints (X-Orchestrator-Key auth)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/integrations/v1/push-requests` | Push a product to OPS. Calls `prepare_push_intent()` then `execute_push()` as BackgroundTask |
| `GET` | `/api/integrations/v1/push-requests/{push_log_id}` | Poll push status until terminal state |
| `POST` | `/api/integrations/v1/suppliers/{slug}/products` | Catalog upsert (wired to Task 6 when ready) |
| `GET` | `/api/integrations/v1/suppliers/{slug}/schema` | Discover required + optional fields for a supplier |

#### Admin endpoints (JWT + vg_admin role)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/integrations/keys` | List all integration keys |
| `POST` | `/api/integrations/keys` | Create new key — returns `raw_key` once |
| `POST` | `/api/integrations/keys/{id}/revoke` | Revoke a key immediately |

### `backend/main.py` updated

- Integration Gateway router registered without `_auth` (owns its own `X-Orchestrator-Key` auth)
- Admin router registered with `_auth` (JWT required)

---

## Verification

```bash
# Import check
python -c "
from modules.integrations.routes import router, admin_router
from modules.integrations.auth import get_orchestrator_key
from modules.integrations.schemas import PushRequest, PushRequestAccepted
print('imports OK')
"
# → imports OK

# Auth rejection test
curl http://127.0.0.1:8000/api/integrations/v1/push-requests/00000000-0000-0000-0000-000000000000 \
  -H "X-Orchestrator-Key: badkey"
# → {"detail": {"code": "BAD_SIGNATURE", "message": "Invalid API key"}}
```

---

## Error codes implemented

| Code | HTTP | When |
|------|------|------|
| `BAD_SIGNATURE` | 401 | Invalid or missing `X-Orchestrator-Key` |
| `KEY_REVOKED` | 403 | Key is revoked or inactive |
| `KEY_NOT_ALLOWED` | 403 | Key scoped away from requested customer/supplier |
| `UNKNOWN_REF` | 404 | Customer, supplier, or product not found |
| `IDEMPOTENCY_CONFLICT` | 409 | Same key + different payload |
| `IN_FLIGHT` | 409 | Another push for same (customer, product) is processing |
| `PREFLIGHT_BLOCKER` | 422 | Validation failed before any OPS write |

---

## What's next

Tasks 8 and 9 are complete. All of Vidhi's Phase 8 tasks are done. Waiting on:
- Urvashi: Task 4 (OpsClient mutations) + Task 5 (FakeOpsClient)
- Shinchana: Task 6 (payload_builder) + Task 7 (preflight)

When those merge, swap 4 stubs in `gateway.py`, then Urvashi runs Task 11 E2E tests.
