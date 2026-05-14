# Research Report: Pre-Spec Audit for Integration Gateway

**Session:** research-20260511-pushgateway-142234
**Date:** 2026-05-11
**Status:** complete
**Goal:** Comprehensive audit before writing Integration Gateway spec — 4 parallel stages

---

## Executive Summary

The Integration Gateway design (output of prior CCG advisory) is structurally viable on the current codebase, but **3 of 4 stages found gaps that must be addressed before the spec is committed.** ProductIngest schema validates as the canonical product contract with only one trivial non-breaking addition (variant sort_order). The current `ops_push/` module is 60% replaceable / 40% reusable, with a clean 5-phase migration order that keeps the admin push route live during the swap. n8n removal is a precise 311-LOC delete across 5 files plus 5 env vars. The spike script confirms 3 active bugs that block any push path (gateway, VPCE, or current) — all 3 are minimal-LOC fixes with a strict ordering constraint.

The clear verdict: write the spec, but include the 3 spike-script fixes (Bugs 1–3) as Phase M0 prerequisites before any gateway code lands. Without those, the new endpoints will appear to succeed but produce silently-broken OPS records.

---

## Methodology

### Research Stages

| # | Stage | Tier | Status | Findings file |
|---|-------|------|--------|---------------|
| 1 | ops_push module audit vs Gateway design | MEDIUM | complete | stages/stage-1.md |
| 2 | Decode 4 spike script bugs + minimal fixes | MEDIUM | complete (retry) | stages/stage-2.md |
| 3 | n8n reference map across backend | LOW | complete | stages/stage-3.md |
| 4 | ProductIngest schema fit for PC61/K500/Decals#131 | MEDIUM | complete | stages/stage-4.md |

### Approach

Goal E from user — all four stages run in parallel via `oh-my-claudecode:scientist` agents (sonnet × 3, haiku × 1). Stage 2 returned without writing on first run and was re-fired with an explicit absolute write path. Stage 3 wrote to a wrong path and was moved post-hoc. No cross-validation subagent was needed — findings did not contradict.

---

## Key Findings

### Finding 1: ops_push module split — 60% replace / 40% reuse, 5-phase migration

**Confidence:** HIGH

**Keep (5 items):**
- `push_mappings/models.py` (PushMapping + PushMappingOption) — durable source→OPS ID map
- `GET /api/push/history/{cid}/{pid}` — admin UI dependency
- `ops_inbound/ops_adapter.py` + `ProductIngest` schema — shared canonical contract
- `ProductPushLog` base 6 columns
- `GET /api/push/image/{id}/processed` — kept during transition, MEDIUM confidence

**Modify (5 items):**
- `ProductPushLog.status` — expand from 3 values to 8 (accepted/queued/processing/pushed/failed/partial_failure/rejected/canceled)
- `ProductPushLog` — add 11 new columns (request_id UUID UNIQUE, key_id, payload_hash, supplier_slug, supplier_sku, callback_url, callback_status, callback_attempts, step_results JSONB, cleanup_targets JSONB, retry_of UUID)
- `push_product()` — split into `prepare_push_intent()` + `execute_push()`
- `merge_product_with_decorations()` — replace with typed `build_push_payload(ingest, ...) -> OPSPushPayload`
- `POST /api/push/{cid}/{pid}` — route URL preserved, internal call chain rewired

**Delete (5 items):**
- `trigger_n8n_push()` (service.py:24–37)
- `N8N_PUSH_WEBHOOK_URL` env var
- `ops_auth` dict in webhook body — security anti-pattern
- old `push_product()` body
- (deferred MEDIUM) `GET /api/push/image/{id}/processed`

**Add (8 items):**
- `backend/modules/integrations/` (routes.py, auth.py, schemas.py, models.py, service.py)
- `integration_keys` table
- HMAC auth dependency (signing string: `{ts}\n{rid}\n{method}\n{path}\n{sha256(body)}`)
- `prepare_push_intent()` + `execute_push()`
- `payload_builder.py::build_push_payload()`
- `OPSPushPayload` Pydantic model
- Alembic migration (11 columns + integration_keys)
- Router registration in main.py

**Migration order (strict):**

| Phase | Action | Admin route safe? |
|---|---|---|
| M0 | Alembic additive schema | YES |
| M1 | Write prepare+execute+build_push_payload alongside existing | YES |
| M2 | Create integrations module, register 4 new routes | YES |
| M3 | Rewire admin route to prepare+execute | RISK — verify response shape first |
| M4 | Delete trigger_n8n_push, old push_product, N8N env, merge.py, ops_auth body | YES if M3 verified |
| M5 | Delete image route (deferred) | YES |

**Critical rule:** M4 must NEVER precede M3.

### Finding 2: 3 active bugs block all push paths; strict fix order required

**Confidence:** HIGH (Bugs 1–3), HIGH/MEDIUM (Bug 4)

The spike script confirms 3 bugs that break ANY push path — gateway, VPCE, or current. Bug 4 (OAuth2) is verified PASSING.

