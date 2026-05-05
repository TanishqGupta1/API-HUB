# Phase 14b — Task 2: n8n URL Config Tests

**Date:** 2026-05-05
**Branch:** `Vidhi`
**File created:** `backend/tests/test_n8n_url_config.py`
**Status:** Complete — 4/4 tests passing

---

## What We Did

Created `backend/tests/test_n8n_url_config.py` with 4 tests that verify the production startup check correctly enforces `N8N_WEBHOOK_BASE_URL` and `API_BASE_URL` env vars.

## Tests Written

| Test | What It Checks |
|------|---------------|
| `test_dev_mode_does_not_require_n8n_urls` | Dev mode boots fine without any n8n URLs set |
| `test_production_mode_fails_when_n8n_webhook_base_url_missing` | Prod raises `RuntimeError` mentioning `N8N_WEBHOOK_BASE_URL` when that var is missing |
| `test_production_mode_fails_when_api_base_url_missing` | Prod raises `RuntimeError` mentioning `API_BASE_URL` when that var is missing |
| `test_production_mode_passes_when_all_set` | Prod boots cleanly when all required vars are set |

## Why Sync Not Async

`_require_prod_env()` is a plain synchronous function — no database, no async I/O. Writing async tests for it would have triggered the global `conftest.py` DB cleanup fixture unnecessarily. Sync tests are faster and simpler here.

## Note

PostgreSQL must be running for these tests because the global `conftest.py` has an autouse fixture that cleans test data before each test — even for tests that don't use the DB. Run `docker compose up -d postgres` before running the test suite.
