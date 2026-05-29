# Task — Phase 8 T8: Gateway Stub Cleanup + Missing Tests

**Owner:** Vidhi
**Date:** 2026-05-15
**Status:** ✅ Done
**Commit:** `29b7308`
**Related plan:** `docs/superpowers/plans/2026-05-08-sanmar-ops-staging-push.md`
**Related doc:** `docs/May/1_may/13_may/phase8_task8_done.md`

---

## What is this?

When Task 8 (Integration Gateway) was first written on 2026-05-13, it had four stub functions as temporary placeholders for work that other team members (Urvashi and Shinchana) hadn't finished yet. The idea was: we write the gateway logic now, and the stubs get swapped out with real implementations once the other tasks merge.

By 2026-05-15, **Tasks 6 and 7 had already merged from main** — Shinchana's `payload_builder.py` and `preflight.py` were live. But nobody cleaned up the stubs. The dead code was still sitting in `gateway.py`, pointing at functions that weren't being called anywhere.

This task is two things combined:
1. Delete the dead stub code that was left behind after T6 and T7 merged
2. Write the 4 tests that the spec required but hadn't been written yet

---

## Why was this task necessary?

### Dead code is a maintenance trap

The four stubs had `TODO` comments like:
```python
async def _stub_run_preflight(product, customer, db) -> _PreflightStub:
    """TODO Task 7: replace with → from .preflight import run_preflight"""
    logger.warning("preflight stub active — Task 7 not yet merged")
    return _PreflightStub()
```

Task 7 had already merged. The stub was never being called — the real `run_preflight` was wired in at the top of the file. But a new developer reading `gateway.py` would see this comment and think there's still work pending. Or worse, they'd accidentally call the stub instead of the real function and spend hours debugging why preflight always passes.

Dead code like this is dangerous because:
- It creates confusion about what's actually running in production
- It makes the file longer and harder to read
- The `logger.warning("preflight stub active")` would flood production logs if it ever got called

### The 4 missing tests were required by the spec

The spec (`docs/superpowers/specs/2026-05-11-integration-gateway-design.md`) listed specific scenarios that had to be covered by tests. After the initial Task 8 commit on 2026-05-13, only the basic happy-path and auth tests existed. Four scenarios from the spec were still untested:

| Missing test | Why it matters |
|-------------|---------------|
| `IN_FLIGHT 409` | The concurrency guard exists in code but was never verified to actually fire |
| `PREFLIGHT_BLOCKER 422` | The preflight rejection path existed but was never tested |
| `partial_failure + cleanup_targets` | The most critical failure mode — halt-no-rollback — had no test |
| `callback fires on success` | The callback delivery mechanism was completely untested |

If `IN_FLIGHT` was broken and nobody tested it, two simultaneous pushes could write the same product twice to OPS — which is irreversible and would require manual cleanup.

---

## How does it connect to the existing codebase?

### The stubs were in `gateway.py`

`backend/modules/ops_push/gateway.py` is the brain of the push pipeline. Every push request goes through two functions in this file: `prepare_push_intent()` and `execute_push()`. The stubs were dead code sitting between the imports and the actual functions:

```
gateway.py structure (before cleanup):
  imports
  → _PreflightStub class        ← dead, was for Task 7 (REMOVED)
  → _stub_run_preflight()       ← dead, was for Task 7 (REMOVED)
  → _PushPayloadStub class      ← dead, was for Task 6 (REMOVED)
  → _stub_build_push_payload()  ← dead, was for Task 6 (REMOVED)
  → _StubOpsClient              ← still active, for Task 4 (KEPT)
  → _StubFakeOpsClient          ← still active, for Task 5 (KEPT)
  → _redact_auth()
  → _fire_callback()
  → prepare_push_intent()
  → execute_push()
```

The real `run_preflight` is imported at line 32:
```python
from modules.ops_push.preflight import run_preflight
```
...and is called at line 298:
```python
preflight = await run_preflight(db, customer_id, product.id)
```

The stubs were never being called at all. They were just taking up space.

### The tests are in `test_gateway_push_request.py`

This file (`backend/tests/test_gateway_push_request.py`) tests the `/api/integrations/v1/push-requests` endpoint end-to-end, hitting the real database. The new tests follow the same pattern as the existing ones — they use the `push_scaffold` fixture (a customer + product in the DB) and the `integration_key` fixture (a real `IntegrationKey` row), and make HTTP requests via the ASGI test client.

The 4 new tests use `unittest.mock.patch` to simulate failure scenarios:
- `patch("modules.ops_push.gateway.run_preflight", ...)` — makes preflight return a blocker
- `patch("modules.ops_push.gateway._StubOpsClient", ...)` — makes the OPS client fail mid-plan
- `patch("modules.ops_push.gateway._fire_callback", ...)` — intercepts the callback HTTP call

