# Stage 1 — ops_push Gap Analysis vs Integration Gateway Design

**Date:** 2026-05-11
**Objective:** Audit current `backend/modules/ops_push/` module state vs the Integration Gateway design (CCG advisors: Codex + Gemini). Produce keep / modify / delete / add gap list.

---

## [OBJECTIVE]
Determine exactly which files, functions, columns, and tables from the current `ops_push` module survive, need modification, must be deleted, or must be newly created to implement the Integration Gateway architecture.

## [DATA]
Files audited:
- `backend/modules/ops_push/service.py` (156 lines, 2 functions)
- `backend/modules/ops_push/routes.py` (91 lines, 3 routes)
- `backend/modules/ops_push/merge.py` (62 lines, 1 function)
- `backend/modules/push_log/models.py` (24 lines, 7 columns)
- `backend/modules/push_mappings/models.py` (71 lines, 2 models, 13 columns total)
- `backend/modules/ops_inbound/ops_adapter.py` (213 lines, 1 adapter class)
- CCG Codex design: `.omc/artifacts/ask/codex-task-brainstorm-*.md` lines 65–490
- CCG Gemini design: `.omc/artifacts/ask/gemini-task-brainstorm-*.md`

---

## [FINDING:F1.1] KEEP — 5 items
*Confidence: HIGH unless noted*

### F1.1-a: PushMapping + PushMappingOption (models.py:13–70)
`backend/modules/push_mappings/models.py`
Durable source→OPS ID mapping. Gateway success path writes here (unchanged contract).
Already has `UniqueConstraint("source_product_id","customer_id")`.
[STAT:n] 2 models, 13 columns, 1 unique constraint — no change required.

### F1.1-b: GET /api/push/history/{customer_id}/{product_id} (routes.py:66–90)
Admin UI relies on this for push history. Survives Phase 1 intact.
Will eventually be superseded by `GET /api/integrations/v1/push-requests/{id}` but not deleted during migration.
`select(ProductPushLog).where(... customer_id == customer_id, product_id == product_id)`

### F1.1-c: OPSAdapter + ProductIngest schema (ops_adapter.py:93–213)
`ProductIngest` is the canonical ingest contract shared by all adapters AND the new gateway ingest endpoint.
`OPSAdapter._normalize_to_ingest()` already produces the correct shape.
`return ProductIngest(supplier_sku=str(raw['product_id']), product_type='print', ...)`

### F1.1-d: ProductPushLog base columns (models.py:14–23)
id, product_id, customer_id, ops_product_id, error, pushed_at — all carry forward.
Referenced by push history route and frontend. New columns are additive; these are untouched.

### F1.1-e: GET /api/push/image/{image_id}/processed (routes.py:20–46)
*Confidence: MEDIUM — keep during transition only.*
n8n still calls this during migration period. Remove only after `execute_push()` owns image upload.
`webp_bytes = await process_image(image.url); return Response(content=webp_bytes, media_type="image/webp")`

---

## [FINDING:F1.2] MODIFY — 5 items
*Confidence: HIGH unless noted*

### F1.2-a: ProductPushLog.status column vocabulary
`backend/modules/push_log/models.py:18`
Current: `String(50)` with comment `# pushed/failed/skipped` — only 3 values.
Change: expand vocabulary to `accepted / queued / processing / pushed / failed / partial_failure / rejected / canceled`.
Keep VARCHAR(50) — Pydantic validates at app layer (per CLAUDE.md: no PG ENUMs).
Reason: gateway lifecycle requires 8 states; `partial_failure` needed for OPS product-created-but-options-failed.

### F1.2-b: ProductPushLog — add 11 new columns
`backend/modules/push_log/models.py`
Current: 7 columns; no request_id, no callback tracking, no retry chain.
Add via Alembic (all nullable or have defaults — backward-compatible):
```
request_id       UUID UNIQUE
key_id           VARCHAR(100) FK → integration_keys.id
payload_hash     VARCHAR(64)  (sha256 hex)
supplier_slug    VARCHAR(100) (denormalized)
supplier_sku     VARCHAR(255) (denormalized)
callback_url     TEXT nullable
callback_status  VARCHAR(20) DEFAULT 'not_requested'
callback_attempts INT DEFAULT 0
step_results     JSONB nullable
cleanup_targets  JSONB nullable
retry_of         UUID FK → product_push_log.id nullable
```
Reason: gateway 200/202/409 idempotency, callback delivery tracking, and retry chain all require these.

