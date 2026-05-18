# Phase 8 — Task 1: DB Schema Migration

**Owner:** Vidhi
**Status:** Done (redone 2026-05-13 — original built against superseded spec)
**Spec:** `docs/superpowers/specs/2026-05-11-integration-gateway-design.md`
**Commit:** `f91c83a`

---

## What happened

This task was done twice. The first attempt was built against the old VPCE spec (`2026-05-08`), which was superseded on 2026-05-11 by the Integration Gateway spec. After pulling latest from main and comparing the spec files, we redid the task from scratch to match the correct spec.

---

## What is this task?

Task 1 upgrades the `product_push_log` database table and creates the new `integration_keys` table to support the **Integration Gateway** introduced in Phase 8.

Before this task, `product_push_log` was a simple log — it recorded whether a product push succeeded or failed, nothing more. Phase 8 turns the push into an orchestrator-agnostic gateway where any system (n8n, curl, cron) can push products to OPS using an API key. The table now needs to track idempotency, orchestrator identity, callback state, step-by-step execution, and cleanup instructions.

---

## Why is it important?

### 1. It unblocks all parallel tasks

This is the foundational task of Phase 8. All four parallel tasks depend on the new columns and Pydantic shapes defined here:

- **Urvashi (Task 4)** — `OpsClient` mutations write into `step_results`
- **Urvashi (Task 5)** — `FakeOpsClient` appends to `step_results`
- **Shinchana (Task 6)** — `payload_builder` computes `payload_hash` stored in this table
- **Shinchana (Task 7)** — `preflight` checks guard the `accepted` → `processing` transition
- **Vidhi (Task 8)** — `gateway.py` reads and writes every new column

### 2. It enables the safety layer

Pushes to OPS are irreversible. The new schema enforces:

- **Idempotency** — `(key_id, idempotency_key)` index prevents the same orchestrator from accidentally triggering two identical pushes
- **Payload drift detection** — `payload_hash` is recomputed at execute time; mismatch → `IDEMPOTENCY_CONFLICT`
- **Concurrency guard** — partial unique index on `status = 'processing'` prevents two simultaneous pushes for the same `(customer, product)` at DB level
- **Cleanup visibility** — `cleanup_targets` JSONB records exactly what was created in OPS mid-push so operators can manually clean up on failure

### 3. It upgrades the status vocabulary

Old table had three statuses: `pushed`, `failed`, `skipped`. Phase 8 introduces a full lifecycle:

```
accepted → queued → processing → pushed
                               → failed
                               → partial_failure
                               → rejected
                               → canceled
                               → dry_run_pushed
```

### 4. It creates the orchestrator key registry

The new `integration_keys` table is the single source of truth for `X-Orchestrator-Key` API keys. Each key has a scope (`allowed_customer_ids`, `allowed_supplier_slugs`), rate limit, and revocation support. Raw key shown once at creation — only the SHA-256 hash is stored.

---

## What was done

### Files modified

#### `backend/modules/push_log/models.py`

Removed old VPCE columns (`preflight_results`, `preview_payload`, `preview_built_at`, `execution_steps`, `input_hash`, `confirm_token_hash`, `confirm_token_consumed_at`).

Added 12 new Integration Gateway columns:

| Column | Type | Purpose |
|--------|------|---------|
| `request_id` | UUID UNIQUE | Server-generated correlation ID for tracing and retry linkage |
| `key_id` | VARCHAR(64) | Which `integration_keys` row authorized this push |
| `idempotency_key` | VARCHAR(128) | Raw `Idempotency-Key` header from orchestrator |
| `payload_hash` | VARCHAR(64) | SHA-256 of canonical request JSON — replay detection |
| `supplier_slug` | VARCHAR(64) | Supplier context (e.g. `sanmar`) |
| `supplier_sku` | VARCHAR(255) | Product SKU being pushed (e.g. `PC61`) |
| `callback_url` | TEXT | Orchestrator-provided webhook URL for push completion events |
| `callback_status` | VARCHAR(32) | `not_requested` / `pending` / `sent` / `failed` |
| `callback_attempts` | INT | Number of callback delivery attempts made |
| `step_results` | JSONB | Step-by-step execution log. Auth headers redacted to `"Bearer ***"` |
| `cleanup_targets` | JSONB | OPS IDs created before a partial failure — for manual cleanup |
| `retry_of` | UUID | Links a retry push to its original `product_push_log.id` |

Added 3 indexes:

| Index | Type | Purpose |
|-------|------|---------|
| `idx_push_log_payload_hash` | Standard | Fast lookup for idempotency checks |
| `idx_push_log_idempotency` | Composite on `(key_id, idempotency_key)` | Replay detection |
| `uq_push_log_in_flight` | Partial unique on `status = 'processing'` | Concurrency guard |

Updated status vocab comment to full Integration Gateway lifecycle.

#### `backend/modules/push_log/schemas.py`

Removed all VPCE models (`PreflightResults`, `PreviewPayload`, `ExecutionStep`, `MutationPlanStep`, `ComputedPrice`).

Added new models:

| Model | Purpose |
|-------|---------|
| `StepResult` | Shape for one entry in `step_results[]` — step name, ok/fail, ops_id, latency |
| `PushRequestResponse` | 202 response from `POST /api/integrations/v1/push-requests` |
| `PushStatusResponse` | Response from `GET /api/integrations/v1/push-requests/{id}` |

Extended `PushLogRead` with all 12 new columns. No `confirm_token_hash` anywhere — that concept is gone.

### Files created

#### `backend/modules/integrations/__init__.py` + `models.py`

New `integrations` module with `IntegrationKey` SQLAlchemy model. Registered in `main.py` so `Base.metadata.create_all` picks it up.

#### `backend/migrations/push_log_phase8.sql`

Reference SQL covering:
- DROP old VPCE columns
- DROP old VPCE indexes
- ADD 12 new columns
- CREATE new indexes
- CREATE `integration_keys` table

---

## Verification

```bash
# Import check
python -c "
from modules.push_log.models import ProductPushLog
from modules.push_log.schemas import PushLogRead, PushRequestResponse, PushStatusResponse, StepResult
from modules.integrations.models import IntegrationKey
print('imports OK')
"
# → imports OK

# Column + index check
python -c "
from modules.push_log.models import ProductPushLog
cols = [c.key for c in ProductPushLog.__mapper__.columns]
indexes = [i.name for i in ProductPushLog.__table__.indexes]
print(cols)
print(indexes)
"
# → 20 columns, 3 indexes

# Live DB check
# Columns: 20 correct columns present
# Indexes: product_push_log_pkey, product_push_log_request_id_key,
#          idx_push_log_payload_hash, idx_push_log_idempotency, uq_push_log_in_flight
# integration_keys table: exists
```

---

## What's next

Task 1 is done and pushed to `origin/Vidhi`. Parallel tasks can now start:

| Task | Owner | Can start now |
|------|-------|--------------|
| Task 4 — OpsClient mutations + OAuth2 refresh | Urvashi | Yes |
| Task 5 — FakeOpsClient | Urvashi | After Task 4 |
| Task 6 — payload_builder.py | Shinchana | Yes |
| Task 7 — preflight.py | Shinchana | Yes |
| Task 8 — Integration Gateway core | Vidhi | After Tasks 4, 5, 6, 7 |
