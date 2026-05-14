# Phase 8 — Task 8: Integration Gateway Core

**Owner:** Vidhi
**Status:** Done
**Date completed:** 2026-05-13
**Spec:** `docs/superpowers/specs/2026-05-11-integration-gateway-design.md`
**Commit:** `f72b932`

---

## What is this task?

Task 8 builds the core business logic of the Integration Gateway — the two functions that every push request flows through:

- `prepare_push_intent()` — validates the request, checks idempotency, runs preflight, and creates the `push_log` row
- `execute_push()` — transitions the push to `processing`, runs the OPS mutation plan step by step, records results, and fires the callback

This is the brain of the entire Phase 8 push pipeline.

---

## Why is it important?

### 1. It replaces the n8n push path entirely

Before Phase 8, pushing a product to OPS meant calling `trigger_n8n_push()` — a fire-and-forget POST to an n8n webhook. FastAPI had no visibility into what happened after that. The push either worked or it didn't.

This task replaces that with a fully observable, fault-tolerant pipeline that FastAPI owns end-to-end. n8n becomes one possible consumer of the gateway, not the gatekeeper.

### 2. It enforces all the safety rules from the spec

| Rule | How gateway enforces it |
|------|------------------------|
| No duplicate pushes | Idempotency-Key ledger — same key + same body → returns existing push_log_id, no new work |
| No concurrent pushes | `IN_FLIGHT` 409 if `processing` row exists for same `(customer, product)` |
| No silent data drift | `payload_hash` computed at prepare time — replay with different body → 409 `IDEMPOTENCY_CONFLICT` |
| Halt-no-rollback | On any mutation failure: stop, record `cleanup_targets`, set `partial_failure`. No auto-cleanup. |
| Auth headers never logged | `_redact_auth()` replaces `Authorization` header values with `"Bearer ***"` before writing to `step_results` |

### 3. It is designed to work before Tasks 4/5/6/7 are ready

All four parallel tasks (OpsClient mutations, FakeOpsClient, payload_builder, preflight) are stubbed with clear `TODO` comments. When Urvashi and Shinchana merge their work, each stub is replaced with a single import line. Zero rework to the gateway logic itself.

---

## What was done

### File created: `backend/modules/ops_push/gateway.py`

#### Stubs (temporary — swap when parallel tasks merge)

| Stub | Replaces when | One-line swap |
|------|--------------|---------------|
| `_stub_run_preflight()` | Task 7 merges | `from .preflight import run_preflight` |
| `_stub_build_push_payload()` | Task 6 merges | `from .payload_builder import build_push_payload` |
| `_StubOpsClient` | Task 4 merges | Real `OPSClient` with mutation methods |
| `_StubFakeOpsClient` | Task 5 merges | `from .fake_ops_client import FakeOpsClient` |

#### `prepare_push_intent(req, key, db) -> PushRequestAccepted`

Flow:
1. Resolve customer + supplier + product from DB (never trusted from request body)
2. Compute `payload_hash` via `build_push_payload`
3. Check idempotency ledger on `(key_id, idempotency_key)`:
   - Same key + same hash → return existing `push_log_id` (200, no new work)
   - Same key + different hash → 409 `IDEMPOTENCY_CONFLICT`
4. Check `IN_FLIGHT` — 409 if `processing` row exists for `(customer_id, product_id)`
5. Run preflight → 422 `PREFLIGHT_BLOCKER` if blockers (no push_log row created)
6. Insert `ProductPushLog` row with `status=accepted`, hash, key context, callback info
7. Return `{push_log_id, status: "accepted", links}`

#### `execute_push(push_log_id) -> None`

Flow:
1. Atomic UPDATE: `accepted → processing` (prevents double-execution)
2. Load product + customer from DB
3. Select client: `dry_run=True` → `FakeOpsClient`, `dry_run=False` → real `OpsClient`
4. Build mutation plan via `build_push_payload`
5. Execute mutations sequentially. After each step: append to `step_results` with latency
6. On failure: halt, populate `cleanup_targets`, set `partial_failure` or `failed`
7. On success: upsert `push_mappings`, update `CustomerProductSelection`, set `pushed` or `dry_run_pushed`
8. Fire callback if `callback_url` set. Update `callback_status` + `callback_attempts`

Uses its own `async_session` — safe to run as a `BackgroundTask` detached from the request session.

#### Helper functions

- `_redact_auth(steps)` — strips `Authorization` header values before DB write
- `_fire_callback(push_log_id, url, payload)` — POST to orchestrator webhook, returns bool
- `_mutation_to_method(mutation)` — maps GraphQL mutation name to Python method name

---

## Verification

```bash
python -c "
from modules.ops_push.gateway import prepare_push_intent, execute_push
print('imports OK')
"
# → imports OK

curl http://127.0.0.1:8000/health
# → {"status":"ok","service":"api-hub"}
```

---

## What's next

When Urvashi finishes Task 4 (OpsClient mutations) and Task 5 (FakeOpsClient), and Shinchana finishes Task 6 (payload_builder) and Task 7 (preflight) — replace the 4 stubs in `gateway.py` with real imports. Then run Task 11 E2E tests.
