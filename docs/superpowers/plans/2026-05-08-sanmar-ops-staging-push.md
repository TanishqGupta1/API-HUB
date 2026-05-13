# Phase 8 — SanMar → OPS Staging Push (Beta): Implementation Plan

**Spec:** `docs/superpowers/specs/2026-05-08-sanmar-ops-staging-push-design.md`
**Date:** 2026-05-11
**Status:** 3/11 tasks done. Tasks 4–7 are parallel once Task 1 lands.

---

## Task Assignments & Dependencies

| Task | Title | Owner | Status | Depends On | Blocks |
|------|-------|-------|--------|------------|--------|
| 1 | DB schema migration | Vidhi | ⏳ Pending | — | 4, 5, 6, 7 |
| 2 | Fix base_price=None in V2 normalizer | — | ✅ Done | — | — |
| 3 | Wire SanMar Inventory v200 SOAP | — | ✅ Done | — | — |
| 4 | OpsClient: mutation methods + OAuth2 refresh | Urvashi | ⏳ Pending | 1 | 5, 8 |
| 5 | FakeOpsClient (dry-run test double) | Urvashi | ⏳ Pending | 4 | 8 |
| 6 | payload_builder.py | Shinchana | ⏳ Pending | 1 | 8 |
| 7 | preflight.py (8 validation checks) | Shinchana | ⏳ Pending | 1 | 8 |
| 8 | pipeline.py (orchestrator) | Vidhi | ⏳ Pending | 1, 4, 5, 6, 7 | 9 |
| 9 | New API routes + deprecate n8n push path | Vidhi | ⏳ Pending | 8 | 10 |
| 10 | Admin UI: preview page, timeline, dry-run controls | Shinchana | ⏳ Pending | 9 | 11 |
| 11 | E2E manual test against VG OPS staging | Urvashi | ⏳ Pending | All | — |

### Execution Order

```
Task 1 (Vidhi)  ←── start here, unblocks everyone
    ├── Task 4 (Urvashi)   ──┐
    ├── Task 5 (Urvashi)   ──┤  all parallel
    ├── Task 6 (Shinchana) ──┼──► Task 8 (Vidhi) ──► Task 9 (Vidhi) ──► Task 10 (Shinchana)
    └── Task 7 (Shinchana) ──┘                                                  │
                                                                          Task 11 (Urvashi)
```

---

## Goal

Push one real SanMar product (PC61 — Port & Co Essential T-Shirt) to VG OPS staging end-to-end with correct prices, images, inventory, and full operator visibility. Single-product, manually triggered, preview-then-confirm safety layer. No n8n in the push path for beta.

---

## Constraints (locked in spec)

- No n8n in OPS push path for beta. Push runs in FastAPI process.
- Halt-no-rollback on failure. No auto-rollback. Manual cleanup checklist surfaced in UI.
- Preview → Confirm → Execute. Default is dry-run. Live mode requires confirm_token + admin role.
- Concurrency guard via partial unique index on `executing` status — NOT transactional advisory lock.
- `sync_jobs` is NOT used for push tracking (inbound sync only). `product_push_log` owns push state.
- Auth headers redacted (`"Bearer ***"`) before writing to `execution_steps`. Plaintext never persisted.

---

## File Structure

**New (`backend/modules/ops_push/`):**
- `payload_builder.py` — sole owner of OPS-bound payload shape. Replaces `merge.py`.
- `preflight.py` — pure validation rules (DB-only checks). Returns blockers list.
- `pipeline.py` — orchestration only. Validate → build → hash → execute. No DB write logic, no payload shaping, no transport.
- `fake_ops_client.py` — in-memory test double with same interface as real client.

**Extended (not replaced):**
- `backend/modules/ops_inbound/ops_client.py` — add mutation methods + OAuth2 refresh on 401.

**Modified:**
- `backend/modules/promostandards/ps_normalizer_v2.py` — backfill `base_price` ✅ Done
- `backend/modules/promostandards/adapter.py` — add Inventory v200 SOAP call ✅ Done
- `backend/modules/push_log/models.py` — add JSONB cols + updated status vocab
- `backend/modules/push_log/schemas.py` — read shapes for new JSONB cols
- `backend/modules/ops_push/routes.py` — replace single push endpoint with `/preview`, `/execute`, `/{push_log_id}`, `/{push_log_id}/stream`
- `backend/modules/markup/routes.py` — mark `/payload`, `/ops-variants`, `/ops-options` deprecated

