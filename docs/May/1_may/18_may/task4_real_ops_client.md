# Milestone Plan T4 — Wire Real OpsGraphQLClient into Push Gateway

## What this task is

**Backend only.** T4 replaces two placeholder stub classes in `backend/modules/ops_push/gateway.py` with a real implementation that calls the live OnPrintShop (OPS) GraphQL API.

Until T4, every push request — even non-dry-run ones — silently returned fake IDs (`{"products_id": 99001}`) without making any real network call. No product ever actually landed in OPS.

---

## How it relates to the existing project

The push gateway (`gateway.py`) has two stages:

1. **`prepare_push_intent()`** — validates the request, runs preflight checks, creates a `push_log` row in the database.
2. **`execute_push()`** — walks the mutation plan (built by `payload_builder.py`) and calls OPS methods for each step.

Stage 2 was completely stubbed. It called `_StubOpsClient.set_product()` etc., which returned hardcoded values and never touched the network.

The mutation plan is a list of steps like:
```
step 1:  setProduct → returns products_id
step 2:  setProductSize (uses step 1's products_id) → returns size_id
step 3:  setProductPrice (uses step 1's products_id, step 2's size_id)
...
```

Steps reference earlier results using placeholder strings like `"$step1.products_id"`. These were never resolved — stubs just ignored them.

---

## What changed

### `backend/modules/ops_push/gateway.py`

**Removed:**
- `_StubOpsClient` — fake live client that returned hardcoded IDs
- `_StubFakeOpsClient` — fake dry-run client (replaced by cleaner version)

**Added:**
- `RealOpsClient` — wraps `OpsGraphQLClient` with the same method interface (`set_product(variables)`, `set_product_size(variables)`, etc.). Each method calls `OpsGraphQLClient.execute()` with the correct GraphQL query string and returns the inner response dict. Raises `RuntimeError` if OPS returns an error.
- `FakeOpsClient` — cleaner dry_run client. Records calls for inspection, uses auto-incrementing IDs, now covers all 9 mutations (the old stub was missing `setAdditionalOption`, `setAdditionalOptionAttributes`, `updateProductStock`).
- `_resolve_step_refs(value, step_responses)` — recursively replaces `"$step1.products_id"` style placeholder strings with the actual values returned by previous steps. Without this, `setProductSize` would send the literal string `"$step1.products_id"` to OPS instead of the real integer ID.

**Updated `execute_push()`:**
- Builds `OpsAuth` from customer credentials (`ops_base_url`, `ops_token_url`, `ops_client_id`, `ops_auth_config.client_secret`).
- Instantiates `RealOpsClient(OpsGraphQLClient(auth))` for live pushes, `FakeOpsClient()` for dry runs.
- Tracks `step_responses: dict[int, dict]` — after each mutation succeeds, its response is stored by step number.
- Calls `_resolve_step_refs(raw_variables, step_responses)` before every method call so ID references are resolved.

**Updated `_mutation_to_method()`:**
Added three missing mutations:
- `setAdditionalOption` → `set_additional_option`
- `setAdditionalOptionAttributes` → `set_additional_option_attributes`
- `updateProductStock` → `update_product_stock`

---

## Why it was necessary

Without T4, pushing any product to OPS was a no-op. The UI would show "pushed" status, a `push_log` row would be written, but nothing happened in OPS. The placeholder resolution bug would have also caused real mutations to send literal strings as IDs (e.g. OPS receiving `products_id: "$step1.products_id"` instead of `12345`).

---

## How it can be modified in the future

- **New OPS mutations**: Add an entry to `RealOpsClient._QUERIES` dict and a method with the same name pattern. Also add the camelCase → snake_case mapping to `_mutation_to_method()`.
- **Error handling**: Currently any OPS error raises `RuntimeError` which the execution loop catches and marks the push as `failed`/`partial_failure`. Future work could add retry logic for transient errors (e.g. rate limits, 429s) before failing.
- **Parallel steps**: The current execution is sequential. Some steps (e.g. multiple `setProductSize` calls) are independent and could be parallelized. The `requires_response_from` field on each plan step tells you which previous steps it depends on.
- **FakeOpsClient**: If tests need to simulate OPS failures, `FakeOpsClient` can be subclassed to raise errors on specific mutations.

---

## Manual test steps

### Dry run (safe — no OPS call):
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
Expect: `status: "dry_run_pushed"` in push log. No OPS network call.

### Live push (requires real OPS credentials on the customer):
Same request with `"dry_run": false`. The customer record must have `ops_base_url`, `ops_token_url`, `ops_client_id`, and `ops_auth_config.client_secret` configured. The push log `step_results` will show each mutation's latency and the OPS-returned IDs.

### Verify placeholder resolution:
In `step_results`, confirm that `setProductSize` ran after `setProduct` and its `ops_id` shows a real product ID (not the string `"$step1.products_id"`).
