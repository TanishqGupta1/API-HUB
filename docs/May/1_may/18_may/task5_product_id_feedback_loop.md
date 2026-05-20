# Milestone Plan T5 — OPS Product ID Feedback Loop Fix

## What this task is

**Backend only.** T5 verifies and fixes the chain of IDs that flow between OPS mutation steps during a product push.

---

## How it relates to the existing project

When API-HUB pushes a product to OPS, it runs mutations in a fixed sequence. Each mutation returns an ID that the next mutation needs:

```
setProduct          → returns products_id
setProductSize      → needs products_id from setProduct → returns size_id
setProductPrice     → needs products_id + size_id from previous two steps
setAdditionalOption → needs products_id → returns options_id
setAdditionalOptionAttributes → needs options_id from setAdditionalOption
```

T4 built the `_resolve_step_refs()` mechanism that substitutes `"$step1.products_id"` placeholder strings with real values at runtime. T5 checks that the placeholder field names actually match the field names OPS returns.

---

## What was broken

Two field name mismatches in `backend/modules/ops_push/payload_builder.py`:

### Bug 1 — `setProductPrice` looking for wrong field name

`setProductSize` returns `{ "size_id": N }` from OPS.

But `_build_setProductPrice_step` had:
```python
"size_id": _placeholder(size_step, "product_size_id"),
# resolves to "$step2.product_size_id" — field doesn't exist in step 2's response
```

At runtime, `_resolve_step_refs` would look for `product_size_id` in step 2's response, find nothing, and leave the literal string `"$step2.product_size_id"` in the variables. OPS would receive a string where it expects an integer and reject the mutation.

### Bug 2 — `setAdditionalOptionAttributes` looking for wrong field name

`setAdditionalOption` returns `{ "options_id": N }` from OPS.

But `_build_setAdditionalOptionAttributes_step` had:
```python
"option_id": _placeholder(option_step, "option_id"),
# resolves to "$stepN.option_id" — field doesn't exist
```

Same result — unresolved placeholder string sent to OPS instead of the real integer ID.

---

## What changed

**`backend/modules/ops_push/payload_builder.py`**

Two one-line fixes:

```python
# Before (broken):
"size_id": _placeholder(size_step, "product_size_id"),

# After (correct):
"size_id": _placeholder(size_step, "size_id"),
```

```python
# Before (broken):
"option_id": _placeholder(option_step, "option_id"),

# After (correct):
"option_id": _placeholder(option_step, "options_id"),
```

---

## Why it was necessary

Without these fixes:
- Every product push with variants would fail at `setProductPrice` — OPS gets a string `"$step2.product_size_id"` where it expects a numeric `size_id`.
- Every push using `product_local_option_create` strategy would fail at `setAdditionalOptionAttributes` for the same reason.

The failures would only surface with real OPS credentials. The fake/dry-run client accepted any value and returned stub IDs, masking the bug entirely.

---

## How it can be modified in the future

When new mutation steps are added to the plan:
1. Check what fields the new mutation actually returns from OPS (look at the GraphQL response shape in `ops_client/mutations.py`).
2. Make sure any downstream placeholder uses exactly that field name — e.g. if `setFoo` returns `{ "foo_id": N }`, the placeholder must be `_placeholder(foo_step, "foo_id")`, not `"fooId"` or `"id"`.
3. The `FakeOpsClient` in `gateway.py` also needs to return the same field names in its mock responses so dry-run tests catch mismatches early.

---

## Manual test steps

A dry-run push exercises the FakeOpsClient which now has matching field names:

```bash
curl -X POST http://127.0.0.1:8000/api/integrations/v1/push-requests \
  -H "X-API-Key: <key>" \
  -H "Content-Type: application/json" \
  -d '{
    "source": {"supplier_slug": "sanmar"},
    "target": {"customer_id": "<uuid>"},
    "product_ref": {"supplier_sku": "PC61"},
    "dry_run": true
  }'
```

In the returned `step_results`, verify:
- `setProductSize` step shows a numeric `size_id` in `ops_id`, not a `$step...` string.
- `setProductPrice` step runs after `setProductSize` without error.
- `setAdditionalOptionAttributes` (if options are configured) runs after `setAdditionalOption` without error.
