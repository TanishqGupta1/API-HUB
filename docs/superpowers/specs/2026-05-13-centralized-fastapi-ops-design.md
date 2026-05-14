# Centralized FastAPI OPS Push + Ingest — Design Spec

**Date:** 2026-05-13
**Owner:** Tanishq (PM/Tech Lead)
**Status:** Draft Rev 0 — pending team review
**Builds on:** [`2026-05-11-integration-gateway-design.md`](2026-05-11-integration-gateway-design.md) (Rev 3, merged PR #105)
**Implementation phase:** M1 of the Integration Gateway plan
**Scope:** SanMar → API-HUB → OPS (focused first milestone; 4Over/S&S/994-scale deferred)

---

## Goal

Move all OPS GraphQL mutation knowledge **out of n8n** and **into FastAPI**. Make n8n (or curl, or any orchestrator) a dumb HTTP caller. FastAPI owns:

- OPS field naming translation (`name → products_title`, etc.)
- ID threading (`products_id` from `setProduct` → `setProductSize` → `setProductPrice`)
- GraphQL mutations called directly (no n8n in push path)
- Real OPS errors surfaced via clean HTTP responses
- Idempotency (key + payload-hash ledger)

## Why now

Three confirmed gaps from prior CCG audit (`.omc/artifacts/ask/codex-audit-the-ops-payload-contract-*.md`):

1. **Trigger contract mismatch (breaks immediately):** `ops-push.json:23` reads webhook query params; backend `service.py:141` posts JSON body. First push fails.
2. **Field name mismatches:** backend sends `name`/`categories[]`/`price`/`vendor_price`; OPS expects `products_title`/`category_name`+`category_id`/`attributes_price`. Workflow patches some, not all.
3. **ID threading broken:** `setProductPrice` runs once with `size_id: 0` (`ops-push.json:213`). Options stub never calls real `setAdditionalOption` (`ops-push.json:289`).

Senior architect review (`.omc/artifacts/ask/codex-act-as-a-senior-software-architect-*.md`) verdict: API-HUB is **NOT ready** for first real onboarding without these fixes.

## Non-goals (deferred)

- 4Over, S&S Activewear, generic 994-supplier support
- AWS ECS deployment / SQS workers / CloudFront / production logging
- Enterprise SECRET_KEY rotation automation
- `variant_axes` table refactor
- Frontend M2 UI for integration_keys admin
- Print push payload (`options[]/sizes/print_details`) — SanMar PC61 is apparel

These come after the first real SanMar→OPS push works end-to-end.

---

## Architecture

### Endpoint surface (9 new under `/api/integrations/v1/`)

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | `/api/integrations/v1/suppliers/{supplier_slug}/products` | Catalog upsert (batched `ProductIngest[]`) | `X-Orchestrator-Key` + `Idempotency-Key` |
| GET | `/api/integrations/v1/suppliers/{supplier_slug}/schema` | Return JSON Schema for `ProductIngest` | `X-Orchestrator-Key` |
| POST | `/api/integrations/v1/push-mappings` | Upsert OPS↔hub ID map | `X-Orchestrator-Key` + `Idempotency-Key` |
| POST | `/api/integrations/v1/master-options/ingest` | Master options snapshot ingest | `X-Orchestrator-Key` + `Idempotency-Key` |
| **POST** | **`/api/integrations/v1/push-requests`** | **Push 1 product to OPS (dry_run support)** | `X-Orchestrator-Key` + `Idempotency-Key` |
| GET | `/api/integrations/v1/push-requests/{push_log_id}` | Poll push status + step results | `X-Orchestrator-Key` |
| GET | `/api/integrations/v1/customers/{customer_id}/ops/products` | Proxy list OPS products | `X-Orchestrator-Key` |
| GET | `/api/integrations/v1/customers/{customer_id}/ops/products/{ops_product_id}` | Proxy get OPS product | `X-Orchestrator-Key` |
| POST | `/api/integrations/v1/customers/{customer_id}/ops/connection-test` | Real auth probe (fetch token + GraphQL ping) | `X-Orchestrator-Key` |
| POST (changed) | `/api/push/{customer_id}/{product_id}` | Admin UI dispatch → gateway push | JWT cookie |

Auth model and idempotency semantics are defined in [`2026-05-11-integration-gateway-design.md`](2026-05-11-integration-gateway-design.md).

### Push request envelope

```json
POST /api/integrations/v1/push-requests
X-Orchestrator-Key: oh-vidhi-staging-9f3a
Idempotency-Key: sm-pc61-vg-20260513-001
Content-Type: application/json

{
  "target":      { "customer_id": "uuid" },
  "source":      { "supplier_slug": "sanmar" },
  "product_ref": { "product_id": "uuid" },
  "decorations": [],
  "dry_run":     false,
  "callback":    { "url": "https://n8n.example/webhook/done", "secret": "optional" }
}
```

### Push pipeline (server-side)

```
[orchestrator] POST /api/integrations/v1/push-requests
                 ├─ Verify X-Orchestrator-Key → 401/403
                 ├─ Check Idempotency-Key ledger
                 │   ├─ same key + same payload_hash → return existing push_log_id (200)
                 │   └─ same key + different hash → 409 IDEMPOTENCY_CONFLICT
                 ├─ Resolve customer + supplier from DB (never from request)
                 ├─ Resolve product (from catalog by product_id)
                 ├─ Preflight (decorations ready, master-options mapped, prices set, images present)
                 │   └─ blocker → 422 PREFLIGHT_BLOCKER + cleanup_targets=[]
                 ├─ INSERT push_log status='accepted', payload_hash, idempotency_key
                 ├─ dry_run=true
                 │   ├─ FakeOpsClient executes mutation plan in-memory
                 │   ├─ status='dry_run_pushed'
                 │   └─ 202 + {push_log_id, plan}
                 ├─ dry_run=false
                 │   ├─ status='processing'
                 │   ├─ Resolve OPS creds from customer.ops_auth_config (EncryptedJSON)
                 │   ├─ execute_push() via ops_client (sequence in section 4 below)
                 │   │   ├─ success → push_mappings upsert, status='pushed', ops_product_id set
                 │   │   ├─ partial → status='partial_failure', cleanup_targets=[...]
                 │   │   └─ failure → status='failed', error=..., cleanup_targets=[...]
                 │   └─ 202 + {push_log_id}
                 └─ async fire callback if callback.url present
                        └─ retry exponential backoff
```

---

## Field name mapping (canonical)

Authoritative source for OPS field names: `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts` mutation defaults (lines 971, 981, 991, 1000, 1494, 1503, 1512).

| Backend field | OPS GraphQL field | Source mutation | Notes |
|---------------|-------------------|-----------------|-------|
| `product.category_name` | `category_name` | setProductCategory | |
| (default 0) | `parent_id` | setProductCategory | Hardcoded 0 for now; tree resolution later |
| (default 1) | `visible` | setProductCategory + setProduct + setProductSize + setProductPrice | |
| `product.name` | `products_title` | setProduct | |
| `product.supplier_sku` | `products_internal_title` | setProduct | |
| (threaded) `category_id` | `category_id` | setProduct | From `setProductCategory` response |
| `variant.size` | `size_name` | setProductSize | |
| `variant.color` | `color_name` | setProductSize | |
| `variant.sku` | `products_sku` | setProductSize | |
| (threaded) `products_id` | `products_id` | setProductSize + setProductPrice + setAdditionalOption | From `setProduct` response |
| `variant.final_price` | `price` | setProductPrice | from `markup.engine::calculate_price` |
| `variant.base_price` | `vendor_price` | setProductPrice | from markup engine |
| (default 1) | `qty` | setProductPrice | |
| (null or break) | `qty_to` | setProductPrice | |
| (threaded) `size_id` | `size_id` | setProductPrice | From `setProductSize` response |
| Option `title` | `title` | setAdditionalOption | |
| Option `options_type` | `options_type` | setAdditionalOption | |
| (default 'active') | `status` | setAdditionalOption + setAdditionalOptionAttributes | |
| (default 0) | `delete` | setAdditionalOption + setAdditionalOptionAttributes + setProductsAttributePrice | |
| Attribute `title` | `label` | setAdditionalOptionAttributes | **Backend `title` ≠ OPS `title` here** |
| (threaded) `prod_add_opt_id` | `prod_add_opt_id` | setAdditionalOptionAttributes + setProductsAttributePrice | From `setAdditionalOption` response |
| Attribute `price` | `attributes_price` | setProductsAttributePrice | |
| Attribute `vendor_price` | `vendor_price` | setProductsAttributePrice | |
| (threaded) `attribute_id` | `attribute_id` | setProductsAttributePrice | From `setAdditionalOptionAttributes` response |

---

## ID threading sequence (SanMar PC61 push)

```
[1] setProductCategory(category_name, parent_id=0, visible=1)
        → returns category_id

[2] setProduct(category_id, products_title, products_internal_title, visible=1)
        → returns products_id

[3] for each variant v:
        setProductSize(products_id, size_name=v.size, color_name=v.color,
                       products_sku=v.sku, visible=1)
            → returns size_id
        store map sku → size_id

[4] for each variant v:
        setProductPrice(products_id, size_id=map[v.sku], qty=1, qty_to=null,
                        price=v.final_price, vendor_price=v.base_price, visible=1)

[5] (decoration products only — out of scope for PC61)
    for each option o:
        setAdditionalOption(products_id, title=o.title, options_type=o.options_type,
                            status='active', delete=0)
            → returns prod_add_opt_id
        for each attribute a in o.attributes:
            setAdditionalOptionAttributes(prod_add_opt_id, label=a.title,
                                          status='active', delete=0)
                → returns attribute_id
            setProductsAttributePrice(attribute_id, size_from=null, size_to=null,
                                      attributes_price=a.price,
                                      vendor_price=a.vendor_price,
                                      site_admin_markup=null, delete=0)
```

### Python contract (signatures only)

```python
# backend/modules/ops_client/client.py
from dataclasses import dataclass

@dataclass(frozen=True)
class OpsAuth:
    base_url: str
    token_url: str
    client_id: str
    client_secret: str

@dataclass(frozen=True)
class OpsResult:
    ok: bool
    data: dict | None
    ops_error_code: str | None
    ops_error_message: str | None
    raw: dict | None

class OpsGraphQLClient:
    async def execute(self, query: str, *, variables: dict) -> OpsResult: ...

# backend/modules/ops_client/mutations.py
async def set_product_category(*, client, category_name, parent_id, visible) -> OpsResult: ...
async def set_product(*, client, category_id, products_title, products_internal_title, visible) -> OpsResult: ...
async def set_product_size(*, client, products_id, size_name, color_name, products_sku, visible) -> OpsResult: ...
async def set_product_price(*, client, products_id, size_id, qty, qty_to, price, vendor_price, visible) -> OpsResult: ...
async def set_additional_option(*, client, products_id, title, options_type, status, delete) -> OpsResult: ...
async def set_additional_option_attributes(*, client, prod_add_opt_id, label, status, delete) -> OpsResult: ...
async def set_products_attribute_price(*, client, attribute_id, size_from, size_to, attributes_price, vendor_price, site_admin_markup, delete) -> OpsResult: ...

# backend/modules/ops_client/push.py
async def push_apparel_product(
    *, db, customer_id: UUID, product: ProductIngest, dry_run: bool
) -> dict:
    """Executes the 4-step ID-threaded push for an apparel product (PC61-shape).
    Returns dict matching push_log row + step_results JSONB."""
```

---

## Backend file changes

| File | Action | Reason |
|------|--------|--------|
| `backend/modules/ops_client/__init__.py` | NEW | Package |
| `backend/modules/ops_client/client.py` | NEW | OAuth-aware GraphQL transport; typed errors |
| `backend/modules/ops_client/mutations.py` | NEW | 7 mutation wrappers |
| `backend/modules/ops_client/push.py` | NEW | `push_apparel_product` + future `push_print_product` orchestrators |
| `backend/modules/integration_gateway/__init__.py` | NEW | |
| `backend/modules/integration_gateway/routes.py` | NEW | 9 endpoints |
| `backend/modules/integration_gateway/auth.py` | NEW | `X-Orchestrator-Key` enforcement + scope check |
| `backend/modules/integration_gateway/idempotency.py` | NEW | Key + payload-hash ledger |
| `backend/modules/integration_gateway/schemas.py` | NEW | Request/response envelopes |
| `backend/modules/ops_push/service.py` | EDIT | Drop `trigger_n8n_push()`; dispatch to ops_client |
| `backend/modules/ops_push/merge.py` | SHRINK | Hub-domain merge only; OPS field mapping moves to ops_client |
| `backend/modules/markup/routes.py` | EDIT | Collapse `/payload` + `/ops-variants` + `/ops-options` into single payload endpoint |
| `backend/modules/master_options/routes.py` | EDIT | Replace `/sync` (n8n trigger) with direct FastAPI ingest |
| `backend/modules/push_mappings/routes.py` | EDIT | Gateway-owned upsert route |
| `backend/main.py` | EDIT | Register integration_gateway router |

---

## n8n role after change

### Stays (inbound supplier sync only)

| Workflow | Purpose |
|----------|---------|
| `sanmar-soap-pull.json` | Daily SanMar SOAP catalog pull |
| `sanmar-sftp-pull.json` | Daily SanMar SFTP catalog dump |
| `inventory-sync-hourly.json` | Hourly inventory delta across active suppliers |
| `pricing-sync-daily.json` | Daily pricing refresh |
| `catalog-sync-weekly.json` | Weekly full catalog sync |
| `closeouts-monthly.json` | Monthly closeouts pull |
| `vg-ops-pull.json` | VG → OPS inbound product pull |

All POST batched `ProductIngest[]` to `POST /api/integrations/v1/suppliers/{slug}/products`.

### Deleted

| Workflow | Replacement |
|----------|-------------|
| `ops-push.json` | FastAPI push pipeline (`/api/integrations/v1/push-requests`) |
| `ops-master-options-pull.json` | FastAPI direct call to OPS (`master_options/routes.py` rewrite) |

### Curl example — full SanMar → OPS push from terminal

```bash
curl -X POST "$API_BASE/api/integrations/v1/push-requests" \
  -H "Content-Type: application/json" \
  -H "X-Orchestrator-Key: $ORCH_KEY" \
  -H "Idempotency-Key: sanmar-pc61-$CUSTOMER_ID-$PRODUCT_ID" \
  -d '{
    "target":      { "customer_id": "'"$CUSTOMER_ID"'" },
    "source":      { "supplier_slug": "sanmar" },
    "product_ref": { "product_id": "'"$PRODUCT_ID"'" },
    "dry_run":     false
  }'

# Response: 202 Accepted
# { "push_log_id": "uuid", "status": "accepted", ... }

# Poll for terminal status
curl -H "X-Orchestrator-Key: $ORCH_KEY" \
  "$API_BASE/api/integrations/v1/push-requests/$PUSH_LOG_ID"
```

---

## Pre-M1 cleanup (carryover from prior reviews)

Before starting M1 implementation, land these small refactors:

1. **Move `master_options/routes.py:11` import** out of `n8n_proxy` (so M4 deletion of n8n_proxy doesn't break master_options).
2. **Build `frontend/src/lib/push-status.ts`** central status-map. Broaden `SelectionStatus` union to 9 values. Apply across the 16 hardcoded-status sites identified in prior preflight (Codex artifact 2026-05-13T10-04-17).
3. **Collapse `require_ingest_secret()` in `catalog/ingest.py:57-61` to `hmac.compare_digest`** (security fix carried over from PR #106 review).
4. **Real test-connection probe** per protocol (currently `suppliers/routes.py:166-196` is fake; admin sees green and import fails).

---

## Migration phases

| Phase | Action | Risk |
|-------|--------|------|
| **M1.0** | Pre-M1 cleanup (4 items above) | Low |
| **M1.1** | Implement `ops_client/` module (transport + 7 mutations + tests) | Low (greenfield) |
| **M1.2** | Implement `integration_gateway/` module (auth + idempotency + 9 endpoints) | Low (greenfield) |
| **M1.3** | Wire admin route `POST /api/push/{cid}/{pid}` to dispatch through gateway (response shape preserved) | Med — verify admin UI smoke before continuing |
| **M1.4** | Rewrite frontend "Push to OPS" button to call `/api/integrations/v1/push-requests` | Low |
| **M1.5** | Delete `ops-push.json`, `ops-master-options-pull.json` from `n8n-workflows/`. Delete `trigger_n8n_push()` + `N8N_PUSH_WEBHOOK_URL`. Delete `merge.py` (or absorb into ops_client mappers). | Med — only after M1.3+M1.4 verified |
| **M1.6** | Decoration push (option chain). Defer until first decoration product onboards. | Med |

**Critical rule:** M1.5 must NEVER precede M1.3+M1.4. Verified by integration test before merge.

---

## Test strategy (TDD-first per superpowers convention)

### Contract tests (must fail before implementation)

| Test | What it verifies |
|------|------------------|
| `test_ops_client_set_product.py` | Mutation wrapper sends correct GraphQL with right field names |
| `test_ops_client_id_threading.py` | Push orchestrator threads `products_id`/`size_id`/`attribute_id` correctly across mutations |
| `test_gateway_idempotency.py` | Same key + same payload returns existing `push_log_id`; same key + diff payload returns 409 |
| `test_gateway_auth.py` | `X-Orchestrator-Key` enforced; scope respected; missing key → 401 |
| `test_push_dry_run.py` | `dry_run=true` exercises full mutation plan via FakeOpsClient without real OPS calls |
| `test_push_partial_failure.py` | Halt-no-rollback: variant 3 fails → status='partial_failure', cleanup_targets=[ops_product_id, size_ids 1-2] |
| `test_admin_route_preserved.py` | `POST /api/push/{cid}/{pid}` still returns `{status, push_log_id, message, payload}` shape post-rewire |

### Integration tests (real OPS staging)

| Test | What it verifies |
|------|------------------|
| `test_e2e_sanmar_pc61_dry_run.py` | Full PC61 push payload validated against FakeOpsClient with mutation-shape assertions |
| `test_e2e_sanmar_pc61_real_ops.py` | Live PC61 push to OPS staging; verify products_id returned, sizes attached, prices set |

---

## Effort estimate (senior dev-days)

| Module | Days | Size |
|--------|------|------|
| Pre-M1 cleanup (4 items) | 1-2 | S |
| `ops_client` (transport + OAuth + 7 mutation wrappers + typed errors) | 3-5 | L |
| `integration_gateway` (auth + idempotency + 9 endpoints + status model) | 3-4 | L |
| Replace `ops_push/service.py` n8n trigger with direct ops_client + ID threading | 2-3 | M |
| Admin route rewire + frontend push-button repoint | 1-2 | S/M |
| Markup route collapse into single payload endpoint | 1-2 | S/M |
| Options push (decoration product mutations) — out of scope for PC61 but design-ready | 2-4 | L (later) |
| n8n workflow deletions + cleanup | 0.5-1 | S |

**Total for PC61 first-push milestone:** ~12-15 senior dev-days. ~3 weeks calendar.

---

## Out of scope (explicit)

- 4Over REST adapter (no real creds yet)
- S&S Activewear adapter (no real creds yet)
- 994-supplier scale optimization (capability matrix, virtualization, hot-load adapter registry)
- AWS ECS / SQS / Fargate worker migration
- CloudFront / S3 / CDN for images
- SECRET_KEY rotation automation
- JWT refresh endpoint
- `variant_axes` table refactor
- Print push payload (`options[]/sizes/print_details`)
- Admin UI for `integration_keys` (M2 of gateway spec)
- Frontend status-vocab expansion to 9 values (deferred to M2 frontend sprint)

Revisit only if a P0 blocker forces it.

---

## Open questions

1. **OPS auth model for supplier inbound:** `ops_inbound/ops_adapter.py:96-104` wants `auth_token` (single token). UI labels as OAuth2 (client_id + client_secret + token_url). Pick one and unify before M1.1. Recommendation: keep OAuth2 (already works for customer push), drop `auth_token` field.

2. **Markup route collapse vs preserve:** today 3 endpoints (`/payload`, `/ops-variants`, `/ops-options`) exist for n8n. After M1.5 deletion they have no caller. Recommendation: collapse into single `/api/integrations/v1/customers/{cid}/products/{pid}/payload` for admin UI + curl debugging only.

3. **Push-mappings ownership:** spec implies gateway writes them on success. Today `push_mappings/routes.py:15-22` is ingest-secret gated. Recommendation: gateway writes inline during `execute_push()`; public POST route becomes read-only.

4. **Idempotency-Key TTL:** spec doesn't define ledger retention. Recommendation: 30 days (covers retry windows + audit).

---

## References

### Companion specs (tracked in git)

| File | Purpose |
|------|---------|
| `docs/superpowers/specs/2026-05-11-integration-gateway-design.md` | Rev 3 architecture — auth, idempotency, status vocab, 4-endpoint base |
| `docs/superpowers/specs/2026-05-08-sanmar-ops-staging-push-design.md` | Superseded VPCE spec (banner at top explains why) |

### Plans (tracked in git under `.omc/`)

| File | Purpose |
|------|---------|
| `.omc/plans/2026-05-12-m0-integration-gateway-foundation.md` | M0 impl plan — additive DB + persistence snapshot + contract tests |

### Research (tracked in git under `.omc/`)

| File | Content |
|------|---------|
| `.omc/research/research-20260511-pushgateway-142234/report.md` | Top-level research findings |
| `.omc/research/research-20260511-pushgateway-142234/stages/stage-1.md` | Preconditions audit |
| `.omc/research/research-20260511-pushgateway-142234/stages/stage-2.md` | Spike bug confirmation (Bugs 1+2+3) |
| `.omc/research/research-20260511-pushgateway-142234/stages/stage-3.md` | Auth/secret patterns |
| `.omc/research/research-20260511-pushgateway-142234/stages/stage-4.md` | `ProductIngest` validated against PC61/K500/Decals #131 |

### CCG advisor artifacts (runtime-only, NOT in git — `.omc/artifacts/ask/`)

These are paper-trail evidence for design decisions. Future agents can re-run CCG; humans can read these to understand why a choice was made.

| Artifact | Source for |
|----------|-----------|
| `codex-act-as-a-senior-software-architect-2026-05-13T14-13-01.md` | Supplier readiness table, P0/P1/P2 action plan, 7 onboarding gaps |
| `codex-audit-the-ops-payload-contract-2026-05-13T15-39-22.md` | Field-name mismatches, ID threading gaps, master options storage |
| `codex-design-a-centralized-fastapi-owned-2026-05-13T17-09-21.md` | This spec's source — endpoint surface, field mapping, Python contracts |
| `codex-three-pre-flight-verifications-2026-05-13T10-04-17.md` | persist_product snapshot scope, 16 hardcoded frontend status sites, file:line spot-check |
| `gemini-deep-ux-product-flow-review-2026-05-13T13-52-36.md` | Full UX journey audit (T1-T5), top-5 UX gaps with fix priority |
| `codex-review-the-old-push-implementation-2026-05-13T09-38-25.md` | Old n8n-coupled push call graph, what to preserve/delete in M4 |
| `gemini-review-the-frontend-push-related-surface-2026-05-13T09-37-58.md` | Frontend touchpoint inventory, status-vocab gap, M2 integration_keys UI requirements |

### Backend code anchors

| Path | Why it matters for M1 |
|------|----------------------|
| `backend/modules/ops_push/service.py` | Old push path (M1 replaces); `trigger_n8n_push` deleted in M1.5 |
| `backend/modules/ops_push/merge.py` | Hub-domain merge (M1 shrinks; OPS field mapping moves to ops_client) |
| `backend/modules/ops_push/routes.py:48-65` | Admin push route (M1.3 rewires internally; response shape preserved) |
| `backend/modules/markup/engine.py:173` | Markup payload contract (`base_price`/`final_price` → OPS `vendor_price`/`price`) |
| `backend/modules/markup/routes.py:32-90` | 3 endpoints M1 collapses into one |
| `backend/modules/ops_inbound/ops_client.py` | Existing GraphQL client (M1 `ops_client` extends this pattern) |
| `backend/modules/ops_inbound/ops_adapter.py:42-84` | Inbound queries reference |
| `backend/modules/master_options/models.py:15,38` | DB tables (stay; M1 changes ingest path only) |
| `backend/modules/master_options/routes.py:124` | `/sync` n8n trigger (M1 replaces with direct FastAPI ingest) |
| `backend/modules/master_options/ingest.py:18` | Existing ingest endpoint (stays; gateway proxies to it) |
| `backend/modules/push_log/models.py:11-22` | Push log model (M0 expands +11 cols; M1 writes step_results/cleanup_targets) |
| `backend/modules/push_mappings/models.py:13-70` | Mapping table (M1 writes inline during `execute_push()`) |
| `backend/modules/push_mappings/routes.py:15-22` | Current ingest-secret upsert route |
| `backend/modules/auth/dependencies.py` | `X-Ingest-Secret` (existing); `X-Orchestrator-Key` will follow same pattern |
| `backend/modules/suppliers/routes.py:166-196` | Fake test-connection — pre-M1 cleanup item |
| `backend/modules/catalog/schemas.py:252` | `ProductIngest` canonical contract |
| `backend/modules/catalog/ingest.py:57-61` | `require_ingest_secret()` — collapse to `hmac.compare_digest` (pre-M1 security fix) |
| `backend/modules/import_jobs/registry.py:1-44` | Adapter registry (boot-time; stays as-is for M1) |
| `backend/modules/promostandards/adapter.py:129-172` | SanMar `hydrate_product` (Bugs 1+2 fixed in PR #104) |
| `backend/database.py:70-117` | `EncryptedJSON` Fernet (used for OPS creds) |
| `backend/main.py:80-85,247` | Adapter imports + router includes |

### Frontend code anchors

| Path | Why it matters for M1 |
|------|----------------------|
| `frontend/src/components/products/push-row-action.tsx:53-56` | Current "Push to OPS" button → bypasses backend; M1.4 repoints to `/api/integrations/v1/push-requests` |
| `frontend/src/app/(admin)/push-log/page.tsx:21,26,31` | Hardcoded statuses (`pushed`/`pending`/`failed`) — broadens to 9-value vocab |
| `frontend/src/app/(admin)/customers/[id]/catalog/page.tsx:24-345` | 9 hardcoded status sites (selected/pushed/stale/failed) — refactor via central status-map |
| `frontend/src/components/SelectionBadge.tsx:14-32` | 4 hardcoded badge entries — broaden to 9 |
| `frontend/src/components/products/push-history.tsx:55-63` | Hardcoded `pushed`/`failed` checks — broaden |
| `frontend/src/lib/types.ts:374` | `SelectionStatus` union — broaden to 9 values |
| `frontend/src/app/(admin)/suppliers/new/page.tsx:34-180` | Protocol enum + credential field mismatches (P0 fixes from senior review) |
| `frontend/src/app/(admin)/suppliers/[id]/page.tsx:217-231` | Supplier detail — needs Refresh Endpoints button |
| `frontend/src/app/(admin)/suppliers/[id]/import/page.tsx:49-94` | Orphan import page — needs entry point from detail |
| `frontend/src/app/(admin)/mappings/[supplierId]/page.tsx:41-45` | Mapping save wrapper bug |

### n8n custom node anchors (CANONICAL OPS GraphQL contract)

The custom node is the **source of truth** for OPS field names + mutation shapes. M1's `ops_client/mutations.py` must match these.

| Path | Defines |
|------|---------|
| `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts:823+` | Full mutation operations list |
| `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts:971` | `setProduct` input default (`category_id`, `visible`, `products_title`, `products_internal_title`) |
| `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts:981` | `setProductSize` input (`product_size_id`, `products_id`, `size_name`, `color_name`, `products_sku`, `visible`) |
| `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts:991` | `setProductPrice` input (`product_price_id`, `products_id`, `qty`, `qty_to`, `price`, `vendor_price`, `size_id`, `visible`) |
| `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts:1000` | `setProductCategory` input (`category_id`, `category_name`, `parent_id`, `visible`) |
| `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts:1494` | `setAdditionalOption` (beta) input (`prod_add_opt_id`, `products_id`, `title`, `options_type`, `status`, `delete`) |
| `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts:1503` | `setAdditionalOptionAttributes` (beta) input (`attribute_id`, `prod_add_opt_id`, `label`, `status`, `delete`) |
| `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts:1512` | `setProductsAttributePrice` (beta) input (`attribute_id`, `size_from`, `size_to`, `attributes_price`, `vendor_price`, `site_admin_markup`, `delete`) |
| `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts:6856` | `setAdditionalOption` mutation string + response shape (`prod_add_opt_id`) |
| `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts:6863` | `setAdditionalOptionAttributes` mutation string + response shape (`attribute_id`) |
| `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts:6870` | `setProductsAttributePrice` mutation string |
| `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts:7959` | GraphQL endpoint (n8n uses `${baseUrl}/api/`; backend `ops_inbound/ops_client.py:48` uses `/graphql` — verify which OPS accepts during M1.1) |

### n8n workflow anchors

| Path | M1 disposition |
|------|----------------|
| `n8n-workflows/ops-push.json:23` | Webhook reads query params (cause of trigger mismatch); DELETE in M1.5 |
| `n8n-workflows/ops-push.json:108` | Builds setProductCategory_input + setProduct_input + setProductPrice_template; DELETE |
| `n8n-workflows/ops-push.json:178,213` | `setProductSize` loop + single `setProductPrice` with `size_id: 0`; DELETE |
| `n8n-workflows/ops-push.json:289-312` | "Stub Apply Options" — never calls real `setAdditionalOption`; DELETE |
| `n8n-workflows/ops-master-options-pull.json:30,77` | `getManyMasterOptions` + POST to `/api/ingest/master-options`; DELETE (replaced by direct FastAPI call) |
| `n8n-workflows/sanmar-soap-pull.json` | KEEP (inbound supplier sync) |
| `n8n-workflows/sanmar-sftp-pull.json` | KEEP |
| `n8n-workflows/inventory-sync-hourly.json` | KEEP |
| `n8n-workflows/pricing-sync-daily.json` | KEEP |
| `n8n-workflows/catalog-sync-weekly.json` | KEEP |
| `n8n-workflows/closeouts-monthly.json` | KEEP |
| `n8n-workflows/vg-ops-pull.json` | KEEP (VG self-pull from OPS) |

### Recent merged PRs (context)

| # | Commit | Adds |
|---|--------|------|
| #103 | `8598137` | Phase 6+7 customer catalog selection + dashboard metrics |
| #104 | `0997937` | Spike bug fixes (Bug 1 `base_price`, Bug 2 Inventory v200) — preconditions for M1 |
| #105 | `5991f63` | Integration Gateway design spec Rev 3 |
| #106 | `cc91a35` | `X-Ingest-Secret` scope narrowing (timing-safe + path allow-list + `ingest_service` role) |

### Project conventions (CLAUDE.md highlights)

- **Modular monolith**, not microservices
- **Suppliers = DB config**, not per-supplier code (protocol adapter pattern)
- **VARCHAR for type columns**, not PG ENUMs
- **EncryptedJSON** for `suppliers.auth_config` + `customers.ops_auth_config`
- **PostgreSQL upserts** — `ON CONFLICT DO UPDATE`
- **Never add Co-Authored-By** lines to commits
- **shadcn/ui + Tailwind**, Blueprint design system (Outfit + Fira Code, paper #f2f0ed, blueprint blue #1e4d92)
