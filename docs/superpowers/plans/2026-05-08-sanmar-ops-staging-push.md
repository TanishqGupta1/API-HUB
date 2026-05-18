# Phase 8 — SanMar → OPS Staging Push (Beta): Implementation Plan

**Spec:** `docs/superpowers/specs/2026-05-11-integration-gateway-design.md`
**Previous spec (superseded):** `docs/superpowers/specs/2026-05-08-sanmar-ops-staging-push-design.md`
**Date:** 2026-05-13 (updated to match Integration Gateway spec)
**Status:** 7/11 tasks done. Tasks 4–7 are parallel once Task 1 lands.

> ⚠️ **Plan updated 2026-05-13** — Original plan was based on the VPCE spec (preview/execute + confirm_token). That spec was superseded on 2026-05-11 by the Integration Gateway design. Tasks 1, 8, 9, 11 have been rewritten. Tasks 4, 7 unchanged. Tasks 5, 6, 10 have minor naming updates.

---

## Task Assignments & Dependencies

| Task | Title | Owner | Status | Depends On | Blocks |
|------|-------|-------|--------|------------|--------|
| 1 | DB schema migration | Vidhi | ✅ Done | — | 4, 5, 6, 7 |
| 2 | Fix base_price=None in V2 normalizer | — | ✅ Done | — | — |
| 3 | Wire SanMar Inventory v200 SOAP | — | ✅ Done | — | — |
| 4 | OpsClient: mutation methods + OAuth2 refresh | Urvashi | ⏳ Pending | 1 | 5, 8 |
| 5 | FakeOpsClient (dry-run test double) | Urvashi | ⏳ Pending | 4 | 8 |
| 6 | payload_builder.py | Shinchana | ⏳ Pending | 1 | 8 |
| 7 | preflight.py (4 validation checks) | Shinchana | ⏳ Pending | 1 | 8 |
| 8 | Integration Gateway core (prepare + execute + build) | Vidhi | ✅ Done | 1, 4, 5, 6, 7 | 9 |
| 9 | New API routes (`/api/integrations/v1/`) + delete n8n path | Vidhi | ✅ Done | 8 | 10 |
| 10 | Admin UI: push log detail, integration keys page | Shinchana | ⏳ Pending | 9 | 11 |
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

Push one real SanMar product (PC61 — Port & Co Essential T-Shirt) to VG OPS staging end-to-end with correct prices, images, inventory, and full operator visibility. Single-product, manually triggered. No n8n in the push path for beta. Any orchestrator (n8n, curl, cron) can call the gateway via `X-Orchestrator-Key`.

---

## Constraints (locked in spec)

- No n8n in OPS push path for beta. Push runs in FastAPI process.
- Halt-no-rollback on failure. No auto-rollback. Manual cleanup checklist surfaced in UI.
- Idempotency-Key + payload_hash replace the old preview_id + confirm_token approach.
- Concurrency guard: `IN_FLIGHT` 409 if another push for same `(customer, product)` is `processing`.
- `sync_jobs` is NOT used for push tracking (inbound sync only). `product_push_log` owns push state.
- Auth headers redacted (`"Bearer ***"`) before writing to `step_results`. Plaintext never persisted.
- `integration_keys` table is the single source of truth for orchestrator API keys.

---

## File Structure

**New (`backend/modules/integrations/`):**
- `routes.py` — 4 gateway endpoints under `/api/integrations/v1/`
- `auth.py` — `X-Orchestrator-Key` dependency, key lookup + scope check
- `schemas.py` — push request/response envelopes, error envelope
- `service.py` — gateway shim calling `prepare_push_intent()` + `execute_push()`

**New (`backend/modules/ops_push/`):**
- `payload_builder.py` — sole owner of OPS-bound payload shape (`build_push_payload()`). Replaces `merge.py`.
- `preflight.py` — pure validation rules. Returns blockers list.
- `fake_ops_client.py` — in-memory test double with same interface as real OpsClient.

**Extended (not replaced):**
- `backend/modules/ops_inbound/ops_client.py` — add mutation methods + OAuth2 refresh on 401.

