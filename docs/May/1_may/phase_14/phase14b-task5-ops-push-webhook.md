# Phase 14b — Task 5: ops_push Reads N8N_PUSH_WEBHOOK_URL

**Date:** 2026-05-05
**Branch:** `dev/phase14b-n8n-decouple`
**File changed:** `backend/modules/ops_push/service.py`
**Status:** Complete

---

## What We Did

Added a `trigger_n8n_push()` function to `ops_push/service.py` that reads `N8N_PUSH_WEBHOOK_URL` from the environment and POSTs a push payload to n8n. Also added `os`, `httpx`, and `Any` imports required by the new function.

## What Was There Before

`ops_push/service.py` only had `push_product()` — it prepared the payload and logged the intent in the DB but had no mechanism to actually send it to n8n. The comment said "n8n owns the actual OPS API call" but there was no code to trigger n8n at all.

## What We Added

```python
async def trigger_n8n_push(payload: dict[str, Any]) -> None:
    """POST payload to N8N_PUSH_WEBHOOK_URL.

    Silently skips in dev when the env var is unset.
    Raises in production if unset, or on any non-2xx response.
    """
    webhook_url = os.getenv("N8N_PUSH_WEBHOOK_URL", "").strip()
    if not webhook_url:
        if os.getenv("ENVIRONMENT", "development").lower() == "production":
            raise RuntimeError("N8N_PUSH_WEBHOOK_URL is required in production")
        return
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(webhook_url, json=payload)
        response.raise_for_status()
```

## Why

- **Dev convenience:** if `N8N_PUSH_WEBHOOK_URL` is not set, the function silently returns — no errors, no broken local dev
- **Production safety:** if it IS production and the var is missing, it fails loud at call time so the push log gets flipped to `failed` instead of silently doing nothing
- **`raise_for_status()`:** if n8n returns 5xx, the exception propagates to the caller which can flip `push_log.status = "failed"` with the error message — no push gets silently lost
- This function is ready to be called from `push_product()` in a follow-up task once the full OPS push flow is wired end-to-end
