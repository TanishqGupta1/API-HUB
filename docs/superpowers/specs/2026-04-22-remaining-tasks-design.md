# Remaining Tasks — Consolidated Spec

**Date:** 2026-04-22  
**Author:** Tanishq (brainstorm session)  
**Status:** Approved — proceed to implementation planning

---

## Purpose

Single source of truth for all remaining work across V0 Cleanup, V1a–V1g, and the ops-push plan. Compiled from live code audit (2026-04-22) against all plan docs. Supersedes the individual plan-doc checkbox lists where they conflict with actual code state.

---

## What Is Actually Done (Code Audit)

Plans were stale. Verified in code on 2026-04-22:

| Module / Feature | Status | Evidence |
|---|---|---|
| All V0 backend modules | ✅ Done | `backend/modules/` — all 8 present |
| shadcn/ui installed | ✅ Done | `frontend/src/components/ui/` — button, card, input, table, badge, separator, scroll-area, select, tabs |
| Product options ingest + frontend | ✅ Done | `catalog/models.py`, `ingest.py`, `product-options.tsx` |
| Storefront redesign (PDPLayout, ImageGallery, VariantPicker, PriceBlock) | ✅ Done | `frontend/src/components/storefront/` |
| promostandards module (resolver, client, normalizer, routes, schemas) | ✅ Done | `backend/modules/promostandards/` — all 5 files |
| rest_connector (S&S + 4Over) | ✅ Done | `client.py`, `ss_normalizer.py`, `fourover_client.py`, `fourover_normalizer.py` |
| ops_push module (image pipeline + routes) | ✅ Done | `backend/modules/ops_push/` |
| n8n_proxy module | ✅ Done | `backend/modules/n8n_proxy/routes.py` |
| push_log module (models + routes) | ✅ Done | `backend/modules/push_log/` |
| n8n vg-ops-pull.json + ops-push.json | ✅ Done | `n8n-workflows/` |
| OPS node setProduct (A1) | ✅ Done | `OnPrintShop.node.ts` |
| OPS node setProductPrice (A2) | ✅ Done | `OnPrintShop.node.ts` |
| Backend tests (normalizer + S&S + catalog ingest) | ✅ Done | `backend/tests/` |

---

## Remaining Work

### Tier 1 — Unblocked, Ship Now

#### OPS Node Mutations (A3–A6)

| Task | File | Effort |
|------|------|--------|
| **A3** — `setProductSize` mutation | `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts` | S |
| **A4** — `setProductCategory` mutation | `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts` | S |
| **A5** — Update gap analysis doc (mark rows 12, 13, 15, 21 implemented) | `n8n-nodes-onprintshop/OPS-NODE-GAP-ANALYSIS.md` | XS |
| **A6** — Combined smoke test: Category → Product → Size → Price chain | n8n UI (no file) | M |

Full step-by-step code for A3 and A4 is in `docs/superpowers/plans/2026-04-20-ops-push.md` Tasks A3 and A4.

---

#### FastAPI Push Orchestration (B1–B7)

| Task | Files | Effort |
|------|-------|--------|
| **B1** — push_log Pydantic schemas + `POST /api/push-log` | `backend/modules/push_log/schemas.py` (create), `routes.py` (modify) | S |
| **B2** — `push_candidates` module | `backend/modules/push_candidates/__init__.py`, `service.py`, `routes.py`; wire in `main.py` | M |
| **B3** — `OPSProductInput` schema + `/ops-input` endpoint | `backend/modules/markup/schemas.py`, `engine.py`, `routes.py` | M |
| **B4** — `OPSVariantsBundle` + `/ops-variants` endpoint | `backend/modules/markup/schemas.py`, `routes.py` | S |
| **B5** — `OPSCategoryInput` + `/categories/{id}/ops-input` endpoint | `backend/modules/catalog/schemas.py`, `routes.py` | S |
| **B6** — Image pipeline `Cache-Control` header | `backend/modules/ops_push/image_pipeline.py` | XS |
| **B7** — Integration verification (curl sequence) | No files — manual | S |

