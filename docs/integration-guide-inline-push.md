# Integration Guide — Push a Product to OnPrintShop via n8n

This guide shows how **any** orchestrator (n8n, a cron job, a Lambda, or plain
`curl`) can push a product to a customer's OnPrintShop (OPS) storefront through
the API-HUB Integration Gateway, using a single scoped credential.

The flow is **load → send**: first upsert the product into the hub catalog, then
ask the gateway to push it. Markup rules, OPS credentials, and option mappings
all stay hub-side — the orchestrator only supplies the product and names the
target storefront.

> **Inline (single-call) mode.** The gateway envelope reserves a `product` field
> for shipping the full product inline so load + send happens in one POST. That
> path is **not yet enabled** on this build — `PushRequest.product` is declared
> but the gateway does not yet upsert from it (Tasks 1–2 of
> `plans/2026-06-01-n8n-inline-push-implementation.md`). Until it lands, use the
> two-step load-then-send recipe documented here. Everything else (auth,
> idempotency, polling, callbacks, error codes) is identical, so migrating to
> inline mode later is a one-line body change.

---

## 1. Mint an orchestrator key

Keys are managed in the admin UI: **Integration Keys** in the sidebar
(`/integrations`).

1. Click **Create Key**.
2. Give it a **Key ID** (a unique slug, e.g. `n8n-prod`) and a **Display Name**.
3. Optionally scope it:
   - **Allowed Customer IDs** — leave blank for all customers, or paste a
     comma-separated list of Customer UUIDs.
   - **Allowed Supplier Slugs** — leave blank for all, or list slugs
     (`sanmar, alphabroder, …`).
   - **Rate limit** — requests/minute (default 60).
4. On create, the **raw key is shown exactly once** in a yellow banner. Copy it
   immediately into your secret store (e.g. the n8n credential vault). It is
   hashed at rest and can never be retrieved again — if you lose it, revoke and
   mint a new one.

Every gateway request authenticates with the header:

```
X-Orchestrator-Key: <raw key>
```