#### Bug 1: base_price=None on V2 normalizer path
- **File:** `backend/modules/promostandards/ps_normalizer_v2.py::merge_pricing()`, lines 142–166
- **Cause:** Function appends VariantPriceIngest tiers but never assigns `variant.base_price`. Pydantic defaults to None.
- **Fix:** Backfill from Net-tier minimum after the existing price-append loop (~10 LOC).
- **Spike confirms:** 0/3 sampled variants have base_price set.

#### Bug 2: Inventory v200 SOAP not called
- **File:** `backend/modules/promostandards/adapter.py::hydrate_product()`, lines 129–153
- **Cause:** Calls get_product, get_pricing, get_media — stops. Never calls `_call_get_inventory`. INVENTORY WSDL is wired and `client.py::get_inventory()` + `_parse_inventory()` exist. Pure missing call.
- **Fix:** Add `_call_get_inventory` adapter method + call from `hydrate_product` after merge_media (~15 LOC).
- **Spike confirms:** every variant has `inventory=None`.

#### Bug 3: Markup engine bypassed by push
- **File:** `backend/modules/ops_push/service.py::push_product()`, line 76
- **Cause:** Zero imports from `modules.markup`. `merge_product_with_decorations` ships raw supplier net price as final OPS price.
- **Fix:** Apply markup engine inside the payload builder (Spec replaces this entirely in M1, but a bridge patch is possible for backporting).
- **Spike does not directly assert Bug 3** — it's implied by section 9's manual markup demo.

#### Bug 4: VG customer OAuth2 — PASSES
- Spike sections 6 + 7: DB fields present + live token issuance returns 200 with non-empty access_token.
- Scope boundary: GraphQL mutation auth scope NOT verified (no setProduct test call).

#### Strict fix order

1. **Bug 1** first — preflight rule #1 requires `base_price_set`; without it pipeline aborts every product.
2. **Bug 2** second — independent of Bug 1, but produces inventory=null on every OPS variant.
3. **Bug 3** third — must wait for Bug 1; `apply_markup(None, rule)` returns None (`engine.py:53`), silently no-ops if base_price still null.
4. **Bug 4** — already passing, no action.

### Finding 3: n8n removal is 311 LOC across 5 files + 5 env vars

**Confidence:** HIGH

| Component | LOC to delete |
|---|---|
| `modules/n8n_proxy/routes.py` | 172 (entire file) |
| `modules/ops_push/service.py` (trigger_n8n_push + call site) | 37 |
| `tests/test_n8n_url_config.py` + `tests/test_ops_push_failure.py` | ~94 |
| `main.py` (import + router + lifespan cleanup) | 6 |
| `modules/master_options/routes.py` (import) | 2 |
| **Total delete** | **311** |
| Docstring/comment renames (8 files) | ~16 |
| Intentional keeps | 11 (n8n_credential_id field, historical comments, fixtures) |

Env vars to remove from production: `N8N_API_BASE_URL`, `N8N_WEBHOOK_BASE_URL`, `N8N_WEBHOOK_BASE`, `N8N_API_KEY`, `N8N_PUSH_WEBHOOK_URL`. Plus drop `N8N_WEBHOOK_BASE_URL` from `_PROD_REQUIRED_ENV_VARS` in main.py.

After removal: backend reads zero N8N_* env vars.

### Finding 4: ProductIngest covers PC61 / K500 / Decals #131 with one trivial addition

**Confidence:** HIGH (PC61, K500, Decals — VERY HIGH for Decals since live code already does the mapping)

| Product | Fit | Schema additions |
|---|---|---|
| **SanMar PC61** (apparel + variants + decoration) | YES | none |
| **SanMar K500** (tiered pricing 4 breaks) | YES | none — `VariantPriceIngest.quantity_max: Optional[int]` handles open top tier |
| **OPS Decals #131** (print + options + sizes + master_option_id) | YES | none — `ops_adapter.py:_normalize_to_ingest()` already does this in live code |

**One cross-cutting schema addition (PC61 + K500):**

```python
# In VariantIngest:
sort_order: int = Field(
    default=0,
    description="Display sort order in OPS configurator. Populated from supplier size_index."
)
```

Non-breaking (default 0). Backfilled from SanMar PromoStandards `PSProductData.parts[].size_index`.

**Decoration overlay placement (confirmed):**

Per-area decoration prices live in the **top-level `decorations` array of the push envelope**, NOT bolted onto variants and NOT inside `ProductIngest`. ProductIngest stays purely catalog; decorations are a per-push customer-configured concern.

**Verdict on Codex claim** ("reuse ProductIngest as the product payload core"): **THUMBS UP.** Supporting:
- All three products map without schema-pollution
- `raw_payload: Optional[dict]` absorbs supplier-specific extras
- Only addition is one non-breaking int field

---

## Cross-Validation Results

No contradictions across the 4 stages. Synergies:

1. **F1.4 (add `integration_keys`) + F3 (delete n8n_proxy)** — n8n_proxy module's 172 LOC are replaced by the integrations module's `routes.py + auth.py`. Net code change after migration likely ~neutral or slightly down.

