# API-HUB Integration Gateway — Design Spec

**Date:** 2026-05-11
**Owner:** Tanishq (PM/Tech Lead)
**Status:** Draft — pending team review
**Supersedes:** [`2026-05-08-sanmar-ops-staging-push-design.md`](2026-05-08-sanmar-ops-staging-push-design.md) (VPCE approach — could not run on current code state)
**Research backing:** [`.omc/research/research-20260511-pushgateway-142234/report.md`](../../../.omc/research/research-20260511-pushgateway-142234/report.md)
**Advisor input:** CCG (Codex + Gemini) artifacts under `.omc/artifacts/ask/`

---

## Goal

Replace the n8n-coupled push pipeline with an **orchestrator-agnostic Integration Gateway**: a small set of secure HTTP endpoints that any external system (n8n, Zapier, Lambda, cron+bash, in-house worker) can call to push products from API-HUB to a customer's OPS storefront.

The backend will have **zero knowledge of n8n** after this lands. n8n becomes one possible consumer; the workflows + custom node stay in the repo but are no longer coupled to backend code.

## Why the prior VPCE spec failed

The 2026-05-08 spec assumed:
- `base_price` populated by the normalizer → it isn't (Bug 1, spike-confirmed)
- Inventory v200 SOAP wired into hydrate_product → it isn't (Bug 2)
- Markup engine applied in push path → it isn't (Bug 3)
- `merge.py` is the right place for the payload builder → it isn't (n8n-shaped, no markup, no validation)
- `service.py::push_product` is the right place to extend → it isn't (still POSTs creds in webhook body)

Net: VPCE preview/execute on top of broken inputs produces a working API surface that ships broken OPS records. Spec D was technically correct but rested on an unproven foundation.

## What this spec keeps from VPCE

- Halt-no-rollback on partial failure
- Per-step OPS target IDs captured for manual cleanup
- High operator visibility (push_log + admin UI)
- No bulk push for beta (single-product gateway request)
- Forward SanMar image URLs as-is (no rehost)
- Global 50% markup rule for VG OPS staging customer
- Manual master-options seed acceptable

## What this spec changes

