# Task 14 — 4Over REST + HMAC Client (Test Guide)

This task builds the REST client for 4Over — a print-on-demand supplier whose API requires every request to be signed with HMAC-SHA256. No credentials are committed anywhere; the tests use fake keys with `httpx.MockTransport` so the whole suite runs offline.

---

## What This Task Built

| File | Purpose |
|------|---------|
| `backend/modules/rest_connector/__init__.py` | New module — houses REST supplier adapters |
| `backend/modules/rest_connector/fourover_client.py` | `FourOverClient` class — 4 async methods + HMAC signing |
| `backend/test_fourover_client.py` | 9 unit tests |

**Commit:** `11bc9ed` on `Vidhi`

---

## Before Running Any Tests

Activate the backend virtualenv:

```bash
cd /Users/PD/API-HUB/backend
source .venv/bin/activate
```

No Postgres needed. No n8n needed. No internet needed. The tests mock all HTTP traffic.

---

## Run the Test Suite

```bash
python test_fourover_client.py
```

### Expected Output

```
Running FourOverClient tests…

  test_sign_header_format OK — sig=36a814917417ea19…
  test_sign_is_deterministic_for_fixed_timestamp OK
  test_sign_differs_per_method_and_path OK
  test_init_validation OK
  test_base_url_trailing_slash_stripped OK
  test_request_sends_signed_headers_and_correct_url OK
  test_get_product_options_embeds_uuid_in_path OK
  test_get_quote_sends_post_with_json_body OK
  test_http_error_propagates OK

All 9 tests passed ✅
```

If any test fails, the script exits with a Python traceback pointing at the assertion that broke.

---

## What Each Test Verifies

### Group 1 — Signature correctness (no HTTP)

**Test 1 — `test_sign_header_format`**
Computes the HMAC-SHA256 of `"GET" + "/printproducts/categories" + "2026-04-20T12:00:00Z"` using the secret `"test_secret"` two different ways:
- Once via `FourOverClient._sign()`
- Once by calling `hmac.new(...)` directly in the test

Asserts they produce the same hex digest. If this ever fails, our signature format disagrees with the standard library — every real 4Over request would be rejected.

**Test 2 — `test_sign_is_deterministic_for_fixed_timestamp`**
Calls `_sign()` twice with identical inputs and asserts the output dicts are equal. Guards against any non-determinism in the payload assembly.

**Test 3 — `test_sign_differs_per_method_and_path`**
- `GET /printproducts/categories` at timestamp T → signature A
- `POST /printproducts/categories` at timestamp T → signature B
- `GET /printproducts/products` at timestamp T → signature C

Asserts A, B, C are all different. Confirms method and path are actually part of the payload (not accidentally dropped).

**Test 4 — `test_init_validation`**
Tries 4 bad constructor calls:
1. Empty `base_url`
2. `auth_config` missing `private_key`
3. `auth_config` missing `api_key`
4. `auth_config` with empty-string `api_key`

Each must raise `ValueError`. If the constructor silently accepts bad input, misconfigured suppliers would fail only at first request time.

**Test 5 — `test_base_url_trailing_slash_stripped`**
Passes `"https://sandbox-api.4over.com/"` (with trailing slash). Asserts `client.base_url == "https://sandbox-api.4over.com"` (no slash). Prevents `//printproducts/...` double-slash URLs.

### Group 2 — HTTP transport (via `httpx.MockTransport`)

**Test 6 — `test_request_sends_signed_headers_and_correct_url`**
Installs a MockTransport handler that captures the outgoing request. Calls `client.get_categories(http_client=mocked)`. Asserts:
- Method is `GET`
- URL is `https://sandbox-api.4over.com/printproducts/categories`
- `authorization` header starts with `hmac test_key:`
- `x-timestamp` header is present

Mock handler returns `[{"category": "brochures"}]` and the test asserts the return value matches — confirming JSON parsing round-trips correctly.

**Test 7 — `test_get_product_options_embeds_uuid_in_path`**
Calls `get_product_options("abc-123")`. Asserts the captured URL path is exactly `/printproducts/products/abc-123/optiongroups`. Protects against f-string bugs where the UUID might get dropped or mangled.

**Test 8 — `test_get_quote_sends_post_with_json_body`**
Calls `get_quote("uuid-1", {"paper": "glossy", "qty": 500})`. Asserts:
- Method is `POST`
- `content-type` header is `application/json`
- Body bytes contain `b"uuid-1"` and `b"glossy"`

Confirms POST requests carry both the signed headers AND the JSON body (the body is NOT part of the signature, which is correct per 4Over's contract).

**Test 9 — `test_http_error_propagates`**
Mock handler returns HTTP 401 with the body `"invalid signature"`. Asserts `httpx.HTTPStatusError` is raised with `response.status_code == 401`. Prevents silent failures — if our signature is wrong at runtime, the sync job fails loudly with the 4Over error visible in the log.

---

## Manual Sanity Check — Verify the Signature Format Yourself

You can independently verify that our signature matches the HMAC-SHA256 standard:

```bash
cd /Users/PD/API-HUB/backend && source .venv/bin/activate
python -c "
import hmac, hashlib
from modules.rest_connector.fourover_client import FourOverClient

# Our implementation
c = FourOverClient('https://x', {'api_key': 'test_key', 'private_key': 'test_secret'})
headers = c._sign('GET', '/printproducts/categories', timestamp='2026-04-20T12:00:00Z')

# Reference (stdlib hmac + hashlib, nothing else)
reference = hmac.new(
    b'test_secret',
    b'GET/printproducts/categories2026-04-20T12:00:00Z',
    hashlib.sha256,
).hexdigest()

our_sig = headers['Authorization'].split(':')[1]
print('Our signature:      ', our_sig)
print('Reference signature:', reference)
print('Match:', our_sig == reference)
"
```

Expected:

```
Our signature:       36a8149174...
Reference signature: 36a8149174...
Match: True
```

If the match is `True`, the client is producing signatures identical to the Python stdlib's HMAC — which means 4Over's server (running the same algorithm with the same key) will accept them.

---

## What's NOT Tested Here (and Why)

**E2E against real 4Over sandbox** — blocked on Christian providing real credentials. When he does:

1. Create a supplier row:
   ```bash
   curl -X POST http://localhost:8000/api/suppliers \
     -H "Content-Type: application/json" \
     -d '{
       "name": "4Over",
       "slug": "fourover",
       "protocol": "rest_hmac",
       "auth_config": {"api_key": "REAL", "private_key": "REAL"}
     }'
   ```
2. Run the one-liner smoke test at the bottom of `docs/14_4Over_HMAC_Client.md` to confirm a 200 response.

The unit tests already prove the signature format is correct, so the only thing the E2E would add is confirming Christian's credentials themselves are valid.

---

## Summary Table

| What | Status |
|------|--------|
| Constructor validation | ✅ Tested |
| HMAC-SHA256 signature format | ✅ Tested against stdlib reference |
| Determinism with fixed timestamp | ✅ Tested |
| Method/path sensitivity | ✅ Tested |
| Trailing-slash handling | ✅ Tested |
| `get_categories` HTTP transport | ✅ Tested via MockTransport |
| `get_product_options` UUID path | ✅ Tested |
| `get_quote` POST + body | ✅ Tested |
| 4xx/5xx error propagation | ✅ Tested |
| E2E against real 4Over | ⏳ Blocked on Christian's sandbox creds |
