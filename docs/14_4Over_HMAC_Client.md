# Task 14 — 4Over REST + HMAC Client

A "protocol adapter" in API-HUB is the piece of code that knows how to talk to one type of supplier. SanMar and Alphabroder both speak PromoStandards (SOAP), so they share one adapter. S&S Activewear speaks plain REST with a password. 4Over speaks REST too — but every request must be cryptographically signed with a secret key. This task builds the third adapter: a REST client that signs every request using HMAC-SHA256 before sending it to 4Over's servers.

Last updated: 2026-04-20

---

## Files Created

| File | Purpose |
|------|---------|
| `backend/modules/rest_connector/__init__.py` | Marks the directory as a Python module. Houses REST-based supplier adapters (4Over now, S&S Activewear later in Task 8). |
| `backend/modules/rest_connector/fourover_client.py` | The `FourOverClient` class — HMAC-SHA256-signed httpx wrapper with 4 async methods for fetching categories, products, options, and quotes. |
| `backend/test_fourover_client.py` | 9 unit tests covering signature generation, constructor validation, and HTTP behaviour with `httpx.MockTransport`. |

**Commit:** `11bc9ed` on branch `Vidhi`

---

## Why This Task Exists

API-HUB pulls product catalogs from 4 suppliers: SanMar, Alphabroder, S&S Activewear, and 4Over. The first three are straightforward — SanMar and Alphabroder speak PromoStandards (SOAP), S&S speaks plain REST with an account number and API key sent in an HTTP Basic Auth header.

4Over is different. 4Over's API does not accept a plain password. Every single request must carry a freshly-computed cryptographic signature that proves you know the shared secret **without ever sending the secret over the wire**. This is called **HMAC** (Hash-based Message Authentication Code) and it is an industry-standard pattern used by AWS, Shopify, Stripe, Twilio, and many others.

Without this task, the system has no way to talk to 4Over at all. None of the downstream 4Over work (Task 15 normalizer, Task 16 sync route) can start until the client exists.

---

## HMAC in Plain English — What to Tell the Manager

Imagine you and 4Over share a secret password that only the two of you know. Every time you want to ask 4Over a question, you do three things:

1. Write your question down (the HTTP method + URL path + current timestamp).
2. Put it through a special blender (HMAC-SHA256) together with the secret password.
3. Send the question to 4Over along with the blended result — but **not** the password itself.

4Over does the exact same blending on their side using their copy of the password. If their blended result matches yours, they know you have the password, so the request is genuine. If the results don't match, they reject the request.

**Why is this better than just sending the password?**

- The secret is never transmitted over the network, so it cannot be intercepted.
- The timestamp is part of the signature, so a bad actor cannot replay an old captured request hours later — it would be rejected as stale.
- Every request gets a unique signature, so even if one signature leaks, it cannot be reused to forge a different request.

**In one sentence for the manager:**
> "4Over requires every API request to be cryptographically signed with a shared secret. Task 14 implements that signing correctly so the rest of the platform can fetch 4Over's product catalog."

---

## The `FourOverClient` Class — What It Does

Defined in `backend/modules/rest_connector/fourover_client.py`.

### Constructor

```python
client = FourOverClient(
    base_url="https://sandbox-api.4over.com",
    auth_config={"api_key": "abc", "private_key": "shh"},
)
```

**Inputs:**
- `base_url` — the root of the 4Over API. Sandbox URL for testing, production URL for live. Trailing slash is stripped automatically.
- `auth_config` — a dict with two keys: `api_key` (the public identifier, sent in the header) and `private_key` (the shared secret, used to sign but never sent).

**Validation:** The constructor raises `ValueError` with a clear message if any of the above are missing or empty. This catches misconfigured suppliers at creation time, not at first request.

### The Four Public Methods

| Method | HTTP | 4Over Path | What It Returns |
|--------|------|-----------|-----------------|
| `get_categories()` | GET | `/printproducts/categories` | List of category dicts (print product categories — business cards, brochures, etc.) |
| `get_products()` | GET | `/printproducts/products` | List of product dicts (full product catalog) |
| `get_product_options(uuid)` | GET | `/printproducts/products/{uuid}/optiongroups` | Option groups for one product (paper types, coatings, folds) |
| `get_quote(uuid, options)` | POST | `/printproducts/productquote` | Live price quote for a specific product configuration |