### F1.2-c: service:push_product() — extract into prepare + execute
`backend/modules/ops_push/service.py:39–155`
Current: monolithic — loads data, merges, logs, calls n8n, error-handles.
Change: split into:
- `prepare_push_intent(db, customer_id, product_id, request_id, key_id, callback_url)` → creates `ProductPushLog(status='accepted')`, returns push_log row. Does NOT call OPS.
- `execute_push(db, push_log_id)` → resolves OPS creds from `customer.ops_auth_config` (EncryptedJSON), calls `build_push_payload()`, calls OPS GraphQL, updates push_log, fires callback.
Admin route calls both inline (synchronous). Gateway calls `prepare_push_intent()` only, then `BackgroundTask(execute_push)`.

### F1.2-d: merge:merge_product_with_decorations() → replaced by build_push_payload()
`backend/modules/ops_push/merge.py:3–62`
Current problems: (a) takes ORM object directly, (b) ignores markup engine entirely, (c) returns untyped dict, (d) fallback path produces `price=0.0` for products without variants.
Change: replace with `build_push_payload(ingest: ProductIngest, decorations: list[dict], markup_rules: list) -> OPSPushPayload` — typed input, markup applied, typed Pydantic output validated before OPS call.

### F1.2-e: routes:POST /api/push/{customer_id}/{product_id} — internal call chain only
`backend/modules/ops_push/routes.py:48–64`
Route URL and JWT cookie auth: UNCHANGED (admin UI depends on both).
Internal call: replace `push_product()` → `prepare_push_intent() + execute_push()` (inline, synchronous).
Ensures admin and gateway routes share identical push logic with no divergence.

---

## [FINDING:F1.3] DELETE — 5 items
*Confidence: HIGH unless noted*

### F1.3-a: trigger_n8n_push() function
`backend/modules/ops_push/service.py:24–37`
The entire purpose — forward payload to N8N_PUSH_WEBHOOK_URL — is eliminated. Backend owns OPS push directly.
Safe to delete after: `execute_push()` implemented + admin route re-wired (M3 complete).

### F1.3-b: N8N_PUSH_WEBHOOK_URL env var
`backend/modules/ops_push/service.py:30` + `.env` + `docker-compose`
No longer needed once `trigger_n8n_push()` deleted. Remove from all env config files.

### F1.3-c: ops_auth dict shipped in webhook body (service.py:128–134)
```python
"ops_auth": {
    "base_url": customer.ops_base_url,
    "client_secret": (customer.ops_auth_config or {}).get("client_secret")
}
```
Security anti-pattern: shipping client_secret in n8n webhook body.
Replacement: `execute_push()` resolves OPS creds from `customer.ops_auth_config` (EncryptedJSON) server-side.

### F1.3-d: old push_product() code path
`backend/modules/ops_push/service.py:39–155`
The route URL `/api/push/{cid}/{pid}` survives, but its current implementation calling `push_product() → trigger_n8n_push()` is deleted after M3 re-wire. The function itself becomes dead code and is removed in M4.

### F1.3-e: GET /api/push/image/{image_id}/processed (deferred delete)
`backend/modules/ops_push/routes.py:20–46`
*Confidence: MEDIUM — deferred to Phase 2.*
Delete only after `execute_push()` handles OPS image upload directly. Keep during transition.

---

## [FINDING:F1.4] ADD — 8 items

### F1.4-a: NEW MODULE backend/modules/integrations/
Files to create:
- `__init__.py`
- `routes.py` — 4 endpoints (catalog ingest, schema, push-requests POST, push-requests GET)
- `auth.py` — HMAC `verify_signature()` FastAPI dependency
- `schemas.py` — `PushRequest`, `PushRequestResponse`, `CatalogIngestEnvelope`
- `models.py` — `IntegrationKey` ORM model
- `service.py` — thin gateway wrapper calling shared push service

Endpoints:
```
POST /api/integrations/v1/suppliers/{slug}/products   catalog upsert, HMAC auth
GET  /api/integrations/v1/suppliers/{slug}/schema     ProductIngest JSON schema
POST /api/integrations/v1/push-requests               push intent, returns 202
GET  /api/integrations/v1/push-requests/{id}          poll push status
```

