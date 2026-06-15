# V2 Plan — SanMar → OPS Push + Multi-Supplier Verification + Security

**Date:** 2026-06-11
**Author:** Vidhi / GraphX Connect Team
**Horizon:** ~5 weeks (July 2026)

**Goal:** Ship a production-ready end-to-end pipeline — SanMar products fully pushed to OPS
storefronts with working images, correct SKUs, and live inventory. Then verify all other
suppliers — split by product type because apparel (S&S, Alphabroder) and print (4Over) need
completely different OPS push paths. Close out with a full security audit.

---

## Critical Finding — Two Product Types, One Pipeline (Currently Broken for Print)

All four suppliers are confirmed working at the **ingest + normalise** stage.
However the OPS push pipeline (`payload_builder.py`) is **apparel-only**. It has no
`product_type` branch. Pushing a 4Over print product today produces a broken OPS listing:
zero price, no variant options, invisible in the storefront.

| Supplier | Product Type | Push Pipeline Today | Status |
|----------|-------------|--------------------|----|
| SanMar | Apparel | Colour/Size variants, tiered pricing | ✅ Works |
| S&S Activewear | Apparel | Colour/Size variants, flat pricing | ✅ Works (needs creds) |
| Alphabroder | Apparel | Colour/Size variants, tiered pricing | ✅ Works (needs creds) |
| 4Over | **Print** | Dimensions + formula pricing | ❌ **Not built** |

---

## Current State (2026-06-11)

What is confirmed working:
- All four supplier adapters ingest and normalise product data ✅
- `product_type` field stored correctly in DB — `"apparel"` or `"print"` ✅
- `ApprelDetails` / `PrintDetails` tables created and populated correctly ✅
- Integration Gateway accepts push jobs ✅
- 9-step OPS mutation plan built — **apparel products only** ✅
- Durable arq queue, idempotency, step resumption all working ✅
- Auth hardened ✅

Known gaps:
1. **Images** — S3/R2 not configured; `OPS_PUSH_INCLUDE_IMAGES=0`
2. **SKU dedup** — untested against real OPS storefront
3. **Stock** — `OPS_PUSH_INCLUDE_STOCK=0`; `updateProductStock` never run live
4. **Print push path** — `payload_builder.py` has no print branch; 4Over products
   produce broken OPS listings (empty price, no options)
5. **Preflight is product-type blind** — no check validates `PrintDetails` exist or
   dimensions are set; print products silently pass preflight and fail mid-push
6. **4Over decoration mapping** — `setAdditionalOption` for embroidery/screen print not
   built in `fourover_normalizer.py`
7. **All Phase 5 tests fully mocked** — no live API call ever made to S&S, Alphabroder,
   or 4Over

---

## Phase Map

| Phase | What | Blocker | Est. Time |
|-------|------|---------|-----------|
| **Phase 1** | Image pipeline — S3/R2 config + OPS image push | R2 bucket creds | 3–4 days |
| **Phase 2** | SKU dedup + idempotency verified against real OPS | SanMar API creds | 2–3 days |
| **Phase 3** | Stock/Inventory — live `updateProductStock` | Phase 1 + 2 done | 2–3 days |
| **Phase 4** | SanMar E2E sign-off — codebase checklist, new customer onboarding | Phase 1–3 done | 2 days |
| **Phase 5A** | Apparel suppliers — S&S + Alphabroder verified end-to-end | Live creds from Christian | 3–4 days |
| **Phase 5B** | Print push path — build `payload_builder` print branch + preflight | None (code task, no creds needed) | 4–5 days |
| **Phase 5C** | 4Over verified end-to-end (print) | Phase 5B done + 4Over creds | 3–4 days |
| **Phase 6** | Security audit — full codebase review | None (parallel-safe after Phase 4) | 3–4 days |

---

## Phase 1 — Image Pipeline (S3 / R2)

