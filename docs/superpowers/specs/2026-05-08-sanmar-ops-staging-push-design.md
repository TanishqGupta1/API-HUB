# SanMar → OPS Staging Push (Beta) — Design Spec

**Date:** 2026-05-08
**Owner:** Tanishq (PM/Tech Lead)
**Phase mapping:** Slice of Phase 8 (Push Polish) from `2026-04-30-post-mvp-roadmap.md`. Beta-only deviation: removes n8n from push path.
**Approach:** D — VPCE (Validate → Preview → Confirm → Execute) inside FastAPI.

---

## Goal

Ship a single SanMar product (PC61 — Port & Co Essential T-Shirt) to VG OPS staging end-to-end with full feature parity (decoration overlay, markup, images, inventory) and full operator-facing transparency, without sending broken or partial data to staging.

## Constraints

1. **No n8n in OPS push path for beta.** n8n custom node + workflows kept on disk for post-beta and for inbound SanMar pull. Push runs in FastAPI process.
2. **Cannot pollute VG OPS staging storefront** with zero-priced, image-less, or partially-built products.
3. **High operator visibility.** Every stage inspectable in DB and admin UI before, during, and after execution.
4. **Halt-no-rollback** on partial failure. Per-step OPS target IDs captured for manual cleanup. UI surfaces cleanup checklist loud.
5. **Portable.** No hardcoded n8n workflow IDs anywhere. Beta = no n8n in this path; post-beta = webhook-path-based config.
6. **VG OPS staging customer row already seeded.** Manual master-options seed acceptable. Forward SanMar image URLs as-is (no rehost). Global 50% markup rule. Decorations included.

## Out of scope (explicit)

- Bulk push (multi-product). Today's `n8n-workflows/ops-push.json` supports it via `supplier_id+limit` mode; explicitly dropped for beta. Returns post-n8n.
- Image rehost / CDN (Phase 11).
- Scheduled push retries (Phase 9).
- Multi-tenant RBAC beyond admin/non-admin (Phase 12).
- OTel/Sentry observability (Phase 13).
- Per-supplier OPS rate limiting (Phase 9).

---

## Architecture

### Pipeline

```
[POST /api/push/{cid}/{pid}/preview]            (admin auth)
   ├─ Concurrency lock check on (cid, pid)        → 409 if push in flight
   ├─ Stage 1 Preflight Validate (no OPS writes)  → blockers? abort with list
   └─ Stage 2 Preview Build
        ├─ Compute normalized inputs from DB
        ├─ Build full mutation plan
        ├─ Compute input_hash (SHA-256 over normalized inputs)
        ├─ Issue confirm_token (single-use, server-side stored)
        ├─ Persist push_log row: status=preview_ready,
                                 preview_payload, preflight_results,
                                 input_hash, confirm_token, preview_built_at
        └─ Return {preview_id, input_hash, confirm_token, plan, blockers, warnings}

[Operator inspects preview in UI]

[POST /api/push/{cid}/{pid}/execute]            (admin auth + role gate)
   body: { preview_id, input_hash, dry_run, confirm_token? }
   ├─ Concurrency lock check on (cid, pid)        → 409 if push in flight
   ├─ Recompute current input_hash
   │     ├─ Mismatch → 409 PreviewExpired (force re-preview)
   │     └─ Match    → continue
   ├─ dry_run=true (default)
   │     └─ FakeOpsClient (in-memory, fabricated IDs)
   │         └─ Stage 4 Execute → push_log.status=dry_run_pushed
   │              No push_mappings upsert. Dry-run never writes mapping.
   └─ dry_run=false
         requires confirm_token (single-use, server-issued at preview time)
         + admin role check
         └─ OpsClient (extended ops_inbound/ops_client.py)
             └─ Stage 4 Execute (sequential, append-only execution_steps log)
                  ├─ success → push_mappings upsert + push_log.status=pushed
                  └─ failure → halt, push_log.status=failed
                                cleanup_targets recorded per-step
                                UI red banner with manual cleanup checklist

[Variant count >20] → 202 + background asyncio.Task. Background task writes
                       directly to product_push_log.execution_steps. Response
                       body returns push_log_id (the canonical async identifier).
                       SSE streams from product_push_log row updates.
                       sync_jobs is NOT used for push tracking — it remains for
                       inbound supplier sync orchestration only.
[Variant count ≤20] → synchronous request/response.
```