**Removed (beta):**
- `backend/modules/ops_push/service.py::trigger_n8n_push` + `N8N_PUSH_WEBHOOK_URL` env var
- `backend/modules/ops_push/merge.py` (replaced by `payload_builder.py`)
- `n8n-workflows/ops-push.json` → move to `n8n-workflows/deprecated/ops-push.json` with tombstone README

---

## Task 1 — DB schema migration ⏳ Pending

**Files:**
- Modify: `backend/modules/push_log/models.py`
- Modify: `backend/modules/push_log/schemas.py`
- Create: `backend/migrations/push_log_phase8.sql` (reference only — app uses `create_all`)

**Steps:**
- [ ] Step 1: Add columns to `ProductPushLog` in `models.py`:
  ```python
  preflight_results: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
  preview_payload:   Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
  execution_steps:   Mapped[list]           = mapped_column(JSONB, default=list)
  cleanup_targets:   Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
  input_hash:        Mapped[Optional[str]]  = mapped_column(String(64), nullable=True)
  confirm_token_hash:         Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
  confirm_token_consumed_at:  Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
  preview_built_at:  Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
  dry_run:           Mapped[bool]           = mapped_column(Boolean, default=False)
  ```
- [ ] Step 2: Update status comment in `models.py` to reflect full vocab:
  `pending → preview_ready → executing → dry_run_pushed | pushed | failed`
- [ ] Step 3: Add index declarations to `models.py`:
  ```python
  __table_args__ = (
      Index("idx_push_log_input_hash", "input_hash"),
      Index(
          "uq_push_log_in_flight",
          "customer_id", "product_id",
          unique=True,
          postgresql_where=text("status = 'executing'"),
      ),
  )
  ```
- [ ] Step 4: Update `push_log/schemas.py` — add `PreflightResults`, `ExecutionStep`, `PreviewPayload` Pydantic models matching the JSONB shapes in the spec `§Data model`. Exclude `confirm_token_hash` from all response schemas.
- [ ] Step 5: Start backend, confirm tables alter cleanly: `uvicorn main:app --reload`. Check logs for errors.

**Test:** `GET /api/push-log` returns rows without error. New columns present in `\d product_push_log` in psql.

**Commit:** `feat(push_log): Phase 8 schema — JSONB cols, status vocab, concurrency index`

---

## Task 2 — Fix base_price=None in V2 normalizer ✅ Done

**Branch:** `origin/fix/spike-bugs-1-2` (commit `78a4a42`) — not yet merged to main.

`ps_normalizer_v2.merge_pricing()` now backfills `variant.base_price` from the cheapest qty=1 Net tier after building price tiers. Existing `base_price` values are not overwritten.

**Merge when ready:** `git merge origin/fix/spike-bugs-1-2`

---

## Task 3 — Wire SanMar Inventory v200 SOAP ✅ Done (manual test deferred)

**Branch:** `origin/fix/spike-bugs-1-2` (commit `78a4a42`) — not yet merged to main.

`adapter.py::hydrate_product()` now calls `inv_client.get_inventory()` after `merge_media`, maps `quantity_available` + `warehouse_code` onto each variant by `part_id`. Swallows on failure (`variant.inventory=None` treated as unknown downstream).

**Note:** Verified by code review + pattern match. Manual test against live SanMar SOAP deferred.

**Merge when ready:** same branch as Task 2.

---

## Task 4 — Extend OpsClient with mutation methods + OAuth2 refresh ⏳ Pending

**Files:**
- Modify: `backend/modules/ops_inbound/ops_client.py`
- Modify: `backend/tests/test_ops_client_mutations.py` (create if not exists)