**Why this is first:** OPS product listings without images are incomplete and get rejected or look
wrong in the storefront. Images are the visual foundation everything else depends on.

**What the code already has:**
- `backend/modules/images/mirror.py` — downloads supplier image URLs, converts to WebP (1200px,
  85% quality, alpha-channel preserved), uploads to S3/R2 with content-addressed keys
- `backend/modules/ops_push/payload_builder.py` step 8 — `setProductsImageGallery` mutation is
  built and part of the 9-step plan
- `OPS_PUSH_INCLUDE_IMAGES` env flag — currently defaults to `0`

**What is missing / needs configuring:**
- [ ] **1.1** — Set S3/R2 environment variables in `.env`:
  ```
  S3_ACCESS_KEY_ID=<from Cloudflare R2 dashboard>
  S3_SECRET_ACCESS_KEY=<from Cloudflare R2 dashboard>
  S3_REGION=auto
  S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
  S3_PRODUCT_IMAGES_BUCKET=graphx-product-images
  CDN_BASE_URL=https://images.graphxcpi.com
  ```
- [ ] **1.2** — Align bucket name with Christian's existing image upload bucket (graphxcpi.com).
  If they share a bucket: same `CDN_BASE_URL`, zero code change. If separate: leave as-is.
- [ ] **1.3** — Enable images in push: set `OPS_PUSH_INCLUDE_IMAGES=1` in env
- [ ] **1.4** — Run image mirror for one SanMar product:
  ```
  POST /api/images/mirror/{product_id}
  ```
  Verify: CDN URL returned, image accessible at `CDN_BASE_URL/products/sanmar/...`
- [ ] **1.5** — Trigger a dry-run push with images:
  ```
  POST /api/integrations/v1/push-requests
  { "customer_id": "...", "product_id": "...", "dry_run": true }
  ```
  Inspect `step_results[7]` (setProductsImageGallery) — confirm CDN URLs are in the payload
- [ ] **1.6** — Trigger a live push to OPS staging. Verify image appears in storefront.
- [ ] **1.7** — Run batch mirror for all SanMar products:
  ```
  POST /api/images/mirror-batch
  { "product_ids": [...] }
  ```

**Exit criteria:** A SanMar product pushed to OPS staging shows at least one image loaded from the
CDN. Mirror status endpoint returns `mirrored > 0` for the product.

---

## Phase 2 — SKU Mapping + Deduplication

**Why this matters:** OPS assigns its own `products_id` per product. If we push the same SanMar
SKU twice, we should update the existing OPS product, not create a duplicate. This is handled by
the pre-push dedup check (P2.2 in `gateway.py`) but it has never been validated against a real
OPS storefront.

**What the code already has:**
- `push_mappings` table — stores `(customer_id, supplier_sku) → ops_product_id` after each push
- `execute_push()` step P2.2 — queries OPS for an existing product with the same SKU before pushing
- `idempotency_key` + `payload_hash` on `ProductPushLog` — prevents duplicate jobs for same content

**Tasks:**
- [ ] **2.1** — Push SanMar product to OPS staging for the first time. Confirm `push_mappings` row
  is created with `ops_product_id` populated.
- [ ] **2.2** — Push the same product a second time (same payload). Confirm:
  - Gateway returns the existing `push_log_id` (idempotency hit), not a new one
  - OPS product is updated, not duplicated
  - `push_mappings` row is upserted (not doubled)
- [ ] **2.3** — Push the same product after a price change (different payload hash). Confirm:
  - New push job is created (different hash = not idempotent)
  - OPS product is updated, not duplicated
  - `push_mappings.ops_product_id` is preserved
- [ ] **2.4** — Check `supplier_sku` field is populated for all SanMar variants in the DB:
  ```sql
  SELECT COUNT(*) FROM product_variants WHERE supplier_sku IS NULL;
  ```
  If any are null: trace through `ps_normalizer_v2.py` and fix the mapping.