**Modified:**
- `backend/modules/push_log/models.py` — add +12 columns + `integration_keys` table + updated status vocab
- `backend/modules/push_log/schemas.py` — read shapes for new columns
- `backend/modules/ops_push/routes.py` — rewire admin push button to new `prepare_push_intent()` + `execute_push()`
- `backend/modules/markup/routes.py` — mark `/payload`, `/ops-variants`, `/ops-options` deprecated
- `backend/main.py` — register new integrations router, delete `N8N_*` env var checks (M4)

**Removed (M4):**
- `backend/modules/ops_push/service.py::trigger_n8n_push` + `N8N_PUSH_WEBHOOK_URL` env var
- `backend/modules/ops_push/merge.py` (replaced by `payload_builder.py`)
- `backend/modules/n8n_proxy/` (entire module — 172 LOC)
- `n8n-workflows/ops-push.json` → move to `n8n-workflows/deprecated/ops-push.json`

---

## Task 1 — DB schema migration ✅ Done

**All 12 Integration Gateway columns added, `integration_keys` table created, Pydantic schemas updated.**

**Files:**
- Modify: `backend/modules/push_log/models.py`
- Modify: `backend/modules/push_log/schemas.py`
- Create: `backend/migrations/push_log_phase8.sql` (reference only — app uses `create_all`)

**Steps:**
- [x] Step 1: Replace old VPCE columns with new Integration Gateway columns on `ProductPushLog`:
  ```python
  # Remove: preflight_results, preview_payload, preview_built_at,
  #         confirm_token_hash, confirm_token_consumed_at, input_hash, execution_steps

  # Add these 12 columns:
  request_id:        Mapped[uuid_mod.UUID] = mapped_column(default=uuid_mod.uuid4, unique=True)
  key_id:            Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
  idempotency_key:   Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
  payload_hash:      Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
  supplier_slug:     Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
  supplier_sku:      Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
  callback_url:      Mapped[Optional[str]] = mapped_column(Text, nullable=True)
  callback_status:   Mapped[str]           = mapped_column(String(32), default="not_requested")
  callback_attempts: Mapped[int]           = mapped_column(default=0)
  step_results:      Mapped[Optional[list]]= mapped_column(JSONB, nullable=True)
  cleanup_targets:   Mapped[Optional[dict]]= mapped_column(JSONB, nullable=True)
  retry_of:          Mapped[Optional[uuid_mod.UUID]] = mapped_column(nullable=True)
  ```
- [x] Step 2: Update status vocab comment in `models.py`:
  `accepted → queued → processing → pushed | failed | partial_failure | rejected | canceled | dry_run_pushed`
- [x] Step 3: Add indexes:
  ```python
  __table_args__ = (
      Index("idx_push_log_payload_hash", "payload_hash"),
      Index("idx_push_log_idempotency", "key_id", "idempotency_key"),
      Index(
          "uq_push_log_in_flight",
          "customer_id", "product_id",
          unique=True,
          postgresql_where=text("status = 'processing'"),
      ),
  )
  ```
- [x] Step 4: Create `integration_keys` table as a new model in `backend/modules/integrations/models.py`:
  ```python
  class IntegrationKey(Base):
      __tablename__ = "integration_keys"
      id:                    Mapped[str]            = mapped_column(String(64), primary_key=True)
      key_hash:              Mapped[str]            = mapped_column(String(128))
      name:                  Mapped[str]            = mapped_column(String(255))
      allowed_customer_ids:  Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
      allowed_supplier_slugs:Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
      rate_limit_per_minute: Mapped[int]            = mapped_column(default=60)
      is_active:             Mapped[bool]           = mapped_column(Boolean, default=True)
      last_used_at:          Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
      created_at:            Mapped[datetime]       = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
      revoked_at:            Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
  ```
- [x] Step 5: Update `push_log/schemas.py` — add `StepResult`, `PushRequestResponse`, `PushStatusResponse` Pydantic models. No `confirm_token_hash` anywhere. No `preview_payload`.
- [ ] Step 6: Start backend, confirm tables alter cleanly.

**Test:** `GET /api/push-log` returns rows without error. New columns present in `\d product_push_log`. `integration_keys` table exists.

**Commit:** `feat(push_log): Phase 8 schema — Integration Gateway columns, integration_keys table`

---

## Task 2 — Fix base_price=None in V2 normalizer ✅ Done

