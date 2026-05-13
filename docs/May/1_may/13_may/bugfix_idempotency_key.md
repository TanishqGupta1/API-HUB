# Bug Fix — Idempotency Key Stored as Supplier SKU

**Owner:** Vidhi
**Status:** Fixed
**Date:** 2026-05-13
**Files:** `backend/modules/ops_push/gateway.py`, `backend/modules/integrations/routes.py`

---

## What was the bug?

The `idempotency_key` column in `product_push_log` was being stored with the value of `supplier_sku` instead of the actual `Idempotency-Key` HTTP request header.

---

## Why is it important?

The idempotency ledger is the core safety mechanism of the Integration Gateway. It answers two questions:

1. **"Has this exact request been sent before?"** — if yes, return the existing push_log_id, do no new work
2. **"Was the same key sent with a different payload?"** — if yes, return 409 IDEMPOTENCY_CONFLICT

Both checks are keyed on `(key_id, idempotency_key)`. If `idempotency_key` is always set to `supplier_sku` instead of the actual header value:

- Two completely different requests for the same SKU (e.g. pushed by two different orchestrators) would incorrectly collide — the second one would be treated as a replay of the first
- An orchestrator sending `Idempotency-Key: my-unique-job-id-001` would have that value silently ignored — their key is never stored
- Retry safety breaks — the orchestrator cannot safely retry a failed request because the stored key doesn't match what they sent

---

## Root Cause

In `prepare_push_intent()`, the `idempotency_key` was hardcoded to `supplier_sku` in two places:

```python
# Before fix — both lookup and insert used supplier_sku

# Lookup:
existing = (await db.execute(
    select(ProductPushLog).where(
        ProductPushLog.key_id == key.id,
        ProductPushLog.idempotency_key == req.product_ref.supplier_sku,  # WRONG
    )
)).scalar_one_or_none()

# Insert:
push_log = ProductPushLog(
    ...
    idempotency_key=supplier_sku,  # WRONG — should be the header value
    ...
)
```

The route also never extracted the `Idempotency-Key` header, so there was no way for `prepare_push_intent()` to receive the correct value.

---

## What was fixed

### `backend/modules/integrations/routes.py`

Added `Header` extraction for `Idempotency-Key` and passed it to `prepare_push_intent()`:

```python
from fastapi import Header

async def create_push_request(
    req: PushRequest,
    background_tasks: BackgroundTasks,
    key: OrchestratorKey,
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),  # NEW
):
    accepted = await prepare_push_intent(req, key, db, idempotency_key=idempotency_key)
```

### `backend/modules/ops_push/gateway.py`

Updated `prepare_push_intent()` signature to accept the header value, and used it in both the lookup and the insert:

```python
async def prepare_push_intent(
    req: PushRequest,
    key: IntegrationKey,
    db: AsyncSession,
    idempotency_key: Optional[str] = None,  # NEW
) -> PushRequestAccepted:

    # Lookup now uses the actual header value
    existing = (await db.execute(
        select(ProductPushLog).where(
            ProductPushLog.key_id == key.id,
            ProductPushLog.idempotency_key == idempotency_key,  # FIXED
        )
    )).scalar_one_or_none() if idempotency_key else None

    # Insert now stores the actual header value
    push_log = ProductPushLog(
        ...
        idempotency_key=idempotency_key,  # FIXED
        ...
    )
```

---

## Result

| Before | After |
|--------|-------|
| Idempotency ledger keyed on `supplier_sku` | Keyed on the actual `Idempotency-Key` header value |
| Two requests for same SKU incorrectly collide | Each request's uniqueness determined by orchestrator-chosen key |
| Orchestrator retry safety broken | Orchestrator can safely retry with same key, gets same push_log_id back |
| Header value silently ignored | Header value stored and used for exact replay detection |