- [ ] **2.5** — Verify `setProduct` mutation payload includes the `sku` field correctly mapped to
  `supplier_sku` from the product record.

**Exit criteria:** The same SanMar product can be pushed 3× without creating duplicates in OPS.
`push_mappings` has exactly one row per (customer, product) pair.

---

## Phase 3 — Stock / Inventory

**Why this matters:** Storefronts showing out-of-stock products that are actually available (or
vice versa) directly impacts orders. SanMar provides real-time inventory via their SOAP API.

**What the code already has:**
- Step 9 of the mutation plan: `updateProductStock` — built in `payload_builder.py`
- `OPS_PUSH_INCLUDE_STOCK` env flag — currently defaults to `0`
- `discover_changed(since=datetime)` on SanMarAdapter — delta sync for inventory-only updates
- Stock ID resolution in `execute_push()` Phase 6 — resolves OPS `stock_id` from `ops_product_id`

**Tasks:**
- [ ] **3.1** — Enable stock in push: set `OPS_PUSH_INCLUDE_STOCK=1` in env
- [ ] **3.2** — Verify SanMar inventory data is being stored in variants:
  ```sql
  SELECT color, size, inventory_quantity FROM product_variants
  WHERE product_id = '<sanmar-product-id>' LIMIT 20;
  ```
  If `inventory_quantity` is all null: check `merge_inventory()` in `ps_normalizer_v2.py`
- [ ] **3.3** — Push a SanMar product with stock enabled (dry run first). Inspect
  `step_results[8]` — confirm `updateProductStock` payload has correct quantities per size.
- [ ] **3.4** — Run a live push. Verify in OPS staging that product sizes show inventory counts.
- [ ] **3.5** — Trigger a delta sync (inventory-only) for SanMar:
  ```
  POST /api/suppliers/{sanmar_id}/import?mode=delta
  ```
  Confirm only `inventory_quantity` is updated in DB, not full product re-fetch.
- [ ] **3.6** — Push the same product again after the delta sync. Confirm stock quantities in OPS
  are updated to match the latest values from SanMar.

**Exit criteria:** A SanMar product in OPS staging shows correct per-size inventory counts.
A delta sync + re-push updates those counts without touching product name/price/images.

---

## Phase 4 — SanMar E2E Sign-Off

**Goal:** Formally confirm that the entire SanMar → OPS pipeline is production-ready and that
**the only thing needed to onboard a new SanMar customer is entering their API credentials in the
UI**. No code changes. No manual steps.

**Codebase checklist — verify each item in the actual code:**

- [ ] **4.1** — Adapter self-registration: confirm `SanMarAdapter` is registered in
  `backend/modules/promostandards/adapters/__init__.py` and auto-loads from DB supplier row
- [ ] **4.2** — Auth config: confirm `suppliers.auth_config` (EncryptedJSON) is the only place
  SanMar credentials live. No hardcoded keys, no .env secrets for SanMar.
- [ ] **4.3** — SOAP fault handling: confirm `AuthError` aborts the sync with a clear error
  message in the sync job log (not a silent 500).
- [ ] **4.4** — Full product types: SanMar sells both apparel (tiered pricing) and some
  accessories. Confirm both resolve correctly through `TieredVariantResolver`.
- [ ] **4.5** — Image types: SanMar provides front/back/side/detail images via `getMediaContent`.
  Confirm all image types are stored and the primary image is set correctly in OPS.
- [ ] **4.6** — Retry safety: kill the arq worker mid-push. Restart it. Confirm the push resumes
  from the last completed step (not from scratch), using `step_results` resumption logic.
- [ ] **4.7** — New customer onboarding test (the real test):
  1. Add a new customer row in UI with OPS staging URL + fresh OAuth2 creds
  2. Add SanMar supplier row with test API credentials (username + password only)
  3. Click "Sync" → wait for products to appear in catalog
  4. Click "Push to Store" on one product
  5. Open OPS staging — product is live with image, price, stock
  6. **Zero code was written. Zero .env changes were made.**