Full code for each step is in `docs/superpowers/plans/2026-04-20-ops-push.md` Phase B.

---

#### n8n Push Workflow Validation (C1–C4)

`n8n-workflows/ops-push.json` exists. Verify it matches the Phase C spec, then:

| Task | Effort |
|------|--------|
| **C1** — Confirm workflow JSON matches spec (9-node flow including error branch) | S |
| **C2** — Manual E2E run with single test product | M |
| **C3** — Error path test (inject bad sku, verify failed push-log row) | S |
| **C4** — Write `n8n-workflows/PUSH_README.md` operator guide | S |

---

#### V0 Cleanup Frontend (still missing)

| Task | Files | Effort |
|------|-------|--------|
| **0.4** — Customers (Storefronts) page: list + add/edit form with OAuth2 fields | `frontend/src/app/customers/page.tsx` | M |
| **0.5** — Workflows page: animated pipeline diagram | `frontend/src/app/workflows/page.tsx` | M |
| **0.6 / Task 22** — Dashboard wired to `/api/stats` + `/api/sync-jobs?limit=5` | `frontend/src/app/page.tsx` | S |

The customers page is urgent — OPS push needs a customer to push to.

---

#### Frontend Publish UI (D1–D3)

| Task | Files | Effort |
|------|-------|--------|
| **D1** — `ProductPushLogRead` TS type | `frontend/src/lib/types.ts` | XS |
| **D2** — `PushHistory` component | `frontend/src/components/products/push-history.tsx` | S |
| **D3** — `PublishButton` + wire into product detail admin page | `frontend/src/components/products/publish-button.tsx`, `app/(admin)/products/[id]/page.tsx` | M |

Full component code in `docs/superpowers/plans/2026-04-20-ops-push.md` Phase D.

---

### Tier 2 — Blocked on External Credentials

| Task | Plan Ref | Blocker |
|------|----------|---------|
| SanMar E2E verify (V1a Task 6) | v1-pipeline | Christian's SanMar API creds |
| S&S Activewear E2E verify | v1-pipeline V1b | S&S API creds |
| 4Over E2E verify | v1-pipeline V1d | 4Over API creds |

No code work needed until credentials arrive. Steps documented in V1a plan Task 6.

---

### Tier 3 — V1e Scheduling + V1f UX (Unblocked, Next Sprint)

#### V1e: Scheduled Sync + Delta Sync + Dashboard

| Task | Files | Effort |
|------|-------|--------|
| **Task 17** — n8n cron workflows: inventory-sync-30min, pricing-sync-daily, delta-sync-daily, full-sync-weekly | `n8n-workflows/*.json` (4 files) | M |
| **Task 18** — Delta sync: `get_product_date_modified` in client + `?delta=true` route param | `backend/modules/promostandards/client.py`, `routes.py` | M |
| **Task 19** — Sync dashboard health: last sync time, per-supplier health badge, error preview | `frontend/src/app/page.tsx`, `frontend/src/app/sync/page.tsx` | M |

#### V1f: Frontend UX Overhaul

| Task | Files | Effort |
|------|-------|--------|
| **Task 20** — Terminology: all jargon → business language, empty states per page, sidebar rename | All frontend pages + `layout.tsx`, `Sidebar.tsx` | M |
| **Task 21** — Simplified supplier form: 5-step → 3-step, no SOAP/HMAC jargon | `frontend/src/components/suppliers/reveal-form.tsx` | L |

Terminology map and exact string replacements in `plans/2026-04-16-v1-integration-pipeline.md` Task 20.

---

### Tier 4 — V1g (Blocked on V1c Working + OPS Creds)

| Task | Effort |
|------|--------|
| **Task 23** — OPS Storefront Config page: categories, options mapping, pricing preview | XL |

Do not start until at least one product has been successfully pushed end-to-end via V1c.

---

## Gaps Not in Any Plan

These are issues discovered in the 2026-04-22 code audit. Not covered by any existing plan doc.