**Steps:**
- [ ] Step 1: Add mutation methods to `OpsClient` — one per mutation in the spec `§Mutation sequence`:
  - `set_product_category(input: dict) -> dict` — returns `{"products_id": int}`
  - `set_product(input: dict) -> dict` — returns `{"products_id": int}`
  - `set_product_size(input: dict) -> dict` — returns `{"products_id": int, "size_id": int}`
  - `set_product_price(input: dict) -> dict`
  - `set_assign_options(input: dict) -> dict`
  - `set_product_design(input: dict) -> dict`
  Each wraps `self.query(MUTATION_STRING, variables={"input": input})` and unwraps the response key.
- [ ] Step 2: Add OAuth2 refresh on 401 — catch `AuthError` in `query()`, call `_refresh_token()`, retry once, then re-raise.
- [ ] Step 3: Add `_refresh_token(self)` method — POST to `self.token_url` with `client_credentials` grant, update `self.auth_token`.
- [ ] Step 4: Add mutation GraphQL strings as module-level constants (not inline) — easier to audit.
- [ ] Step 5: Tests — mock `httpx.AsyncClient`, assert each mutation method sends correct query string and unwraps response key correctly.

**Test:** `pytest backend/tests/test_ops_client_mutations.py -v` — all pass.

**Commit:** `feat(ops_client): add mutation methods + OAuth2 refresh-on-401`

---

## Task 5 — FakeOpsClient (dry-run test double) ⏳ Pending

**Files:**
- Create: `backend/modules/ops_push/fake_ops_client.py`
- Create: `backend/tests/test_fake_ops_client.py`

**Steps:**
- [ ] Step 1: Create `FakeOpsClient` with identical method signatures to `OpsClient` mutations from Task 4.
- [ ] Step 2: Each method returns fabricated incrementing IDs:
  - `set_product_category` → `{"products_id": 1}`
  - `set_product` → `{"products_id": 10001}`
  - `set_product_size` → `{"products_id": 10001, "size_id": self._next_id()}`
  - others follow same pattern
- [ ] Step 3: Record every call in `self.calls: list[dict]` with `method`, `input`, `response`, `called_at` — written to `execution_steps` JSONB by pipeline.
- [ ] Step 4: `cleanup_targets` always `None`. Status never set to `pushed` — pipeline uses `dry_run_pushed`.
- [ ] Step 5: `confirm_token` check skipped in dry-run mode (enforced by pipeline, not FakeOpsClient).
- [ ] Step 6: Tests — call all 6 methods, assert IDs are unique and incrementing, assert `calls` list populated.

**Test:** `pytest backend/tests/test_fake_ops_client.py -v` — all pass.

**Commit:** `feat(ops_push): FakeOpsClient — in-memory dry-run test double`

---

## Task 6 — payload_builder.py ⏳ Pending

**Files:**
- Create: `backend/modules/ops_push/payload_builder.py`
- Create: `backend/tests/test_payload_builder.py`
- Delete: `backend/modules/ops_push/merge.py` (replaced — spec §Module map)

**Steps:**
- [ ] Step 1: Create `OpsPushPayloadBuilder` with `from_db(product, customer, markup_rules, push_mappings)` factory classmethod.
- [ ] Step 2: Implement `.to_mutation_plan() -> list[dict]` — returns spec's `preview_payload.plan[]` shape:
  ```json
  {"step": 1, "mutation": "setProductCategory", "variables": {...}, "requires_response_from": null}
  {"step": 2, "mutation": "setProduct", "variables": {...}, "requires_response_from": [1]}
  ...
  ```
  Mutation ordering from spec `§Mutation sequence`: setProductCategory → setProduct → setProductSize × N → setProductPrice × ≥N → setAssignOptions → setProductDesign.
- [ ] Step 3: Implement `.input_hash() -> str` — SHA-256 over canonical JSON of normalized inputs (prices, variant list, markup rule id, push_mappings ids). Deterministic: sort keys, strip whitespace.
- [ ] Step 4: Implement `.computed_prices() -> list[dict]` — `{sku, base_price, final_price, markup_pct, rounding}` per variant. Markup applied here.
- [ ] Step 5: Absorb synthesis logic from `n8n-workflows/ops-push.json:250-261`.
- [ ] Step 6: Re-implement `GET /customers/{cid}/products/{pid}/payload` (`markup/routes.py:29`) on top of `payload_builder` internally — keep response shape identical for existing callers.
- [ ] Step 7: Tests — every variant has `vendor_price > 0`; `input_hash` is deterministic (same inputs → same hash); mutation plan ordering matches spec sequence; markup applied correctly to `final_price`.

