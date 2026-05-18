# Phases 0–13 Dependency Table

> `✅` hard dep | `⚠️` soft dep | `🔑` external gate | `—` none

---

## Phase Dependency Table (All Phases)

| Phase | Name | Status | Depends On | External Gates | Parallel-Safe With |
|-------|------|--------|------------|----------------|--------------------|
| **P0** | Hygiene | 🟡 Partial | — | User OK for DB purge 🔑 | P1, P4, P5 |
| **P1** | Polymorphic Model | ✅ Complete | — | — | P0 |
| **P2** | OPS Adapter | 🟡 Partial (DELTA missing) | P1 ✅ | OPS auth token 🔑 | P0, P4 |
| **P3** | SanMar PS Adapter | ⏸ Blocked | P1 ✅, P2 ⚠️ | SanMar creds 🔑 | P4, P5 |
| **P4** | Pricing API | 🟢 Ready | P1 ✅ | — | P0, P2, P3, P5 partial |
| **P5** | Frontend PDP | 🟢 Ready (after P4) | P1 ✅, P4 ✅ | — | P0, P3, P6 |
| **P6** | Customer Catalog | ✅ Complete | P1 ✅ | — | P5, P9 |
| **P7** | Decoration Overlay | ✅ Complete | P1 ✅, P3 ✅, P6 ✅ | — | P9 |
| **P8** | Push Pipeline Polish | ✅ Complete | P6 ✅, P7 ✅ | OPS error codes 🔑 | — |
| **P9** | Sync Orchestration | ⬜ Not started | P2 ✅ (+ DELTA gap) | n8n cron design 🔑 | P7 |
| **P10** | More Suppliers | ⬜ Not started | P3 ✅ | S&S / Alpha / 4Over creds 🔑 | P11 |
| **P11** | Image Pipeline | ⬜ Not started | P1 ✅, P3 ✅ | S3 + CDN + SanMar FTP 🔑 | P10 |
| **P12** | Multi-Tenant SaaS | ✅ Complete | P6 ✅ | — | — |
| **P13** | Production Hardening | 🟡 Partial | All above ✅ | AWS account, pen-test vendor 🔑 | — |

---

## Critical Path

```
P1 → P4 → P5
P1 → P6 → P7 → P8 → P12 → P13
P1 → P2(DELTA fix) → P9 → P10 → P11
P3 unblocks: P7, P10, P11
```

---

## Phase 0–5 Status Snapshot

| Phase | Name | Status | Remaining |
|-------|------|--------|-----------|
| **P0** | Hygiene | 🟡 PARTIAL | Tasks 5–11 pending (tailwind.js delete, image domains, log util, hardcoded paths, CR doc, DB purge) |
| **P1** | Polymorphic Product Model | ✅ COMPLETE | Run backfill on dev DB; clean up scratch files |
| **P2** | OPS Inbound Adapter | 🟡 PARTIAL | DELTA ingest (`discover_changed`) not implemented — rolls into P9 |
| **P3** | SanMar PS Adapter | ⏸ BLOCKED | Needs plan revision (P2 shipped BaseAdapter); creds-blocked |
| **P4** | Pricing API | 🟢 UNBLOCKED | Ready to execute |
| **P5** | Frontend PDP | 🟢 UNBLOCKED | Depends on P4 pricing endpoint; parallel-safe with P6 |

---

## Phase 0–5 Dependency Matrix

| Phase | Depends On | Parallel-Safe With | External Gates |
|-------|-----------|-------------------|----------------|
| **P0** Hygiene | — (independent patches) | P1, P4, P5 (no file overlap) | — |
| **P1** Polymorphic Model | — (foundation) | P0 | — |
| **P2** OPS Adapter | P1 ✅ | P0, P4 | OPS GraphQL schema 🔑, OPS auth token 🔑 |
| **P3** SanMar Adapter | P1 ✅, P2 ⚠️ (registry) | P4, P5 | SanMar API credentials 🔑 (Christian) |
| **P4** Pricing API | P1 ✅ | P0, P2, P3, P5 partial | — |
| **P5** Frontend PDP | P1 ✅, P4 ✅ | P0, P3, P6 (no file overlap) | — |

**Critical path (P0–P5):** `P1 → P2 → P9(DELTA)` and `P1 → P4 → P5`

---

## Phase 0 — Hygiene (🟡 PARTIAL)

> Tasks 1–4 complete. Tasks 5–11 pending. Each task is **independent** — no intra-phase dependencies.

| Task ID | Layer | Description | Status | Depends On | Blocks |
|---------|-------|-------------|--------|------------|--------|
| P0-BE-1 | Backend | Extend test cleanup to purge leaked `Test Customer*` rows | ✅ Done | — | — |
| P0-BE-2 | Backend | Wire `TEST_DATABASE_URL` override in conftest | ✅ Done | P0-BE-1 | — |
| P0-BE-3 | Backend | Normalize `push_log` router prefix (`APIRouter(prefix=...)`) | ✅ Done | — | — |
| P0-BE-4 | Backend | Hoist `from sqlalchemy import` out of `seed_demo.py` loop | ✅ Done | — | — |
| P0-FE-1 | Frontend | Delete dead `frontend/tailwind.config.js` | ⬜ Pending | — | — |
| P0-FE-2 | Frontend | Add `images.remotePatterns` for SanMar / OPS / 4Over / S&S CDNs | ⬜ Pending | — | P5 (images break without this) |
| P0-FE-3 | Frontend | Create `lib/log.ts` + replace 17 `console.error/warn` calls | ⬜ Pending | — | — |
| P0-DOC-1 | Docs | Fix hardcoded `/Users/PD/API-HUB` paths in 4 task-fill docs | ⬜ Pending | — | — |
| P0-DOC-2 | Docs | Update `code_review_all_tasks.md` with resolution status | ⬜ Pending | — | — |
| P0-BE-5 | Backend | Purge 12 stale `Test Customer` rows from dev DB (requires user OK) | ⬜ Pending | User approval 🔑 | — |
| P0-BE-6 | Backend | Full stack smoke: pytest + frontend build + curl health checks | ⬜ Pending | P0-BE-1..5, P0-FE-1..3 | — |