**Branch:** `origin/fix/spike-bugs-1-2` (commit `78a4a42`) — not yet merged to main.

`ps_normalizer_v2.merge_pricing()` now backfills `variant.base_price` from the cheapest qty=1 Net tier after building price tiers. Existing `base_price` values are not overwritten.

**Merge when ready:** `git merge origin/fix/spike-bugs-1-2`

---

## Task 3 — Wire SanMar Inventory v200 SOAP ✅ Done (manual test deferred)

**Branch:** `origin/fix/spike-bugs-1-2` (commit `78a4a42`) — not yet merged to main.

`adapter.py::hydrate_product()` now calls `inv_client.get_inventory()` after `merge_media`, maps `quantity_available` + `warehouse_code` onto each variant by `part_id`. Swallows on failure (`variant.inventory=None` treated as unknown downstream).

**Merge when ready:** same branch as Task 2.

---

## Task 4 — Extend OpsClient with mutation methods + OAuth2 refresh ⏳ Pending

**Files:**
- Modify: `backend/modules/ops_inbound/ops_client.py`
- Create: `backend/tests/test_ops_client_mutations.py`

**Steps:**
- [ ] Step 1: Add 6 mutation methods to `OpsClient`:
  - `set_product_category(input: dict) -> dict` — returns `{"products_id": int}`
  - `set_product(input: dict) -> dict` — returns `{"products_id": int}`
  - `set_product_size(input: dict) -> dict` — returns `{"products_id": int, "size_id": int}`
  - `set_product_price(input: dict) -> dict`
  - `set_assign_options(input: dict) -> dict`
  - `set_product_design(input: dict) -> dict`
  Each wraps `self.query(MUTATION_STRING, variables={"input": input})` and unwraps the response key.
- [ ] Step 2: Add OAuth2 refresh on 401 — catch `AuthError` in `query()`, call `_refresh_token()`, retry once, then re-raise.
- [ ] Step 3: Add `_refresh_token(self)` — POST to `self.token_url` with `client_credentials` grant, update `self.auth_token`.
- [ ] Step 4: Add mutation GraphQL strings as module-level constants (not inline).
- [ ] Step 5: Tests — mock `httpx.AsyncClient`, assert each mutation sends correct query and unwraps response key.

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
- [ ] Step 3: Record every call in `self.calls: list[dict]` with `method`, `input`, `response`, `called_at` — written to `step_results` JSONB by pipeline (note: `step_results`, not `execution_steps`).
- [ ] Step 4: `cleanup_targets` always `None`. Status set to `dry_run_pushed`, never `pushed`.
- [ ] Step 5: Tests — call all 6 methods, assert IDs are unique and incrementing, assert `calls` list populated.

**Test:** `pytest backend/tests/test_fake_ops_client.py -v` — all pass.

**Commit:** `feat(ops_push): FakeOpsClient — in-memory dry-run test double`

---

## Task 6 — payload_builder.py ⏳ Pending

**Files:**
- Create: `backend/modules/ops_push/payload_builder.py`
- Create: `backend/tests/test_payload_builder.py`
- Delete: `backend/modules/ops_push/merge.py`

**Steps:**
- [ ] Step 1: Create `build_push_payload(product, customer, markup_rules, push_mappings) -> OPSPushPayload`.
- [ ] Step 2: `OPSPushPayload` Pydantic model with `.mutation_plan: list[dict]` — ordered mutations:
  `setProductCategory → setProduct → setProductSize × N → setProductPrice × ≥N → setAssignOptions → setProductDesign`
- [ ] Step 3: Implement `payload_hash(product, customer, markup_rules, push_mappings) -> str` — lowercase hex SHA-256 using RFC 8785 canonicalization (sort keys, no nulls, no whitespace). Used by gateway for idempotency ledger.
- [ ] Step 4: Implement computed prices — `{sku, base_price, final_price, markup_pct, rounding}` per variant. **Markup engine applied here** (this is Bug 3 fix — markup was previously bypassed).
- [ ] Step 5: Tests — every variant has `vendor_price > 0`; `payload_hash` is deterministic; mutation plan ordering matches spec sequence; `final_price = base_price * (1 + markup_rate)`.

**Test:** `pytest backend/tests/test_payload_builder.py -v` — all pass.

