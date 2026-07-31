# Connect → Manage — Sprint Plan & Task Breakdown

> ℹ️ **Authoritative spec = [`2026-06-29-connect-integration-plan-final.md`](2026-06-29-connect-integration-plan-final.md)** (2026-06-29). This doc remains the **task/sprint breakdown** under it; update task acceptance criteria to match the final plan's §6–§8 (auth bearer TTL, re-sync STALE choice, supplier-down structured PO + WhatsApp).

**Source spec:** [`2026-06-24-connect-agnostic-api-restructure.md`](2026-06-24-connect-agnostic-api-restructure.md) (agnostic API, 7 phases, v2 — updated 2026-06-26 with canonical-field-name blocking, S3/S4 scope gates, SanMar modeling prerequisite, config-driven onboarding, and risks R9–R11).
**Team:** 2 engineers — **Vidhi (E1, critical path)** + **Engineer B (E2, parallel tracks)**
**Cadence:** 2-week sprints · estimates in **eng-days** · acceptance = the spec's AC per phase.
**Scope:** Connect ↔ Manage integration plumbing only. *Supplier modeling (SanMar-as-options vs. template-clone) is a separate doc and a separate work item.*

## ⚠️ Hard gates before any sprint starts
**D1 and D2 remain blocking** — do not write code for the affected phase until Christian signs off. **D3 and D6 were resolved on 2026-06-26** (kept below for traceability).

| Gate | Blocks | Action needed |
|---|---|---|
| **D1 — Canonical field names locked** | Sprint 1 adapter work (S1-5) and all of Phase 2+ | Schedule a call with Christian; agree platform-neutral names before any adapter is written |
| **D2 — SanMar apparel modeling decision** | Sprint 2 catalog work (S2-1 onward) | Demo both approaches (master-options vs. template-clone) on 1–2 products; get Christian's pick before Sprint 2 |
| ~~D3 — S3 + S4 scope~~ ✅ **RESOLVED 2026-06-26** | (was Sprints 3–7) | **S4 fulfillment IN scope** (both directions); **S3 real-time deferred** → daily-cron refresh. No longer blocking. |
| ~~D6 — Auth mechanism~~ ✅ **RESOLVED 2026-06-26** | (was S1-3) | Use **API/auth key → short-lived bearer token** (drop cookie). S1-3 now builds this. |

## 0. Already built (do NOT redo — reconcile + commit only)
From prior work; currently **local/uncommitted**:

| Area | Artifact | State |
|---|---|---|
| Crosswalk (Manage) | `ConnectIdMap` + `ConnectSyncState` models, migrations | built, untested on fresh DB |
| Ingest (Manage) | `connect-ingest.ts` (`ingestConnectProducts`, crosswalk) | built (uses `ProductOption` path) |
| Handler/route (Manage) | `ingestConnectProductsHandler`, `POST /integration/connect/ingest/products`, `integration:connect:sync` perm, bridge principal | built |
| Client (Connect) | `ManageClient` (`from_env`) | built |
| Push (Connect) | `manage_push/builder.py` + `routes.py` (`POST /api/manage-push/{supplier_id}`) | built, cost-only |
| Docs | Postman collection (`postman/graphx-connect.postman_collection.json`) | built, importable |
| Infra | pg18 docker volume fix | done |

➡️ **These cover Phase 1 + Phase 2 functionally.** The agnostic reframe adds reconcile tasks (canonical field model, **API-key→bearer auth**, adapter seam, error envelope, config-driven onboarding, **master + per-tenant shadow catalogs**) — see Sprints 1–2.

---

## Sprint 1 — Foundation reconcile + agnostic API (Weeks 1–2)
*Goal: the existing build matches the agnostic spec, is committed, and the Postman collection is publishable + n8n-ready.*
> ⚠️ **D1 must resolve before S1-5.** All other Sprint 1 tasks proceed in parallel while D1 is agreed with Christian.