> **Note:** P0-FE-2 (`images.remotePatterns`) should be done before Phase 5 PDP ships — SanMar images will be broken in prod-mode without it.

---

## Phase 1 — Polymorphic Product Model (✅ COMPLETE)

> All 16 tasks shipped in commit `93de4b5`. Listed for cross-phase dependency tracing only.

| Task ID | Layer | Description | Status | Depends On | Blocks |
|---------|-------|-------------|--------|------------|--------|
| P1-BE-1 | Backend | `ApprelDetails`, `PrintDetails` ORM models | ✅ | — | P1-BE-7, P1-BE-8, P1-BE-9 |
| P1-BE-2 | Backend | `VariantPrice`, `ProductSize` ORM models | ✅ | — | P1-BE-8, P1-BE-9 |
| P1-BE-3 | Backend | `Supplier` columns: `adapter_class`, `last_full_sync`, `last_delta_sync` | ✅ | — | P2, P3, P9, P10 |
| P1-BE-4 | Backend | `SyncJob.errors JSONB` column | ✅ | — | P2, P9 |
| P1-BE-5 | Backend | `PrintDetailsIngest`, `ApparelDetailsIngest`, `ProductSizeIngest`, `PriceTierIngest` schemas | ✅ | — | P1-BE-6 |
| P1-BE-6 | Backend | Extend `ProductIngest` with polymorphic fields + `model_validator` | ✅ | P1-BE-5 | P1-BE-7 |
| P1-BE-7 | Backend | `persist_product` service skeleton — product spine upsert | ✅ | P1-BE-1, P1-BE-6 | P1-BE-8, P1-BE-9, P2, P3, P4 |
| P1-BE-8 | Backend | `persist_product` — print path (print_details + sizes + options) | ✅ | P1-BE-7, P1-BE-1 | P2, P4 |
| P1-BE-9 | Backend | `persist_product` — apparel path (apparel_details + variants + variant_prices + images) | ✅ | P1-BE-7, P1-BE-2 | P3, P4 |
| P1-BE-10 | Backend | OPS decal fixture + fixture-driven persist test | ✅ | P1-BE-8 | P2 |
| P1-BE-11 | Backend | Refactor `ingest_products` to call `persist_product` | ✅ | P1-BE-7 | P2 |
| P1-BE-12 | Backend | `ProductRead` schema with polymorphic detail fields | ✅ | P1-BE-5 | P5 |
| P1-BE-13 | Backend | Product query routes: eager-load new relationships | ✅ | P1-BE-12 | P5 |
| P1-BE-14 | Backend | Wire all new models in `main.py` + full test suite | ✅ | All above | P2, P3 |
| P1-BE-15 | Backend | Backfill script for existing VG OPS print products | ✅ | P1-BE-7 | — |
| P1-BE-16 | Backend | Final integration test — HTTP round-trip for both product types | ✅ | P1-BE-11 | — |

---

## Phase 2 — OPS Inbound Adapter (🟡 PARTIAL)

> Tasks 1–11, 13–15 shipped in commit `b391baa`. **DELTA ingest (Task 12 equivalent) missing** — rolls into P9.

| Task ID | Layer | Description | Status | Depends On | Blocks |
|---------|-------|-------------|--------|------------|--------|
| P2-BE-1 | Backend | `BaseAdapter` ABC + `ProductRef` + error types | ✅ | P1 ✅ | P2-BE-2, P3 |
| P2-BE-2 | Backend | Adapter registry (`register_adapter`, `get_adapter`) | ✅ | P2-BE-1 | P2-BE-3, P2-BE-7 |
| P2-BE-3 | Backend | `OPSClient` — thin httpx wrapper for OPS GraphQL | ✅ | P2-BE-1 | P2-BE-4 |
| P2-BE-4 | Backend | `OPSAdapter.discover()` — explicit_list / first_n / full modes | ✅ | P2-BE-3 | P2-BE-5 |
| P2-BE-5 | Backend | `OPSAdapter.hydrate_product()` — GraphQL fetch + normalize | ✅ | P2-BE-4 | P2-BE-7 |
| P2-BE-6 | Backend | `OPSAdapter.discover_changed()` — DELTA mode | 🟡 Ships `NotImplementedError` | P2-BE-4 | **P9-BE-1** |
| P2-BE-7 | Backend | `run_import` orchestrator — auth-fatal + per-product error handling | ✅ | P2-BE-2, P2-BE-5 | P2-BE-8, P2-BE-9 |
| P2-BE-8 | Backend | Per-product error path + `partial_success` status | ✅ | P2-BE-7 | — |
| P2-BE-9 | Backend | `ImportRequest` / `ImportResponse` Pydantic schemas | ✅ | — | P2-BE-10 |
| P2-BE-10 | Backend | `POST /api/suppliers/{id}/import` endpoint + BackgroundTasks | ✅ | P2-BE-9, P2-BE-7 | P2-BE-11 |
| P2-BE-11 | Backend | Return real `sync_job_id` to caller (split create/execute) | ✅ | P2-BE-10 | — |
| P2-BE-12 | Backend | Concurrency guard — 409 on duplicate in-flight job | ✅ | P2-BE-10 | — |
| P2-BE-13 | Backend | E2E test — full OPS Decals import via mocked GraphQL | ✅ | P2-BE-11 | — |
| P2-BE-14 | Backend | Stamp `last_full_sync` / `last_delta_sync` on success | ✅ | P2-BE-7 | P9 |
| P2-BE-15 | Backend | OPS inbound adapter runbook | ✅ | — | — |