**Exit criteria:** The onboarding test in 4.7 passes in a clean environment. Document any manual
step that was required — if any exist, they are bugs to fix before this phase is done.

---

## Phase 5A — Apparel Suppliers (S&S + Alphabroder)

**Why this is separate from 5B/5C:** S&S and Alphabroder are both apparel. Their products
produce Colour/Size variants with base prices — exactly what the current push pipeline
expects. These two suppliers work through the existing pipeline with **zero code changes**.
The only blocker is live credentials from Christian.

> ⚠️ **Blocked on credentials only. No code work needed.**

### S&S Activewear
- [ ] **5A.1** — Seed S&S credentials in the suppliers table:
  `auth_config = { "account_number": "...", "api_key": "..." }` (HTTP Basic Auth — not OAuth)
- [ ] **5A.2** — Trigger a sync. Confirm products land in catalog with colour/size variants + images.
- [ ] **5A.3** — Verify pricing: S&S uses flat `yourPrice` per SKU (not tiered).
  Confirm `TieredVariantResolver` falls back to `variant.base_price` correctly when no tiers exist.
- [ ] **5A.4** — Push one S&S product to OPS staging. Verify name, price, colour/size options,
  images all appear correctly in storefront.

### Alphabroder
- [ ] **5B.1** — Seed Alphabroder credentials: `auth_config = { "id": "...", "password": "..." }`
- [ ] **5B.2** — Trigger a sync. Note: WSDLs are hardcoded in `alphabroder_adapter.py` as
  constants (`ALPHABRODER_WSDLS` dict) — DB `endpoint_cache` takes priority if set but hardcoded
  fallbacks always exist. This is intentional and correct behaviour.
- [ ] **5B.3** — Confirm products ingest with tiered pricing (Net/Sale/MSRP/Case) same as SanMar.
- [ ] **5B.4** — Push one Alphabroder product to OPS staging. Verify full payload correct.

**Exit criteria:** Both S&S and Alphabroder products appear live in OPS staging with correct
pricing, colour/size options, and images. No code was changed — only credentials were seeded.

---

## Phase 5B — Print Push Path (4Over code work, no creds needed)

**Why this must be built:** The current `payload_builder.py` has **no `product_type` branch**.
It always runs the apparel path (colour/size variants, 6 tiered price steps). A 4Over print
product has no colour/size variants — it has dimensions (width × height), a formula price, and
options like paper weight, lamination, coating. Pushing it through the apparel path today creates
a broken OPS product with `price=0` and no visible options.

**This is pure code work. Can be started immediately — no credentials needed.**

### 5B.1 — Add `product_type` branch to `payload_builder.py`

The builder at `ops_push/payload_builder.py` needs a top-level split:

```python
if product.product_type == "print":
    return _build_print_payload(ctx)
else:
    return _build_apparel_payload(ctx)   # existing logic, unchanged
```

**`_build_print_payload()` must:**
- [ ] Read `PrintDetails` (dimensions bounds, formula, base_price_per_sq_unit)
- [ ] Read `ProductSize` rows (preset width × height pairs) instead of variants
- [ ] Build `setProduct` with print-specific fields (no colour/size)
- [ ] Build `setProductSize` from `ProductSize` rows (dimensions as size labels)
- [ ] Build `setProductPrice` using formula: `base × area × area_factor + setup_fee`
  instead of tiered variant pricing
- [ ] Build `setAdditionalOption` for print options (paper weight, lamination, coating,
  finish, fold) from `PSProductPart.attributes` dict populated by `fourover_normalizer.py`
- [ ] Skip colour/size `setAdditionalOption` steps (not applicable to print)
- [ ] Respect `OPS_PUSH_INCLUDE_IMAGES` and `OPS_PUSH_INCLUDE_STOCK` flags same as apparel

