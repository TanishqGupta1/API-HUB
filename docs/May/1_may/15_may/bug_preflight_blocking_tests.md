# Bug — Real `run_preflight` Blocking All Push Tests After Main Pull

**Date found:** 2026-05-15
**Severity:** High (blocked all gateway + push tests from running)
**Status:** ✅ Fixed
**Commit:** `29b7308`
**Files fixed:** `test_gateway_push_request.py`, `test_admin_route_preserved.py`, `test_ops_push.py`, `test_ops_push_failure.py`

---

## What was the bug?

After pulling from main (which brought in Shinchana's Tasks 6 and 7 — `payload_builder.py` and `preflight.py`), most push tests started returning `422 PREFLIGHT_BLOCKER` instead of testing what they were supposed to test.

For example, a test like `test_happy_path_push_returns_202` would get a `422` response with an error body like:

```json
{
  "detail": {
    "code": "PREFLIGHT_BLOCKER",
    "blockers": [
      "No markup rule found for this customer and product",
      "Product has no images",
      "Customer has no OPS credentials configured"
    ]
  }
}
```

...instead of the expected `202 Accepted`. The test fails before it even gets to the part it's meant to verify.

---

## Why did this happen?

### What preflight actually checks

The real `run_preflight` function (from `backend/modules/ops_push/preflight.py`) validates that a product is ready to push to OPS before anything gets written. It checks:

1. Does this customer have a markup rule for this product?
2. Does the product have at least one variant?
3. Does the product have at least one image?
4. Does the customer have OPS credentials configured (the OAuth2 tokens to call OPS GraphQL)?

These are all real, important checks. If any of them fail, the push is blocked with a 422. This is by design — you should not push an incomplete product to OPS.

### Why test products fail preflight

The test fixtures create minimal objects. A `push_scaffold` fixture in the test suite creates a customer and a product in the database, but:
- No markup rules are attached to the product for that customer
- The product has no images
- The customer has no OPS credential rows
- The product may not have variants

These are "skeleton" fixtures — enough to test the routing and auth logic, but not enough to pass a real preflight check.

### Why it worked before

Before the main pull, `run_preflight` was a stub in `gateway.py`:

```python
async def _stub_run_preflight(product, customer, db) -> _PreflightStub:
    """TODO Task 7: replace with → from .preflight import run_preflight"""
    logger.warning("preflight stub active — Task 7 not yet merged")
    return _PreflightStub()
```

`_PreflightStub` always returned `ok=True` with an empty `blockers` list. So all tests that exercised the push path sailed straight through preflight without issue — but they were being tested against a fake version of it.

Once Task 7 merged, the gateway wired in the real `run_preflight`:
```python
from modules.ops_push.preflight import run_preflight
```

Now every push call hits the real implementation, and minimal test fixtures fail immediately.

### Why this wasn't caught earlier

The stub was intentionally temporary. While Tasks 6 and 7 hadn't merged yet, the tests were valid — they were testing the gateway's response to preflight passing. The expectation was that once the real `run_preflight` merged, tests would be updated. That update just hadn't happened before the merge.

---

## How does this connect to the existing codebase?

The `run_preflight` function sits at the start of `execute_push()` in `gateway.py`. Every push request — whether from the admin UI or from an external orchestrator via `X-Orchestrator-Key` — calls `execute_push()`, which calls `run_preflight()` first.

The test files affected all test the push path in different ways:

- **`test_gateway_push_request.py`** — tests the new Integration Gateway endpoint `POST /api/integrations/v1/push-requests`
- **`test_admin_route_preserved.py`** — tests the old admin push endpoint `POST /api/push/{customer_id}/{product_id}`
- **`test_ops_push.py`** — tests general OPS push behavior
- **`test_ops_push_failure.py`** — tests what happens when OPS mutations fail

All of these go through the same `execute_push()` → `run_preflight()` chain, so all were blocked.

---

## The fix

Added an `autouse` pytest fixture to each affected test file that patches `run_preflight` to always return `ok=True`:

```python
@pytest.fixture(autouse=True)
def _mock_preflight_ok():
    ok_result = MagicMock()
    ok_result.ok = True
    with patch("modules.ops_push.gateway.run_preflight", new=AsyncMock(return_value=ok_result)):
        yield
```

`autouse=True` means every test in the file gets this fixture automatically — no test has to opt into it. This way all gateway tests focus on what they're meant to test: routing, auth, concurrency guards, failure handling, callbacks.

For `test_ops_push.py`, the fix was slightly different. That file's tests call the full push pipeline including `execute_push()`, which also calls `build_push_payload()` — the payload builder from Task 6. Test products don't have variants or catalog data that the real payload builder needs, so that was mocked too:

```python
@pytest.fixture(autouse=True)
def _mock_gateway_deps():
    ok_preflight = MagicMock()
    ok_preflight.ok = True
    step = MagicMock()
    step.model_dump.return_value = {"mutation": "setProduct", "variables": {}}
    mock_payload = MagicMock()
    mock_payload.plan = [step]
    with patch("modules.ops_push.gateway.run_preflight", new=AsyncMock(return_value=ok_preflight)):
        with patch("modules.ops_push.gateway.build_push_payload", new=AsyncMock(return_value=mock_payload)):
            yield
```

### How the preflight blocker test still works

There's one test that specifically tests the `422 PREFLIGHT_BLOCKER` path: `test_push_preflight_blocker_returns_422`. This test applies its own inner patch *on top of* the autouse fixture:

```python
def test_push_preflight_blocker_returns_422(...):
    failing_result = MagicMock()
    failing_result.ok = False
    failing_result.blockers = ["No markup rule found"]
    with patch("modules.ops_push.gateway.run_preflight", new=AsyncMock(return_value=failing_result)):
        # inside this block, the inner patch wins over the autouse fixture
        response = client.post(...)
    assert response.status_code == 422
```

Python's `unittest.mock.patch` is a stack. When the inner `with patch(...)` block opens, it replaces the mock that the autouse fixture put in place. When the block closes, the autouse fixture's mock is restored. This means one test can specifically test the failure path without affecting any other test.

---

## How can this be prevented in the future?

### Option 1 (current): Keep the autouse mock in test files

The approach used here is the standard Django/FastAPI testing pattern: mock external dependencies at the boundary, test the unit you actually care about. The preflight mock stays in the test files. If `run_preflight`'s interface changes (different fields, async behavior), these mocks need to be updated — but that's a small, contained change.

### Option 2: Create a fully-equipped test fixture

If the team wants fully end-to-end integration tests with no mocking, you'd need a test fixture that creates a product complete with:
- A markup rule
- At least one variant
- At least one image
- A customer with valid OPS credentials

The downside is test complexity and brittleness — if preflight adds a new check, all these tests break again. The upside is that these tests would catch real integration issues between preflight and the push pipeline.

### Option 3: Write preflight-specific tests separately

The right separation is: `test_preflight.py` tests `run_preflight` thoroughly against real and fake products. `test_gateway_push_request.py` tests the gateway's response to preflight results. They don't need to be the same test. This is how the codebase is set up now — the mock makes the boundary explicit.

For now, the autouse mock approach is the right call: it keeps gateway tests focused on gateway behavior, and preflight behavior is tested separately in `test_preflight.py`.