> **Open follow-up:** Verify OPS adapter handles OAuth2 token refresh (currently reads static `auth_config.auth_token`).

---

## Phase 3 — SanMar PS Adapter (⏸ BLOCKED)

> Plan needs revision (remove duplicate BaseAdapter/registry tasks — P2 already shipped those). Creds-blocked.

| Task ID | Layer | Description | Status | Depends On | Blocks |
|---------|-------|-------------|--------|------------|--------|
| P3-BE-1 | Backend | `SanMarSOAPClient` — zeep wrapper for PS SOAP services | ⬜ Pending | P2-BE-1 ✅, SanMar creds 🔑 | P3-BE-2 |
| P3-BE-2 | Backend | `PromoStandardsAdapter` base — discover / hydrate / discover_changed | ⬜ Pending | P3-BE-1 | P3-BE-3 |
| P3-BE-3 | Backend | `SanMarAdapter` subclass — WSDL resolution, auth shape, live_inventory | ⬜ Pending | P3-BE-2 | P3-BE-4 |
| P3-BE-4 | Backend | `ps_normalizer_v2.py` — PS XML → `ProductIngest` (apparel path) | ⬜ Pending | P3-BE-3, P1-BE-9 ✅ | P3-BE-5, P7, P10 |
| P3-BE-5 | Backend | Fixture-driven tests (PC61, MM1000, pricing, media, auth failure) | ⬜ Pending | P3-BE-4 | — |
| P3-BE-6 | Backend | Register `SanMarAdapter` in adapter registry; DB row for SanMar supplier | ⬜ Pending | P3-BE-3 | P9, P10 |
| P3-BE-7 | Backend | `Supplier.protocol_config JSONB` column (discovery_mode, max_products, FTP flag) | ⬜ Pending | — | P9 |
| P3-BE-8 | Backend | `SyncJob.discovery_mode VARCHAR(32)` column | ⬜ Pending | — | P9 |

> **Gate:** SanMar API credentials from Christian 🔑 required before any live test (fixtures can proceed without creds).

---

## Phase 4 — Pricing API (🟢 UNBLOCKED)

| Task ID | Layer | Description | Status | Depends On | Blocks |
|---------|-------|-------------|--------|------------|--------|
| P4-BE-1 | Backend | Pricing module scaffold + `QuoteRequest` / `QuoteResult` / error schemas | ⬜ Pending | P1 ✅ | P4-BE-2 |
| P4-BE-2 | Backend | `resolve_quote` dispatch by `product.pricing_method` | ⬜ Pending | P4-BE-1 | P4-BE-3, P4-BE-4 |
| P4-BE-3 | Backend | `TieredVariantResolver` — apparel tiered lookup + base_price fallback | ⬜ Pending | P4-BE-2, P1-BE-9 ✅ | P4-BE-5 |
| P4-BE-4 | Backend | `FormulaResolver` — print: base × area × multipliers + setup_cost + qty break | ⬜ Pending | P4-BE-2, P1-BE-8 ✅ | P4-BE-5 |
| P4-BE-5 | Backend | `POST /api/pricing/quote` route | ⬜ Pending | P4-BE-3, P4-BE-4 | P4-BE-6, P5 |
| P4-BE-6 | Backend | `customer_quote.py` — markup + storefront override wrapper | ⬜ Pending | P4-BE-5, markup module ✅ | P4-BE-7 |
| P4-BE-7 | Backend | `POST /api/customers/{id}/pricing/quote` route | ⬜ Pending | P4-BE-6 | P5 |
| P4-BE-8 | Backend | Storefront override E2E test (`fixed_unit_price`) | ⬜ Pending | P4-BE-6 | — |
| P4-BE-9 | Backend | Decimal precision regression suite | ⬜ Pending | P4-BE-3 | — |
| P4-BE-10 | Backend | Full pricing suite + regression sweep + OpenAPI smoke | ⬜ Pending | All above | — |

> **Note:** P4-BE-3 open question — verify `persist_product` apparel path writes `variant_prices` rows from `ProductIngest.price_tiers` before starting P4-BE-3 (Phase 1 should have done this, but confirm).

---

## Phase 5 — Frontend PDP (🟢 UNBLOCKED after P4)

