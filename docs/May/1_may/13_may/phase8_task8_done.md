# Phase 8 — Task 8: Integration Gateway Core

**Owner:** Vidhi
**Status:** Done
**Date completed:** 2026-05-15 (initial: 2026-05-13, finalized: 2026-05-15)
**Spec:** `docs/superpowers/specs/2026-05-11-integration-gateway-design.md`
**Commit:** `29b7308`

---

## What is this task?

Task 8 builds the core business logic of the Integration Gateway — the two functions that every push request flows through:

- `prepare_push_intent()` — validates the request, checks idempotency, runs preflight, and creates the `push_log` row
- `execute_push()` — transitions the push to `processing`, runs the OPS mutation plan step by step, records results, and fires the callback

This is the brain of the entire Phase 8 push pipeline.

---

## Why is it important?

### 1. It replaces the n8n push path entirely

Before Phase 8, pushing a product to OPS meant calling `trigger_n8n_push()` — a fire-and-forget POST to an n8n webhook. FastAPI had no visibility into what happened after that.

This task replaces that with a fully observable, fault-tolerant pipeline that FastAPI owns end-to-end. n8n becomes one possible consumer of the gateway, not the gatekeeper.

### 2. It enforces all the safety rules from the spec

| Rule | How gateway enforces it |
|------|------------------------|
| No duplicate pushes | Idempotency-Key ledger — same key + same body → returns existing push_log_id, no new work |
| No concurrent pushes | `IN_FLIGHT` 409 if `processing` row exists for same `(customer, product)` |
| No silent data drift | `payload_hash` at prepare time — replay with different body → 409 `IDEMPOTENCY_CONFLICT` |
| Halt-no-rollback | On any mutation failure: stop, record `cleanup_targets`, set `partial_failure`. No auto-cleanup. |
| Auth headers never logged | `_redact_auth()` replaces `Authorization` values with `"Bearer ***"` before writing to `step_results` |

---

## What was done

### File: `backend/modules/ops_push/gateway.py`

#### `prepare_push_intent(req, key, db) -> PushRequestAccepted`

Flow:
1. Resolve customer + supplier + product from DB
2. Compute `payload_hash` via `compute_payload_hash(req.model_dump())`
3. Check idempotency ledger on `(key_id, idempotency_key)`:
   - Same key + same hash → return existing `push_log_id` (no new work)
   - Same key + different hash → 409 `IDEMPOTENCY_CONFLICT`
4. Check `IN_FLIGHT` — 409 if `processing` row exists for `(customer_id, product_id)`
5. Run preflight via `run_preflight(db, customer_id, product_id)` → 422 `PREFLIGHT_BLOCKER` if blockers
6. Insert `ProductPushLog` row with `status=accepted`
7. Return `{push_log_id, status: "accepted", links}`

#### `execute_push(push_log_id) -> None`

Flow:
1. Atomic UPDATE: `accepted → processing`
2. Select client: `dry_run=True` → `_StubFakeOpsClient`, `dry_run=False` → `_StubOpsClient`
3. Build mutation plan via `build_push_payload(db, customer_id, product_id)`
4. Execute mutations sequentially; append to `step_results` with latency
5. On failure: halt, populate `cleanup_targets`, set `partial_failure` or `failed`
6. On success: upsert `push_mappings`, update `CustomerProductSelection`, set `pushed` or `dry_run_pushed`
7. Fire callback if `callback_url` set; update `callback_status` + `callback_attempts`

Uses its own `async_session` — safe to run as a `BackgroundTask` detached from the request session.

#### Active stubs (Tasks 4 & 5 — Urvashi)

| Stub | Replaces when | One-line swap |
|------|--------------|---------------|
| `_StubOpsClient` | Task 4 merges | Real `OpsClient` with mutation methods |
| `_StubFakeOpsClient` | Task 5 merges | `from .fake_ops_client import FakeOpsClient` |

**Removed on 2026-05-15:** `_PreflightStub`, `_stub_run_preflight`, `_PushPayloadStub`, `_stub_build_push_payload` — these were dead code after Task 6 (payload_builder) and Task 7 (preflight) merged from main.

#### Helper functions

- `_redact_auth(steps)` — strips `Authorization` header values before DB write
- `_fire_callback(push_log_id, url, payload)` — POST to orchestrator webhook, returns bool
- `_mutation_to_method(mutation)` — maps GraphQL mutation name to Python method name

---

## Tests

**File:** `backend/tests/test_gateway_push_request.py`

All tests use an autouse `_mock_preflight_ok` fixture that patches `run_preflight` to return `ok=True` — so test products don't need markup rules, images, or OPS credentials to reach the push stage. Tests that verify preflight behaviour apply their own inner patch.

| Test | What it verifies |
|------|-----------------|
| `test_push_without_orchestrator_key_returns_401` | Missing key → 401 |
| `test_push_with_bad_orchestrator_key_returns_401` | Bad key → 401 |
| `test_push_resolves_product_by_supplier_sku` | Lookup by supplier_sku |
| `test_push_resolves_product_by_product_id` | Lookup by product UUID |
| `test_push_rejects_when_product_ref_empty` | No product_ref → 422 |
| `test_push_dry_run_returns_terminal_status_inline` | dry_run=True → `dry_run_pushed` inline |
| `test_push_idempotent_replay_returns_same_push_log` | Same key + body → same push_log_id |
| `test_push_idempotency_conflict_on_different_body` | Same key + different body → 409 |
| `test_push_in_flight_returns_409` | Processing row exists → 409 IN_FLIGHT |
| `test_push_preflight_blocker_returns_422` | Preflight blocks → 422 PREFLIGHT_BLOCKER |
| `test_execute_push_partial_failure_records_cleanup_targets` | Step fails → partial_failure + cleanup_targets |
| `test_execute_push_fires_callback_on_success` | Successful push → callback POSTed, `callback_status=sent` |

Also added missing schema migration in `main.py`:
```python
"ALTER TABLE integration_keys ADD COLUMN IF NOT EXISTS is_synthetic BOOLEAN NOT NULL DEFAULT FALSE"
```

---

## What's next

Waiting on:
- Urvashi: Task 4 (OpsClient mutations) + Task 5 (FakeOpsClient) → swap 2 stubs in `gateway.py`
- Urvashi: Task 11 E2E test against VG OPS staging