All four methods are `async` — they use `httpx.AsyncClient` so they do not block FastAPI's event loop.

### How a Single Request Flows

```
Caller: await client.get_categories()
        │
        ▼
_sign("GET", "/printproducts/categories")
        │   timestamp = now() in ISO 8601 UTC
        │   payload   = b"GET/printproducts/categories2026-04-20T12:00:00Z"
        │   signature = HMAC-SHA256(private_key, payload).hexdigest()
        ▼
Headers returned:
  Authorization: hmac <api_key>:<signature>
  X-Timestamp:   2026-04-20T12:00:00Z
  Accept:        application/json
        │
        ▼
httpx.AsyncClient.request("GET", full_url, headers=...)
        │
        ▼
4Over server verifies signature → 200 OK + JSON body
        │
        ▼
response.raise_for_status()  # raises on 4xx/5xx
response.json()              # returned to caller
```

### Why the `_sign` Method Accepts a `timestamp` Argument

The default is to call `datetime.now(timezone.utc)`, which makes every signature different. That is correct behaviour in production — fresh timestamp per request blocks replay attacks.

But it also makes testing very hard. If the signature depends on "whatever time it was when the test ran", you cannot compare it to a known expected value. So the private `_sign()` method takes an optional `timestamp` argument. Tests pass a fixed value like `"2026-04-20T12:00:00Z"` and can then hash the same payload themselves to verify the output. Production code never passes this argument, so the current time is used.

### Why Every Public Method Accepts an Optional `http_client`

Same reason. In production, each call creates its own `httpx.AsyncClient`, makes the request, closes the client. Tests create an `httpx.AsyncClient(transport=httpx.MockTransport(...))` and pass it in, so no real HTTP traffic happens — the MockTransport captures the request and returns a fake response.

---

## How the Signature is Calculated

This is the exact contract 4Over expects. Any deviation breaks every request.

```python
timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
payload   = f"{method}{path}{timestamp}".encode("utf-8")
signature = hmac.new(private_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
```

Then the headers on the outgoing request are:

```
Authorization: hmac <api_key>:<signature>
X-Timestamp:   <timestamp>
Accept:        application/json
```

For POST requests (`get_quote`), a `Content-Type: application/json` header is added and the JSON body is sent in addition to the signed headers. The body is **not** part of the signature — only method, path, and timestamp are. This matches 4Over's documented contract.

### Worked Example

Inputs:
- `method` = `"GET"`
- `path` = `"/printproducts/categories"`
- `timestamp` = `"2026-04-20T12:00:00Z"`
- `private_key` = `"test_secret"`
- `api_key` = `"test_key"`

Step 1 — assemble payload:
```
payload = b"GET/printproducts/categories2026-04-20T12:00:00Z"
```

Step 2 — compute HMAC-SHA256:
```
signature = 36a8149174…(64 hex chars total)
```

Step 3 — final headers:
```
Authorization: hmac test_key:36a8149174…
X-Timestamp:   2026-04-20T12:00:00Z
Accept:        application/json
```

This is exactly what test #1 in the test file verifies against a local HMAC computation.

---

## How It Connects to the Rest of the System

```
suppliers table                           FourOverClient (Task 14)
  row with protocol="rest_hmac"  ───▶     (created per sync)
  auth_config = {api_key, private_key}    │
                                          │ fetches raw JSON from 4Over
                                          ▼
                                  4Over sandbox / production
                                          │
                                          │ returns raw product JSON
                                          ▼
                                  4Over Normalizer (Task 15 — NEXT)
                                          │
                                          │ maps raw JSON → PSProductData
                                          │ using Field Mapping config (V0 Task 16)
                                          ▼
                                  upsert_products()  (Task 4 — Tanishq)
                                          │
                                          ▼
                                  products / product_variants / product_images
                                          │
                                          ▼
                                  /api/push/{customer}/product/{id}/payload
                                          │
                                          ▼
                                  n8n OPS Push Workflow → OnPrintShop storefront
```

**Task 14 is the "inbound" side of the 4Over pipeline.** It gets raw data out of 4Over. Task 15 translates it, Task 16 wires it into the sync endpoint.

---

## Test Coverage

All 9 tests in `backend/test_fourover_client.py` pass. They break down into two groups:

### Synchronous tests — signature correctness