**Commit:** `feat(ops_push): payload_builder — build_push_payload + markup engine fix`

---

## Task 7 — preflight.py (validation checks) ⏳ Pending

**Files:**
- Create: `backend/modules/ops_push/preflight.py`
- Create: `backend/tests/test_preflight.py`

**Steps:**
- [ ] Step 1: Create `run_preflight(product, customer, db) -> PreflightResults` async function.
- [ ] Step 2: Implement validation checks. Each returns `(name, ok: bool, detail: str)`:
  1. `base_price_set` — every `ProductVariant.base_price` not null and > 0
  2. `markup_rule_resolves` — markup engine resolves a rule for this product
  3. `push_mappings_present` — every `ProductOption` + attribute has OPS mapping IDs populated
  4. `ops_oauth2_reachable` — smoke-test token fetch against `customer.ops_token_url`
  5. `image_urls_reachable` — HEAD per image URL returns 2xx (5s timeout)
  6. `prefix_collision` — check OPS for existing product with same `supplier_sku`; block if found with no `push_mapping` row
  7. `required_fields` — `product_name`, `supplier_sku`, ≥1 variant, ≥1 image
  8. `decoration_attached` — if supplier has decoration overlay, require decoration options present
- [ ] Step 3: Return `PreflightResults` with `checks`, `blockers`, `warnings`, `computed_at`. Blockers → 422 `PREFLIGHT_BLOCKER` in gateway. No `push_log` row created on blocker.
- [ ] Step 4: Tests — all-pass path; single blocker path; `ops_oauth2_reachable` fail; `prefix_collision` fire.

**Test:** `pytest backend/tests/test_preflight.py -v` — all pass.

**Commit:** `feat(ops_push): preflight — validation checks before any OPS write`

---

## Task 8 — Integration Gateway core ⚠️ Partial (stubs in place; blocked on Tasks 4–7)

**Depends on:** Tasks 1, 4, 5, 6, 7

**Migration phases this task covers: M0 prereqs done + M1 + M3**

**Files:**
- Create: `backend/modules/ops_push/gateway.py`
- Create: `backend/tests/test_gateway.py`

**Steps:**
- [x] Step 1: Create `prepare_push_intent(request_body, key_id, idempotency_key, db) -> PushLogRow`:
  - Verify `X-Orchestrator-Key` → 401 `BAD_SIGNATURE` / 403 `KEY_NOT_ALLOWED` / 403 `KEY_REVOKED`
  - Check idempotency ledger on `(key_id, idempotency_key)`:
    - Same key + same `payload_hash` → return existing `push_log_id` (200, no new work)
    - Same key + different `payload_hash` → 409 `IDEMPOTENCY_CONFLICT`
    - First-seen → continue
  - Check `IN_FLIGHT` — 409 if `processing` row exists for `(customer_id, product_id)`
  - Resolve customer + supplier from DB (never from request body directly)
  - Run `run_preflight()` → 422 `PREFLIGHT_BLOCKER` if blockers (no push_log row created)
  - Compute `payload_hash` via `payload_builder.payload_hash()`
  - Insert `ProductPushLog` row: `status=accepted`, `payload_hash`, `idempotency_key`, `key_id`, `supplier_slug`, `supplier_sku`, `callback_url`, `dry_run`
  - Return `{push_log_id, status: "accepted", ...}`

- [x] Step 2: Create `execute_push(push_log_id, db) -> None` (runs synchronously or as BackgroundTask):
  - Atomic UPDATE: `status=accepted → processing`
  - Select client: `dry_run=True` → `FakeOpsClient`, `dry_run=False` → real `OpsClient`
  - Call `build_push_payload()` — get mutation plan
  - Execute mutations sequentially. After each: append to `step_results` (auth headers redacted to `"Bearer ***"`)
  - On partial failure: halt, populate `cleanup_targets`, set `status=partial_failure`
  - On hard failure before any OPS write: `status=failed`
  - On success: upsert `push_mappings` (live only), set `status=pushed` or `dry_run_pushed`, set `ops_product_id`
  - Fire callback if `callback_url` set — exponential backoff, max 5 attempts, update `callback_status`

- [x] Step 3: Async path — variant count > 20 → `BackgroundTask(execute_push)`, return 202 immediately with `push_log_id`.

