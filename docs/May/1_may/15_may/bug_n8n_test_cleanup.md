# Bug — Tests Patching and Testing Deleted n8n Code

**Date found:** 2026-05-15
**Severity:** Medium (blocked test suite run after Task 9 cleanup)
**Status:** ✅ Fixed
**Commit:** `29b7308`
**Files fixed:** `test_admin_route_preserved.py`, `test_n8n_url_config.py`

---

## What were the bugs?

Two separate test failures appeared immediately after removing the n8n push code in Task 9.

### Bug A: `AttributeError` in `test_admin_route_no_n8n_webhook_trigger`

```
AttributeError: <module 'modules.ops_push.service'> does not have attribute 'trigger_n8n_push'
```

This happened in `backend/tests/test_admin_route_preserved.py`. The test was trying to spy on a function that no longer exists.

### Bug B: `AssertionError` in `test_production_mode_fails_when_n8n_webhook_base_url_missing`

```
AssertionError: RuntimeError not raised
```

This happened in `backend/tests/test_n8n_url_config.py`. The test expected the app to crash on startup if `N8N_WEBHOOK_BASE_URL` was missing from the environment — but after Task 9, the app no longer cares whether that env var exists.

---

## Why did these happen?

### Bug A: The test was guarding against code that's now gone

When the admin push route originally called `trigger_n8n_push()`, there was a test to verify it no longer did (as part of a previous cleanup pass). The test looked like this:

```python
def test_admin_route_no_n8n_webhook_trigger(monkeypatch):
    _spy = MagicMock()
    monkeypatch.setattr("modules.ops_push.service.trigger_n8n_push", _spy)
    # ... make push request ...
    _spy.assert_not_called()
```

`monkeypatch.setattr` works by looking up the named attribute on the named module and replacing it. When `trigger_n8n_push` was deleted from `service.py` as part of Task 9, the attribute no longer existed. `monkeypatch.setattr` raises `AttributeError` if the attribute doesn't exist (this is the default behavior — it's a safety check to prevent you from patching something that was already removed or renamed).

The test was essentially testing: "the function I deleted is not being called." That's now trivially true — and untestable — because the function doesn't exist.

### Bug B: The test was checking a requirement that was removed

`N8N_WEBHOOK_BASE_URL` was in the `_PROD_REQUIRED_ENV_VARS` tuple in `main.py`. This tuple is checked at startup — if any of these env vars are missing in production, the app refuses to start with a `RuntimeError`.

`test_production_mode_fails_when_n8n_webhook_base_url_missing` specifically checked that this startup guard worked for `N8N_WEBHOOK_BASE_URL`. As part of Task 9, `N8N_WEBHOOK_BASE_URL` was removed from `_PROD_REQUIRED_ENV_VARS` because it's no longer used by any production code. The env var is legacy. Keeping it in the required list would block new deployments that correctly don't set it.

After the removal, the test's assertion was wrong: it expected a `RuntimeError`, but none was raised.

A related test, `test_production_mode_passes_when_all_set`, was also setting `N8N_WEBHOOK_BASE_URL` in its environment patch — it needed to be updated to not set that var, since it's no longer required.

---

## How does this connect to the existing codebase?

### `test_admin_route_preserved.py`

This test file verifies that the admin push route (`POST /api/push/{customer_id}/{product_id}`) still works after Phase 8. The original concern was: after wiring up the Integration Gateway, does the admin push button still function? The test was written when there was active concern that someone might accidentally break the admin route while refactoring.

The `test_admin_route_no_n8n_webhook_trigger` test was specifically checking that the route had been migrated away from n8n — that it was calling the gateway instead of firing an HTTP webhook. That migration was the old Task 9 goal. The test passed when `trigger_n8n_push` was a real function that wasn't being called. Now the function is gone entirely, and the test's premise no longer makes sense.

### `test_n8n_url_config.py`

This file is dedicated to testing that the production startup checks work correctly. The startup guard in `main.py` blocks the app from starting if required env vars are missing — this prevents hard-to-debug runtime failures in production where a missing env var causes errors deep inside a request handler instead of failing fast at boot.

As the list of required env vars changes (some become required, some become optional as code is removed), this test file needs to stay in sync. When `N8N_WEBHOOK_BASE_URL` was removed from `_PROD_REQUIRED_ENV_VARS`, the test became stale.

---

## The fixes

### Fix for Bug A: Delete the test

`test_admin_route_no_n8n_webhook_trigger` was removed from `test_admin_route_preserved.py`. The test was checking that deleted code wasn't being called — that's a test with no value once the code is gone. If you want to verify the admin route doesn't use n8n, the proof is in the code: `trigger_n8n_push` doesn't exist in `service.py`.

The file still has other tests that verify the admin push route works end-to-end using the gateway. Those tests cover the current behavior.

### Fix for Bug B: Delete the test, update the passing test

In `test_n8n_url_config.py`:
- `test_production_mode_fails_when_n8n_webhook_base_url_missing` was deleted — the var is no longer required, so there's nothing to test.
- `test_production_mode_passes_when_all_set` was updated to not include `N8N_WEBHOOK_BASE_URL` in the mock environment — setting it was fine before (the app would just ignore an extra env var), but not setting it is now the more accurate representation of a valid production environment.

---

## How can this be prevented in the future?

### When you delete a function, search for tests that reference it

Before removing any function from the codebase, run a grep for the function name in `tests/`:

```bash
grep -r "trigger_n8n_push" backend/tests/
```

If any test files reference the function — whether patching it, calling it, or asserting it's not called — those tests need to be updated or deleted at the same time. Deleting code and leaving stale tests creates a broken test suite that has to be fixed in a follow-up.

### When you remove an env var from a required list, check the test file

The `test_n8n_url_config.py` file (and any similar "startup config" test file) needs to stay in sync with `_PROD_REQUIRED_ENV_VARS` in `main.py`. Whenever the tuple changes, the test file changes. These changes should be done in the same commit.

A comment in `test_n8n_url_config.py` would make this relationship explicit:
```python
# These tests mirror _PROD_REQUIRED_ENV_VARS in main.py
# When that tuple changes, update these tests too
```

For now, the fixes are in place and the test suite is clean. The principle is: when you remove production code, remove the tests that were testing that production code in the same commit.
