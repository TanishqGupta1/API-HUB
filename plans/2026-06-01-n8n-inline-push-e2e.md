# Work Plan: n8n → Hub end-to-end inline product push

**Date:** 2026-06-01
**Status:** PENDING APPROVAL — do not implement until explicit go-ahead
**Owner:** Tanishq (PM/Tech Lead)
**Mode:** `/oh-my-claudecode:plan` direct

## Requirements summary

Let **any** n8n instance push a complete product to a customer's OnPrintShop (OPS)
storefront through the FastAPI Integration Gateway via a documented, self-serve, secured
contract. A single authenticated HTTP call both **loads** (catalog upsert) and **sends**
(OPS mutation chain). Outcome delivered by polling **and** webhook callback.

### Locked decisions
| Decision | Choice |
|---|---|
| Body | Inline full product (n8n is source of truth) |
| Granularity | Single product per request |
| Key provisioning | Admin UI (backend API already exists) |
| Result delivery | Poll **and** webhook |
| Extras (all in) | Preflight blockers in 202; `mutations.py` contract check (P0); example n8n workflow JSON; integration guide doc |

## Verified current state (file:line on `main`)

- Push entry `POST /api/integrations/v1/push-requests` — `modules/integrations/routes.py:104` (`create_push_request`); auth `X-Orchestrator-Key` via `auth.py:160` + `check_key_scope` (`auth.py:216`).
- `PushRequest` schema — `modules/integrations/schemas.py:89`. **Already has** `product: Optional[dict[str, Any]] = None  # inline upsert (future)` (`schemas.py:92`), `callback` (`schemas.py:95`), `decorations`, `sync_before_push`. **`product_ref` is currently required** (`schemas.py:91`).
- `prepare_push_intent` — `modules/ops_push/gateway.py:203`; `execute_push` — `gateway.py:399`; live client wired `gateway.py:441`/`:149`.
- Mutation chain — `ops_client/mutations.py` + `ops_push/payload_builder.py`; dispatch map `gateway.py:47`.
- Catalog upsert — `modules/catalog/persistence.py:31` `async def persist_product(...)` (ON CONFLICT DO UPDATE).
- Canonical inbound product schema — `ProductIngest` `modules/catalog/schemas.py:253` (fields: `supplier_sku`, `product_name`, `product_type`, `variants[]`, `images[]`, `options[]`, `sizes[]`, `apparel_details`/`print_details`, …). Discovery endpoint `GET /api/integrations/v1/suppliers/{slug}/schema` (`routes.py:304`).
- **Orchestrator-key admin API already exists**: `GET /api/integrations/keys` (`routes.py:624` `list_keys`), `POST /api/integrations/keys` (`routes.py:633` `create_key` → `IntegrationKeyCreated`, reveal-once), `POST /api/integrations/keys/{key_id}/revoke` (`routes.py:672`). Schemas `IntegrationKeyCreate/Created/Out` (`schemas.py:196+`).
- Callback SSRF validation `_validate_callback_url` (`schemas.py:46`).
- **Gap:** no n8n workflow calls `/push-requests`; n8n only ingests (`/suppliers/{slug}/products` + `X-Ingest-Secret`); custom node still calls OPS directly (legacy).
- **Open SSRF gap (issue #147):** `preflight.py:680` `check_image_urls_reachable` does `client.head(url, follow_redirects=True)` with no `assert_safe_url`.

## Design

**Inline push = upsert-then-push, one path.** When `PushRequest.product` is present: validate as
`ProductIngest`, `persist_product` upsert, then run the existing reference-based push over the
now-present product. Absent → current reference mode (backward compatible). Markup rules, OPS creds,
and `push_mappings` stay hub-side; inline supplies only the product.

## Implementation phases

### Phase 0 — P0 prereq: OPS mutation-contract correctness (blocking for live)
- **Steps:** For each mutation in `ops_client/mutations.py` (setProductCategory, setProduct, setProductSize, setProductPrice, setAssignOptions, setAdditionalOption(s), setProductsAttributePrice, updateProductStock, setProductDesign), compare GraphQL operation name, input type, and selected fields against the OPS Postman collection (source of truth) and the working n8n node mutations in `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts`. Record a mapping table mutation→Postman op→verdict.
- **Acceptance criteria:**
  - [ ] A table in this plan's appendix lists every mutation with verdict CONFIRMED/MISMATCH and the Postman op id.
  - [ ] Every MISMATCH has a concrete diff (field/type) and a fix applied to `mutations.py`.
  - [ ] `FakeOpsClient` dry-run sequence unchanged (dry-run is contract-agnostic).
- **Verification:** Diff `mutations.py` query strings vs Postman export; `pytest -m no_db -k ops_client`.

### Phase 1 — Backend: inline push mode
- **Steps:**
  1. `schemas.py:89` — change `product: Optional[dict[str, Any]]` → `product: Optional[ProductIngest]`; make `product_ref: Optional[PushRequestProductRef] = None`. Add a model validator: exactly one of (`product`, `product_ref`) required; if `product` set, derive `product_ref` (supplier_sku from `product.supplier_sku`, supplier_slug from `source.supplier_slug`).
  2. `gateway.py:203 prepare_push_intent` — when `req.product` set, call `persist_product(db, supplier, req.product)` (reuse ingest's session/upsert pattern) **before** the resolve-from-catalog step; keep the rest unchanged.
  3. `payload_hash` computed over `(target, product)` when inline, else current basis.
  4. Extend `PushRequestAccepted` (`schemas.py:113`) with `preflight: PreflightSummary` (blockers[], warnings[]); populate from `run_preflight` in the 202.
- **Acceptance criteria:**
  - [ ] POST with inline `product` + `dry_run:true` → 202, catalog row upserted (assert via DB query), response `status=dry_run_pushed`, `preflight.blockers==[]`.
  - [ ] FakeOpsClient records sequence `setProductCategory→setProduct→setProductSize×N→setProductPrice×N` for the inline product.
  - [ ] POST with `product_ref` only (no `product`) still works unchanged (regression).
  - [ ] POST with neither / both → 422 with stable error code.
  - [ ] Idempotent replay: same inline body + same `Idempotency-Key` → no duplicate push_log, returns prior result.
- **Verification:** `pytest -m no_db -k "push and inline"`; manual dry-run curl.

### Phase 2 — Security: inline image SSRF guard (also closes #147)
- **Steps:** Route every image URL from inline `product` (`image_url`, `images[].url`) through `assert_safe_url` before persistence/preflight. In `preflight.py:680` set `follow_redirects=False` and call `assert_safe_url(url)` before `client.head`. Same for mirror path.
- **Acceptance criteria:**
  - [ ] Inline product with image URL `http://169.254.169.254/...` → rejected pre-push (422/blocker), no outbound request made.
  - [ ] Private IP (10/8, 192.168/16) and redirect-to-internal image URLs blocked.
  - [ ] Legitimate supplier image URL passes.
- **Verification:** unit tests in `tests/` mocking resolver; assert `assert_safe_url` raises.

### Phase 3 — Frontend: orchestrator-keys admin page (backend already exists)
- **Steps:** New `frontend/src/app/(admin)/integration-keys/page.tsx`. Wire to existing `GET/POST /api/integrations/keys` + `/keys/{id}/revoke`. List (masked key, scope, last_used, revoke); "Create key" modal (multiselect customers + suppliers) → reveal-once banner (key shown once). Blueprint design system, shadcn/ui + Tailwind. Add nav entry.
- **Acceptance criteria:**
  - [ ] Page lists keys with scope + last_used; raw secret shown exactly once on create, never refetched.
  - [ ] Revoke disables the key (subsequent use → 401).
  - [ ] `tsc --noEmit` clean (excl. pre-existing sentry); page gated behind vg_admin.
- **Verification:** `npm run build`; manual click-through; key created → used against `/push-requests` → revoked → 401.

### Phase 4 — n8n recipe + integration docs
- **Steps:** (a) Example workflow JSON in `n8n-workflows/ops-inline-push.json`: HTTP Request → `POST /push-requests` (header `X-Orchestrator-Key`, body from prior nodes), then a Wait+poll `GET /push-requests/{id}` branch, plus a Webhook trigger node receiving the callback. (b) `docs/integration-guide-inline-push.md`: auth + key minting, body schema (link discovery endpoint), full example, error codes, idempotency, poll-vs-webhook, partial-failure contract.
- **Acceptance criteria:**
  - [ ] Workflow JSON imports cleanly into n8n (valid schema).
  - [ ] Guide documents every error code the endpoint can return and the partial-failure semantics (catalog upserted, push_log=partial_failure).
- **Verification:** import JSON into local n8n; doc reviewed against actual response shapes.

### Phase 5 — E2E verification
- **Steps:** Full path test: mint key (Phase 3 API) → inline `dry_run` push (assert plan) → live push with mocked `OpsGraphQLClient` → poll terminal → assert callback webhook fired with correct event + HMAC.
- **Acceptance criteria:**
  - [ ] One e2e test covers mint→push→poll→webhook; passes in `pytest -m no_db`.
  - [ ] Partial-failure path asserted (inline upsert ok, OPS step fails → `partial_failure`, catalog still has product).
- **Verification:** `cd backend && pytest -m no_db -k e2e_inline_push`.

## Risks and mitigations
| Risk | Severity | Mitigation |
|---|---|---|
| Wrong OPS mutation contracts → live push fails late | HIGH | Phase 0 is P0/blocking; dry-run unaffected |
| SSRF via inline image URLs | HIGH | Phase 2 `assert_safe_url` + `follow_redirects=False` (closes #147) |
| Inline payload abuse / size | MED | pydantic caps + per-key rate limit (`auth.py`) |
| Missing hub-side markup/creds/mapping | MED | preflight blockers surfaced in 202 → n8n fails fast |
| `product_ref`→optional breaks existing callers | LOW | validator keeps `product_ref`-only path working; regression test |

## Verification steps (global)
1. `cd backend && source .venv/bin/activate && pytest -m no_db -q` — all green.
2. `python -c "import main"` — imports.
3. `cd frontend && npm run build` — clean (excl. pre-existing sentry).
4. Manual: mint key → curl inline dry-run → live (mock) → poll → webhook received.

## Out of scope (YAGNI)
- Batch/multi-product inline push (separate bulk schema already exists).
- Migrating the legacy n8n node off direct-OPS.
- Field-level hybrid ref+inline override (presence of `product` is the only switch).

## Appendix — Phase 0 mutation-contract table (to be filled during Phase 0)
| Mutation | Postman op | Input type | Verdict | Notes |
|---|---|---|---|---|
| _populate in Phase 0_ | | | | |