| ID | Task | Side | Owner | Dep | Est | Acceptance |
|---|---|---|---|---|---|---|
| S1-1 | Commit existing Phase 1/2 work to a branch + open PR (never touch prod `manage.graphxcpi.com`) | both | E1 | — | 0.5 | PR open, CI green |
| S1-2 | Verify migration applies on **fresh** + existing Manage DB | Manage | E2 | S1-1 | 0.5 | AC1.1 |
| S1-3 | Auth: **API/auth key → short-lived bearer token** on all routes (drop the `auth_token` cookie — confirmed cookie-only today in `main.py`) | Connect | E1 | — | 2.5 | 401 w/o key; key→bearer exchange works; 200 w/ bearer |
| S1-4 | Standardize the **error envelope** `{error, detail, request_id}` across all endpoints | Connect | E1 | S1-3 | 1 | Non-2xx returns envelope on every route |
| S1-5 | Define the **canonical field model** + per-target **adapter seam**; Manage = first adapter. ⚠️ **Blocked on D1.** | both | E2 | S1-1 + D1 | 2 | Core has no OPS/Manage field names; adapter maps out |
| S1-6 | **Config-driven tenant onboarding** — verify a new tenant connects to a supplier via DB config only, zero code deployment | Connect | E1 | S1-3 | 1 | New tenant onboards with config row only |
| S1-7 | Finalize Postman collection (all seams, examples, auth, errors) → hand to Christian for the n8n node | Connect | E2 | S1-3, S1-4 | 1 | Collection imports; generates a working n8n node |
| S1-8 | Crosswalk write/read round-trip integration test | Manage | E2 | S1-2 | 0.5 | AC1.4 |

**Sprint 1 exit:** committed, authenticated agnostic API + published Postman doc + config-driven onboarding verified; both engineers unblocked. D1 + D6 resolved.

---

## Sprint 2 — Catalog hardening (S1) + Inventory (S2) (Weeks 3–4)
> ⚠️ **D2 must resolve before Track A.** SanMar modeling demo shown to Christian and approved before any catalog work. Track B (Inventory) starts independently.

### Track A — Catalog reconcile (E1) — *blocked on D2*
| ID | Task | Side | Dep | Est | Acceptance |
|---|---|---|---|---|---|
| S2-1 | Confirm catalog payload uses **canonical** names via adapter (not raw Manage fields) | both | S1-5 + D2 | 1.5 | Payload validates against canonical schema |
| S2-2 | Idempotency + overlay-preservation regression test | Manage | S2-1 | 1 | AC2.2, AC2.3 |
| S2-3 | Central **SKU/stock map** — option-combination ↔ supplier-SKU table in Connect; round-trip test | Connect | S2-1 | 2 | Combination → supplier SKU resolves |
| S2-4 | Per-product ok/error counts; never raises on Manage 5xx | Connect | S2-1 | 0.5 | AC2.8 |
| S2-9 | **Master catalog** — one canonical catalog across suppliers in Connect | Connect | S2-1 | 2 | Master catalog holds all synced products |
| S2-10 | **Per-tenant shadow catalog** — curated subset + negotiated per-tenant cost; pulls from master | Connect | S2-9 | 3 | Tenant curates a subset; negotiated cost drives PO price |
| S2-11 | **Destination ID mapping** — line-for-line tenant-product ↔ destination ID ↔ supplier item | Connect | S2-10 | 1.5 | Destination ID round-trips to the correct supplier item |

### Track B — Inventory S2 (E2) — *can start after Sprint 1*
| ID | Task | Side | Dep | Est | Acceptance |
|---|---|---|---|---|---|
| S2-5 | Scheduled per-supplier inventory poller → store qty/variant in Connect DB | Connect | S1-1 | 2 | Stock stored per variant |
| S2-6 | `POST /integration/connect/ingest/inventory` handler (reverse-lookup via crosswalk; update stock + discontinued) | Manage | S1-8 | 2 | AC3.1–3.3 |
| S2-7 | Connect route `POST /api/manage-push/{supplier}/inventory` + idempotency | Connect | S2-5 | 1 | AC3.4 |
| S2-8 | Cadence configurable per supplier (default 30 min) | Connect | S2-5 | 0.5 | AC3.5 |

