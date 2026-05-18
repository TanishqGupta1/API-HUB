# M1 — Tasks 6–9: OPS GraphQL Mutation Wrappers

**Owner:** Vidhi
**Status:** Done (2026-05-14)
**Plan:** `docs/superpowers/plans/2026-05-14-centralized-fastapi-ops-m1.md`
**Phase:** M1.1 — `ops_client` Module (Tasks 6, 7, 8, 9 of 25)
**Depends on:** T5 (OpsGraphQLClient transport) — see `docs/May/1_may/14_may/m1_task5_ops_client_transport.md`

---

## What are these tasks?

Four wrapper functions — one for each OPS GraphQL mutation needed to push an apparel product. They go in a single file: `backend/modules/ops_client/mutations.py`.

Think of it this way: T5 built the **phone line** to OPS. These four tasks are the **four conversations** we have over that phone line — in order, each one depending on the answer from the previous one.

---

## The ID Threading Chain

This is the core concept. When pushing a product to OPS, you must call 4 mutations in sequence, and each step returns an ID that the next step needs:

```
Step 1 (T6):  setProductCategory("T-Shirts")
              → OPS returns category_id = 42
                    ↓ pass category_id to step 2

Step 2 (T7):  setProduct(category_id=42, "Port & Company PC61")
              → OPS returns products_id = 12345
                    ↓ pass products_id to step 3

Step 3 (T8):  setProductSize(products_id=12345, "Navy", "S", "PC61-NAV-S")
              → OPS returns size_id = 555
                    ↓ pass products_id + size_id to step 4

Step 4 (T9):  setProductPrice(products_id=12345, size_id=555, price="9.99")
              → OPS returns product_price_id = 7777
              → Done! Variant is live on the storefront.
```

**Note:** Steps 3 and 4 are called once **per variant**. A product with 3 colors × 4 sizes = 12 calls to Step 3 + 12 calls to Step 4.

---

## How do these connect to the existing codebase?

### Where the data comes from

| Mutation input | Where it comes from in our DB |
|---------------|------------------------------|
| `category_name` ("T-Shirts") | `products.category` column |
| `products_title` ("Port & Company PC61") | `products.product_name` column |
| `size_name` ("S"), `color_name` ("Navy") | `product_variants.size`, `product_variants.color` columns |
| `products_sku` ("PC61-NAV-S") | `product_variants.sku` column |
| `price` ("9.99") | Calculated by `markup.engine.calculate_price()` — base price + markup rules |
| `vendor_price` ("5.50") | `product_variants.base_price` column |

### What they replace

Today, these exact same OPS mutations are called by n8n workflows:
- `n8n-workflows/ops-push.json` — the workflow JSON contains nodes for each mutation
- The n8n custom node `n8n-nodes-onprintshop` sends the GraphQL

After M1, the Python wrappers in `mutations.py` replace those n8n nodes entirely.

### What calls these functions

Nobody calls them directly. They are called by the **orchestrator** (`push.py`, T11) which chains them together with error handling. The orchestrator is the next task.

---

## Why are they necessary?

### 1. They make the push testable

Each wrapper can be tested individually with mock HTTP responses. We wrote 7 tests covering success, error, and parameter passing. Try doing that with an n8n workflow JSON file — you can't.

### 2. They separate "what to call" from "how to call"

The wrapper knows the GraphQL query string and variable shape. The client (T5) knows how to authenticate and send HTTP. The orchestrator (T11) knows the sequence and error handling. Clean separation.

### 3. They're the building blocks for T11

The orchestrator (T11) reads like plain English because of these wrappers:
```python
# T11 will do this:
cat_result = await set_product_category(client, "T-Shirts")
prod_result = await set_product(client, cat_result.data["..."]["category_id"], "PC61")
# ... and so on
```

Without wrappers, T11 would be 200+ lines of raw GraphQL strings mixed with business logic.

---

## What was done

### File created: `backend/modules/ops_client/mutations.py`

Four functions, all following the same pattern:

| Function | Task | GraphQL Mutation | Key Input | Returns |
|----------|------|-----------------|-----------|---------|
| `set_product_category()` | T6 | `SetProductCategory` | `category_name`, `parent_id` | `category_id` |
| `set_product()` | T7 | `SetProduct` | `category_id`, `products_title` | `products_id` |
| `set_product_size()` | T8 | `SetProductSize` | `products_id`, `size_name`, `color_name`, `products_sku` | `size_id` |
| `set_product_price()` | T9 | `SetProductPrice` | `products_id`, `size_id`, `price`, `vendor_price` | `product_price_id` |

Each function:
1. Defines a GraphQL mutation string (the exact query OPS expects)
2. Accepts the required parameters
3. Calls `client.execute(query, variables=...)` from T5
4. Returns `OpsResult` — never raises exceptions