**Test:** `pytest backend/tests/test_payload_builder.py -v` — all pass.

**Commit:** `feat(ops_push): payload_builder — sole owner of OPS-bound payload shape`

---

## Task 7 — preflight.py (8 validation checks) ⏳ Pending

**Files:**
- Create: `backend/modules/ops_push/preflight.py`
- Create: `backend/tests/test_preflight.py`

**Steps:**
- [ ] Step 1: Create `run_preflight(product, customer, db) -> PreflightResults` async function.
- [ ] Step 2: Implement all 8 checks from spec `§Preflight validation rules`. Each returns `(name, ok: bool, detail: str)`:
  1. `base_price_set` — every `ProductVariant.base_price` not null and > 0
  2. `markup_rule_resolves` — `markup.engine.resolve_rule(rules, supplier_sku, category)` returns non-None
  3. `push_mappings_present` — every `ProductOption` + attribute has `target_ops_option_id` / `target_ops_attribute_id` populated
  4. `ops_oauth2_reachable` — smoke-test token fetch against `customer.ops_token_url`
  5. `image_urls_reachable` — HEAD per image URL returns 2xx (5s timeout)
  6. `prefix_collision` — query OPS via `getProducts` for `internal_title = supplier_sku`; block if match found and no `push_mapping` row claims it
  7. `required_fields` — `product_name`, `supplier_sku`, ≥1 variant, ≥1 image
  8. `decoration_attached` — if `supplier.has_decoration_overlay = true`, require non-empty `customer_product_decorations.decoration_options`
- [ ] Step 3: Return `PreflightResults` with `checks`, `blockers` (names of failed checks), `warnings`, `computed_at`.
- [ ] Step 4: Tests — mock DB + httpx. Test: all-pass path; single blocker path; `ops_oauth2_reachable` fail path; `prefix_collision` fire path.

**Test:** `pytest backend/tests/test_preflight.py -v` — all pass.

**Commit:** `feat(ops_push): preflight — 8 validation checks before any OPS write`

---

## Task 8 — pipeline.py (orchestrator) ⏳ Pending

**Depends on:** Tasks 1, 4, 5, 6, 7

**Files:**
- Create: `backend/modules/ops_push/pipeline.py`
- Create: `backend/tests/test_pipeline.py`

**Steps:**
- [ ] Step 1: Create `preview(customer_id, product_id, db) -> PreviewResponse`:
  - Check for in-flight row on `(customer_id, product_id)` → 409 if found
  - Call `run_preflight()` → if blockers, return 422 with `preflight.blockers` (no push_log row created)
  - Call `payload_builder.to_mutation_plan()` + `.input_hash()` + `.computed_prices()`
  - Generate `confirm_token`: 32-byte `secrets.token_urlsafe()`. Store HMAC-SHA256 (key=`SECRET_KEY`) in `confirm_token_hash`. Return plaintext to caller once — never persisted.
  - Insert `ProductPushLog` row: `status=preview_ready`, `preview_payload`, `preflight_results`, `input_hash`, `confirm_token_hash`, `preview_built_at`.
  - Return `{preview_id, input_hash, confirm_token, plan, preflight, warnings}`.

- [ ] Step 2: Create `execute(preview_id, input_hash, dry_run, confirm_token, db, user) -> ExecuteResponse`:
  - Check for in-flight row → 409 if `executing` row exists for `(cid, pid)`
  - Atomic UPDATE: `WHERE id=preview_id AND status='preview_ready' SET status='executing'` — partial unique index prevents race
  - Recompute current `input_hash` → mismatch → 409 `PreviewExpired`, reset status to `preview_ready`
  - `dry_run=false`: verify admin role + validate `confirm_token` via HMAC compare + check `confirm_token_consumed_at` is null → 403 if any fail; set `confirm_token_consumed_at=now`
  - Select client: `dry_run=True` → `FakeOpsClient`, `dry_run=False` → real `OpsClient`
  - Execute mutation plan sequentially. After each mutation: append to `execution_steps` (with `Authorization` header redacted to `"Bearer ***"`).
  - On failure: halt, populate `cleanup_targets`, set `status=failed`. Return with cleanup info.
  - On success: upsert `push_mappings` (live only), set `status=pushed` or `dry_run_pushed`.