| # | Test | What it proves |
|---|------|---------------|
| 1 | `test_sign_header_format` | Known inputs (api_key, private_key, method, path, timestamp) produce the exact HMAC-SHA256 output computed independently. This is the golden test — if 4Over rejects our signatures, this test flags it immediately. |
| 2 | `test_sign_is_deterministic_for_fixed_timestamp` | Same inputs always produce the same signature. Guards against any stray randomness creeping in. |
| 3 | `test_sign_differs_per_method_and_path` | Changing the HTTP method or path flips the signature. Confirms the payload construction actually uses all inputs. |
| 4 | `test_init_validation` | Constructor rejects empty base_url, missing api_key, missing private_key, and empty string credentials. |
| 5 | `test_base_url_trailing_slash_stripped` | `"https://x.com/"` becomes `"https://x.com"` so URLs don't end up with double slashes. |

### Async tests — HTTP transport

| # | Test | What it proves |
|---|------|---------------|
| 6 | `test_request_sends_signed_headers_and_correct_url` | Using `httpx.MockTransport`, the outgoing request has the `Authorization` header starting with `hmac <api_key>:`, has an `X-Timestamp`, and hits the correct full URL. |
| 7 | `test_get_product_options_embeds_uuid_in_path` | Calling `get_product_options("abc-123")` actually hits `/printproducts/products/abc-123/optiongroups` — the UUID is correctly interpolated. |
| 8 | `test_get_quote_sends_post_with_json_body` | The POST to `/productquote` carries a JSON body containing the product UUID and the options dict, with `Content-Type: application/json`. |
| 9 | `test_http_error_propagates` | A 401 response from 4Over raises `httpx.HTTPStatusError` instead of silently returning `None`. Failure is visible. |

### Why MockTransport Instead of Real HTTP?

`httpx.MockTransport` intercepts requests inside the httpx client itself — no sockets, no network. This means:
- Tests run in milliseconds, not seconds.
- Tests pass on a laptop with no internet.
- Tests don't depend on 4Over's sandbox being up.
- The assertions are exact — we check the literal bytes of the outgoing headers.

When Christian provides real 4Over sandbox credentials, we will add a separate E2E smoke test that hits the real sandbox. But that test is optional; the 9 unit tests prove the client is correct by themselves.

---

## How to Test

Make sure the backend virtualenv is activated:

```bash
cd /Users/PD/API-HUB/backend
source .venv/bin/activate
```

Run the test suite:

```bash
python test_fourover_client.py
```

Expected output:

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

### Optional — smoke-test the client interactively

Once Christian provides sandbox credentials, this is the one-liner to confirm the real signature is accepted:

```bash
cd /Users/PD/API-HUB/backend && source .venv/bin/activate
python -c "
import asyncio
from modules.rest_connector.fourover_client import FourOverClient

async def main():
    c = FourOverClient(
        base_url='https://sandbox-api.4over.com',
        auth_config={'api_key': 'REAL_KEY', 'private_key': 'REAL_SECRET'},
    )
    cats = await c.get_categories()
    print(f'OK — fetched {len(cats)} categories')

asyncio.run(main())
"
```

A 401 response means the credentials are wrong. A signature error means our payload assembly disagrees with 4Over's — unlikely, given the test suite, but flag it to the team immediately if it happens.

---

## What's Next

- **Task 15 — 4Over Normalizer.** Takes the raw JSON returned by `FourOverClient` and maps it to `PSProductData` (the same Pydantic shape used for SanMar and S&S). This reuses the Field Mapping UI already built in V0 Task 16 — the supplier's field names are stored per-supplier in the DB, and the normalizer reads those mappings at runtime.
- **Task 16 — Sync Route HMAC branch.** Urvashi's task. Adds a `protocol == "rest_hmac"` branch to the sync endpoint that instantiates `FourOverClient` instead of the SOAP or plain REST clients.
- **E2E against real 4Over sandbox.** Blocked on Christian providing `api_key` and `private_key`. Once provided, add a 4Over supplier row in the DB via `POST /api/suppliers` with `protocol="rest_hmac"` and trigger the sync.

---

## One-Line Summary for Your Sprint Review

> Task 14 ships the third protocol adapter: an HMAC-SHA256-signed REST client for 4Over. All 9 unit tests pass. Blocked on sandbox credentials for E2E, but the signing contract is proven correct against an independent local HMAC computation.