| Task ID | Layer | Description | Status | Depends On | Blocks |
|---------|-------|-------------|--------|------------|--------|
| P5-FE-1 | Frontend | Add Vitest + Playwright dev deps + base config | ⬜ Pending | — | P5-FE-2..14 |
| P5-FE-2 | Frontend | Extend `lib/types.ts` with polymorphic types (`apparel_details`, `print_details`, `variant_prices`, `product_sizes`, `PriceQuote`) | ⬜ Pending | P1-BE-12 ✅ | P5-FE-4..9 |
| P5-FE-3 | Frontend | `<ProductDetailPanel>` — type dispatcher (apparel vs print) | ⬜ Pending | P5-FE-2 | P5-FE-4, P5-FE-5 |
| P5-FE-4 | Frontend | `<ApparelDetailPanel>` — apparel body wrapper (variant picker + price block) | ⬜ Pending | P5-FE-3, P5-FE-2 | — |
| P5-FE-5 | Frontend | `<PrintDetailPanel>` — print body wrapper (dimension + options + live quote) | ⬜ Pending | P5-FE-3, P5-FE-6, P5-FE-7, P5-FE-8 | — |
| P5-FE-6 | Frontend | `<DimensionInput>` — width × height input bounded by `print_details` | ⬜ Pending | P5-FE-2 | P5-FE-5 |
| P5-FE-7 | Frontend | `<OptionGroupedForm>` — print options grouped by section | ⬜ Pending | P5-FE-2 | P5-FE-5 |
| P5-FE-8 | Frontend | `useDebouncedQuote` hook — calls `/api/pricing/quote` with 250ms debounce | ⬜ Pending | P4-BE-5 ✅ | P5-FE-9 |
| P5-FE-9 | Frontend | `<LivePriceQuote>` — debounced quote display with breakdown | ⬜ Pending | P5-FE-8 | P5-FE-5 |
| P5-FE-10 | Frontend | `<PriceTierTable>` — apparel `variant_prices` summary table | ⬜ Pending | P5-FE-2 | P5-FE-4 |
| P5-FE-11 | Frontend | `<ProductTypeFilter>` — catalog list filter pill (apparel/print) | ⬜ Pending | P5-FE-2 | — |
| P5-FE-12 | Frontend | Wire `<ProductDetailPanel>` into existing PDP route | ⬜ Pending | P5-FE-3..10 | — |
| P5-FE-13 | Frontend | Vitest unit tests for all new components | ⬜ Pending | P5-FE-1, P5-FE-3..11 | — |
| P5-FE-14 | Frontend | Playwright E2E: apparel PDP, print PDP, catalog filter | ⬜ Pending | P5-FE-12 | — |

> **Note:** P0-FE-2 (`images.remotePatterns`) must be done before P5 ships — SanMar images will be broken in prod-mode without CDN allow-listing.

---

## Complete Phase Dependency Matrix (P0–P13)

|  | P0 | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 | P10 | P11 | P12 | P13 |
|--|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:---:|:---:|:---:|:---:|
| **P1 needs** | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| **P2 needs** | — | ✅ | — | — | — | — | — | — | — | — | — | — | — | — |
| **P3 needs** | — | ✅ | ⚠️ | — | — | — | — | — | — | — | — | — | — | — |
| **P4 needs** | — | ✅ | — | — | — | — | — | — | — | — | — | — | — | — |
| **P5 needs** | ⚠️ | ✅ | — | — | ✅ | — | — | — | — | — | — | — | — | — |
| **P6 needs** | — | ✅ | — | — | — | — | — | — | — | — | — | — | — | — |
| **P7 needs** | — | ✅ | — | ✅ | — | — | ✅ | — | — | — | — | — | — | — |
| **P8 needs** | — | — | — | — | — | — | ✅ | ✅ | — | — | — | — | — | — |
| **P9 needs** | — | — | ✅ | ⚠️ | — | — | — | — | — | — | — | — | — | — |
| **P10 needs** | — | — | — | ✅ | — | — | — | — | — | — | — | — | — | — |
| **P11 needs** | — | ✅ | — | ✅ | — | — | — | — | — | — | — | — | — | — |
| **P12 needs** | — | — | — | — | — | — | ✅ | — | — | — | — | — | — | — |
| **P13 needs** | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |

**Two parallel critical paths:**
- **Data path:** `P1 → P2 → P9 → P10 → P11`
- **Product path:** `P1 → P4 → P5` and `P1 → P6 → P7 → P8 → P12 → P13`

---

## All External Gates (P0–P13)

| Gate | Needed For | Owner | Status |
|------|-----------|-------|--------|
| User OK to purge 12 Test Customer rows | P0-BE-5 | User 🔑 | Pending |
| OPS GraphQL schema + auth token | P2-BE-3 | Christian 🔑 | Need to verify |
| SanMar API credentials | P3-BE-1 | Christian 🔑 | Pending |
| Free-form vs templated decorations decision | All P7 | Christian 🔑 | Pending |
| OPS GraphQL error codes for "already exists" | P8-BE-5 | Christian / OPS Postman 🔑 | Pending |
| n8n cron workflow design (one template per type) | P9-N8N-1 | Team | Pending |
| S&S Activewear credentials | P10-BE-1 | Christian 🔑 | Pending |
| Alphabroder credentials | P10-BE-2 | Christian 🔑 | Pending |
| 4Over credentials | P10-BE-3 | Christian 🔑 | Pending |
| Image cost model approved | P11-BE-2 | Team | Pending |
| SanMar FTP access | P11-BE-1 | Christian 🔑 | Pending |
| S3 bucket + CDN provisioned | P11-BE-2, P11-BE-3 | Infra 🔑 | Pending |
| Auth provider chosen | P12-BE-1 | Team | Pending |
| Billing vendor chosen | P12-BE-6 | Christian 🔑 | Pending |
| Prod DB snapshot | P13-BE-2 | DevOps 🔑 | Pending |
| AWS account provisioned | P13-BE-1 | Infra 🔑 | Pending |
| Pen-test vendor engaged | P13-BE-7 | Christian 🔑 | Pending |
| Stale detection rule locked (P6 spec) | P6-BE-2 | Team | Pending |

