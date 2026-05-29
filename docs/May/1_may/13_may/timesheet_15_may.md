# Timesheet — 2026-05-15

**Developer:** Vidhi
**Branch:** `Vidhi`
**Commit pushed:** `29b7308`
**Test suite:** 418 / 418 passed

---

## Tasks Completed

### Phase 8 — Task 8: Integration Gateway Core (finalized)

**What was left from last session:** Dead stub code still in `gateway.py`, and 4 tests from the spec still not written (`IN_FLIGHT 409`, `PREFLIGHT_BLOCKER 422`, `partial_failure + cleanup_targets`, `callback fires on success`).

**What was done today:**

1. **Removed dead stubs from `gateway.py`** — `_PreflightStub`, `_stub_run_preflight`, `_PushPayloadStub`, `_stub_build_push_payload` were all still in the file as leftover code from before Tasks 6 and 7 (preflight, payload_builder) merged from main. They were never being called but were cluttering the file. Removed all four + the unused `hashlib` import.

2. **Wrote 4 missing tests in `test_gateway_push_request.py`:**

   | Test | What it covers |
   |------|---------------|
   | `test_push_in_flight_returns_409` | Manually inserts a `processing` row in DB, then pushes → expects 409 IN_FLIGHT |
   | `test_push_preflight_blocker_returns_422` | Patches `run_preflight` to return `ok=False` → expects 422 PREFLIGHT_BLOCKER |
   | `test_execute_push_partial_failure_records_cleanup_targets` | Calls `execute_push` directly with a 2-step plan where step 2 raises → asserts `status=partial_failure` and `cleanup_targets` populated |
   | `test_execute_push_fires_callback_on_success` | Calls `execute_push` with `callback_url` set → asserts `_fire_callback` called and `callback_status=sent` |

3. **Added `_mock_preflight_ok` autouse fixture** — real `run_preflight` (which landed from main) blocks test products that don't have markup rules/images/OPS creds. Added an autouse fixture that patches it to `ok=True` for all tests, so tests focus on gateway logic not on test data being "perfect". Tests that specifically test preflight behaviour apply their own inner patch.

**Status:** ✅ Done

---

### Phase 8 — Task 9: n8n Path Retirement (completed)

**What was left from last session:** Steps 4–7 — the actual deletion of the n8n push code — had not been done yet.

**What was done today:**

1. **Removed `trigger_n8n_push()` from `service.py`** — the function that fired a POST to `N8N_PUSH_WEBHOOK_URL`. Also cleaned up the now-unused imports: `os`, `httpx`, `Any`.

2. **Removed n8n proxy router from `main.py`:**
   - Deleted `from modules.n8n_proxy.routes import router as n8n_proxy_router`
   - Deleted `app.include_router(n8n_proxy_router, ...)` registration
   - Deleted the `n8n_proxy` HTTP client `aclose()` call from the lifespan shutdown handler
   - Removed `N8N_WEBHOOK_BASE_URL` from `_PROD_REQUIRED_ENV_VARS`

3. **Marked old route deprecated** — added `deprecated=True` to `POST /api/push/{customer_id}/{product_id}` in `ops_push/routes.py`. Route still works but Swagger UI shows it crossed out.

4. **Moved ops-push.json to deprecated folder** — moved `n8n-workflows/ops-push.json` → `n8n-workflows/deprecated/ops-push.json` and wrote a tombstone `README.md` explaining it was superseded by the Integration Gateway.

**Status:** ✅ Done

---

## Conflicts

### 1. Git push rejected (from previous session)
**What happened:** After pulling main into the `Vidhi` branch, `git push` was rejected because `origin/Vidhi` had been updated remotely (someone had force-pushed to the remote branch).
**Fix:** `git pull origin Vidhi --no-rebase` to merge the remote state, then push.

---

## Bugs Fixed

### Bug 1: `is_synthetic` column missing from schema migrations

**Where:** `backend/modules/integrations/models.py` + `backend/main.py`