- [ ] Step 3: Async background path — if variant count > 20, detach `execute()` into `asyncio.create_task()`, return 202 with `{push_log_id, status: "executing", status_url, stream_url}`.

- [ ] Step 4: SSE helper `stream_push_log(push_log_id, db)` — polls `execution_steps` for new appends, yields events. Final event: `{"status": "pushed"|"failed"|"dry_run_pushed"}`.

- [ ] Step 5: Tests — dry-run full flow (FakeOpsClient, assert `dry_run_pushed`, no push_mappings row); preflight blocker aborts before push_log insert; concurrency: two concurrent executes → second gets 409; hash drift → 409 PreviewExpired; mid-sequence failure → `failed` + `cleanup_targets` populated.

**Test:** `pytest backend/tests/test_pipeline.py -v` — all pass.

**Commit:** `feat(ops_push): pipeline — preview/execute orchestrator with concurrency guard`

---

## Task 9 — New API routes + deprecate old n8n push routes ⏳ Pending

**Depends on:** Task 8

**Files:**
- Modify: `backend/modules/ops_push/routes.py`
- Modify: `backend/modules/ops_push/service.py` (remove `trigger_n8n_push`)
- Move: `n8n-workflows/ops-push.json` → `n8n-workflows/deprecated/ops-push.json`
- Create: `n8n-workflows/deprecated/README.md` (tombstone)

**Steps:**
- [ ] Step 1: Add new routes to `ops_push/routes.py` from spec `§API surface`:
  - `POST /api/push/{customer_id}/{product_id}/preview` → calls `pipeline.preview()`
  - `POST /api/push/{customer_id}/{product_id}/execute` → calls `pipeline.execute()`
  - `GET /api/push/{push_log_id}` → returns push_log row; **excludes `confirm_token_hash`**
  - `GET /api/push/{push_log_id}/stream` → SSE endpoint calling `pipeline.stream_push_log()`
- [ ] Step 2: Remove `trigger_n8n_push` function and `N8N_PUSH_WEBHOOK_URL` references from `service.py`.
- [ ] Step 3: Mark old push route (`POST /api/push/{cid}/{pid}`) as `deprecated=True` in OpenAPI decorator. Add `logger.warning("deprecated route hit")`.
- [ ] Step 4: Mark `GET /customers/{cid}/products/{pid}/payload`, `/ops-variants`, `/ops-options` in `markup/routes.py` as `deprecated=True` in OpenAPI. Do not delete — live callers still exist.
- [ ] Step 5: Move `n8n-workflows/ops-push.json` to `n8n-workflows/deprecated/ops-push.json`. Write `n8n-workflows/deprecated/README.md`: explains that `ops-push.json` is tombstoned for beta, what changed, and when it returns (post-beta scheduling phase).
- [ ] Step 6: Register any new routers in `backend/main.py` if not already registered.

**Test:** `curl -X POST http://localhost:8000/api/push/{cid}/{pid}/preview` returns 422 (preflight) or 200 with `preview_id`. Old route still responds (not 410 yet).

**Commit:** `feat(ops_push): new preview/execute routes; tombstone n8n push path for beta`

---

## Task 10 — Admin UI: preview page, push timeline, dry-run controls ⏳ Pending

**Depends on:** Task 9

**Files:**
- Create: `frontend/src/app/(admin)/push/[push_log_id]/page.tsx`
- Modify: `frontend/src/app/(admin)/products/page.tsx` (update Push button flow)
- Create: `frontend/src/components/push/preview-panel.tsx`
- Create: `frontend/src/components/push/execution-timeline.tsx`
- Create: `frontend/src/components/push/dry-run-controls.tsx`