---

## Cross-Phase Task Dependency Chains (P0–P13)

Critical chains where one task blocks another across phase boundaries:

```
P1-BE-3 (Supplier.adapter_class column)
  └─→ P2-BE-2 (adapter registry)
        └─→ P3-BE-6 (SanMarAdapter registration)
              └─→ P9-N8N-1 (cron workflows)

P2-BE-6 (discover_changed — currently NotImplementedError)
  └─→ P9-BE-1 (complete DELTA ingest)
        └─→ P9-BE-2 (import endpoint delta mode)
              └─→ P9-N8N-1 → P9-N8N-2 → P9-N8N-3 (cron scheduling)

P1-BE-7 (persist_product)
  └─→ P4-BE-3 (TieredVariantResolver)
  └─→ P4-BE-4 (FormulaResolver)
        └─→ P4-BE-5 (pricing quote endpoint)
              └─→ P5-FE-8 (useDebouncedQuote hook)
                    └─→ P5-FE-9 (LivePriceQuote component)

P6-BE-1 (customer_product_selections table)
  └─→ P6-BE-2 (state machine)
        └─→ P8-BE-6 (update status → pushed)
              └─→ P8-FE-1 (push history view)

P7-BE-4 (upsert decorations)
  └─→ P8-BE-2 (decoration merge at push time)

P12-BE-4 (scoped query guards)
  └─→ P12-BE-8 (scoping audit — required for P13)
        └─→ P13-BE-7 (pen test gate)

P13-BE-2 (Alembic — prod DB snapshot FIRST)
  └─→ P13-BE-1 (AWS deployment)
        └─→ P13-BE-5, P13-BE-6, P13-BE-8
```

---

## Total Task Count (All Phases)

| Phase | Backend | Frontend | n8n | Docs | Total | Status |
|-------|:-------:|:--------:|:---:|:----:|:-----:|--------|
| P0 | 6 | 3 | 0 | 2 | **11** | 🟡 4 done, 7 pending |
| P1 | 16 | 0 | 0 | 0 | **16** | ✅ All done |
| P2 | 15 | 0 | 0 | 0 | **15** | 🟡 14 done, 1 missing (DELTA) |
| P3 | 8 | 0 | 0 | 0 | **8** | ⏸ 0 done |
| P4 | 10 | 0 | 0 | 0 | **10** | 🟢 0 done (ready) |
| P5 | 0 | 14 | 0 | 0 | **14** | 🟢 0 done (blocked on P4) |
| P6 | 5 | 5 | 0 | 0 | **10** | 🟢 0 done |
| P7 | 6 | 3 | 0 | 0 | **9** | ⬜ 0 done |
| P8 | 6 | 3 | 0 | 0 | **9** | ⬜ 0 done |
| P9 | 5 | 2 | 3 | 0 | **10** | ⬜ 0 done |
| P10 | 6 | 0 | 0 | 0 | **6** | ⬜ 0 done |
| P11 | 7 | 2 | 0 | 0 | **9** | ⬜ 0 done |
| P12 | 8 | 5 | 0 | 0 | **13** | ⬜ 0 done |
| P13 | 8 | 3 | 0 | 0 | **11** | ⬜ 0 done |
| **TOTAL** | **106** | **40** | **3** | **2** | **151** | 35 done, 116 remaining |

---

## Phase 6–13 Dependency Table

## Phase Dependency Matrix

Which phases must be complete before another can begin.

|  | P6 | P7 | P8 | P9 | P10 | P11 | P12 | P13 |
|--|:--:|:--:|:--:|:--:|:---:|:---:|:---:|:---:|
| **P6 needed by** | — | ✅ | ✅ | — | — | — | ✅ | ✅ |
| **P7 needed by** | — | — | ✅ | — | — | — | — | ✅ |
| **P8 needed by** | — | — | — | — | — | — | — | ✅ |
| **P9 needed by** | — | — | — | — | — | — | — | ✅ |
| **P10 needed by** | — | — | — | — | — | — | — | ✅ |
| **P11 needed by** | — | — | — | — | — | — | — | ✅ |
| **P12 needed by** | — | — | — | — | — | — | — | ✅ |

**Critical path:** `P6 → P7 → P8 → P12 → P13`

**Parallel windows:**
- P6 complete → start **P7 + P9** simultaneously
- P9 complete → start **P10** (per supplier, independently)
- P10 starts → **P11** can run alongside it

---

## Task-Level Dependency Table

### Phase 6 — Customer-curated catalog views