- [x] Step 4: Rewire existing admin route `POST /api/push/{cid}/{pid}` to call `prepare_push_intent()` + `execute_push()` internally. Keep response shape identical — admin UI push button must still work unchanged (M3).

- [ ] Step 5: Tests — dry-run full flow (assert `dry_run_pushed`, no push_mappings); idempotency replay (same key+body → 200 same id); conflict (same key+different body → 409); `IN_FLIGHT` (409); preflight blocker aborts before push_log insert; mid-sequence failure → `partial_failure` + `cleanup_targets`; callback fires on success.

> **Note (2026-05-15):** `gateway.py` exists with `prepare_push_intent()` + `execute_push()`. All 4 dependencies (Tasks 4–7) are currently stubs in gateway.py. Swap-in comments left in place for each — gateway is functional for stub/dry-run but not real OPS pushes until stubs are replaced.

**Test:** `pytest backend/tests/test_gateway.py -v` — all pass.

**Commit:** `feat(ops_push): Integration Gateway core — prepare_push_intent + execute_push + M3 rewire`

---

## Task 9 — New gateway routes + delete n8n path ⚠️ Partial (routes done; n8n cleanup remaining)

**Depends on:** Task 8

**Migration phases: M2 + M4**

**Files:**
- Create: `backend/modules/integrations/routes.py`
- Create: `backend/modules/integrations/auth.py`
- Create: `backend/modules/integrations/schemas.py`
- Modify: `backend/modules/ops_push/service.py` (remove `trigger_n8n_push`)
- Modify: `backend/main.py` (register integrations router, delete N8N env checks)
- Move: `n8n-workflows/ops-push.json` → `n8n-workflows/deprecated/ops-push.json`
- Create: `n8n-workflows/deprecated/README.md`

**Steps:**
- [x] Step 1: Create 4 gateway endpoints in `integrations/routes.py` (all under `/api/integrations/v1/`):
  - `POST /suppliers/{supplier_slug}/products` — catalog upsert (auth: `X-Orchestrator-Key`)
  - `GET  /suppliers/{supplier_slug}/schema` — discover required + optional fields
  - `POST /push-requests` — calls `prepare_push_intent()` + `execute_push()`
  - `GET  /push-requests/{push_log_id}` — poll push status; returns `PushStatusResponse`
- [x] Step 2: Create `integrations/auth.py` — `get_orchestrator_key()` FastAPI dependency. Reads `X-Orchestrator-Key` header, SHA-256 hashes it, looks up `integration_keys` table, checks `is_active`, `revoked_at`, `allowed_customer_ids`, `allowed_supplier_slugs`. Updates `last_used_at`.
- [x] Step 3: Create `integrations/schemas.py` — request envelope, 202 response, terminal GET response, error envelope with all error codes from spec.
- [ ] Step 4: Remove `trigger_n8n_push` + `N8N_PUSH_WEBHOOK_URL` from `service.py` (M4).
- [ ] Step 5: Delete `backend/modules/n8n_proxy/` entire module (M4).
- [ ] Step 6: Mark old push route (`POST /api/push/{cid}/{pid}`) as `deprecated=True` in OpenAPI — do not delete yet.
- [ ] Step 7: Move `n8n-workflows/ops-push.json` → `n8n-workflows/deprecated/`. Write tombstone `README.md` explaining what changed and that n8n is now a consumer of the gateway, not in the push path.
- [x] Step 8: Register `integrations` router in `backend/main.py`.

**Test:** `curl -H "X-Orchestrator-Key: test" -H "Idempotency-Key: test-1" POST /api/integrations/v1/push-requests` → 401. With valid key → 422 (preflight) or 202 (accepted). Old route still responds.

**Commit:** `feat(integrations): M2+M4 — 4 gateway endpoints, X-Orchestrator-Key auth, delete n8n push path`

---

## Task 10 — Admin UI: push log detail + integration keys page ⏳ Pending

**Depends on:** Task 9

**Files:**
- Modify: `frontend/src/app/(admin)/push-log/[push_log_id]/page.tsx` (or create if not exists)
- Create: `frontend/src/app/(admin)/integrations/keys/page.tsx`
- Create: `frontend/src/components/push/step-results-timeline.tsx`
- Create: `frontend/src/components/push/cleanup-banner.tsx`