### 5B.2 — Add product-type preflight checks to `preflight.py`

Currently `preflight.py` is product-type blind — a print product with no `PrintDetails`
passes all 8 checks and fails mid-push. Add:

- [ ] `check_print_details_present` — if `product_type == "print"`: verify `PrintDetails`
  row exists, `base_price_per_sq_unit > 0`, `min_width` and `max_width` are set
- [ ] `check_apparel_variants_present` — if `product_type == "apparel"`: verify at least
  one variant exists with `base_price > 0` and `color` or `size` set
- [ ] Gate: a print product with missing `PrintDetails` returns `422 PREFLIGHT_BLOCKER`
  with a clear message before any mutation fires

### 5B.3 — Build 4Over decoration mapping

Currently `fourover_normalizer.py` does not map decoration options (embroidery, screen
print, setup fees) to `setAdditionalOption`. This is a gap — no code exists anywhere for it.

- [ ] In `fourover_normalizer.py`: identify which product option fields represent decoration
  types vs. print specifications (paper, lamination = print spec; embroidery, imprint = decoration)
- [ ] Map decoration fields to `DecorationCharge` ingest model
- [ ] In `_build_print_payload()`: include `setAdditionalOption` step for decoration options
  (separate from paper/lamination options)

### 5B.4 — Add unit tests (no live creds needed)

- [ ] `test_payload_builder_print.py` — mock a 4Over product with `PrintDetails` + `ProductSize`
  rows, run `_build_print_payload()`, assert correct mutation plan shape
- [ ] `test_preflight_print.py` — assert `check_print_details_present` blocks a print
  product with missing `PrintDetails`; assert it passes a complete print product
- [ ] These tests must be hermetic (no DB, no OPS calls) matching the existing test pattern

**Exit criteria:** A 4Over print product produces a valid OPS mutation plan when dry-run through
the push pipeline. Preflight correctly gates incomplete print products. All new tests pass.
CI stays green.

---

## Phase 5C — 4Over End-to-End (Print)

> ⚠️ **Blocked on Phase 5B complete + 4Over credentials from Christian.**
> `auth_config = { "api_key": "...", "private_key": "..." }` (HMAC-SHA256 signing)

- [ ] **5C.1** — Seed 4Over credentials. Trigger a sync. Confirm HMAC signature accepted by
  4Over API and products land in catalog with `product_type="print"` + `PrintDetails` populated.