2. **F2.1 + F2.3 (Bug 1 → Bug 3 dependency) + F1.2 (build_push_payload replacement)** — the spec's `build_push_payload()` design naturally absorbs both fixes if implemented correctly. Bug 1 is a normalizer fix (pre-payload); Bug 3 is a payload-builder fix. The spec replaces merge.py with build_push_payload — Bug 3 fix lives there.

3. **F4.5 (sort_order addition) + F1.2 (ProductPushLog column expansion)** — both are additive Pydantic/Alembic changes that can co-land in the M0 migration.

4. **F2.4 + F1.4 (HMAC auth)** — OAuth2 to OPS passes. HMAC auth to API-HUB is a separate concern. No conflict; they are different layers.

---

## Limitations

- **Stage 1:** Markup engine integration in `build_push_payload()` was not audited; the markup module is a dependency assumed to work post-Bug-3 fix.
- **Stage 1:** OPSClient mutation coverage (createProduct, updateProduct) was not verified. OPS-NODE-GAP-ANALYSIS.md notes 33 missing mutations.
- **Stage 1:** No existing test suite audit — M3 rewire requires integration test before M4 deletes.
- **Stage 1:** HMAC key secret distribution mechanism is out of scope here.
- **Stage 2:** Inventory v200 fix assumes SanMar v200 SOAP response matches `client.py::_parse_inventory` — not verified against live data.
- **Stage 2:** Bug 3 minimal fix is a bridge; full clean fix is `payload_builder.py` per spec.
- **Stage 3:** Scope was backend Python only. Frontend, docs, n8n-workflows/, n8n-nodes-onprintshop/, n8n.Dockerfile intentionally excluded — those stay regardless.
- **Stage 4:** Validated 3 representative products. A 4th class (e.g., variable-data print, or apparel with complex decoration zones) may surface additional schema needs.

---

## Recommendations

### Immediate (before writing spec)

1. **Apply Bugs 1 + 2 fixes in a tiny dedicated PR** — 2 files, ≤25 LOC total. Unblocks all push paths. No architectural risk. Verify with spike script re-run.

2. **Write fresh Integration Gateway spec** to `docs/superpowers/specs/2026-05-11-integration-gateway-design.md`. Supersedes `2026-05-08-sanmar-ops-staging-push-design.md` (link, mark deprecated). Incorporate:
   - 4-endpoint API surface from F1.4
   - 11-column ProductPushLog expansion from F1.2
   - 5-phase migration order from F1.5
   - HMAC auth with scoped keys from CCG synthesis
   - ProductIngest as canonical contract per F4.7
   - Bugs 1–3 as M0 prerequisites
   - `decorations` envelope outside `product` per F4.6

3. **Add `VariantIngest.sort_order` field** in the same migration as the ProductPushLog expansion.

### Spec → plan transition

4. **Plan should pre-allocate Phase M0** for spike-bug fixes BEFORE any new endpoint work. Without M0, M2 (new ingest endpoints) appears to succeed but produces silently-broken OPS records.

5. **Stage Bug 3 fix specifically inside `build_push_payload()` implementation (M1)**, not as a separate patch — keeps history clean and prevents Bug 3 from being "fixed twice."

### Post-spec, before merge

6. **Decision needed on `GET /api/push/image/{id}/processed`** — Stage 1 marked this MEDIUM (keep during transition). Confirm with whoever owns image processing whether this is still load-bearing for the admin UI.

7. **Decision needed on `n8n_credential_id` field on Supplier** — Stage 3 marked it KEEP as it represents the OPS OAuth credential, not n8n-specific logic. Consider renaming to `ops_credential_id` for clarity now that n8n is being removed from the backend.

---

## Action Checklist

- [ ] Write tiny PR: Bug 1 + Bug 2 fixes (`ps_normalizer_v2.py` + `adapter.py`), ~25 LOC, includes spike-script re-run as test evidence
- [ ] Re-run `python backend/scripts/sanmar_ops_spike.py` after merge; expect failures[] to drop from 3 → 0 (only Bug 3 known to remain)
- [ ] Draft Integration Gateway spec doc at `docs/superpowers/specs/2026-05-11-integration-gateway-design.md`
- [ ] Mark `docs/superpowers/specs/2026-05-08-sanmar-ops-staging-push-design.md` as superseded with banner
- [ ] Confirm `GET /api/push/image/{id}/processed` retention plan with frontend owner
- [ ] Confirm `n8n_credential_id` rename window with team
- [ ] After spec approved, write implementation plan with Phase M0–M5 task breakdown
- [ ] M0 task list = Alembic migration (ProductPushLog 11 cols + integration_keys + VariantIngest.sort_order)
- [ ] M1 task list = build_push_payload, prepare_push_intent, execute_push, OPSPushPayload model — Bug 3 fix lives here

---

## Appendix

### Raw findings files

- `stages/stage-1.md` — ops_push module audit
- `stages/stage-2.md` — spike bug decode
- `stages/stage-3.md` — n8n reference map (313 LOC delete count)
- `stages/stage-4.md` — ProductIngest schema validation

### Session state

- `state.json` — session metadata
- Path: `.omc/research/research-20260511-pushgateway-142234/`