#### Why price is a string, not a number

`price="9.99"` is a string to prevent floating-point precision loss. Python `float(9.99)` is actually `9.98999999999999...`. Passing it as a string preserves the exact decimal value. OPS expects a string for price fields.

### File modified: `backend/tests/test_ops_mutations.py`

7 tests total, all using `respx` to mock HTTP responses:

| Test | What it verifies |
|------|-----------------|
| `test_set_product_category_sends_correct_mutation` | T6 returns `category_id` on success |
| `test_set_product_category_with_parent` | T6 passes `parent_id` correctly |
| `test_set_product_category_handles_ops_error` | T6 returns `ok=False` with error details |
| `test_set_product_returns_products_id` | T7 returns `products_id` on success |
| `test_set_product_handles_error` | T7 returns `ok=False` on OPS error |
| `test_set_product_size_returns_size_id` | T8 returns `size_id` on success |
| `test_set_product_price_returns_price_id` | T9 returns `product_price_id` on success |

#### How the tests work (no real OPS needed)

```python
# 1. We pre-fill the OAuth token so the client doesn't try to log in:
client._token = "fake-token-for-tests"

# 2. We use respx to intercept the HTTP call and return a fake response:
respx.post("https://test-store.ops.com/graphql").mock(
    return_value=httpx.Response(200, json={"data": {"setProduct": {"products_id": 12345}}})
)

# 3. We call the wrapper and check the result:
result = await set_product(client, category_id=42, ...)
assert result.ok is True
assert result.data["setProduct"]["products_id"] == 12345
```

### Dependency installed: `respx`

`respx` is a testing library that intercepts `httpx` HTTP calls and returns fake responses. It's only used in tests — doesn't affect production code. Installed via `pip install respx` into the backend venv.

---

## Verification

```bash
cd backend && source .venv/bin/activate && pytest tests/test_ops_mutations.py -v

# Output:
# test_set_product_category_sends_correct_mutation PASSED
# test_set_product_category_with_parent PASSED
# test_set_product_category_handles_ops_error PASSED
# test_set_product_returns_products_id PASSED
# test_set_product_handles_error PASSED
# test_set_product_size_returns_size_id PASSED
# test_set_product_price_returns_price_id PASSED
# ========================= 7 passed in 0.96s =========================
```

---

## How these can change in the future

- **M1.6 — Decoration mutations:** Three more wrappers will be added to `mutations.py`: `set_additional_option()`, `set_additional_option_attributes()`, `set_products_attribute_price()`. Same pattern, different GraphQL strings.
- **Update vs Create:** Currently all mutations create new records. When OPS supports upsert (create-or-update), the wrappers can add an optional `products_id` parameter to switch between create and update mode.
- **Batch variants:** If OPS adds batch mutation support, `set_product_size` could accept a list of variants instead of one at a time — reducing 12 API calls to 1.

---

## Current module structure

```
backend/modules/ops_client/
├── __init__.py      ← Package marker (T5)
├── client.py        ← OpsAuth + OpsResult + OpsGraphQLClient (T5)
└── mutations.py     ← set_product_category, set_product,
                        set_product_size, set_product_price (T6–T9)

backend/tests/
├── test_ops_client_transport.py  ← 6 tests for T5
└── test_ops_mutations.py         ← 7 tests for T6–T9
```

---

## What's next

| Task | Owner | Status | Blocked by |
|------|-------|--------|-----------|
| T5 — OpsGraphQLClient transport | Vidhi | ✅ Done | — |
| T6 — `set_product_category` | Vidhi | ✅ Done | T5 |
| T7 — `set_product` | Vidhi | ✅ Done | T5 |
| T8 — `set_product_size` | Vidhi | ✅ Done | T5 |
| T9 — `set_product_price` | Vidhi | ✅ Done | T5 |
| T11 — `push_apparel_product` orchestrator | Vidhi | ⬜ Next | T6–T9 ✅ + T10 (Shinchna, not merged yet) |

T11 is the orchestrator — it chains all 4 wrappers with ID threading and error handling. It needs `FakeOpsClient` (T10, assigned to Shinchna) to run its tests. Once Shinchna's branch merges, T11 can start.

---

## References

- **T5 doc:** `docs/May/1_may/14_may/m1_task5_ops_client_transport.md`
- **Phase 8 Task 1 (DB schema):** `docs/May/1_may/13_may/phase8_task1_done.md`
- **M1 Plan:** `docs/superpowers/plans/2026-05-14-centralized-fastapi-ops-m1.md` (Tasks 6–9)
- **Existing n8n push (being replaced):** `backend/modules/ops_push/service.py`
- **Product/variant data source:** `backend/modules/catalog/models.py`
- **Markup engine (calculates price):** `backend/modules/markup/engine.py`