---

## Sprint 3 — Supplier Directory (S7) + Pricing Quote start (S3) (Weeks 5–6)

### Track B — Supplier Directory S7 (E2) — *no blockers*
| ID | Task | Side | Dep | Est | Acceptance |
|---|---|---|---|---|---|
| S3-1 | `GET /api/suppliers/directory` — slug, name, categories, active, capability flags | Connect | S1-3 | 1.5 | AC7.1 |
| S3-2 | Manage fetch + **TTL cache** (default 1h) + read-only sourcing UI list | Manage | S3-1 | 2 | AC7.2, AC7.3 |

### Track A — Pricing Refresh S3 (E1) — *daily cron (real-time deferred)*
| ID | Task | Side | Dep | Est | Acceptance |
|---|---|---|---|---|---|
| S3-3 | **Daily cron (~12:01 AM)** per supplier → refresh wholesale cost into the master catalog | Connect | S2-9 | 2.5 | Master cost refreshed daily; run logged |
| S3-4 | Layer tenant **negotiated cost** into the shadow catalog; existing `/api/pricing/quote` stays as-is | Connect | S3-3, S2-10 | 1.5 | Tenant PO price uses negotiated cost; consumer quote unchanged |

---

## Sprint 4 — Pricing finish (S3) + Images (S6) (Weeks 7–8)

### Track A — Pricing Refresh hardening (E1)
| ID | Task | Side | Dep | Est | Acceptance |
|---|---|---|---|---|---|
| S4-1 | Cron scheduling + **stale-cost alert** (warn if a supplier refresh fails or is stale) | Connect | S3-3 | 1.5 | Failed/stale refresh raises an alert |
| S4-2 | E2E: cron refresh → updated cost reflected in the consumer quote (cost 2.95 + 30% markup → 3.84) | both | S4-1 | 1 | Refreshed cost flows through to the quote |

### Track B — Images S6 (E2) — *no blockers*
| ID | Task | Side | Dep | Est | Acceptance |
|---|---|---|---|---|---|
| S4-3 | Adapters fetch supplier images → store URLs per product/variant | Connect | S2-1 | 2 | AC6.1 |
| S4-4 | Extend catalog payload `images[]` w/ per-color tagging | Connect | S4-3 | 1 | AC6.4 |
| S4-5 | Manage upsert `ProductImage` by URL; preserve consumer-uploaded images | Manage | S4-4 | 2 | AC6.2, AC6.3 |

---

## Sprint 5–7 — Order Fulfillment + Status (S4 + S5) (Weeks 9–14)
*Largest phase (4–6 wks). Both engineers.*
> ✅ **S4 confirmed in scope (2026-06-26).** Still gated on **D5** (first supplier fulfillment APIs — OPS SKU/inventory API due ~Jun 29–30).

| ID | Task | Side | Owner | Dep | Est | Acceptance |
|---|---|---|---|---|---|---|
| S5-1 | `POST /api/fulfillment/submit` — map order → supplier PO format → supplier PO API | Connect | E1 | S2-3 + D5 | 4 | AC5.1, AC5.2 |
| S5-2 | Status polling job per supplier → `POST /integration/connect/order-status` on change | Connect | E1 | S5-1 | 3 | AC5.3 |
| S5-3 | Manage fulfillment trigger — Job `source=CONNECT` at fulfillment stage calls submit; create `JobOutsource` | Manage | E2 | S5-1 | 3 | AC5.1, AC5.2 |
| S5-4 | Manage status receiver — update `JobOutsource` status + tracking; notify (no-op until email stack) | Manage | E2 | S5-2 | 3 | AC5.3, AC5.4 |
| S5-5 | Failure path — supplier down leaves status SENT, retries next poll; order never lost | both | E1 | S5-2 | 1.5 | AC5.5 |
| S5-7 | **Supplier-down manual-PO fallback** — email/notify tenant + hand a structured PO for manual ordering; "place manually" cancels the API call (no duplicate) | both | E1 | S5-5 | 2 | Tenant notified + gets PO; manual choice cancels the auto-call |
| S5-6 | Full E2E: confirm order → submit → simulate supplier status → Manage job updates | both | E2 | S5-4 | 2 | Order confirmed in Manage → Connect submits → status polling updates `JobOutsource` → tracking visible in Manage |

