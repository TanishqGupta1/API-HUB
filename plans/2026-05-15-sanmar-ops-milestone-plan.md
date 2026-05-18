# SanMar → API-HUB → OPS: Milestone Plan

**Date:** 2026-05-15  
**Author:** Vidhi  
**Branch:** Vidhi  
**Audience:** Manager + Tech Lead  
**Scope:** End-to-end SanMar product import and OPS push — nothing else.

---

## 1. Milestone Goal

Make the following journey work, reliably, end to end:

```
Admin adds SanMar credentials
       ↓
API-HUB tests real SanMar connection
       ↓
API-HUB imports SanMar products (SOAP)
       ↓
Admin previews product (title, images, variants, sizes, colors, prices, errors)
       ↓
API-HUB maps SanMar fields → OPS fields
       ↓
API-HUB pushes product to OPS
       ↓
Admin sees success / failure status
```

No other suppliers. No AWS/ECS. No S&S, 4Over, Alphabroder. Those come after this works cleanly.

---

## 2. Current State (Post Code Audit)

A codebase audit was done on 2026-05-15. Key findings:

### What already works (do not rebuild)

| Component | Status | Evidence |
|-----------|--------|----------|
| SanMar Test Connection | ✅ Real | 3-step SOAP probe: PS directory → WSDL parse → `getProductSellable()` call |
| SanMar SOAP import | ✅ Real | `PromoStandardsClient` handles products, pricing, inventory, media |
| Category-based import | ✅ Real | `POST /api/suppliers/{id}/import-category` + background job |
| Import UI (frontend) | ✅ Real | Category picker → limit selector → live job polling |
| OPS push payload builder | ✅ Exists | Builds `setProduct`, `setProductSize`, `setProductPrice`, option steps, `updateProductStock` |
| Push log | ✅ Exists | Records every push attempt |
| Customer credential storage | ✅ Safe | `ops_auth_config` is excluded from all API responses |
| Mapping schema (backend) | ✅ Clean | `PushMappingUpsert` — well-typed, no shape bugs found |

### What is broken or unverified

| # | Problem | Severity | Location |
|---|---------|----------|----------|
| B1 | `auth_config` (SanMar password) returned in `GET /api/suppliers/` response | **Critical** | `backend/modules/suppliers/schemas.py` — `SupplierRead` includes `auth_config` field |
| B2 | End-to-end push not verified — pipeline exists but OPS response handling (product_id feedback loop) has not been traced live | **High** | `modules/integrations/routes.py`, `modules/ops_push/`, `modules/ops_client/` |
| B3 | Product preview page — unclear if it exists and shows all required fields (images, variants, missing-field errors) | **High** | Frontend — no preview page found in audit |
| B4 | REST/HMAC test connection is stubbed (not SanMar, but affects other suppliers added later) | **Medium** | `modules/suppliers/routes.py` — REST probe returns `{"ok": true}` without API call |
| B5 | Push status visibility — after push completes, it is unclear if admin sees a clear success/failure with OPS product ID | **Medium** | Push log UI + integration response |
| B6 | UI/backend field alignment on supplier form not fully verified | **Low** | Frontend supplier create/edit form vs `SupplierCreate` schema |

---

## 3. Task Plan

Organized into four phases. Each phase must complete before the next starts.

---

### Phase 1 — Security Fix (Day 1)
**Goal:** Stop leaking supplier credentials in API responses.

| Task | Description | File | Effort |
|------|-------------|------|--------|
| **T1** | Remove `auth_config` from `SupplierRead` schema. Return only non-secret fields: `id`, `name`, `slug`, `protocol`, `promostandards_code`, `base_url`, `adapter_class`, `is_active`, `created_at`, `product_count`. Add a separate `GET /api/suppliers/{id}/credentials-set` endpoint that returns only `{has_credentials: bool}` for the UI to show a "credentials configured" indicator. | `suppliers/schemas.py`, `suppliers/routes.py` | 2–3 hrs |

**Exit criteria:** `GET /api/suppliers/` response contains zero credential fields. Frontend still shows "credentials configured" status.

---

### Phase 2 — Product Preview Page (Days 2–3)
**Goal:** Admin can see what a product looks like before pushing it to OPS.

| Task | Description | Effort |
|------|-------------|--------|
| **T2** | Create `GET /api/catalog/products/{id}/preview` backend endpoint. Returns: `title`, `description`, `brand`, `category`, `images[]`, `variants[]` (each with `sku`, `size`, `color`, `price`, `inventory`), `missing_fields[]` (list of fields that are null/empty). | 4–5 hrs |
| **T3** | Build frontend preview page at `/products/{id}/preview`. Show: product header (title, brand, category), image gallery, variants table (sku/size/color/price/inventory), missing fields warning banner, "Push to OPS" button. | 6–8 hrs |