**What happened:** The `IntegrationKey` model had an `is_synthetic` column (used to mark the admin-UI synthetic key so it can't be forged via `X-Orchestrator-Key` header). But there was no `ALTER TABLE` migration in `_SCHEMA_UPGRADES`. The test DB didn't have the column, so any test that looked up an integration key hit:
```
UndefinedColumnError: column integration_keys.is_synthetic does not exist
```

**Fix:** Added to `_SCHEMA_UPGRADES` in `main.py`:
```python
"ALTER TABLE integration_keys ADD COLUMN IF NOT EXISTS is_synthetic BOOLEAN NOT NULL DEFAULT FALSE"
```

---

### Bug 2: `test_happy_path_mutation_order` KeyError on `size_id` (from previous session)

**Where:** `backend/tests/test_ops_client_push.py`

**What happened:** The test's `_capture` helper intercepted mutations and matched them by checking `"SetProduct" in query`. But `"SetProduct"` is a substring of `"SetProductSize"` — so the second `setProductSize` call matched the `setProduct` branch and returned `_PRODUCT_OK` (which has `{"setProduct": {"products_id": 200}}`). The `set_product_size` wrapper then tried `data["setProductSize"]` which was `None`, giving `r.data = {}`. Then `push.py` tried `r.data["size_id"]` and raised `KeyError`.

**Fix:** Reordered conditions in `_capture` — check `SetProductSize` and `SetProductPrice` **before** `SetProduct`, so the longer/more specific names match first.

---

### Bug 3: Test suite failures after real `run_preflight` landed from main

**Where:** Multiple test files

**What happened:** After pulling from main, Tasks 6 and 7 (payload_builder, preflight) were now real implementations. The real `run_preflight` checks for markup rules, at least one variant, images, and OPS credentials. Test products in the existing tests don't have any of these — they're minimal fixture objects. So any test that tried to push a product immediately got a `422 PREFLIGHT_BLOCKER` instead of proceeding.

**Tests failing:**
- `test_gateway_push_request.py` — all push tests except auth ones
- `test_admin_route_preserved.py` — admin push route tests
- `test_ops_push.py` — old push route tests
- `test_ops_push_failure.py` — failure path test

**Fix:** Added an autouse `_mock_preflight_ok` fixture (or `_mock_gateway_deps` where `build_push_payload` also needed mocking) to each affected test file. The fixture patches `run_preflight` to return `ok=True` for the duration of the test, without changing the real production code at all.

---

### Bug 4: `test_production_mode_fails_when_n8n_webhook_base_url_missing` false failure

**Where:** `backend/tests/test_n8n_url_config.py`

**What happened:** Test asserted that production startup fails when `N8N_WEBHOOK_BASE_URL` is missing. After removing it from `_PROD_REQUIRED_ENV_VARS` as part of Task 9, the test started failing (it expected a RuntimeError about `N8N_WEBHOOK_BASE_URL` but none was raised).

**Fix:** Deleted that test case. Also updated `test_production_mode_passes_when_all_set` to not set `N8N_WEBHOOK_BASE_URL` since it's no longer required.

---

### Bug 5: `test_admin_route_no_n8n_webhook_trigger` AttributeError

**Where:** `backend/tests/test_admin_route_preserved.py`

**What happened:** Test used `monkeypatch.setattr("modules.ops_push.service.trigger_n8n_push", _spy)` to verify the admin push route doesn't call the legacy n8n webhook. After we deleted `trigger_n8n_push` from `service.py` as part of Task 9, monkeypatch raised `AttributeError: <module> does not have attribute trigger_n8n_push`.

**Fix:** Removed the test — it was testing deleted functionality. The gateway has replaced the n8n path entirely, so there's nothing to spy on anymore.

---

## Summary

| Item | Count |
|------|-------|
| Tasks completed | 2 (Phase 8 T8, T9) |
| Files modified | 10 |
| Files created | 2 (deprecated/README.md, timesheet) |
| Tests added | 4 new gateway tests |
| Bugs fixed | 5 |
| Test suite result | 418 / 418 ✅ |