**Steps:**
- [ ] Step 1: Push log detail page — show new fields: `orchestrator key_id`, `idempotency_key`, `payload_hash`, `callback_status`, `callback_attempts`.
- [ ] Step 2: `step-results-timeline.tsx` — renders `step_results[]` as a timeline. Each step: mutation name, ok/failed, ops_id if returned.
- [ ] Step 3: `cleanup-banner.tsx` — red banner on `partial_failure` status. Renders `cleanup_targets` as a checklist with manual deletion instructions.
- [ ] Step 4: Green banner on `dry_run_pushed` — fabricated `ops_product_id` (10001).
- [ ] Step 5: Green banner on `pushed` — real `ops_product_id` with link to OPS staging storefront.
- [ ] Step 6: `/integrations/keys` page — `vg_admin` only. Table of `integration_keys` (id, name, scope, last_used_at, status). Actions: create new key (show raw key once), revoke.

**Test:** Start dev server. Push log detail shows new fields. Cleanup banner appears on `partial_failure`. Keys page lists + creates keys.

**Commit:** `feat(frontend): push log detail + integration keys management UI`

---

## Task 11 — E2E manual test against VG OPS staging ⏳ Pending

**Depends on:** All tasks complete.

**Acceptance criteria (from spec §Acceptance criteria):**

- [ ] AC1: M0 migration applied — `integration_keys` table exists, 12 columns on `product_push_log`, `VariantIngest.sort_order` field present.
- [ ] AC2: `dry_run=true` for PC61 via curl + `X-Orchestrator-Key` → `dry_run_pushed`, full `step_results` in DB, no `push_mappings` row, no OPS writes. UI green banner with fabricated product_id 10001.
- [ ] AC3: `dry_run=false` happy path → `status=pushed`, `push_mappings` row written with real `target_ops_product_id`, OPS storefront shows PC61 with 30 variants, markup-applied prices, image, brand. Callback fires.
- [ ] AC4: Send same `Idempotency-Key` + same body twice → second call returns 200 with same `push_log_id`, no new OPS work.
- [ ] AC5: Send same `Idempotency-Key` + different body → 409 `IDEMPOTENCY_CONFLICT`.
- [ ] AC6: Send key scoped away from this customer → 403 `KEY_NOT_ALLOWED`.
- [ ] AC7: Send invalid/unknown key → 401 `BAD_SIGNATURE`.
- [ ] AC8: Break OPS creds mid-execution → `partial_failure`, `cleanup_targets` populated, UI red banner, no `push_mappings` row, no auto-rollback.
- [ ] AC9: Two concurrent pushes for same `(customer, product)` → second returns 409 `IN_FLIGHT`.
- [ ] AC10: Stop n8n container → push still works end-to-end (n8n not in path).
- [ ] AC11: `grep -rn "n8n" backend/modules/` returns 0 functional refs (M4 verified).

---

## Self-review checklist

Before marking any task done, verify against spec (`2026-05-11-integration-gateway-design.md`):

- [ ] Status vocab is exactly: `accepted → queued → processing → pushed | failed | partial_failure | rejected | canceled | dry_run_pushed`. No invented statuses.
- [ ] Concurrency guard index is on `status = 'processing'` — not `executing`.
- [ ] No `confirm_token` anywhere — replaced by `Idempotency-Key` + `payload_hash`.
- [ ] `OpsClient` extended in `ops_inbound/ops_client.py` — no new `ops_push/ops_client.py`.
- [ ] No auto-rollback anywhere — halt-no-rollback is locked.
- [ ] `Authorization` header redacted to `"Bearer ***"` in `step_results` before DB write.
- [ ] `merge.py` deleted once `payload_builder.py` ships.
- [ ] Markup engine called inside `build_push_payload()` — never bypassed.
- [ ] `n8n-workflows/ops-push.json` moved to `deprecated/` with tombstone README.
- [ ] `n8n_proxy` module deleted in M4.
- [ ] Admin push button (`POST /api/push/{cid}/{pid}`) still works after M3 rewire.
- [ ] `integration_keys` raw key shown only once at creation — never stored, only `key_hash`.
