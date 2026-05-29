# Bug — `test_happy_path_mutation_order` KeyError on `size_id`

**Date found:** 2026-05-14 (previous session)
**Severity:** Medium (test-only failure, not a production bug)
**Status:** ✅ Fixed
**Commit:** `29b7308`
**File fixed:** `backend/tests/test_ops_client_push.py`

---

## What was the bug?

The test `test_happy_path_mutation_order` in `test_ops_client_push.py` was failing with:

```
KeyError: 'size_id'
```

The test was meant to verify that the OPS client calls GraphQL mutations in the correct order when pushing a product. Instead, it crashed mid-way through because a mock helper function returned the wrong response for the wrong mutation.

---

## Why did this happen?

### Background: How the test intercepts mutations

The test uses a helper function called `_capture` to intercept GraphQL mutation calls and return fake responses. Each mutation has its own expected response. For example:

- `setProduct` should return `{"setProduct": {"products_id": 200}}`
- `setProductSize` should return `{"setProductSize": {"size_id": 301}}`
- `setProductPrice` should return `{"setProductPrice": {"price_id": 401}}`

`_capture` works by checking what's in the mutation query string and returning the matching fake response:

```python
def _capture(query: str, variables: dict):
    if "SetProduct" in query:
        return _PRODUCT_OK       # {"setProduct": {"products_id": 200}}
    if "SetProductSize" in query:
        return _SIZE_OK          # {"setProductSize": {"size_id": 301}}
    if "SetProductPrice" in query:
        return _PRICE_OK         # {"setProductPrice": {"price_id": 401}}
```

### The substring problem

The check `"SetProduct" in query` is a substring match. The string `"SetProduct"` appears inside both:
- `"setProduct"` (the product mutation)
- `"setProductSize"` (the size mutation)
- `"setProductPrice"` (the price mutation)

Because the conditions are evaluated top to bottom and `"SetProduct"` is checked first, **the `setProductSize` call matches the `SetProduct` branch** before it gets to check `"SetProductSize"`. It returns `_PRODUCT_OK` — the product response — instead of `_SIZE_OK`.

The wrapper function `set_product_size()` then receives `_PRODUCT_OK`:
```python
{"setProduct": {"products_id": 200}}
```

It tries to access `data["setProductSize"]`, which is `None` (that key doesn't exist in the product response). Then the push code tries:
```python
r.data["size_id"]   # KeyError: 'size_id'
```

And the test crashes.

### Why this is easy to miss

The bug only shows up because Python's `if/elif` chain evaluates top to bottom. It looks correct at first glance — each condition mentions the mutation name. But substring matching against a short name (`"SetProduct"`) breaks when longer names share that substring (`"SetProductSize"`, `"SetProductPrice"`).

This is a classic "longest match first" problem. The more specific strings need to be checked before the generic one.

---

## How does this connect to the existing codebase?

The `_capture` function lives in `backend/tests/test_ops_client_push.py` and is a test-only helper. It doesn't affect production behavior — the real OPS client makes actual HTTP calls to the OnPrintShop GraphQL API and reads real responses. The bug only affects the test infrastructure.

The mutation names come from `backend/modules/ops_client/client.py` (the real OPS GraphQL client) and the push pipeline in `gateway.py`. The test is verifying the order in which the client fires those mutations: first create the product (`setProduct`), then set sizes (`setProductSize`), then set prices (`setProductPrice`). If any mutation returns an unexpected response, the downstream code that reads `size_id` or `price_id` from the response will fail.

---

## The fix

Reorder the conditions in `_capture` so more specific names are checked before shorter ones:

```python
def _capture(query: str, variables: dict):
    # Check longer/more specific names FIRST
    if "SetProductSize" in query:
        return _SIZE_OK
    if "SetProductPrice" in query:
        return _PRICE_OK
    if "SetProduct" in query:
        return _PRODUCT_OK
```

Now `"setProductSize"` matches `"SetProductSize"` first and returns the correct size response. It never reaches the `"SetProduct"` check. Same for `"setProductPrice"`.

The fix is a one-line reorder — move the `SetProductSize` and `SetProductPrice` checks above `SetProduct`.

---

## How can this be prevented in the future?

### Rule: Most specific string first

Whenever you write a chain of `if "X" in string` checks where one string is a substring of another, always put the longer/more specific string first. This is the same rule used in regex alternation (`SetProductSize|SetProduct`, not `SetProduct|SetProductSize`).

### Alternative: Exact match instead of substring

Instead of checking `"SetProduct" in query`, check for an exact match or a match that includes context:
```python
if '"setProduct"' in query and '"setProductSize"' not in query:
    ...
```

Or use a function name that can't be confused:
```python
if query.strip().startswith("mutation SetProduct("):
    ...
```

Exact or anchored matches are harder to get wrong because they don't silently match partial strings.

### Alternative: A dispatch dict

Instead of `if/elif`, use a dict keyed by mutation name:
```python
_RESPONSES = {
    "SetProductSize": _SIZE_OK,
    "SetProductPrice": _PRICE_OK,
    "SetProduct": _PRODUCT_OK,
}

def _capture(query: str, variables: dict):
    for name, response in _RESPONSES.items():
        if name in query:
            return response
```

This doesn't solve the substring problem on its own, but it makes the priority explicit — dict iteration order is insertion order in Python 3.7+, so putting more specific entries first in the dict has the same effect as the reorder fix.

For now, the simple reorder is the right fix — it's minimal and correct.
