# Phase 8 — Task 1: DB Schema Migration

**Owner:** Vidhi
**Status:** Done
**Date completed:** 2026-05-13

---

## What is this task?

Task 1 upgrades the `product_push_log` database table to support the new **Preview → Confirm → Execute** push flow introduced in Phase 8.

Before this task, the table was a simple log — it recorded whether a product push succeeded or failed, nothing more. Phase 8 turns the push into a multi-stage process with validation, mutation planning, step-by-step execution tracking, and safety guards. All of that state needs to live in the database.

---

## Why is it important?

### 1. It unblocks everyone else

This is the foundational task of Phase 8. All four parallel tasks (4, 5, 6, 7) depend on the new columns and Pydantic shapes defined here:

- **Urvashi (Task 4)** — `OpsClient` mutations write into `execution_steps`
- **Urvashi (Task 5)** — `FakeOpsClient` also appends to `execution_steps`
- **Shinchana (Task 6)** — `payload_builder` produces the `preview_payload` shape
- **Shinchana (Task 7)** — `preflight` produces the `preflight_results` shape
- **Vidhi (Task 8)** — `pipeline.py` reads and writes every new column

Nothing in Phase 8 can be built until this lands.

### 2. It enables the safety layer

The entire point of Phase 8 is that a push to OPS staging is **irreversible** — once a product is created in OPS, you can't auto-rollback. The new schema enforces:

- **Preview before push** — a push_log row in `preview_ready` state must exist before execute is allowed
- **Concurrency guard** — the partial unique index prevents two people from pushing the same product simultaneously (DB-enforced, not application-enforced)
- **Input drift detection** — `input_hash` lets the pipeline reject an execute if prices or variants changed after preview was generated
- **Token security** — `confirm_token_hash` stores only the HMAC, never the plaintext token. Live pushes require this token.

### 3. It upgrades the status vocabulary

The old table had three statuses: `pushed`, `failed`, `skipped`. Phase 8 introduces a proper lifecycle:

```
pending → preview_ready → executing → dry_run_pushed
                                    → pushed
                                    → failed
```

This gives the frontend and operators full visibility into where a push is in the pipeline at any moment.

---

## What was done

### Files modified

#### `backend/modules/push_log/models.py`

Added 9 new columns to `ProductPushLog`:

| Column | Type | Purpose |
|--------|------|---------|
| `preflight_results` | JSONB | Results of 8 validation checks (prices set? mappings ready? OPS reachable?) |
| `preview_payload` | JSONB | Full mutation plan — ordered list of OPS mutations with their variables |
| `preview_built_at` | TIMESTAMPTZ | When the preview was generated |
| `execution_steps` | JSONB (default `[]`) | Append-only log of each mutation as it executes. Auth headers redacted to `"Bearer ***"` before write. |
| `cleanup_targets` | JSONB | If push fails mid-way: what to manually delete in OPS (category_id, product_id, size_ids) |
| `dry_run` | BOOLEAN | Whether this was a dry-run (FakeOpsClient) or a live push |
| `input_hash` | VARCHAR(64) | SHA-256 of inputs at preview time. Recomputed at execute — mismatch → 409 PreviewExpired |
| `confirm_token_hash` | VARCHAR(64) | HMAC-SHA256 of the confirm token. Never returned in any API response. |
| `confirm_token_consumed_at` | TIMESTAMPTZ | Timestamp of token use — prevents reuse |

Added 2 indexes:

| Index | Type | Purpose |
|-------|------|---------|
| `idx_push_log_input_hash` | Standard | Fast lookup when checking for input drift |
| `uq_push_log_in_flight` | Partial unique on `status = 'executing'` | Concurrency guard — DB rejects a second concurrent push for the same `(customer_id, product_id)` |

Updated the status comment to the full Phase 8 vocabulary.

#### `backend/modules/push_log/schemas.py`

Added 6 new Pydantic models representing the JSONB shapes:

| Model | Maps to | Purpose |
|-------|---------|---------|
| `PreflightCheck` | One entry in `preflight_results.checks[]` | Name, ok/fail, detail message |
| `PreflightResults` | `preflight_results` column | Full preflight outcome — checks, blockers list, warnings, timestamp |
| `ExecutionStep` | One entry in `execution_steps[]` | Mutation name, status, latency, response, timestamp |
| `MutationPlanStep` | One entry in `preview_payload.plan[]` | Step number, mutation name, variables, response dependencies |
| `ComputedPrice` | One entry in `preview_payload.computed_prices[]` | Per-variant markup-applied pricing |
| `PreviewPayload` | `preview_payload` column | Full preview — mutation plan + computed prices |

Extended `PushLogRead` with all Phase 8 fields. `confirm_token_hash` is intentionally excluded — it never appears in any API response.

### Files created

#### `backend/migrations/push_log_phase8.sql`

Reference SQL for the migration. The app applies it automatically via `Base.metadata.create_all` on startup, but this file documents exactly what changes for manual use or auditing.

---

## Verification

```bash
# Import check
python -c "from modules.push_log.models import ProductPushLog; from modules.push_log.schemas import PushLogRead, PreflightResults, ExecutionStep, PreviewPayload; print('OK')"
# → imports OK

# Column + index reflection
python -c "
from modules.push_log.models import ProductPushLog
cols = [c.key for c in ProductPushLog.__mapper__.columns]
indexes = [i.name for i in ProductPushLog.__table__.indexes]
print(cols)
print(indexes)
"
# → 16 columns, 2 indexes registered correctly
```

New columns apply to the live DB automatically on next `uvicorn main:app --reload`.

---

## What's next

Task 1 is the gate. With this merged, the parallel tasks can start:

| Task | Owner | Can start now |
|------|-------|--------------|
| Task 4 — OpsClient mutations + OAuth2 refresh | Urvashi | Yes |
| Task 5 — FakeOpsClient | Urvashi | After Task 4 |
| Task 6 — payload_builder.py | Shinchana | Yes |
| Task 7 — preflight.py | Shinchana | Yes |
| Task 8 — pipeline.py | Vidhi | After Tasks 4, 5, 6, 7 |