---

## Engineer assignment summary
- **Vidhi (E1) — critical path:** S1 auth/envelope/onboarding → Catalog reconcile → Pricing Quote → Fulfillment submit/polling. *Owns the Connect-side spine.*
- **Engineer B (E2) — parallel tracks:** Foundation tests/adapter seam → Inventory → Supplier Directory → Images → Manage-side fulfillment. *Owns Manage-side + standalone seams.*

## Definition of Done (every task)
1. Code + tests; CI green. 2. Auth enforced (API key → bearer token). 3. Idempotent; overlay never clobbered. 4. Cost-only (no `apply_markup`). 5. Doc/Postman updated in the same PR. 6. **Never deploy to prod `manage.graphxcpi.com`; never `prisma db push` against prod.** 7. New tenant onboarding requires config only — no code change.

## Critical path & timeline
`Sprint 1 (Foundation) → Catalog → Pricing → Fulfillment` ≈ **10–14 weeks**. Inventory (S2), Directory (S7), Images (S6) run on E2's parallel track and finish before the fulfillment phase.
```
Sprint 1 — Foundation + Postman        [D1 must resolve · D6 resolved → build API-key/bearer]
   ├── Sprint 2 Track A — Catalog       [D2 must resolve before this] + master/shadow catalogs
   ├── Sprint 2 Track B — Inventory     [no blocker]
   ├── Sprint 3 Track A — Pricing Refresh (daily cron)  [no blocker]
   ├── Sprint 3 Track B — Directory     [no blocker]
   ├── Sprint 4 Track A — Pricing Refresh hardening     [no blocker]
   ├── Sprint 4 Track B — Images        [no blocker]
   └── Sprints 5–7 — Fulfillment        [S4 confirmed · D5 gates start]
```

## Risks (mirrored from the integration spec)
| # | Risk | Mitigation |
|---|---|---|
| R9 | Starting Sprint 2 before SanMar modeling decision (D2) | Demo both approaches on 1–2 products; Christian approval first — hard gate above |
| R10 | Building adapters (S1-5) before canonical field names locked (D1) | D1 signed off before S1-5 starts — do not skip |
| R11 | Pricing/fulfillment scope drift | D3 resolved 2026-06-26 — S4 in scope; S3 reduced to daily-cron refresh |
| R12 | Deploy to prod `manage.graphxcpi.com` | DoD item 6 — never; staging only |
| R13 | Double markup | Connect emits wholesale cost only; no `apply_markup` in any payload |
| R14 | Re-sync clobbers consumer overlay | Ingest writes base fields only; overlay columns never touched |

## Open blockers feeding this plan
> **D-numbering:** D1–D6 below match the integration spec exactly. **G1** is sprint-specific (Manage staging env) — kept separate so it does **not** collide with the spec's D-numbers.

| ID | Decision | Blocks | Status |
|---|---|---|---|
| D1 | Canonical field names — lock with Christian | S1-5 and all Phase 2+ | ⚠️ Blocking |
| D2 | SanMar apparel modeling — demo both, get Christian's pick | Sprint 2 Track A | ⚠️ Blocking |
| D3 | S3 + S4 scope | (was Sprints 3–7) | ✅ Resolved 2026-06-26 — S4 in; S3 daily-cron |
| D6 | Auth mechanism | (was S1-3) | ✅ Resolved 2026-06-26 — API key → bearer |
| D5 | Supplier fulfillment APIs availability | Sprint 5 (S5-1) | Open — gates Sprint 5 |
| **G1** | Staging `MANAGE_INGEST_URL` + principal token *(sprint-specific)* | Sprint 2 integration runs | Open |