---

## The `_mock_preflight_ok` fixture — why was it needed?

When the tests were written on 2026-05-13, the real `preflight.py` hadn't merged yet. So tests passed because the stub always returned `ok=True`. After pulling from main, the real preflight ran — and immediately failed on every test product, because:

- Test products have no markup rules (preflight checks: does this customer have a price rule for this product?)
- Test products have no images (preflight checks: is there at least one image to push?)
- Test products point to fake OPS URLs like `https://test.ops.com` that don't exist

Every single push test was returning `422 PREFLIGHT_BLOCKER` instead of testing what it was meant to test.

The fix was a fixture that patches `run_preflight` to always return `ok=True`:
```python
@pytest.fixture(autouse=True)
def _mock_preflight_ok():
    ok_result = MagicMock()
    ok_result.ok = True
    with patch("modules.ops_push.gateway.run_preflight", new=AsyncMock(return_value=ok_result)):
        yield
```

`autouse=True` means every test in the file automatically gets this mock — no test has to ask for it. The `test_push_preflight_blocker_returns_422` test overrides it with its own inner patch to specifically test the failure path.

This approach is important because it separates concerns: the gateway tests are testing *gateway logic*, not whether the test product has all the required fields. Those are separate tests in `test_preflight.py`.

---

## What was done step by step

### 1. Removed dead stubs from `gateway.py`

Deleted:
- `class _PreflightStub` — a fake preflight result with empty blockers list
- `async def _stub_run_preflight()` — always returned the fake preflight result, logged a warning
- `class _PushPayloadStub` — a fake payload builder with one hardcoded stub step
- `def _stub_build_push_payload()` — always returned the fake payload, logged a warning

Also removed `import hashlib` which was only used inside `_PushPayloadStub` and was now unused. `import json` was kept because it's still used in the `_fire_callback` function.

Updated the module docstring from the verbose "Stub swap guide" to a single clean line.

### 2. Added 4 tests to `test_gateway_push_request.py`

**Test 1: `test_push_in_flight_returns_409`**

Manually inserts a `ProductPushLog` row with `status="processing"` into the database for the same `(customer, product)` pair. Then makes a push request and asserts the response is `409` with the code `IN_FLIGHT`. Uses a `try/finally` to clean up the manually inserted row so it doesn't leak into other tests.

**Test 2: `test_push_preflight_blocker_returns_422`**

Applies its own `patch("modules.ops_push.gateway.run_preflight", ...)` inside the test body, setting `ok=False` and providing a realistic error envelope. This inner patch overrides the autouse `_mock_preflight_ok` fixture for the duration of this test. Asserts `422` and `detail.code == "PREFLIGHT_BLOCKER"`.

**Test 3: `test_execute_push_partial_failure_records_cleanup_targets`**

Calls `execute_push()` directly (not through the HTTP route) with a 2-step plan where step 2 raises a `RuntimeError`. Patches both `build_push_payload` (to return a controlled plan) and `_StubOpsClient` (to succeed on step 1, fail on step 2). After execution, reads the push_log row from DB and asserts `status="partial_failure"` and `cleanup_targets` has the `ops_product_id` that was created in step 1.

**Test 4: `test_execute_push_fires_callback_on_success`**

Creates a push_log row with `callback_url="https://callback.example.com/webhook"` and `callback_status="pending"`. Patches `build_push_payload` to return a single-step plan, and `_StubOpsClient` to succeed. Patches `_fire_callback` to return `True` without making a real HTTP call. After execution, asserts `push_log.callback_status == "sent"` in the DB and that `_fire_callback` was actually called.

---

## How can this be modified in the future?

### When Tasks 4 and 5 merge (Urvashi's work)

The two remaining stubs in `gateway.py` get swapped:
- `_StubOpsClient` → real `OpsClient` from `modules/ops_client/client.py`
- `_StubFakeOpsClient` → real `FakeOpsClient` from `modules/ops_push/fake_ops_client.py`

This is a two-line change in `gateway.py` — replace the stub class definitions with import statements. The tests don't change at all because they mock the client at the class level.

### Adding more test scenarios

The test file follows a pattern that's easy to extend. Future tests could cover:
- Push to an inactive supplier → `SUPPLIER_INACTIVE` error
- Key scoped to a different customer → `KEY_NOT_ALLOWED` 403
- Callback URL returns 500 → `callback_status="failed"`, `callback_attempts=1`
- Retry with `retry_of` linking → verify the `retry_of` column on the new push_log row

### Changing the autouse fixture

If the team decides to create a fully-featured test product that passes all preflight checks (has markup rules, variants, images, valid OPS creds), the `_mock_preflight_ok` fixture could be removed. The tests would then be true end-to-end integration tests with no mocking. The trade-off is more fixture setup code vs more realistic tests.