### F1.4-b: NEW TABLE integration_keys
```sql
id               VARCHAR(100) PRIMARY KEY   -- human-readable: 'ops-staging-a'
secret_hash      VARCHAR(255)               -- bcrypt/SHA-256; secret never stored plain
name             VARCHAR(255)               -- 'n8n-vidhi-staging'
allowed_customers JSONB                     -- list of customer_id UUIDs
allowed_suppliers JSONB                     -- list of supplier slugs
is_active        BOOLEAN DEFAULT true
created_at       TIMESTAMPTZ
last_used_at     TIMESTAMPTZ nullable
```

### F1.4-c: HMAC auth.py
`verify_signature()` FastAPI dependency:
- Reads `X-ApiHub-Key-Id`, `X-ApiHub-Timestamp`, `X-ApiHub-Request-Id`, `X-ApiHub-Signature`
- Rejects timestamp skew > 300s (401)
- Signing string: `{ts}\n{rid}\nMETHOD\n{path}\n{sha256(raw_body)}`
- Idempotency: same `(key_id, request_id, payload_hash)` → 200 replay; different hash → 409

### F1.4-d: prepare_push_intent() + execute_push() in service.py
New functions alongside (not replacing) existing push_product() until M3.
`prepare_push_intent()`: creates `ProductPushLog(status='accepted')`, no OPS call.
`execute_push()`: resolves creds from DB, calls OPS, updates log, fires callback.

### F1.4-e: payload_builder.py — build_push_payload()
`backend/modules/ops_push/payload_builder.py`
Typed `ProductIngest` in → typed `OPSPushPayload` out.
Applies markup engine. Handles both apparel (variants) and print (sizes+options) product types.

### F1.4-f: OPSPushPayload Pydantic model
`backend/modules/ops_push/schemas.py` (new file)
Typed output of `build_push_payload()`. Validated before any OPS GraphQL call.
Fields match OPS `createProduct` / `updateProduct` mutation shape.

### F1.4-g: Alembic migration
One migration: adds 11 columns to `product_push_log` + creates `integration_keys` table.
All additions backward-compatible (nullable or defaulted).

### F1.4-h: Router registration in main.py
```python
from modules.integrations.routes import router as integrations_router
app.include_router(integrations_router)
```

---

## [FINDING:F1.5] Migration Order (admin route safe throughout)

| Phase | Action | Admin route /api/push/{cid}/{pid} |
|-------|--------|-----------------------------------|
| M0 | Alembic: expand product_push_log + create integration_keys | SAFE — additive schema only |
| M1 | Write prepare_push_intent() + execute_push() + build_push_payload() alongside existing code | SAFE — nothing calls new functions yet |
| M2 | Create integrations module, register 4 new routes | SAFE — additive new path prefix |
| M3 | Re-wire admin route to call prepare+execute instead of push_product() | RISK: verify response shape compatibility before deploy |
| M4 | Delete trigger_n8n_push(), old push_product(), N8N_PUSH_WEBHOOK_URL, merge.py, ops_auth body | SAFE — only deletes dead code after M3 verified |
| M5 | Delete image route (deferred) | SAFE — only after execute_push() owns image upload |

Critical constraint: M4 (deletes) must NEVER precede M3 (re-wire). Deleting trigger_n8n_push() before the admin route is re-wired would break the existing push flow.

[STAT:n] 23 current items audited across 6 files; 5 kept, 5 modified, 5 deleted, 8 added
[STAT:effect_size] ~60% of current ops_push code is replaced or deleted; ~40% survives (push_mappings, push history route, ProductIngest schema)

---

## [LIMITATION]
- merge.py replacement (`build_push_payload()`) requires markup engine integration — markup module not audited in this stage. If markup engine API has changed, F1.2-d implementation effort increases.
- OPSClient (used by ops_inbound) reuse in execute_push() assumes it supports createProduct/updateProduct mutations — not confirmed in this stage (OPS-NODE-GAP-ANALYSIS.md mentions 33 missing mutations).
- Integration test coverage for M3 re-wire is required before M4 deletes proceed. No existing test suite was audited.
- HMAC secret distribution mechanism (how operators receive key secrets) is outside scope of this stage.