| Task ID | Layer | Description | Depends On | Blocks |
|---------|-------|-------------|------------|--------|
| P6-BE-1 | Backend | Create `customer_product_selections` table | Phase 1 ✅ | P6-BE-2, P6-BE-3, P6-BE-4, P6-BE-5 |
| P6-BE-2 | Backend | State machine: `selected → pushed → stale` | P6-BE-1 | P6-FE-4, P8-BE-6 |
| P6-BE-3 | Backend | `GET /api/customers/{id}/catalog` | P6-BE-1 | P6-FE-2, P6-FE-3 |
| P6-BE-4 | Backend | `POST /api/customers/{id}/catalog/{product_id}` | P6-BE-1 | P6-FE-2 |
| P6-BE-5 | Backend | `DELETE /api/customers/{id}/catalog/{product_id}` | P6-BE-1 | P6-FE-3 |
| P6-FE-1 | Frontend | Customer dropdown in admin top nav | Existing customers API ✅ | P6-FE-2, P6-FE-3 |
| P6-FE-2 | Frontend | "Available Catalog" view with add-to-customer button | P6-BE-3, P6-BE-4, P6-FE-1 | — |
| P6-FE-3 | Frontend | "Customer Catalog" view (selected products only) | P6-BE-3, P6-BE-5, P6-FE-1 | — |
| P6-FE-4 | Frontend | Status badges: Available / Selected / Pushed / Stale | P6-BE-2 | P6-FE-2, P6-FE-3 |
| P6-FE-5 | Frontend | Verify supplier filter works on both catalog views | P6-FE-2, P6-FE-3 | — |

> **Gate:** Stale detection rule (`last_synced > pushed_at`) must be locked before P6-BE-2 starts.

---

### Phase 7 — Decoration overlay model

| Task ID | Layer | Description | Depends On | Blocks |
|---------|-------|-------------|------------|--------|
| P7-BE-1 | Backend | Create `customer_product_decorations` table | Phase 1 ✅, Phase 3 ✅, Phase 6 ✅ | P7-BE-3, P7-BE-4 |
| P7-BE-2 | Backend | Reuse Phase 1 `OptionIngest` schema for decoration shape | Phase 1 ✅ | P7-BE-4, P7-FE-2 |
| P7-BE-3 | Backend | `GET /api/customers/{id}/products/{product_id}/decorations` | P7-BE-1 | P7-FE-1 |
| P7-BE-4 | Backend | `PUT /api/customers/{id}/products/{product_id}/decorations` (upsert) | P7-BE-1, P7-BE-2 | P7-BE-5, P8-BE-2 |
| P7-BE-5 | Backend | Validation: SanMar products require decoration before push | P7-BE-4 | P8-BE-1 |
| P7-BE-6 | Backend | Integration with `master_options` module (if templated) | master_options ✅ 🔑 | P7-FE-2 |
| P7-FE-1 | Frontend | "Add Decoration" tab on SanMar product detail page | P7-BE-3 | P7-FE-2 |
| P7-FE-2 | Frontend | Decoration option editor UI | P7-BE-2, P7-BE-6, P7-FE-1 | — |
| P7-FE-3 | Frontend | "Needs Decoration" badge on product card | P7-BE-5 | — |

> **Gate:** Free-form vs templated decorations decision 🔑 must be resolved before ANY P7 task starts — it changes the schema.

---

### Phase 8 — Push pipeline polish

| Task ID | Layer | Description | Depends On | Blocks |
|---------|-------|-------------|------------|--------|
| P8-BE-1 | Backend | Push routing: branch on `has_decoration_overlay` supplier flag | P7-BE-5 | P8-BE-2, P8-FE-2 |
| P8-BE-2 | Backend | Decoration merge: base apparel + `customer_product_decorations` | P8-BE-1, P7-BE-4 | P8-BE-6 |
| P8-BE-3 | Backend | Configurable internal name prefix per (supplier, customer) | P6-BE-1 | — |
| P8-BE-4 | Backend | Verify `push_mappings` retry path is idempotent | Existing push_mappings ✅ | — |
| P8-BE-5 | Backend | Handle OPS "already exists" GraphQL errors gracefully | OPS error codes 🔑 | P8-BE-6 |
| P8-BE-6 | Backend | Update `customer_product_selections.status → pushed` post-push | P8-BE-2, P8-BE-5, P6-BE-2 | P8-FE-1 |
| P8-FE-1 | Frontend | Push history view per (customer, product) | P8-BE-6, push_log ✅ | — |
| P8-FE-2 | Frontend | "Push" button on Customer Catalog product cards | P8-BE-1, P6-FE-3 | P8-FE-3 |
| P8-FE-3 | Frontend | Push status feedback: spinner, success toast, error message | P8-FE-2 | — |

> **Gate:** OPS GraphQL error codes for "product already exists" 🔑 — get from Christian or OPS Postman collection before P8-BE-5.

---

### Phase 9 — Sync orchestration via n8n

| Task ID | Layer | Description | Depends On | Blocks |
|---------|-------|-------------|------------|--------|
| P9-BE-1 | Backend | Complete DELTA ingest (Phase 2 gap — `last_synced` delta queries) | Phase 2 ⚠️ | P9-BE-2, P9-BE-3, P9-N8N-1 |
| P9-BE-2 | Backend | Ensure `POST /api/suppliers/{id}/import?mode=` covers delta/full/closeouts | P9-BE-1 | P9-N8N-1 |
| P9-BE-3 | Backend | Write `last_full_sync` / `last_delta_sync` on successful import | P9-BE-1 | P9-FE-1 |
| P9-BE-4 | Backend | `GET /api/suppliers/{id}/sync-status` (last run, error count, throughput) | P9-BE-3 | P9-FE-1 |
| P9-BE-5 | Backend | Slack/email alert on consecutive failures (webhook or SMTP) | P9-BE-4 | P9-FE-2 |
| P9-N8N-1 | n8n | Canonical cron workflow template per sync_type | P9-BE-2 | P9-N8N-2 |
| P9-N8N-2 | n8n | Parameterize template by `supplier_id` from DB | P9-N8N-1 | P9-N8N-3 |
| P9-N8N-3 | n8n | Set schedules: catalog weekly / inventory hourly / pricing daily / closeouts monthly | P9-N8N-2 | — |
| P9-FE-1 | Frontend | Sync dashboard: last-success, error count, throughput per supplier | P9-BE-3, P9-BE-4 | — |
| P9-FE-2 | Frontend | Alert config UI (where to send failure notifications) | P9-BE-5 | — |