**Steps:**
- [ ] Step 1: `preview-panel.tsx` — displays `preview_payload.plan[]` as a human-readable mutation list. Shows `computed_prices` table. Shows `preflight.checks` as pass/fail badges.
- [ ] Step 2: `dry-run-controls.tsx` — two buttons per spec:
  - "Send Dry-Run" (primary, default)
  - "Send to OPS staging (LIVE)" (secondary, red-outlined) — opens confirm dialog requiring user to type `"PUSH PC61 TO STAGING"` before enabling submit. Admin role required.
- [ ] Step 3: `execution-timeline.tsx` — renders `execution_steps[]` as a timeline. Each step shows mutation name, latency, status. Streams new steps via SSE (`/api/push/{push_log_id}/stream`).
- [ ] Step 4: On `failed` status — red banner with `cleanup_targets` rendered as a checklist (category_id, product_id, size_ids, instructions from spec `§cleanup_targets JSONB shape`).
- [ ] Step 5: On `dry_run_pushed` — green banner showing fabricated `ops_product_id` (10001).
- [ ] Step 6: On `pushed` — green banner with real `ops_product_id` and link to OPS staging storefront.
- [ ] Step 7: Update `products/page.tsx` push button to navigate to `/push/preview?product_id=X&customer_id=Y` instead of directly triggering n8n webhook.

**Test:** Start dev server. Open `/products`, click Push → lands on preview page → dry-run → green banner. Verify red cleanup banner by hitting `/execute` with broken creds.

**Commit:** `feat(frontend): Phase 8 push UI — preview panel, dry-run controls, execution timeline`

---

## Task 11 — End-to-end manual test against VG OPS staging ⏳ Pending

**Depends on:** All tasks complete. Christian has seeded `push_mappings` with OPS color/size master-option IDs.

**Acceptance criteria (from spec `§Acceptance criteria`):**

- [ ] AC1: Preflight all-pass + dry-run for PC61 → `dry_run_pushed`, full `execution_steps` in DB, UI green banner with fabricated product_id 10001. No `push_mappings` row written.
- [ ] AC2: Delete one `push_mapping_options` row → `/preview` returns 422 with explicit `blockers` list. No `push_log` row created in `preview_ready` state.
- [ ] AC3: Live push (`dry_run=false` + valid `confirm_token` + admin role) → real OPS product created, `push_mappings` row written with real `target_ops_product_id`, `push_log.status = pushed`, OPS storefront shows PC61 with 30 variants, markup-applied prices, image, brand.
- [ ] AC4: Break OPS creds after preview, then execute → `failed` status, `cleanup_targets` populated with category_id + product_id + size_ids, UI red banner with cleanup instructions, no `push_mappings` row, no auto-rollback.
- [ ] AC5: Two concurrent `/execute` calls on same `(cid, pid)` → second returns 409.
- [ ] AC6: Change product price between preview and execute → execute returns 409 `PreviewExpired`.
- [ ] AC7: Every preview + execute appears in `audit_log` table with user, timestamp, route.
- [ ] AC8: Stop n8n container → preview + execute (live) still work end-to-end.

**Manual prerequisite:** Christian seeds OPS color/size master-option IDs into `push_mappings` table. One-time, ~15 min.

---

## Self-review checklist

Before marking any task done, verify against spec:

- [ ] Status vocab is exactly: `pending → preview_ready → executing → dry_run_pushed | pushed | failed`. No invented statuses.
- [ ] Partial unique index is on `status = 'executing'` only — not on `preview_ready`.
- [ ] No `/preflight` standalone route — preflight is Stage 1 inside `/preview`.
- [ ] `OpsClient` extended in `ops_inbound/ops_client.py` — no new `ops_push/ops_client.py`.
- [ ] No auto-rollback anywhere — halt-no-rollback is a locked spec decision.
- [ ] `confirm_token_hash` never appears in any API response — only `confirm_token` (plaintext, once).
- [ ] `sync_jobs` not used for push tracking — only `product_push_log`.
- [ ] `Authorization` header redacted to `"Bearer ***"` in `execution_steps` before DB write.
- [ ] `merge.py` deleted once `payload_builder.py` ships.
- [ ] `n8n-workflows/ops-push.json` moved to `deprecated/` with tombstone README.
