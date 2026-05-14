# Bug Fix — Sync Health Showing 0%

**Owner:** Vidhi
**Status:** Fixed
**Date:** 2026-05-13
**File:** `backend/main.py`

---

## What was the bug?

The dashboard **Sync Health** card was always showing **0%** even though SanMar syncs were completing successfully and products were being imported correctly.

---

## Why is it important?

Sync Health is the primary indicator on the dashboard that tells operators whether the supplier sync pipeline is working. A 0% reading when everything is actually fine causes:

- False alarms — operators think something is broken when it isn't
- Loss of trust in the dashboard — if one metric is wrong, operators stop trusting all of them
- Wasted time investigating a problem that doesn't exist

Getting this right matters because as more suppliers are onboarded, this metric becomes the first thing anyone checks every morning.

---

## Root Cause

The health formula in `GET /api/stats` only counted jobs with `status = "success"` as healthy:

```python
# Before fix
success_jobs = len([j for j in jobs_24h if j.status == "success"])
health = (success_jobs / total_jobs * 100) if total_jobs > 0 else 100.0
```

But the actual sync jobs written to the DB use `status = "completed"` — not `"success"`. So the formula was finding **0 successful jobs out of 5 total** and correctly computing 0%.

The mismatch happened because the status vocab in `sync_jobs` uses `"completed"` for a clean run, but the stats endpoint was checking for `"success"` — a value that is never actually written.

---

## What was fixed

Added `"completed"` and `"partial_success"` to the healthy status list — matching the same vocab already used by the sync health endpoint (`/api/sync-jobs/health`):

```python
# After fix
success_jobs = len([j for j in jobs_24h if j.status in ("success", "completed", "partial_success")])
```

---

## Result

Sync Health now shows **100%** on the dashboard — correctly reflecting that all recent SanMar syncs completed without errors.