> **Gate:** n8n cron workflow design decision 🔑 — one template parameterized by supplier_id (not one workflow per supplier) must be enforced from P9-N8N-1.

---

### Phase 10 — More suppliers

| Task ID | Layer | Description | Depends On | Blocks |
|---------|-------|-------------|------------|--------|
| P10-BE-1 | Backend | `SSAdapter` — PromoStandards REST (subclass of Phase 3 adapter) | Phase 3 ✅, S&S creds 🔑 | P10-BE-4, P10-BE-5 |
| P10-BE-2 | Backend | `AlphabroderAdapter` — PromoStandards SOAP (same parent) | Phase 3 ✅, Alphabroder creds 🔑 | P10-BE-4, P10-BE-5 |
| P10-BE-3 | Backend | `FourOverAdapter` — REST + HMAC auth (new auth path) | Phase 3 ✅, 4Over creds 🔑 | P10-BE-4, P10-BE-5 |
| P10-BE-4 | Backend | DB row per supplier (adapter_class, auth_config, endpoint) | P10-BE-1 or P10-BE-2 or P10-BE-3 | — |
| P10-BE-5 | Backend | Per-supplier fixture sets in `backend/tests/fixtures/` | P10-BE-1, P10-BE-2, P10-BE-3 | P10-BE-6 |
| P10-BE-6 | Backend | "How to add a supplier" one-pager in `docs/` | P10-BE-5 | — |

> **Note:** Each supplier (P10-BE-1, P10-BE-2, P10-BE-3) is independently unblocked — they can be built in parallel once their credentials arrive. No frontend work required.

---

### Phase 11 — Image pipeline

| Task ID | Layer | Description | Depends On | Blocks |
|---------|-------|-------------|------------|--------|
| P11-BE-1 | Backend | SanMar FTP image pull script | Phase 3 ✅, SanMar FTP access 🔑 | P11-BE-2, P11-BE-7 |
| P11-BE-2 | Backend | S3 upload job (idempotent — skip if CDN URL already set) | P11-BE-1, S3 bucket 🔑 | P11-BE-3, P11-BE-4, P11-BE-7 |
| P11-BE-3 | Backend | CDN configuration in front of S3 (CloudFront or equivalent) | P11-BE-2, CDN setup 🔑 | P11-BE-4 |
| P11-BE-4 | Backend | Write CDN URL back to `product_images.url` in DB | P11-BE-3 | P11-FE-1 |
| P11-BE-5 | Backend | Color-to-image mapping: `variant.color` → `image.color` | Phase 1 color schema ✅ | P11-FE-1 |
| P11-BE-6 | Backend | Image type taxonomy enforcement: front/back/side/detail/lifestyle | Phase 1 image schema ✅ | P11-FE-2 |
| P11-BE-7 | Backend | Background job runner (Celery / n8n trigger / FastAPI BackgroundTask) | P11-BE-2 | — |
| P11-FE-1 | Frontend | Color-aware image swap on PDP (swatch click → image change) | P11-BE-4, P11-BE-5 | — |
| P11-FE-2 | Frontend | Image type tabs / carousel on PDP: Front / Back / Side / Detail / Lifestyle | P11-BE-6 | — |

> **Gate:** Cost model (50–100K images) 🔑 must be approved before P11-BE-2 (S3 provisioning). Lazy-pull vs bulk-pull strategy must be decided at spec time.

---

### Phase 12 — Multi-tenant SaaS

| Task ID | Layer | Description | Depends On | Blocks |
|---------|-------|-------------|------------|--------|
| P12-BE-1 | Backend | Customer auth: email+password (bcrypt) or OAuth | Phase 6 ✅, auth provider 🔑 | P12-BE-2 |
| P12-BE-2 | Backend | JWT / session token issuance + refresh | P12-BE-1 | P12-BE-3, P12-FE-1 |
| P12-BE-3 | Backend | RBAC middleware: `vg_admin` vs `customer_admin` roles | P12-BE-2 | P12-BE-4, P12-FE-2 |
| P12-BE-4 | Backend | Scoped query guards on all routes (inject `customer_id` from token) | P12-BE-3 | P12-BE-8 |
| P12-BE-5 | Backend | Customer onboarding endpoints: signup, verify email, connect OPS | P12-BE-2 | P12-FE-3 |
| P12-BE-6 | Backend | Billing integration: Stripe webhook handlers + subscription check | Billing vendor 🔑 | P12-FE-5 |
| P12-BE-7 | Backend | Settings endpoints: OPS auth, markup rules, supplier toggles per customer | P12-BE-3 | P12-FE-4 |
| P12-BE-8 | Backend | Scoping audit — every query in catalog/push_log/markup has `customer_id` filter | P12-BE-4 | P13 |
| P12-FE-1 | Frontend | Login / signup pages | P12-BE-2 | P12-FE-2, P12-FE-3 |
| P12-FE-2 | Frontend | Role-based nav: admin sees customer switcher, customer sees own data | P12-BE-3, P12-FE-1 | — |
| P12-FE-3 | Frontend | Customer onboarding wizard UI | P12-BE-5, P12-FE-1 | — |
| P12-FE-4 | Frontend | Settings page: OPS auth config, markup editor, supplier toggles | P12-BE-7 | — |
| P12-FE-5 | Frontend | Billing / subscription status UI (Stripe portal or custom) | P12-BE-6 | — |

