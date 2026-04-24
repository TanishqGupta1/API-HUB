# Sinchana — Sprint Tasks

**Sprint:** Demo Push Pipeline (VG team demo)
**Spec:** `docs/superpowers/specs/2026-04-23-demo-push-pipeline-design.md`
**Full plan + code:** `docs/superpowers/plans/2026-04-23-demo-push-pipeline.md` (Tasks 1–3)
**Branch per task:** `sinchana/<task-slug>` → one PR per task

---

## Overview

3 tasks — all backend, all foundational. Your work blocks Vidhi (Tasks 4, 5) and Urvashi (Task 7). Ship in order: 1 → 2 → 3. Tests must pass before each PR merges.

Pre-work: branch `fix/onprintshop-nodes` has open merge conflicts (see `git status`). Resolve locally before starting, then branch off.

---

## Task 1 — DB Models: `push_mappings` + `push_mapping_options`

**Files:** `backend/modules/push_mappings/__init__.py` + `models.py` (new), `backend/main.py` (add import)

Full code in plan file → Task 1 → Step 2.

**Key points:**
- `push_mappings` table: UUID PK, FK to `products.id` + `customers.id` (CASCADE), UNIQUE on (source_product_id, customer_id), stores target_ops_product_id + target_ops_base_url snapshot + status
- `push_mapping_options` table: FK to push_mappings.id (CASCADE), stores source_master_* + source_*_key + target_ops_* (nullable for now — stub mutations) + title + price + sort_order
- SQLAlchemy 2 typed Mapped pattern, matches existing `master_options/models.py` style
- Register model import in `backend/main.py` near other `import modules.XXX.models` lines

**Acceptance:** `docker compose exec postgres psql -U vg_user -d vg_hub -c "\d push_mappings"` shows all columns + FK constraints + unique index. Same for `push_mapping_options`.

---

## Task 2 — Pydantic Schemas

**Files:** `backend/modules/push_mappings/schemas.py` (new)

Full code in plan → Task 2 → Step 1.

**Schemas to write:**
- `PushMappingOptionIngest` — all fields Optional
- `PushMappingUpsert` — what n8n POSTs after successful OPS push
- `PushMappingOptionRead`, `PushMappingRead` — for GET endpoints
- `OPSProductAttribute` + `OPSProductOption` — product-scoped shape (used by Vidhi's Task 4 endpoint)

**Why shape matters:** `OPSProductOption` + `OPSProductAttribute` intentionally DROP `master_option_id` / `ops_attribute_id` from the core push shape. Retain as `source_master_option_id` / `source_master_attribute_id` only for mapping traceback. This is the architectural rule from meeting with Christian (outbound = product options only, never master options).

**Acceptance:** `python -c "from modules.push_mappings.schemas import PushMappingUpsert, PushMappingRead, OPSProductOption; print('ok')"` prints `ok`.

---

## Task 3 — Service layer + POST / GET / DELETE endpoints + tests

**Files:**
- `backend/modules/push_mappings/service.py` (new)
- `backend/modules/push_mappings/routes.py` (new)
- `backend/main.py` (register router)
- `backend/tests/test_push_mappings.py` (new — 4 tests)

Full code in plan → Task 3 → Steps 1–4.

**Endpoints:**
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/push-mappings` | UPSERT on (source_product_id, customer_id). Requires `X-Ingest-Secret`. Replaces options (delete-and-reinsert). |
| GET | `/api/push-mappings?customer_id=&source_product_id=` | List mappings with nested options |
| DELETE | `/api/push-mappings/{id}` | Soft-delete (status='deleted') — preserves audit |

**Service pattern:** `pg_insert(...).on_conflict_do_update(...)` — reuse pattern from `backend/modules/master_options/ingest.py:35-62`. Attributes replaced via delete-and-reinsert (same pattern).

**Tests required (TDD — write first, then impl):**
1. `test_upsert_mapping_creates_row` — 201 + nested options returned
2. `test_upsert_is_idempotent_on_product_customer_conflict` — second POST updates same row, GET returns 1 row
3. `test_ingest_rejects_bad_secret` — 401
4. `test_delete_marks_status` — DELETE returns 200, GET shows `status='deleted'`

Run: `docker compose exec -T api pytest tests/test_push_mappings.py -v` — 4 PASS.

**Dependencies blocked after this task:**
- Vidhi Task 4 (needs your schemas)
- Vidhi Task 5 (needs your POST endpoint for n8n to call)

---

## Files You Own

- `backend/modules/push_mappings/` — CREATE entire module
- `backend/main.py` — MODIFY (2 lines: import model, include_router)
- `backend/tests/test_push_mappings.py` — CREATE

## Reused utilities

- `require_ingest_secret` dep → `backend/modules/catalog/ingest.py:56`
- `pg_insert(...).on_conflict_do_update` → `backend/modules/master_options/ingest.py`
- Test fixtures + async_session → `backend/tests/conftest.py`