### Process model

Single FastAPI process. >20-variant pushes detach into background `asyncio.Task` with row in `sync_jobs`. Postgres holds all state. No external queue, no n8n.

### Concurrency lock — durable state machine, not transactional advisory

Transactional advisory locks (`pg_advisory_xact_lock`) release on commit. Push pipeline writes incrementally (preview_ready row, execution_steps appends, status flips), so a transaction-scoped lock would drop between writes and a concurrent `/execute` could slip through.

**Mechanism: Postgres partial unique index enforces single-flight execution.**

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_push_log_in_flight
  ON product_push_log (customer_id, product_id)
  WHERE status IN ('executing');
```

`/execute` flow:
1. Atomic UPDATE: `WHERE id = preview_id AND status = 'preview_ready' SET status = 'executing'`. The partial index prevents two concurrent transitions to `executing` for the same `(customer_id, product_id)`.
2. Conflict on the partial index → 409 Conflict (push already in flight).
3. On completion (success or fail), status moves out of `executing` (`pushed` | `failed` | `dry_run_pushed`) — index frees the slot.
4. Crashed worker leaving stale `executing` rows: scheduled sweep job (out of scope for beta — manual cleanup acceptable).

This guarantees single-flight across the whole multi-step push, regardless of how many incremental writes happen inside.

### Module map

**New (`backend/modules/ops_push/`):**
- `payload_builder.py` — sole owner of OPS-bound payload shape. Replaces `merge.py` and absorbs the synthesis logic from `n8n-workflows/ops-push.json:250-261`.
- `preflight.py` — pure validation rules (DB-only checks). Returns blockers list.
- `pipeline.py` — orchestration only. Validate → build → hash → execute. Delegates each. No DB write logic, no payload shaping, no transport.
- `fake_ops_client.py` — in-memory test double with same interface as real client. Returns fabricated incrementing IDs.

**Extended (not replaced):**
- `backend/modules/ops_inbound/ops_client.py` — add mutation methods + OAuth2 refresh on 401. Single OPS client for both inbound and outbound. Avoids duplication.

**Modified:**
- `backend/modules/promostandards/ps_normalizer_v2.py::merge_pricing` — backfill `VariantIngest.base_price` from min Net-tier price. Currently appends tiers only.
- `backend/modules/promostandards/sanmar_adapter.py` + `adapter.py::hydrate` — add Inventory v200 SOAP call. Currently hits product/pricing/media only.
- `backend/modules/push_log/models.py` — add JSONB cols + status vocab.
- `backend/modules/push_log/schemas.py` — read shapes for the JSONB cols.
- `backend/modules/ops_push/routes.py` — replace single push endpoint with `/preview`, `/execute`, `/{push_log_id}`, `/{push_log_id}/stream` (SSE).
- `backend/modules/markup/routes.py` — `/payload`, `/ops-variants`, `/ops-options` deprecated. Logic absorbed into `payload_builder`. Routes return `410 Gone` with pointer to new endpoints.
- `n8n-nodes-onprintshop/nodes/OnPrintShop/graphql/mutations.ts` — `setProduct` return shape includes `products_id` (not just `id title status`). Custom node still kept for post-beta and ad-hoc use.

**Removed (beta only):**
- `backend/modules/ops_push/service.py::trigger_n8n_push` + `N8N_PUSH_WEBHOOK_URL` env.
- Frontend env `NEXT_PUBLIC_PUSH_WORKFLOW_ID`.
- `n8n-workflows/ops-push.json` → moved to `n8n-workflows/deprecated/ops-push.json` with tombstone `README.md` explaining why and when it returns. Canonical name retired.

---

## Data model

### `push_log` additions

```sql
ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS preflight_results JSONB;
ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS preview_payload JSONB;
ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS execution_steps JSONB DEFAULT '[]'::jsonb;
ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS cleanup_targets JSONB;
ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS input_hash VARCHAR(64);
ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS confirm_token_hash VARCHAR(64);  -- HMAC-SHA256, never plaintext
ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS confirm_token_consumed_at TIMESTAMPTZ;
ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS preview_built_at TIMESTAMPTZ;
ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS dry_run BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_push_log_input_hash ON product_push_log(input_hash);
CREATE UNIQUE INDEX IF NOT EXISTS uq_push_log_in_flight
  ON product_push_log (customer_id, product_id)
  WHERE status IN ('executing');