| ID | Gap | Severity | Suggested Fix |
|----|-----|----------|---------------|
| **G1** | No API authentication — every endpoint is publicly accessible | **High** | Add API key header middleware (simple shared secret, same pattern as `INGEST_SHARED_SECRET`). JWT in V2. |
| **G2** | `rest_connector` protocol adapters (S&S, 4Over) not wired into `POST /api/sync/{id}` dispatch — only `promostandards` protocol is handled | **High** | Add `"rest"` and `"rest_hmac"` branches to `promostandards/routes.py` sync endpoint |
| **G3** | `push_log/schemas.py` does not exist — inline body shapes still in `routes.py` | **Medium** | B1 task creates it |
| **G4** | No product archiving — if supplier removes a SKU, old row stays active in DB forever | **Medium** | Add `is_discontinued` flag to Product; normalizer sets it on any SKU absent from the latest full sync |
| **G5** | Sync batch partial failure — if SOAP fails mid-batch (e.g. at product 200/500), `SyncJob` status goes to "failed" with 0 records_processed even though 199 were committed | **Medium** | Track `records_processed` incrementally in the background task; commit counter to SyncJob every batch |
| **G6** | Alphabroder supplier row — V1b Task 7 is "zero code, just a DB row" but has never been created | **Low** | `POST /api/suppliers` with Alphabroder PS code. One curl. |
| **G7** | `n8n_proxy` module — purpose not documented, routes not in README | **Low** | Add inline docstring to `routes.py`; add entry to `docs/` |
| **G8** | Push history UI (D2) shows truncated customer UUID `slice(0,8)` — should show customer name | **Low** | Join customer name in the push-log API response, or fetch customers list in the component |

---

## Priority Order (Recommended: Option A — Ship Push End-to-End First)

```
Sprint 1 (this week):
  Tanishq:   A3 → A4 → A5 → B1 → B2 → B3 → B4 → B5 → B6 → C1 verify → C2 E2E
  Intern:    0.4 (Customers page) → D1 → D2 → D3 (Publish UI)
  Fix gaps:  G2 (routing gap) alongside B2 — same file

Sprint 2:
  V0.5 (Workflows page) → 0.6 (Dashboard wiring) → V1e Tasks 17-19

Sprint 3:
  V1f Tasks 20-21 (UX overhaul)
  V1g Task 23 (Storefront config) — only after V1c E2E green

Waiting (credentials gate):
  V1a Task 6 (SanMar E2E)
  V1b S&S E2E, V1d 4Over E2E
```

**Why Option A:** The push pipeline is the core deliverable. Every other feature is secondary until at least one product appears in OPS via the hub. The Customers page is the only blocking dependency — without a customer row in the DB, push has nowhere to push to.

---

## Team Assignment (Next Sprint)

| Person | Tasks | Priority |
|--------|-------|----------|
| Tanishq | A3, A4, A5, B1–B6, G2 fix | Start A3 immediately |
| Intern (any) | Task 0.4 (Customers page), D1, D2, D3 | Customers page first |
| Vidhi or Sinchana | Task 0.5 (Workflows page), Task 0.6 (Dashboard wiring) | After 0.4 |

---

## Blockers to Chase

| Blocker | Owner | Urgency |
|---------|-------|---------|
| SanMar API credentials | Christian → Tanishq | Medium (E2E only) |
| S&S API credentials | Christian → Tanishq | Medium |
| 4Over API credentials | Christian → Tanishq | Medium |
| OPS Postman collection export | Tanishq exports from browser | High (needed for exact GraphQL input shapes before C2) |
| OPS customer credentials (ops_auth_config for at least one storefront) | Christian → Tanishq | **Critical for C2 E2E** |

---

## References

- V1 master plan: `plans/2026-04-16-v1-integration-pipeline.md`
- V1a SanMar plan: `plans/2026-04-17-v1a-sanmar-inbound-pipeline.md`
- OPS push plan (full task code): `docs/superpowers/plans/2026-04-20-ops-push.md`
- Gap analysis: `n8n-nodes-onprintshop/OPS-NODE-GAP-ANALYSIS.md`
- Code review issues: `docs/code_review_all_tasks.md`