> **Gate:** Auth provider choice 🔑 and billing vendor 🔑 must both be decided before P12-BE-1 and P12-BE-6 respectively.
> **Critical:** P12-BE-8 (scoping audit) is a mandatory pre-gate for Phase 13 — missing one unscoped query is a data-leak bug.

---

### Phase 13 — Production hardening

| Task ID | Layer | Description | Depends On | Blocks |
|---------|-------|-------------|------------|--------|
| P13-BE-1 | Backend | AWS deployment (follow `2026-04-24-aws-deployment-readiness.md`) | All phases ✅, AWS account 🔑 | P13-BE-6, P13-BE-8, P13-FE-1 |
| P13-BE-2 | Backend | Alembic adoption — snapshot prod schema, baseline migration | Prod DB snapshot 🔑 | P13-BE-1 (prerequisite) |
| P13-BE-3 | Backend | Audit log table + middleware (user, table, row_id, before, after, timestamp) | Phase 12 ✅ | P13-FE-3 |
| P13-BE-4 | Backend | Rate limiting per customer (FastAPI middleware or API Gateway) | Phase 12 ✅ | — |
| P13-BE-5 | Backend | Secret rotation: `SECRET_KEY` + `INGEST_SHARED_SECRET` via AWS Secrets Manager | P13-BE-1, AWS Secrets Manager 🔑 | — |
| P13-BE-6 | Backend | Backup strategy: automated RDS snapshots, RPO/RTO documented | P13-BE-1 | — |
| P13-BE-7 | Backend | Pen test findings remediation | P12-BE-8 ✅, pen-test vendor 🔑 | — |
| P13-BE-8 | Backend | Monitoring: Grafana/Datadog setup, alerts, SLO/SLI tracking | P13-BE-1 | P13-FE-1 |
| P13-FE-1 | Frontend | Monitoring dashboard integration (iframe or link to Grafana/Datadog) | P13-BE-8 | — |
| P13-FE-2 | Frontend | Error boundary pages: 500, 403, 404 with actionable messages | P12-FE-1 | — |
| P13-FE-3 | Frontend | Admin audit log viewer — searchable table of recent writes | P13-BE-3 | — |

> **Gate:** Alembic adoption (P13-BE-2) must happen before AWS deployment (P13-BE-1) — never migrate prod DB and deploy simultaneously.
> **Gate:** Pen test (P13-BE-7) cannot start until Phase 12 auth is complete and P12-BE-8 scoping audit is signed off.

---

## Cross-Phase Task Dependencies (Key Chains)

Tasks that span phase boundaries and form the backbone of the critical path:

```
P6-BE-1 (selections table)
  └─→ P6-BE-2 (state machine)
        └─→ P8-BE-6 (update status → pushed)
              └─→ P8-FE-1 (push history view)

P7-BE-4 (upsert decorations)
  └─→ P8-BE-2 (decoration merge at push time)
        └─→ P8-BE-6 (update status → pushed)

P7-BE-5 (validation: decoration required)
  └─→ P8-BE-1 (push routing on supplier flag)

P9-BE-1 (DELTA ingest — Phase 2 gap)
  └─→ P9-BE-2 (import endpoint modes)
        └─→ P9-N8N-1 → P9-N8N-2 → P9-N8N-3 (n8n cron workflows)

P12-BE-4 (scoped query guards)
  └─→ P12-BE-8 (scoping audit)
        └─→ P13 (pen test gate)

P13-BE-2 (Alembic — prod DB snapshot)
  └─→ P13-BE-1 (AWS deployment)
        └─→ P13-BE-5, P13-BE-6, P13-BE-8
```

---

## External Gates Tracker

| Gate | Needed For | Owner | Status |
|------|-----------|-------|--------|
| Stale detection rule locked in spec | P6-BE-2 | Team | Pending |
| Free-form vs templated decorations decision | All P7 | Christian 🔑 | Pending |
| OPS GraphQL error codes for "already exists" | P8-BE-5 | Christian / OPS Postman 🔑 | Pending |
| n8n cron workflow design (one template per type) | P9-N8N-1 | Team | Pending |
| S&S Activewear credentials | P10-BE-1 | Christian 🔑 | Pending |
| Alphabroder credentials | P10-BE-2 | Christian 🔑 | Pending |
| 4Over credentials | P10-BE-3 | Christian 🔑 | Pending |
| Image cost model approved | P11-BE-2 | Team | Pending |
| SanMar FTP access | P11-BE-1 | Christian 🔑 | Pending |
| S3 bucket + CDN provisioned | P11-BE-2, P11-BE-3 | Infra 🔑 | Pending |
| Auth provider chosen | P12-BE-1 | Team | Pending |
| Billing vendor chosen | P12-BE-6 | Christian 🔑 | Pending |
| Prod DB snapshot | P13-BE-2 | DevOps 🔑 | Pending |
| AWS account provisioned | P13-BE-1 | Infra 🔑 | Pending |
| Pen-test vendor engaged | P13-BE-7 | Christian 🔑 | Pending |