```

### Status vocab

`pending` → `preview_ready` → `executing` → (`dry_run_pushed` | `pushed` | `failed`).
Existing `pending` and `pushed` retained for backward compat with `customers/routes.py:22-25`. `executing` is the load-bearing concurrency-guard state — partial unique index `uq_push_log_in_flight` enforces single-flight on it.

### `preflight_results` JSONB shape

```json
{
  "checks": [
    {"name": "base_price_set",        "ok": true,  "detail": "all 12 variants have base_price > 0"},
    {"name": "markup_rule_resolves",  "ok": true,  "detail": "global 50% rule (id: ...)"},
    {"name": "push_mappings_present", "ok": false, "detail": "missing target_ops_option_id for 'imprint_method'"},
    {"name": "ops_oauth2_reachable",  "ok": true,  "detail": "token issued, exp 3600s"},
    {"name": "image_urls_reachable",  "ok": true,  "detail": "5/5 HEAD 200"},
    {"name": "prefix_collision",      "ok": true,  "detail": "no existing OPS product with title 'VG-Port & Co...'"},
    {"name": "required_fields",       "ok": true,  "detail": "name, sku, ≥1 variant present"}
  ],
  "blockers": ["push_mappings_present"],
  "warnings": [],
  "computed_at": "2026-05-08T..."
}
```

### `preview_payload` JSONB shape

```json
{
  "plan": [
    {"step": 1, "mutation": "setProductCategory", "variables": {...}, "requires_response_from": null},
    {"step": 2, "mutation": "setProduct",         "variables": {"input": {"category_id": "$step1.products_id", ...}}, "requires_response_from": [1]},
    {"step": 3, "mutation": "setProductSize",     "variables": {"input": {"products_id": "$step2.products_id", "size_name": "M", "color_name": "White", ...}}, "requires_response_from": [2]},
    ...
    {"step": N, "mutation": "setProductPrice",    "variables": {"input": {"products_id": "$step2.products_id", "qty": 1, "qty_to": 999999, "price": 12.49, "vendor_price": 8.32, ...}}, "requires_response_from": [2]}
  ],
  "computed_prices": [
    {"sku": "PC61WHT-M", "base_price": 8.32, "final_price": 12.49, "markup_pct": 50.0, "rounding": "none"}
  ],
  "image_urls": ["https://cdnm.sanmar.com/imglib/mresjpg/2014/f10/PC61_white_model_front_122014.jpg"],
  "estimated_mutations": 17,
  "supplier": "sanmar",
  "supplier_sku": "PC61",
  "ops_target": {"base_url": "...", "client_id_last4": "..."}
}
```

### `execution_steps` JSONB shape

Append-only array. Each entry:

```json
{
  "step": 1,
  "mutation": "setProductCategory",
  "request_body": {...},
  "response_body": {"setProductCategory": {"products_id": 17, "status": "success"}},
  "ops_target_id": 17,
  "ops_target_kind": "category",
  "latency_ms": 432,
  "started_at": "2026-05-08T...",
  "completed_at": "2026-05-08T...",
  "status": "ok"
}
```

### `cleanup_targets` JSONB shape

Set on `failed` status only. Snapshot of every OPS target ID that needs manual cleanup:

```json
{
  "category_ids": [17],
  "product_id": 12345,
  "size_ids": [101, 102, 103],
  "price_ids": [201, 202],
  "instructions": "OPS staging: delete product 12345; orphan category 17 (only delete if not used elsewhere)."
}
```

---

## API surface

**Identifier convention:** `preview_id == push_log_id`. The row created at preview-time is the same row the execute-time updates and the async stream observes. There is no separate job table. `preview_id` is the field name in the preview response body; `push_log_id` is the field name in the execute response and stream URL — same UUID, two route-local names for clarity.

### `POST /api/push/{customer_id}/{product_id}/preview`

Body: none.
Response 200:
```json
{
  "preview_id": "uuid",
  "input_hash": "sha256...",
  "confirm_token": "opaque-string",   // raw value returned ONCE; server stores HMAC-SHA256 hash only
  "plan": [...],
  "preflight": {...},
  "warnings": [...]
}
```
**Confirm token handling:** server generates a 32-byte random secret, computes HMAC-SHA256 (key = SECRET_KEY) of it, stores ONLY the hash in `confirm_token_hash`. Plaintext returned to caller in this response and never persisted. `GET /api/push/{push_log_id}` MUST exclude `confirm_token_hash` from response. Single-use enforced by setting `confirm_token_consumed_at` on first successful match.

Response 409 if push in flight on `(cid, pid)`.
Response 422 if preflight blockers exist (response includes `preflight.blockers`).

### `POST /api/push/{customer_id}/{product_id}/execute`

Body:
```json
{
  "preview_id": "uuid",
  "input_hash": "sha256...",
  "dry_run": true,
  "confirm_token": "opaque-string"   // required when dry_run=false
}
```
Response 200 (sync, ≤20 variants):
```json
{
  "push_log_id": "uuid",
  "status": "pushed" | "dry_run_pushed" | "failed",
  "execution_steps": [...],
  "ops_product_id": 12345,            // only on pushed
  "cleanup_targets": {...}             // only on failed
}
```
Response 202 (async, >20 variants):
```json
{
  "push_log_id": "uuid",                                 // canonical async identifier
  "status": "executing",
  "status_url": "/api/push/{push_log_id}",
  "stream_url": "/api/push/{push_log_id}/stream"
}
```
Push log row owns the async state — no separate `job_id` is issued. SSE streams from row updates.
Response 409 if input_hash drift, push in flight, or token consumed.
Response 403 if dry_run=false without admin role or invalid confirm_token.

### `GET /api/push/{push_log_id}`

Returns push_log row including JSONB cols. **Excludes `confirm_token_hash`** — that value never leaves the database. Excludes redacted `Authorization` header values from `execution_steps` (replaced with `"Bearer ***"` at persist time).

### `GET /api/push/{push_log_id}/stream` (SSE)

Server-sent events. One event per execution_step append. Final event: `{"status": "pushed"|"failed"|"dry_run_pushed"}`.

### Deprecated routes (real migration, not hypothetical)

The following routes exist today and have tests. Migration plan: rewire them to call into `payload_builder` and return the same response shape during the rollout window, then return `410 Gone` once the new UI is the only caller.

- `POST /api/push/{cid}/{pid}` (legacy single push) — covered by `tests/test_ops_push.py`. Replace with calls to new `/preview` + `/execute`. Mark `Deprecated` in OpenAPI for one release, then 410.
- `GET /customers/{cid}/products/{pid}/payload` (`markup/routes.py:29`, tested in `tests/test_markup.py:284`) — has live callers (frontend + n8n workflow). Internally re-implement on top of `payload_builder` so output stays stable. Then deprecate after frontend migration.
- `GET /customers/{cid}/products/{pid}/ops-variants` and `…/ops-options` (`markup/routes.py`) — same migration: re-implement on `payload_builder`, then 410.

No route is deleted in this slice. Deprecation = OpenAPI `deprecated: true` + log warning on hit + add to CHANGELOG. 410 happens in a follow-up cleanup PR after frontend migration is verified.

---

## Preflight validation rules

Block push if any fail:

1. **base_price_set:** every `ProductVariant.base_price` is not null and > 0. Catches the modern-normalizer-leaves-None bug.
2. **markup_rule_resolves:** `markup.engine.resolve_rule(rules, supplier_sku, category)` returns non-None for this customer.
3. **push_mappings_present:** every `ProductOption` (and attribute) has a corresponding `push_mapping_options` row with `target_ops_option_id` (and `target_ops_attribute_id`) populated.
4. **ops_oauth2_reachable:** smoke-test OAuth2 token fetch against `customer.ops_token_url` with stored creds.
5. **image_urls_reachable:** HEAD request per image URL returns 2xx (with 5s timeout).
6. **prefix_collision:** query OPS via `getProducts` for `internal_title = supplier_sku`. Block if existing OPS product matches and no `push_mapping` row claims it (would cause UPDATE-vs-CREATE ambiguity).
7. **required_fields:** product_name, supplier_sku, ≥1 variant, ≥1 image.
8. **decoration_attached:** if `supplier.has_decoration_overlay = true`, require non-empty `customer_product_decorations.decoration_options` for `(customer, product)`.

Each check returns `(name, ok: bool, detail: str)`. Aggregated into `preflight_results`.

---

## Mutation sequence (PC61 reference)

For PC61 (reference: 5 colors × 6 sizes = 30 variants; actual SanMar matrix may be larger):

1. `setProductCategory` — once per push. Creates or finds OPS category for `product.category` ("T-Shirts").
2. `setProduct` — once. `products_title = "VG-" + product_name`. `products_internal_title = "PC61"`. Captures `products_id`.
3. `setProductSize` × N (N = variant count) — one per variant. Carries `color_name`, `size_name`, `products_sku`, `inventory`, `visible`.
4. `setProductPrice` × ≥N — at minimum one per variant. Carries `price` (markup-applied), `vendor_price` (base_price), `qty=1`, `qty_to=999999`. If decoration overlay adds attribute pricing, additional rows per attribute.
5. `setAssignOptions` — once per option mapping. References `target_ops_option_id` from push_mappings.
6. `setProductDesign` — once if decoration overlay present. Carries decoration spec.

**Total mutations PC61 reference:** 1 (category) + 1 (product) + 30 (size) + 30 (price) + M (option assigns) + 1 (design) ≈ 63+. Triggers 202+background path (>20 variants). Single-color/single-size SKUs would stay synchronous.

---

## Failure handling (halt-no-rollback)

On any mid-sequence mutation failure:

1. Halt — no further mutations sent.
2. Append failed step to `execution_steps` with full request, response (or error), latency.
3. Snapshot all OPS target IDs created so far into `cleanup_targets`.
4. Set `push_log.status = failed`.
5. UI red banner with manual cleanup checklist (OPS storefront URL + product/category/size IDs to delete).
6. Operator manually deletes from OPS admin. No auto-rollback per user decision.

If failure is in OAuth2 step (no OPS write yet), no cleanup needed — pure validation failure mode.

---

## Dry-run semantics

`FakeOpsClient` interface:
- Same method signatures as real client.
- Returns fabricated incrementing IDs (`fake_category_id=1`, `fake_product_id=10001`, ...).
- Records all requests in memory for the duration of the call; written to `execution_steps` JSONB just like live mode.
- **Never** triggers `push_mappings` upsert.
- **Never** sets status to `pushed` — uses `dry_run_pushed`.
- `cleanup_targets` always null on dry-run.
- Confirm-token check skipped in dry-run mode.

UI labels:
- "Send Dry-Run" — primary button, default.
- "Send to OPS staging (LIVE)" — secondary red-outlined button. Opens confirm dialog requiring typed confirmation string ("PUSH PC61 TO STAGING") and explicit admin role.

---

## Logging + audit

Two distinct logs with non-overlapping responsibilities:

**`audit_log` (existing, metadata only):** Current middleware (`audit_log/middleware.py`, `audit_log/models.py`) persists `user, method, path, status_code, timestamp` only. It does NOT capture request or response bodies and this slice does NOT extend it. `/preview` and `/execute` flow through it as-is — operator-action provenance, nothing more.

**`product_push_log.execution_steps` (new, body-level forensic capture):** This is where OPS HTTP request bodies, response bodies, latency, and per-step OPS target IDs live. Sole forensic source for OPS payload/response inspection. Captured by `pipeline.py` directly, not by middleware.

- Business-level events emitted via `logger.info` with `extra={"push_log_id", "stage", "step"}` for future Sentry/OTel routing (Phase 13).
- Auth headers redacted: `Authorization` value replaced with `"Bearer ***"` before being written into `execution_steps`. Original token never persisted.
- If body-level audit of admin actions ever becomes a requirement, that's a separate task to extend the audit middleware. Out of scope here.

---

## Acceptance criteria

1. **Preflight all-pass + dry-run** for PC61 produces `dry_run_pushed` status with full mutation plan in `execution_steps`. No push_mappings row written. UI shows green banner with fabricated product_id 10001.
2. **Preflight blocker** (e.g. delete a `push_mapping_options` row to simulate missing `target_ops_option_id`) returns 422 with explicit blockers list. No push_log row in `preview_ready` state created.
3. **Live push to OPS staging** for PC61 with dry_run=false + valid confirm_token + admin role: real OPS product created, `push_mappings` row written with real `target_ops_product_id`, `push_log.status = pushed`, OPS storefront shows PC61 with 30 variants, markup-applied prices, image, brand.
4. **Mid-sequence failure** (manually break OPS creds after preview, then execute) results in `failed` status, `cleanup_targets` populated with category_id + product_id + any size_ids created, UI red banner with cleanup instructions, no `push_mappings` row, no auto-rollback.
5. **Concurrency lock**: two concurrent `/execute` calls on same `(cid, pid)` — second returns 409.
6. **Hash drift**: change product price between preview and execute — execute returns 409 PreviewExpired.
7. **Audit trail**: every preview + execute appears in `audit_log` table with user, timestamp, route.
8. **No n8n in push path**: stop n8n container; preview + execute (live) still work end-to-end.

---

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| OAuth2 token expires mid-execute | Refresh on 401 (in extended OpsClient). Single retry then fail. |
| OPS rate limits hit during 30-variant push | Out of scope for beta. Add 100ms inter-mutation delay if needed. |
| Stale `executing` row from crashed worker blocks future pushes | Manual cleanup acceptable for beta (operator updates `status = failed` via SQL). Scheduled sweep job is Phase 9 follow-up. |
| Operator clicks Execute twice (UI race) | confirm_token single-use; second click → 409. |
| Preview spec drift (someone edits spec doc post-design) | Spec doc + git commit hash referenced in implementation plan. |
| Large variant pushes (e.g. 60+ variants) timeout | 202+background path triggered at >20. SSE for progress. |
| n8n-workflows/ops-push.json revival post-beta | Tombstone README documents what changed and what to update. |

---

## Implementation hand-off

Implementation plan to be drafted next at `docs/superpowers/plans/2026-05-08-sanmar-ops-staging-push.md` using `superpowers:writing-plans`. Plan should split into ~8-10 tasks: schema migration, normalizer fix, inventory wiring, OpsClient extension, FakeOpsClient, payload_builder, preflight, pipeline, routes, frontend preview UI, end-to-end test against staging.