- [ ] **5C.2** — Confirm `FormulaResolver` computes price correctly for a known 4Over product
  (cross-check against 4Over's own quoted price for the same dimensions + qty).
- [ ] **5C.3** — Dry-run push a 4Over print product. Inspect the mutation plan — confirm
  `setProductSize` contains dimension rows, `setProductPrice` uses formula output, and
  `setAdditionalOption` contains paper/lamination options.
- [ ] **5C.4** — Live push to OPS staging. Verify product appears with correct dimensions,
  formula price, and print options visible in storefront.
- [ ] **5C.5** — Verify decoration options appear correctly if the product has embroidery/
  imprint options (requires Phase 5B.3 complete).

**Exit criteria:** A 4Over print product is live in OPS staging with correct formula-based
pricing and print option selections. A customer can select paper weight and dimensions and
see a price change.

---

## Phase 5 — Cross-Supplier Regression

> Runs after 5A + 5B + 5C are all complete.

**Why this matters:** The adapter pattern guarantees all suppliers use the same push pipeline.
But "same pipeline" only holds if every adapter correctly produces a valid `PSProductData` model.
Each supplier has different field names, different image structures, different pricing schemas.

> ⚠️ **CREDENTIAL BLOCKER — All of Phase 5 is blocked until credentials are seeded.**
> Every test in the codebase for S&S, Alphabroder, and 4Over is fully mocked — the HTTP
> clients are patched out in `test_rest_adapters.py` (confirmed: "All tests are hermetic —
> the HTTP client is mocked, no network/DB"). No live API call has ever been made to any of
> these three suppliers. Tasks 5A.1–5E.2 cannot run until real credentials are added to the
> suppliers table by Christian.

**Suppliers to verify:**

### 5A — S&S Activewear (REST)
- [ ] **5A.1** — Trigger a sync for S&S. Confirm products land in catalog with variants + images.
  _(Blocked: requires live S&S credentials in DB)_
- [ ] **5A.2** — Check S&S pricing: REST API returns `price` differently than SanMar SOAP tiers.
  Confirm `TieredVariantResolver` handles S&S price format.
- [ ] **5A.3** — Push one S&S product to OPS staging. Verify images, SKU, stock all correct.
- [ ] **5A.4** — Confirm S&S credentials in `auth_config` are: `account_number` + `api_key`
  (HTTP Basic Auth — **not OAuth**). Verified in `ss_adapter.py` lines 97–107: credentials are
  passed as `httpx` Basic auth tuple `(account_number, api_key)`. No OAuth token exchange.

### 5B — Alphabroder (PromoStandards SOAP)
- [ ] **5B.1** — Alphabroder reuses `PromoStandardsAdapter` (zero new code). Trigger a sync.
  Confirm products ingest correctly. _(Blocked: requires live Alphabroder credentials in DB)_
- [ ] **5B.2** — Alphabroder WSDL handling: WSDLs **are hardcoded** as constants in
  `alphabroder_adapter.py` (`ALPHABRODER_WSDLS` dict, lines 15–19). The `_wsdl_for()` method
  tries the DB `endpoint_cache` first, but falls back to hardcoded URLs regardless. This is
  intentional — Alphabroder's endpoints are stable. No action needed, but do not assume
  the DB row is the only source of truth.
- [ ] **5B.3** — Push one Alphabroder product to OPS. Verify full payload is correct.
- [ ] **5B.4** — Confirm Alphabroder `auth_config` requires: SOAP `id` + `password` only.

### 5C — 4Over (REST + HMAC)
- [ ] **5C.1** — 4Over uses HMAC request signing. Trigger a sync. Confirm HMAC signature is
  computed correctly and 4Over API accepts the request.
  _(Blocked: requires live 4Over api_key + private_key in DB)_
- [ ] **5C.2** — 4Over sells print products (not apparel). Confirm `FormulaResolver` is used
  instead of `TieredVariantResolver` for print product pricing.
- [ ] **5C.3** — Push one 4Over print product to OPS. Verify formula-based pricing appears
  correctly in OPS storefront.
- [ ] **5C.4** — ⚠️ **OPEN GAP — Build decoration mapping (not yet implemented).**
  Decoration data (embroidery, screen print, setup fees) is **not mapped** to
  `setAdditionalOption` anywhere in `fourover_normalizer.py` or `fourover_adapter.py`
  (verified: grep returns no results for `decoration`, `embroidery`, `setAdditionalOption`
  in either file). This is a feature gap, not a done task. Must be built before 4Over
  products with decoration options can be fully pushed to OPS.
- [ ] **5C.5** — Confirm 4Over `auth_config` requires: `api_key` + `private_key` (HMAC signing).

### 5D — Future / Generic PromoStandards Supplier
- [ ] **5D.1** — Pick any PromoStandards-compatible supplier from the PS directory
  (`GET /api/ps-directory`). Add them to the DB using only their WSDL endpoint.
- [ ] **5D.2** — Trigger a sync. Confirm products ingest via the generic SOAP adapter.
- [ ] **5D.3** — Push one product to OPS. Confirm no code was written — only a DB row added.

### 5E — Cross-Supplier Regression
- [ ] **5E.1** — Push one product from each of the 4 suppliers to the **same** OPS storefront.
  Confirm they coexist correctly (no SKU collisions, no overwritten push_mappings).
- [ ] **5E.2** — Run a delta sync for all 4 suppliers simultaneously. Confirm no DB deadlocks or
  race conditions under concurrent sync jobs.

**Exit criteria:** All 4 supplier adapters produce valid OPS listings. A new
PromoStandards-compatible supplier can be onboarded with only a DB row. No supplier-specific code
paths exist outside of the adapters themselves.

---

## Phase 6 — Security Audit

**Why now:** The codebase has already gone through one security remediation pass (PR #160,
merged). Phase 6 is a full re-audit to confirm nothing was missed and no new surface was
introduced during V2 development.

**Audit areas:**

### 6A — Authentication & Authorization
- [ ] **6A.1** — Verify every route in every module has an explicit auth dependency
  (`Depends(get_current_user)` or `Depends(_require_vg_admin)` or `Depends(get_orchestrator_key)`).
  No route should be accidentally public.
- [ ] **6A.2** — Verify `customer_admin` users cannot access other customers' data. Test:
  log in as customer A's admin, attempt to call `GET /api/customers/{customer_B_id}`. Must return 403.
- [ ] **6A.3** — Verify orchestrator keys are scoped. A key with `allowed_customer_ids=["uuid-A"]`
  cannot push to customer B's storefront.
- [ ] **6A.4** — JWT expiry: confirm tokens expire and are not accepted after expiry.
- [ ] **6A.5** — Confirm `SECRET_KEY` and `JWT_SECRET_KEY` are required (not defaulted) when
  `ENVIRONMENT=production`. App should refuse to start without them.

### 6B — Input Validation & Injection
- [ ] **6B.1** — All request bodies use Pydantic v2 models with strict types. No raw `dict`
  inputs that bypass validation.
- [ ] **6B.2** — No raw SQL string interpolation anywhere in SQLAlchemy queries. Only parameterised
  queries via ORM or `text()` with bound params.
- [ ] **6B.3** — Supplier-provided data (product names, descriptions, image URLs) is never
  executed as code or injected into SQL.

### 6C — SSRF & Image Security
- [ ] **6C.1** — `assert_safe_url()` in `mirror.py` blocks private IP ranges (10.x, 172.16.x,
  192.168.x, 127.x, 169.254.x). Test with a `file://` and `http://127.0.0.1` URL — both must be rejected.
- [ ] **6C.2** — Image download size cap (`IMAGE_MAX_DOWNLOAD_BYTES`) is enforced. Test with a
  response that streams more than 20 MB — download must be aborted.
- [ ] **6C.3** — CDN URLs in OPS push payloads are always our own `CDN_BASE_URL`, never raw
  supplier URLs. Supplier URLs never reach OPS directly.

### 6D — Secrets & Credentials
- [ ] **6D.1** — `EncryptedJSON` column is used for all credential fields. Verify in DB:
  `SELECT auth_config FROM suppliers LIMIT 1` — should return ciphertext, not plaintext JSON.
- [ ] **6D.2** — No credentials, API keys, or secrets appear in:
  - Log output (Sentry events, `structlog` records)
  - Error messages returned to API clients
  - `step_results` JSONB in `push_log`
- [ ] **6D.3** — `sanitize_error()` function is called before all user-facing error strings.
  Audit every `raise HTTPException` call in integrations, ops_push, and ops_client modules.
- [ ] **6D.4** — `.env` file is in `.gitignore`. No secrets committed to git history.
  Run: `git log --all --full-history -- .env` — must return nothing.

### 6E — Rate Limiting & Abuse
- [ ] **6E.1** — Integration Gateway rate limiter (Redis sliding window) is active in production.
  Test: send 100 rapid requests with the same API key — should get 429 after the per-minute limit.
- [ ] **6E.2** — Login endpoint has per-email rate limiting. Test: 10 failed logins for same email
  in 60s should be rate-limited.
- [ ] **6E.3** — Batch push endpoint (`/admin/batch-push-requests`) has a max fan-out cap.
  Confirm it cannot be used to enqueue 10,000 push jobs in one request.

### 6F — CORS & Transport
- [ ] **6F.1** — `ALLOWED_ORIGINS` in production is an explicit list, not `*`. Verify in `.env`
  for the production deployment.
- [ ] **6F.2** — All cookies use `HttpOnly=True`, `Secure=True`, `SameSite=Lax` in production.
- [ ] **6F.3** — `FORWARDED_ALLOW_IPS` is set to the VPC CIDR (not `"*"`) in production ECS config.

**Exit criteria:** All checklist items pass. Any failure is a bug filed and fixed before marking
Phase 6 done. A written security sign-off note is added to this plan doc.

---

## Milestone Summary

```
Week 1   [Phase 1] Images → S3/R2 configured, SanMar products push with images ✓
         [Phase 2] SKU dedup verified, no duplicate OPS products ✓

Week 2   [Phase 3] Stock live, delta sync updates inventory in OPS ✓
         [Phase 4] SanMar E2E sign-off — new customer onboarded with zero code ✓

Week 3   [Phase 5A] S&S + Alphabroder (apparel) verified — blocked on creds only ✓
         [Phase 5B] BUILD print push path — payload_builder branch + preflight checks
                    + 4Over decoration mapping (pure code, no creds needed, parallel to 5A) ✓

Week 4   [Phase 5C] 4Over (print) verified end-to-end — blocked on Phase 5B + creds ✓
         [Phase 5D–5E] Generic PS supplier + cross-supplier regression ✓

Week 5   [Phase 6] Full security audit — all 6 areas green ✓
```

> **Key insight:** Phase 5A (apparel) and Phase 5B (print push code) can run **in parallel**
> during Week 3. 5A needs credentials but no code. 5B needs code but no credentials.
> 4Over (5C) is the last to run because it needs both.

---

## Blockers & Dependencies

| Blocker | Needed For | Owner | Type |
|---------|-----------|-------|------|
| Cloudflare R2 bucket credentials | Phase 1 | Vidhi / DevOps | Config |
| CDN domain (`images.graphxcpi.com`) pointing to R2 | Phase 1 | Vidhi / DevOps | Config |
| SanMar API credentials (`username` + `password`) | Phase 1–4 | Christian | Credentials |
| OPS staging OAuth2 credentials | Phase 1–5C | Christian | Credentials |
| S&S credentials: `account_number` + `api_key` (HTTP Basic) | Phase 5A | Christian | Credentials |
| Alphabroder credentials: `id` + `password` (SOAP) | Phase 5A | Christian | Credentials |
| 4Over credentials: `api_key` + `private_key` (HMAC) | Phase 5C | Christian | Credentials |
| **Build print push path** in `payload_builder.py` | Phase 5B | Dev team | **Code** |
| **Add product-type preflight checks** in `preflight.py` | Phase 5B | Dev team | **Code** |
| **Build 4Over decoration mapping** in `fourover_normalizer.py` | Phase 5B | Dev team | **Code** |
| OPS staging storefront with OAuth2 creds | Phase 1–5 | Christian |
| Confirm R2 bucket shared with graphxcpi.com image upload | Phase 1 | Christian + Vidhi |

---

## Definition of Done

The plan is complete when:
1. SanMar → OPS is live with images, correct SKUs, and stock — new customer onboarded with **zero code changes**
2. S&S and Alphabroder (apparel) produce live OPS listings through the existing apparel push path
3. `payload_builder.py` has a working print branch — 4Over print products push with formula pricing and dimension options
4. `preflight.py` validates `product_type` — print products without `PrintDetails` are blocked before push
5. 4Over (print) produces a live OPS listing with correct formula price and print option selections
6. A generic PromoStandards supplier can be added via DB row alone
7. Every item in the Phase 6 security checklist passes
8. This document is fully checked off and committed to `plans/`