**Exit criteria:** Admin can open any imported SanMar product and see all data before pushing. Missing fields are highlighted.

---

### Phase 3 — End-to-End Push Verification & Fixes (Days 4–6)
**Goal:** Push one SanMar product to OPS and confirm the full response chain works.

| Task | Description | Effort |
|------|-------------|--------|
| **T4** | Trace the full push pipeline with real credentials: `POST /api/integrations/v1/push-requests` → preflight → payload builder → `ops_client` mutation execution → OPS response → push_log update. Fix any breaks found. | 4–6 hrs |
| **T5** | Verify OPS product_id feedback loop: `setProduct` returns `products_id` → that ID is used in `setProductSize` and `setProductPrice` calls. Confirm `ops_client` reads step results and passes IDs correctly between mutation steps. | 3–4 hrs |
| **T6** | Verify push status UI: after push, admin should see a clear status panel with: overall result (success/partial/failed), OPS product ID created, per-step results, and error messages if any step failed. Fix or build if missing. | 3–4 hrs |

**Exit criteria:** One SanMar product (e.g., PC61) can be pushed to a test OPS storefront, a product is created in OPS, and the admin UI shows the OPS product ID and success status.

---

### Phase 4 — UI Alignment & Mapping Fix (Days 7–8)
**Goal:** Confirm frontend and backend are fully aligned on all form payloads. Fix mapping save if broken.

| Task | Description | Effort |
|------|-------------|--------|
| **T7** | Audit supplier create/edit form: compare frontend payload shape with `SupplierCreate` / `SupplierUpdate` Pydantic schemas. Fix any mismatches. | 2–3 hrs |
| **T8** | Test mapping save/load flow end-to-end: map one SanMar product's sizes/colors to OPS master options, save, reload, confirm mapping persists correctly and is used during push. | 3–4 hrs |
| **T9** | Add smoke test: script that runs the full journey (import 1 SanMar product → preview → push) and asserts each step returned expected data. | 3–4 hrs |

**Exit criteria:** Mapping round-trips correctly. Supplier form saves and updates without errors. Smoke test passes.

---

## 4. Timeline Summary

| Phase | Work | Days |
|-------|------|------|
| Phase 1 — Security fix | T1 | Day 1 |
| Phase 2 — Product preview | T2, T3 | Days 2–3 |
| Phase 3 — E2E push | T4, T5, T6 | Days 4–6 |
| Phase 4 — UI alignment | T7, T8, T9 | Days 7–8 |
| **Total** | **9 tasks** | **8 working days** |

Buffer: 2 days for unexpected issues during Phase 3 (live OPS API calls often surface edge cases).

**Estimated completion: ~10 working days from start.**

---

## 5. Dependencies & Blockers

| Dependency | Owner | Needed For |
|------------|-------|------------|
| SanMar API credentials (username, password, customer number) | Christian / manager | Phase 3 E2E testing |
| OPS test storefront credentials (client_id, client_secret, token_url) | Christian / manager | Phase 3 E2E testing |
| OPS storefront has at least one category configured | OPS admin | Phase 3 — `setProduct` requires a valid category |

**Nothing in Phases 1 and 2 is blocked.** Phases 3 and 4 require the credentials above.

---

## 6. Out of Scope (Explicitly)

The following will NOT be worked on during this milestone:

- S&S Activewear, Alphabroder, 4Over
- 994-supplier scale / generic REST+HMAC adapter
- AWS ECS, SQS, CloudFront
- Advanced onboarding wizard
- n8n workflow automation (manual push only for this milestone)
- SanMar inventory sync scheduling

---

## 7. Definition of Done

The milestone is complete when:

1. `GET /api/suppliers/` returns no credential fields.
2. Admin can add SanMar credentials and the test connection calls the real SanMar SOAP API.
3. Admin can import a SanMar product category and see products in the catalog.
4. Admin can open a product preview page and see title, images, variants, prices, and any missing fields.
5. Admin can push a product to OPS. OPS creates the product and returns a product ID.
6. Admin can see the push result: OPS product ID, status (success/failed), and error details if any.
7. No SanMar/OPS credentials appear in any API response.

---

## 8. Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| OPS mutation API rejects payload format | Medium | Test with Postman/curl against OPS sandbox first before wiring to UI |
| SanMar credentials not available for E2E test | Medium | Use mock SOAP responses in Phase 3 unit tests; real creds only needed for final E2E |
| OPS category_id requirement — we send category_name, OPS may need category_id | Medium | Confirm with OPS API docs / Postman collection; may need a category lookup step |
| Mapping UI sends wrong payload shape (not yet fully audited) | Low | Phase 4 specifically targets this; schema looks clean but UI audit needed |