- **Approach** — Gateway endpoints (not Preview/Execute pair). Idempotency-key + payload-hash semantics replace `preview_id` + `confirm_token`.
- **Auth** — Scoped API key per orchestrator (`X-Orchestrator-Key`) for beta; HMAC signature for V2. JWT cookie auth stays for admin UI only.
- **Scope** — Backend owns OPS push directly. n8n no longer in the push path. `trigger_n8n_push()` + `N8N_PUSH_WEBHOOK_URL` deleted.
- **Schema** — `ProductIngest` is the canonical product contract for both ingest and push (validated across PC61 / K500 / Decals #131 — research stage 4).

---

## Architecture

### API surface (4 endpoints, all under `/api/integrations/v1/`)

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `POST` | `/suppliers/{supplier_slug}/products` | Catalog upsert (any orchestrator) | `X-Orchestrator-Key` |
| `GET`  | `/suppliers/{supplier_slug}/schema`   | Discover required + optional fields | `X-Orchestrator-Key` |
| `POST` | `/push-requests` | Ask API-HUB to push one product to one customer's OPS | `X-Orchestrator-Key` |
| `GET`  | `/push-requests/{push_log_id}` | Poll push status | `X-Orchestrator-Key` |

Plus optional outbound:
- `POST {callback.url}` — fire-and-forget `push.completed` event (orchestrator-provided URL)

### Pipeline (push)

```
[orchestrator]  POST /api/integrations/v1/push-requests
                  ├─ X-Orchestrator-Key + Idempotency-Key headers
                  ├─ body: { target, source, product_ref|product, decorations, dry_run, callback }
                  │
[api-hub]       ├─ Verify key → 401/403 on bad/scoped
                ├─ Check Idempotency-Key ledger
                │   ├─ same key + same payload_hash → return existing push_log_id (200)
                │   └─ same key + different hash → 409 IDEMPOTENCY_CONFLICT
                ├─ Resolve customer + supplier from DB (never from request body)
                ├─ Resolve product:
                │   ├─ product_ref → load from catalog
                │   └─ product → upsert into catalog (same as POST /suppliers/{slug}/products)
                ├─ Preflight validation (decorations ready, master-options mapped, prices set, images present)
                │   └─ blockers → 422 PREFLIGHT_BLOCKER + cleanup_targets=[]
                ├─ Insert push_log row, status=accepted, payload_hash, idempotency_key
                ├─ dry_run=true
                │   ├─ FakeOpsClient (in-memory) executes mutation plan
                │   ├─ status=dry_run_pushed
                │   └─ 202 + {push_log_id, plan}
                ├─ dry_run=false
                │   ├─ status=processing
                │   ├─ Resolve OPS creds from customer.ops_auth_config (EncryptedJSON)
                │   ├─ execute_push() → OPS GraphQL via existing ops_inbound/ops_client.py
                │   │   ├─ success → push_mappings upsert, status=pushed, ops_product_id set
                │   │   ├─ partial → status=partial_failure, cleanup_targets=[…]
                │   │   └─ failure → status=failed, error=…, cleanup_targets=[…]
                │   └─ 202 + {push_log_id}
                └─ async fire callback if callback.url present
                       └─ retry exponential backoff up to N attempts
                          callback_status independent of push status

[orchestrator]  GET /api/integrations/v1/push-requests/{push_log_id}
                  → poll until terminal state
```

### Async path

| Variant count | Mode |
|---|---|
| ≤ 20 | Synchronous request/response within the POST |
| > 20 | 202 immediately, `BackgroundTask(execute_push)` writes to `step_results JSONB` |

`sync_jobs` table is NOT used for push tracking — reserved for inbound supplier sync.

### Auth model

**Beta: scoped API key**

`integration_keys` table (single source of truth):

```sql
CREATE TABLE integration_keys (
    id VARCHAR(64) PRIMARY KEY,            -- human-readable: "n8n-vidhi-staging"
    key_hash VARCHAR(128) NOT NULL,        -- SHA-256 of raw key (raw key shown ONCE on creation)
    name VARCHAR(255) NOT NULL,
    allowed_customer_ids UUID[],           -- null = all
    allowed_supplier_slugs VARCHAR[],      -- null = all
    rate_limit_per_minute INT DEFAULT 60,
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);
```

Headers required on every gateway request:
```
X-Orchestrator-Key: <raw key>
Idempotency-Key: <orchestrator-chosen unique string, ≤128 chars>
Content-Type: application/json
```

**V2 upgrade path** — add `signing_secret VARCHAR(128)` column. When set, key requires HMAC signature in addition to raw header:
```
X-ApiHub-Timestamp: <unix-seconds>
X-ApiHub-Signature: v1=<hex(hmac_sha256(signing_secret, signing_string))>
```
Signing string: `{timestamp}\n{idempotency_key}\n{method}\n{path}\n{sha256(raw_body)}`. Timestamp skew > 300s → 401. Feature-flag the check by per-key column presence.

### Database changes

#### New table: `integration_keys` (above)

#### Expand `product_push_log` (+11 columns, all nullable, additive migration):

```sql
ALTER TABLE product_push_log
    ADD COLUMN request_id UUID UNIQUE,
    ADD COLUMN key_id VARCHAR(64),
    ADD COLUMN payload_hash VARCHAR(64),
    ADD COLUMN supplier_slug VARCHAR(64),
    ADD COLUMN supplier_sku VARCHAR(255),
    ADD COLUMN callback_url TEXT,
    ADD COLUMN callback_status VARCHAR(32) DEFAULT 'not_requested',
    ADD COLUMN callback_attempts INT DEFAULT 0,
    ADD COLUMN step_results JSONB,
    ADD COLUMN cleanup_targets JSONB,
    ADD COLUMN retry_of UUID;

ALTER TABLE product_push_log
    ALTER COLUMN status TYPE VARCHAR(32);  -- widen for new vocab
```

#### Status vocabulary (locked)

`product_push_log.status`:
| Value | Meaning |
|---|---|
| `accepted` | Request received, payload hash recorded, preflight pending |
| `queued` | Preflight passed, awaiting execution (async path only) |
| `processing` | Sync path: actively calling OPS |
| `pushed` | OPS confirmed product created/updated; push_mappings written |
| `failed` | Hard failure before any OPS writes; nothing to clean up |
| `partial_failure` | Some OPS steps succeeded; cleanup_targets populated |
| `rejected` | Preflight blocker (caller error); cleanup_targets empty |
| `canceled` | Operator-initiated cancel before terminal state |
| `dry_run_pushed` | dry_run=true ran cleanly through FakeOpsClient |

`product_push_log.callback_status`:
| Value | Meaning |
|---|---|
| `not_requested` | callback.url was null |
| `pending` | callback not yet attempted |
| `sent` | callback returned 2xx |
| `failed` | callback exhausted retries |

#### Extend `VariantIngest` schema (non-breaking)

```python
class VariantIngest(BaseModel):
    # ... existing fields ...
    sort_order: int = Field(
        default=0,
        description=(
            "Display sort order in OPS configurator. Populated from supplier "
            "size_index (SanMar PromoStandards) or equivalent supplier hint."
        ),
    )
```

Backfilled from SanMar `PSProductData.parts[].size_index` in `ps_normalizer_v2.py`. Default 0 preserves existing behaviour for products without sort hints.

---

## Payload schemas

### Push request envelope

```json
POST /api/integrations/v1/push-requests
X-Orchestrator-Key: oh-vidhi-staging-9f3a
Idempotency-Key: sm-pc61-vg-20260511-001
Content-Type: application/json

{
  "target":     { "system": "ops", "customer_id": "11111111-1111-1111-1111-111111111111" },
  "source":     { "supplier_slug": "sanmar" },
  "product_ref": { "supplier_sku": "PC61" },
  "product":    null,
  "decorations": [
    { "placement": "Front", "method": "DTG", "price_addition": "5.00" }
  ],
  "dry_run": false,
  "callback": {
    "url": "https://n8n.example.com/webhook/api-hub-push-complete",
    "secret": "optional-shared-secret-for-callback-hmac"
  }
}
```

- `product_ref` only → push already-ingested product
- `product` inline (ProductIngest shape) → upsert + push in one shot
- `decorations` lives OUTSIDE `product` — per-push customer concern, not catalog data
- `callback` optional; absence = no outbound webhook

### Catalog ingest envelope (orchestrator → hub)

```json
POST /api/integrations/v1/suppliers/sanmar/products
X-Orchestrator-Key: oh-vidhi-staging-9f3a
Idempotency-Key: sanmar-bulk-20260511-1430
Content-Type: application/json

{
  "mode": "upsert",
  "items": [ /* ProductIngest[] */ ]
}
```

### Concrete product examples (validated against `ProductIngest`)

#### SanMar PC61 (apparel + variants + decoration)

```json
{
  "supplier_sku": "PC61",
  "product_name": "Port & Company Essential Tee",
  "brand": "Port & Company",
  "description": "A customer favorite, this value-priced tee hits the mark on quality and comfort.",
  "product_type": "apparel",
  "category_name": "T-Shirts",
  "image_url": "https://www.sanmar.com/imgindex/PC61_NAVY_front.jpg",
  "apparel_details": { "pricing_method": "tiered_variant" },
  "variants": [
    {
      "part_id": "PC61-NAV-S", "sku": "PC61-NAV-S",
      "color": "Navy", "size": "S", "sort_order": 1,
      "base_price": "3.99", "inventory": 250, "warehouse": "GA",
      "prices": [{ "price_type": "Net", "quantity_min": 1, "price": "3.99" }]
    },
    {
      "part_id": "PC61-NAV-M", "sku": "PC61-NAV-M",
      "color": "Navy", "size": "M", "sort_order": 2,
      "base_price": "3.99", "inventory": 500, "warehouse": "GA",
      "prices": [{ "price_type": "Net", "quantity_min": 1, "price": "3.99" }]
    }
  ],
  "images": [
    { "url": "https://www.sanmar.com/imgindex/PC61_NAVY_front.jpg", "image_type": "front", "color": "Navy", "sort_order": 0 }
  ],
  "raw_payload": { "gtin": "0093456789012", "case_size": 72 }
}
```

#### SanMar K500 (tiered pricing 4 breaks)

```json
{
  "supplier_sku": "K500",
  "product_name": "Port Authority Silk Touch Polo",
  "product_type": "apparel",
  "apparel_details": { "pricing_method": "tiered_variant" },
  "variants": [
    {
      "part_id": "K500-BLK-S", "sku": "K500-BLK-S",
      "color": "Black", "size": "S", "sort_order": 1,
      "base_price": "12.99", "inventory": 100,
      "prices": [
        { "price_type": "Net", "quantity_min": 1,  "quantity_max": 11,   "price": "12.99" },
        { "price_type": "Net", "quantity_min": 12, "quantity_max": 23,   "price": "11.49" },
        { "price_type": "Net", "quantity_min": 24, "quantity_max": 47,   "price": "10.99" },
        { "price_type": "Net", "quantity_min": 48, "quantity_max": null, "price": "9.99"  }
      ]
    }
  ]
}
```

#### OPS Decals #131 (print + options + sizes)

```json
{
  "supplier_sku": "131",
  "ops_product_id": "131",
  "product_name": "Decals - General Performance",
  "product_type": "print",
  "external_catalogue": 1,
  "print_details": {
    "pricing_method": "formula",
    "ops_product_id_int": 131,
    "default_category_id": 22,
    "external_catalogue": 1
  },
  "sizes": [
    { "width": "0", "height": "0", "unit": "in", "label": "Custom Size", "ops_size_id": 1, "size_title": "Custom Size" },
    { "width": "4", "height": "4", "unit": "in", "label": "4\" x 4\"",    "ops_size_id": 2, "size_title": "4\" x 4\"" }
  ],
  "images": [
    { "url": "https://cdn.ops.test/decals/131_large.jpg", "image_type": "front", "sort_order": 0 }
  ],
  "options": [
    {
      "master_option_id": 59, "option_key": "lamMaterial",
      "title": "Lamination Material", "options_type": "combo", "required": false,
      "attributes": [
        { "title": "Gloss", "attribute_key": "gloss", "ops_attribute_id": 101, "master_attribute_id": 201, "setup_cost": "0.00", "multiplier": "1.00" },
        { "title": "Matte", "attribute_key": "matte", "ops_attribute_id": 102, "master_attribute_id": 202, "setup_cost": "0.00", "multiplier": "1.10" }
      ]
    }
  ]
}
```

### Response shapes

#### Push request 202 (accepted)

```json
{
  "push_log_id": "uuid",
  "status": "accepted",
  "customer_id": "uuid",
  "supplier_slug": "sanmar",
  "supplier_sku": "PC61",
  "ops_product_id": null,
  "dry_run": false,
  "callback_status": "pending",
  "created_at": "2026-05-11T10:00:00Z",
  "links": {
    "self": "/api/integrations/v1/push-requests/{push_log_id}"
  }
}
```

#### Push request terminal (GET status)

```json
{
  "push_log_id": "uuid",
  "status": "pushed",
  "customer_id": "uuid",
  "supplier_slug": "sanmar",
  "supplier_sku": "PC61",
  "ops_product_id": "12345",
  "mapping_id": "uuid",
  "error": null,
  "step_results": [
    { "step": "validate", "ok": true },
    { "step": "ops_create_product", "ok": true, "ops_id": "12345" },
    { "step": "ops_attach_options", "ok": true }
  ],
  "cleanup_targets": [],
  "callback_status": "sent",
  "callback_attempts": 1,
  "finished_at": "2026-05-11T10:00:42Z"
}
```

#### Callback (push.completed)

```json
POST {callback.url}
Content-Type: application/json
X-ApiHub-Event: push.completed

{
  "event": "push.completed",
  "push_log_id": "uuid",
  "idempotency_key": "sm-pc61-vg-20260511-001",
  "status": "pushed",
  "customer_id": "uuid",
  "supplier_slug": "sanmar",
  "supplier_sku": "PC61",
  "ops_product_id": "12345",
  "mapping_id": "uuid",
  "error": null,
  "finished_at": "2026-05-11T10:00:42Z"
}
```

If callback returns non-2xx: `callback_status` flips to `failed`, retry with exponential backoff (max 5 attempts). Orchestrator can still poll the status endpoint.

### Error envelope

```json
{
  "status": "error",
  "code": "PREFLIGHT_BLOCKER",
  "message": "Payload missing mandatory OPS mapping for 'Laminate'.",
  "details": {
    "field": "product.options[1].ops_master_attribute_id",
    "suggestion": "Run /api/push-mappings/resolve to find the missing ID."
  },
  "trace_id": "push_log_uuid"
}
```

Error codes:
| Code | HTTP | Meaning |
|---|---|---|
| `BAD_SIGNATURE` | 401 | Invalid `X-Orchestrator-Key` |
| `KEY_NOT_ALLOWED` | 403 | Key scoped away from this customer/supplier |
| `KEY_REVOKED` | 403 | `integration_keys.revoked_at` set |
| `UNKNOWN_REF` | 404 | Customer or product ref not found |
| `IDEMPOTENCY_CONFLICT` | 409 | Same key + different payload |
| `IN_FLIGHT` | 409 | Another push for same (customer, product) is `processing` |
| `PREFLIGHT_BLOCKER` | 422 | Payload validation failed (with details) |
| `RATE_LIMITED` | 429 | Key exceeded `rate_limit_per_minute` |
| `OPS_UPSTREAM_ERROR` | 502 | OPS GraphQL returned an error |

---

## Migration phases (strict order)

| Phase | Action | Admin route safe? |
|---|---|---|
| **M0** | Spike-bug fixes (Bugs 1+2 already in PR #104; Bug 3 absorbed by M1's payload_builder). Alembic additive migration: +11 columns on `product_push_log`, create `integration_keys` table, add `VariantIngest.sort_order` field. | YES (additive only) |
| **M1** | Write `prepare_push_intent()` + `execute_push()` + `build_push_payload()` + `OPSPushPayload` Pydantic model alongside existing code. New files only; no deletions yet. Bug 3 fix lives inside `build_push_payload()`. | YES |
| **M2** | Create `backend/modules/integrations/` module: `routes.py` (4 endpoints), `auth.py` (`X-Orchestrator-Key` dependency), `schemas.py` (request/response envelopes), `service.py` (gateway shim). Register in `main.py`. | YES |
| **M3** | Rewire `POST /api/push/{cid}/{pid}` admin route's internal call chain from `push_product()` → `prepare_push_intent()` + `execute_push()`. Response shape preserved. Verify with admin UI smoke test before continuing. | RISK — must verify before M4 |
| **M4** | Delete `trigger_n8n_push()`, body of old `push_product()`, `N8N_PUSH_WEBHOOK_URL` env var, `merge.py`, `ops_auth` dict in webhook body, `modules/n8n_proxy/` (entire module — 172 LOC), `N8N_*` env entries from `main.py::_PROD_REQUIRED_ENV_VARS`. | YES (only after M3 verified) |
| **M5** | Delete `GET /api/push/image/{id}/processed` once `execute_push()` owns image upload internally. May be deferred. | YES (when ready) |

**Critical rule:** M4 must NEVER precede M3. Verified by integration test gate before M4 PR can merge.

---

## What changes outside the backend

### Frontend (admin UI)

- New page: `/integrations/keys` — `vg_admin` CRUD for `integration_keys` (create, revoke, view scope, view last_used_at)
- Existing push button on `customers/{id}/catalog` keeps working — admin route URL unchanged
- New panel on push log detail: shows orchestrator key id, idempotency key, payload hash, callback status, step_results, cleanup_targets

### n8n (no longer in backend, but workflow JSONs stay in repo)

- Existing `vg-ops-push-001` workflow becomes obsolete — backend now owns the OPS GraphQL call
- New optional `n8n-workflows/api-hub-orchestrator.example.json` workflow showing how n8n calls the new gateway (`HTTP Request → POST /api/integrations/v1/push-requests` with `X-Orchestrator-Key` header from n8n env)
- Existing inbound sync workflows (catalog pulls, master-options sync) unchanged — they continue to use `INGEST_SHARED_SECRET` on `/api/ingest/*` routes (back-compat preserved)

### Documentation

- New `docs/integrations/README.md` — orchestrator-author onboarding (5-minute from zero to first push)
- New `docs/integrations/openapi.yaml` — formal API spec
- New `docs/integrations/error-codes.md` — table of all error codes + retry strategy per code
- `docs/n8n-integration.md` — updated to point at gateway endpoints (n8n becomes one consumer, not the only one)

---

## Risks

| Risk | Mitigation |
|---|---|
| **Secret distribution at scale** | Per-orchestrator `key_id` shown once at creation; key_hash stored. Rotation = generate new key, revoke old (no shared secret). |
| **Replay attacks (beta, no HMAC)** | TLS-only + short idempotency window (24h ledger) + per-key revocation. Acceptable for beta with trusted orchestrators. |
| **Partial OPS write on failure** | Halt-no-rollback (no auto-cleanup). `cleanup_targets JSONB` records OPS IDs created so operator can manually delete. UI surfaces red banner with checklist. |
| **Retry storms** | Server-side exponential backoff on outbound callbacks (max 5 attempts). No auto-trigger of new push from callbacks. Per-key `rate_limit_per_minute`. |
| **Multi-tenant isolation** | `allowed_customer_ids[]` + `allowed_supplier_slugs[]` per key. Server rejects 403 if request target is out of scope. |
| **Callback SSRF** | Per-key `allowed_callback_hosts[]` allowlist (optional column, can be added later); reject `callback.url` not matching. For beta: any URL allowed, document as risk. |
| **Bug 3 (markup bypass) regression** | Markup engine call lives inside `build_push_payload()` (M1). Unit test on the builder asserts `final_price = base_price * (1 + markup_rate)`. CI gate. |
| **Image-route deletion premature** | `GET /api/push/image/{id}/processed` (M5) is deferred and gated by frontend confirmation that the route is no longer load-bearing. |

---

## Out of scope (explicit, deferred to later phases)

- Bulk push (multi-product in one request) — re-enables post-beta after gateway stabilizes
- Image rehost / CDN — Phase 11
- Scheduled push retries — Phase 9
- Multi-tenant RBAC beyond admin / customer_admin — Phase 12 (already done)
- OTel / Sentry observability — Phase 13
- Per-supplier OPS rate limiting — Phase 9
- HMAC v2 auth — flagged in spec, but implementation deferred until beta proves API key sufficiency
- OPS GraphQL mutation gap (33 mutations missing per `OPS-NODE-GAP-ANALYSIS.md`) — separate workstream, blocks `execute_push` completeness but not the gateway shape

---

## Spike-script bug status (research-confirmed)

| Bug | Status | Where it's fixed in this spec |
|---|---|---|
| 1. `base_price=None` on V2 normalizer | Fixed in PR #104 | Prerequisite — must merge before M1 |
| 2. Inventory v200 SOAP not called | Fixed in PR #104 | Prerequisite — must merge before M1 |
| 3. Markup engine bypassed by push | Fixed by M1's `build_push_payload()` | Inside M1 implementation (no separate patch) |
| 4. VG customer OAuth2 flow | Passing per spike | No action |

---

## Acceptance criteria

Spec is implemented when:

- [ ] PR #104 (spike bugs 1+2) merged into main
- [ ] M0 migration applied: `integration_keys` exists, 11 columns on `product_push_log`, `VariantIngest.sort_order` field present
- [ ] M1 functions exist and unit-tested: `prepare_push_intent`, `execute_push`, `build_push_payload`, `OPSPushPayload`
- [ ] M2: 4 gateway endpoints serve curl tests with `X-Orchestrator-Key` auth
- [ ] M3: admin route end-to-end smoke test passes; existing push button works unchanged
- [ ] M4: `grep -rn "n8n" backend/modules/` returns 0 functional refs (docstrings/comments OK)
- [ ] Contract tests pass:
  - send once → 202
  - send same key+body → 200 same `push_log_id`
  - send same key + different body → 409 `IDEMPOTENCY_CONFLICT`
  - send key out of customer scope → 403 `KEY_NOT_ALLOWED`
  - send invalid key → 401 `BAD_SIGNATURE`
  - `dry_run=true` returns plan, no OPS writes
  - `dry_run=false` happy path → status=pushed + push_mappings row + callback fired
  - OPS error → status=failed, error populated, no push_mappings row
- [ ] Single SanMar PC61 product pushed to VG OPS staging end-to-end via curl + orchestrator-key (no n8n in path) with correct markup, decoration, images, inventory

---

## Open questions for team

1. **API key column naming on Supplier model** — `n8n_credential_id` should be renamed `ops_credential_id` after M4 (it represents OPS OAuth creds, not n8n-specific). Acceptable to rename in M4 PR or separate cosmetic PR?
2. **Callback signing** — beta accepts optional `callback.secret` for orchestrator to verify caller is API-HUB. HMAC-SHA256 on the request body, header `X-ApiHub-Callback-Signature`. Confirm shape before M2.
3. **Image route retention** — does `GET /api/push/image/{id}/processed` still serve the admin UI? If yes, defer M5 indefinitely.
4. **Bulk push reintroduction** — when does multi-product gateway request come back? Spec defers but should document target phase.
5. **Rate limiting backing store** — `rate_limit_per_minute` per key needs either Redis or an in-Postgres counter. Beta acceptable to skip enforcement and just log?

---

## References

- Research report: `.omc/research/research-20260511-pushgateway-142234/report.md`
- Codex advisor artifact: `.omc/artifacts/ask/codex-task-brainstorm-a-dynamic-n8n-agnostic-webhook-rest-api-desi-2026-05-11T07-55-36-137Z.md`
- Gemini advisor artifact: `.omc/artifacts/ask/gemini-task-brainstorm-developer-experience-and-integration-contrac-2026-05-11T07-49-24-950Z.md`
- Stage 1 (ops_push audit): `.omc/research/research-20260511-pushgateway-142234/stages/stage-1.md`
- Stage 2 (spike bugs decode): `.omc/research/research-20260511-pushgateway-142234/stages/stage-2.md`
- Stage 3 (n8n reference map, 311 LOC): `.omc/research/research-20260511-pushgateway-142234/stages/stage-3.md`
- Stage 4 (ProductIngest fit): `.omc/research/research-20260511-pushgateway-142234/stages/stage-4.md`
- Superseded VPCE spec: `docs/superpowers/specs/2026-05-08-sanmar-ops-staging-push-design.md`
- PR #104 (spike bugs 1+2 fix): https://github.com/VisualGraphxLLC/API-HUB/pull/104