A revoked or out-of-scope key returns `401`/`403` with a gateway error envelope
(see [Error codes](#6-error-codes)).

---

## 2. Discover the product schema

Before sending a product, fetch the canonical `ProductIngest` JSON Schema for a
supplier:

```bash
curl -s "$API/api/integrations/v1/suppliers/sanmar/schema" \
  -H "X-Orchestrator-Key: $KEY" | jq
```

Response includes the full generated JSON Schema plus a quick reference:

```json
{
  "supplier_slug": "sanmar",
  "json_schema": { "...full ProductIngest schema..." },
  "required": ["supplier_sku", "product_name", "variants"],
  "optional": ["brand", "description", "images", "options", "decorations"],
  "variant_required": ["part_id", "sku", "base_price"],
  "variant_optional": ["color", "size", "sort_order", "inventory", "prices"]
}
```

---

## 3. Load — upsert the product into the catalog

POST a list of `ProductIngest` objects. This is an idempotent
`ON CONFLICT DO UPDATE` upsert keyed on `(supplier_id, supplier_sku)`, so
re-sending the same body leaves the DB in an identical state.

```bash
curl -s -X POST "$API/api/integrations/v1/suppliers/sanmar/products" \
  -H "X-Orchestrator-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "supplier_sku": "PC61",
      "product_name": "Port & Company Essential Tee",
      "product_type": "apparel",
      "brand": "Port & Company",
      "apparel_details": { "fabric": "cotton" },
      "variants": [
        { "part_id": "PC61-BLK-S", "sku": "PC61-BLK-S", "color": "Black", "size": "S", "base_price": 3.42, "inventory": 120 }
      ],
      "images": [
        { "url": "https://cdn.example-supplier.com/pc61-black.jpg", "image_type": "primary", "color": "Black", "sort_order": 0 }
      ]
    }
  ]'
```

Response (`202`):

```json
{ "status": "completed", "supplier_slug": "sanmar", "sync_job_id": "…", "records_processed": 1, "failed_count": 0, "errors": [] }
```

The key must be allowed for this supplier or you get `403`/`401`. An unknown
supplier slug returns `404 UNKNOWN_REF`; an inactive supplier returns
`409 SUPPLIER_INACTIVE`.

---

## 4. Send — create a push request

Reference the product you just loaded by `supplier_sku` (or by internal
`product_id` UUID). The gateway resolves the catalog row, runs preflight,
computes markup, and executes the OPS mutation chain.

**Dry run first** — `dry_run: true` runs the full plan through an in-memory fake
OPS client and returns terminal status `dry_run_pushed` synchronously, without
touching OPS:

```bash
curl -s -X POST "$API/api/integrations/v1/push-requests" \
  -H "X-Orchestrator-Key: $KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: sanmar-PC61-push-1" \
  -d '{
    "target": { "system": "ops", "customer_id": "<CUSTOMER_UUID>" },
    "source": { "supplier_slug": "sanmar" },
    "product_ref": { "supplier_sku": "PC61" },
    "dry_run": true,
    "callback": { "url": "https://my-n8n.example.com/webhook/ops-push-callback", "secret": "shared-secret" }
  }'
```

Then **go live** by flipping `dry_run` to `false`. A live push returns `202`
immediately with `status: "accepted"` (or `queued`) and runs in the background —
you discover the outcome by [polling](#5-result-delivery-polling-vs-callback) or
[callback](#5-result-delivery-polling-vs-callback).

Accepted response (`202`):

```json
{
  "push_log_id": "…",
  "status": "dry_run_pushed",
  "customer_id": "…",
  "supplier_slug": "sanmar",
  "supplier_sku": "PC61",
  "ops_product_id": null,
  "dry_run": true,
  "callback_status": "not_requested",
  "created_at": "2026-06-01T12:00:00Z",
  "links": { "self": "/api/integrations/v1/push-requests/…" }
}
```

### `product_ref` — two ways to identify the product
- `{ "supplier_sku": "PC61" }` — resolved within the named supplier. **Recommended.**
- `{ "product_id": "<UUID>" }` — internal catalog UUID. Cross-checked against the
  supplier slug; a UUID belonging to a different supplier returns
  `409 SUPPLIER_MISMATCH`.

You must supply at least one; neither → `422 INVALID_REF`.

---

## 5. Result delivery: polling vs. callback

A live push is asynchronous. Use either (or both) of these to learn the outcome.

### Polling
`GET /api/integrations/v1/push-requests/{push_log_id}` (same `X-Orchestrator-Key`).
Poll on an interval until `status` is **terminal**:

| Terminal status | Meaning |
|---|---|
| `pushed` | All OPS mutations succeeded; `push_mappings` written. |
| `dry_run_pushed` | Dry run completed cleanly through the fake OPS client. |
| `partial_failure` | Some OPS steps succeeded, then one failed. See [partial failure](#7-partial-failure-contract). |
| `failed` | Hard failure before any OPS writes. |
| `rejected` | Preflight blocker or policy rejection. |
| `canceled` | Operator-initiated cancel. |

Non-terminal states you'll see while waiting: `accepted`, `queued`, `processing`.
The poll response carries `step_results[]`, `cleanup_targets`, `ops_product_id`,
`error`, and `finished_at` (set once terminal). A poll for an unknown ID — or one
outside your key's scope — returns `404 UNKNOWN_REF` (404 not 403, so a foreign
key can't confirm another tenant's push exists).

### Callback (webhook)
Include `callback.url` in the push request. On completion the hub POSTs the
terminal result to that URL with header:

```
X-ApiHub-Event: push.completed
```

The body is the same terminal status payload. `callback_status` on the push log
transitions `pending → sent` (or `failed`). The callback URL is SSRF-validated at
submit time — it must be `http`/`https` and must not target loopback,
link-local, or private IPs.

> **HMAC note.** The `callback.secret` field is accepted today but the current
> build does **not** yet sign the callback (no HMAC header is emitted). Treat the
> callback as un-authenticated for now: keep the receiver URL secret, verify the
> `push_log_id` against one you submitted, and don't act on a callback you can't
> correlate. HMAC signing is planned; this note will be removed when it ships.

The n8n recipe in `n8n-workflows/ops-inline-push.json` includes a **Webhook**
trigger node (`POST /webhook/ops-push-callback`) wired to receive this callback,
alongside the poll loop — use whichever fits your workflow.

---

## 6. Error codes

All errors return a gateway envelope:

```json
{ "status": "error", "code": "UNKNOWN_REF", "message": "…", "details": {}, "trace_id": "…" }
```

(FastAPI wraps it under `detail` on the HTTP response.)

| HTTP | `code` | Cause |
|---|---|---|
| 401 | `BAD_SIGNATURE` | Missing or invalid `X-Orchestrator-Key`. |
| 403 | `KEY_REVOKED` | Key has been revoked or deactivated. |
| 403 | `KEY_NOT_ALLOWED` | Key not scoped to this customer or supplier. |
| 404 | `UNKNOWN_REF` | Customer, supplier, product, or push-log not found (or out of scope). |
| 422 | `INVALID_REF` | `product_ref` has neither `product_id` nor `supplier_sku`. |
| 409 | `SUPPLIER_MISMATCH` | `product_id` belongs to a different supplier than `source.supplier_slug`. |
| 409 | `SUPPLIER_INACTIVE` | (Load step) supplier exists but is inactive. |
| 409 | `IDEMPOTENCY_CONFLICT` | Same `Idempotency-Key` reused with a **different** body. |
| 409 | `IN_FLIGHT` | Another push for the same (customer, product) is `processing`. |
| 422 | `PREFLIGHT_BLOCKER` | A preflight gate failed (missing markup rule, OPS creds, mapping, etc.). `details` carries the blockers. |
| 429 | `RATE_LIMITED` | Per-key rate limit exceeded. |

A `PREFLIGHT_BLOCKER` (422) means fix-then-retry: the `details` payload names the
failing check, the field to fix, and a one-line suggestion.

---

## 7. Idempotency

Send an `Idempotency-Key` header on the push request.

- **Same key + same body** → returns the original push log, no duplicate push
  (idempotent replay).
- **Same key + different body** → `409 IDEMPOTENCY_CONFLICT`.
- The key is scoped per integration key, so two different orchestrator keys can
  reuse the same idempotency string without colliding.

The **load** step (catalog upsert) is idempotent by construction (`ON CONFLICT DO
UPDATE`), so its `Idempotency-Key` is logged for tracing but never short-circuits
processing — re-POSTing the same product is always safe.

---

## 8. Partial-failure contract

If the load step succeeded but a later OPS mutation fails mid-chain, the push log
lands in `partial_failure`, **not** `failed`:

- The product **remains in the hub catalog** (the load already committed).
- Any OPS-side writes that did succeed are recorded in `step_results[]`, and the
  IDs that may need manual cleanup are listed in `cleanup_targets`.
- `error` describes the failing step.

Treat `partial_failure` as "needs reconciliation in OPS" — inspect
`step_results` and `cleanup_targets`, fix the underlying cause (often a missing
option mapping or a stale OPS product), and re-push with a **new**
`Idempotency-Key`.

---

## 9. Run the n8n recipe

1. Import `n8n-workflows/ops-inline-push.json` (**Workflows → Import from File**).
2. Set these environment variables on the n8n container (see
   `n8n-workflows/README.md` → *Network / environment*):
   - `API_BASE_URL` — e.g. `http://api:8000` (Compose) or your API hostname.
   - `ORCHESTRATOR_KEY` — the raw key from step 1.
   - `CALLBACK_URL` / `CALLBACK_SECRET` — optional, for the webhook branch.
3. Edit the **Build Product + Target** code node: set `customer_id`,
   `supplier_slug`, and the `product` body (use the schema from step 2).
4. **Execute Workflow.** The flow loads the product, sends a `dry_run` push,
   then polls until terminal. Flip `dry_run` to `false` in that node to go live.
5. Activate the workflow only after the credential/env values are bound —
   workflows ship with `"active": false` by design.
