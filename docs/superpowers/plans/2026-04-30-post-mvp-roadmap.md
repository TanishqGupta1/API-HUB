# Post-MVP Roadmap (Phases 6-13)

> **STATUS UPDATE (2026-04-30):**
> - **Phase 1:** ✅ COMPLETE on main (`93de4b5`)
> - **Phase 2:** 🟡 PARTIAL on main (`b391baa`) — DELTA discovery missing, rolls into Phase 9
> - **Phase 3:** ⏸ Plan needs revision (Phase 2 already shipped BaseAdapter framework); creds-blocked
> - **Phase 4:** 🟢 Unblocked, ready next
> - **Phase 5:** 🟢 Unblocked, parallel-safe with Phase 6
> - **Phases 6-13:** Spec needed per phase before plan; see open questions in 2026-04-30 brainstorm

> **For agentic workers:** This is a strategic roadmap, NOT a per-task implementation plan. Each phase below requires its own spec → detailed plan → execution cycle. Use superpowers:brainstorming to spec a phase before writing its implementation plan.

**Goal:** Define the post-MVP trajectory after Phases 1-5 ship. Phases 1-5 deliver the polymorphic product foundation, OPS + SanMar adapters, pricing API, and product detail UI. Phases 6-13 extend that foundation toward production-grade multi-tenant catalog management.

**Source:** Meeting with Christian (2026-04-30) covering catalog management UX (§8), SanMar decoration overlay (§7), and OPS push behavior (§6). Brainstorm session 2026-04-30 produced the slice ordering below.

**Tech Stack:** No new tech introduced. Continues FastAPI + async SQLAlchemy + Pydantic v2 + Next.js 15 + n8n. Phase 13 adds AWS deployment (plan exists: `2026-04-24-aws-deployment-readiness.md`).

---

## Trajectory at a glance

```
Phase 1 (model)  ─┐
Phase 2 (OPS)    ─┤
Phase 3 (SanMar) ─┼─→  MVP catalog ingest works
Phase 4 (pricing)─┤
Phase 5 (PDP)    ─┘

Phase 6 (curation)        ─→  Customer-curated catalogs
Phase 7 (overlay)         ─┐
Phase 8 (push polish)     ─┴─→  Real push pipeline w/ decoration

Phase 9 (sync orch)       ─┐
Phase 10 (more suppliers) ─┴─→  Production scaling (data)

Phase 11 (images)         ─→  Image pipeline
Phase 12 (multi-tenant)   ─→  SaaS readiness
Phase 13 (hardening)      ─→  Production hardening
```

---

## Near-term phases (Christian's meeting items)

### Phase 6 — Customer-curated catalog views

**Maps to Christian §8.**

**Goal:** Admin picks a customer from a dropdown, sees that customer's catalog separate from the global "Available" catalog. Selection model + state machine.

**Deliverables:**
- New table `customer_product_selections` (customer_id, product_id, status, added_at, pushed_at)
- States: `selected` (Pending) → `pushed` → `stale` (source updated since push)
- Customer dropdown UI in admin shell (top nav)
- Two catalog views: "Available Catalog" (all imported), "Customer Catalog" (selected for current customer)
- Status badges per product card (Available / Selected / Pushed / Stale)
- Supplier filter (already exists, verify works on both views)
- Single-tenant operator UX — no auth, all admins see all customers

**Depends on:** Phase 1 done (polymorphic model). Existing `customers` table already in DB.

**Out of scope:** Auth (Phase 12), per-customer self-serve UI (Phase 12), bulk actions (later).

**Risks:** State transitions get gnarly when source product is updated after push. Need clear "stale" detection rule (e.g., `last_synced > pushed_at`).

**Spec needed:** Yes. Brainstorm before plan.

---

### Phase 7 — Decoration overlay model

**Maps to Christian §7.**

**Goal:** SanMar apparel products are blank bases. Admin adds print/decoration options on top per (customer, product). Decoration data is per-customer-per-product, not global.

**Deliverables:**
- New table `customer_product_decorations` (customer_id, product_id, decoration_options JSONB, updated_at)
- Decoration options shape: list of OptionIngest rows (imprint method, location, color, etc.)
- Reuse Phase 1 `OptionIngest` schema — no new option model
- UI: SanMar product detail page → "Add decoration" tab → option editor
- Decoration is required before push for SanMar products (validation rule)
- Push pipeline (Phase 8) merges base apparel options + decoration overlay

**Depends on:** Phase 1, Phase 3 (SanMar adapter), Phase 6 (customer context).

**Out of scope:** Decoration templates (saved configurations reusable across products) — future enhancement. Per-variant decoration — assume decoration applies at product level, not variant level.

**Risks:** Decoration is conceptually a "print-options layer on apparel base" — challenges the strict apparel/print polymorphism from Phase 1. Resolution: decoration options live in their own table, not in `print_details`. Push pipeline materializes the merged shape only at push time.

**Open question to lock in spec:** Are decorations free-form (admin types option titles) or templated (admin picks from canonical "imprint method" master list)? Recommend templated using existing `master_options` module.

**Spec needed:** Yes. Decoration model is the riskiest design call in the roadmap. Brainstorm hard.

---

### Phase 8 — Push pipeline polish

**Maps to Christian §6.**

**Goal:** Push to OPS works correctly for both ready products (VG OPS) and decorated products (SanMar + overlay). Internal name conflict handling.

**Deliverables:**
- Push routing in `modules/ops_push/`:
  - Supplier with stored options → push as-is (spine + product_options + product_option_attributes)
  - Supplier with decoration overlay → merge base apparel + customer_product_decorations → push merged
- Internal name prefix on conflict: configurable per (supplier, customer) — defaults to supplier-initials prefix (`VG-`, `SM-`)
- `push_mappings` already tracks (source_product_id, customer_id, target_ops_product_id) — verify retry path is idempotent
- Push history view per (customer, product) — uses existing `push_log`
- "Push" button per product card on Customer Catalog view (already exists for some flows — verify)

**Depends on:** Phase 6 (customer context), Phase 7 (decoration data).

**Out of scope:** Bulk push (push 50 at once) — future. Push scheduling — Phase 9.

**Risks:** OPS GraphQL mutations don't always handle "exists" gracefully. Need to query first or catch specific error codes.

**Spec needed:** Light. Mostly polishing existing push code + adding decoration merge. Brief brainstorm to nail merge logic.

---

## Mid-term phases

### Phase 9 — Sync orchestration via n8n

**Goal:** All suppliers sync on schedule, not just on demand. Different cadence per data type.

**Deliverables:**
- n8n cron workflows per (supplier, sync_type):
  - Catalog: weekly full reconcile
  - Inventory: hourly delta (per supplier capability)
  - Pricing: daily delta
  - Closeouts: monthly archival sweep
- Workflows trigger `POST /api/suppliers/{id}/import?mode={delta|full|closeouts}` (endpoint from Phase 2)
- `last_full_sync` / `last_delta_sync` columns (already added in Phase 1) drive delta queries
- Sync dashboard: per-supplier last-success timestamp, error counts, throughput
- Slack/email alerts on consecutive failures

**Depends on:** Phase 2, Phase 3, Phase 10 (more suppliers benefit). Existing n8n infra.

**Out of scope:** Real-time inventory (out-of-stock at checkout) — Phase 11+ if needed.

**Risks:** Workflow sprawl. Mitigation: one canonical workflow template per sync_type, parameterized by supplier_id from DB.

**Spec needed:** Yes. n8n workflow design + alert thresholds.

---

### Phase 10 — More suppliers

**Goal:** Add S&S Activewear, Alphabroder, 4Over. Prove the "supplier = DB row + adapter class" model.

**Deliverables:**
- `SSAdapter` (PromoStandards REST) — likely subclass of `PromoStandardsAdapter` from Phase 3
- `AlphabroderAdapter` (PromoStandards SOAP) — same parent class
- `FourOverAdapter` (REST + HMAC auth) — new adapter, new auth path
- Each supplier added as DB row with `adapter_class` set; no router code changes
- Per-supplier fixture sets in `backend/tests/fixtures/`
- Documentation: how to add a new supplier (one-pager)

**Depends on:** Phase 3 (adapter framework). Live credentials per supplier.

**Out of scope:** Suppliers Christian hasn't named yet.

**Risks:** PromoStandards is a spec, but each supplier deviates. Each new supplier ships only after fixture-driven tests pass.

**Spec needed:** One spec per supplier (3 specs total).

---

### Phase 11 — Image pipeline

**Goal:** Pull images from suppliers, host on CDN, serve via API.

**Deliverables:**
- SanMar FTP image pull (separate from PS API)
- S3 (or equivalent) bucket for image storage
- CDN in front of S3
- `product_images.url` updated to CDN URLs after upload
- Color-to-image mapping: variant.color → image.color match for color-aware UI
- Image type taxonomy enforced: `front` | `back` | `side` | `detail` | `lifestyle`
- Background job, idempotent — re-running doesn't re-upload existing images

**Depends on:** Phase 1 (image schema), Phase 3 (SanMar inbound).

**Out of scope:** Image transformations (thumbnails, watermarks) — defer until needed.

**Risks:** ~10K SanMar products × ~5 images × multi-color = 50-100K images. Cost + transfer time. Cache aggressively. Lazy-pull (on first product view) is an alternative.

**Spec needed:** Yes. Storage + pull strategy + cost model.

---

## Far-term phases

### Phase 12 — Multi-tenant SaaS

**Goal:** Customers self-serve. Each customer logs in, sees only their catalog.

**Deliverables:**
- Customer authentication (email + password or OAuth)
- Role-based access: VG admin (sees all customers) vs customer admin (sees own only)
- Scoped queries throughout — every product/selection/decoration query filters by `customer_id`
- Customer onboarding flow: signup → verify → connect OPS storefront → start curating
- Billing integration (if SaaS) — Stripe or similar
- Settings: customer's OPS auth, markup rules, supplier access toggles

**Depends on:** Phase 6 (selections already keyed on customer_id from day one).

**Out of scope:** Free trials, plan tiers, usage metering — product decisions, not engineering.

**Risks:** Migration of existing single-tenant data into multi-tenant model. Mitigation: existing `customers` rows already have `customer_id` — every selection/decoration row is already customer-scoped from Phases 6+7. Phase 12 layers auth on top.

**Spec needed:** Yes. Auth model + role design + scoping audit.

---

### Phase 13 — Production hardening

**Goal:** Ship-ready infrastructure.

**Deliverables:**
- AWS deployment (plan exists: `docs/superpowers/plans/2026-04-24-aws-deployment-readiness.md`)
- Alembic adoption — replace `_SCHEMA_UPGRADES` list in `main.py` with proper migrations
- Audit log: who changed what, when (every write traced)
- Monitoring: Grafana/Datadog dashboards, alerts, SLO/SLI tracking
- Rate limiting per customer (prevent runaway sync from one tenant)
- Backup + DR plan (RPO/RTO targets)
- Secret rotation for `SECRET_KEY` (Fernet key) + `INGEST_SHARED_SECRET`
- Penetration testing + security review

**Depends on:** Everything above. Especially Phase 12 (auth) — can't pen-test before auth exists.

**Out of scope:** SOC 2 / compliance audits — separate workstream.

**Risks:** Migrating from `_SCHEMA_UPGRADES` to Alembic mid-flight is tricky on existing prod data. Mitigation: snapshot prod schema, baseline an Alembic migration matching it, then apply Alembic going forward.

**Spec needed:** Yes. Multiple specs (AWS already has one). Each hardening item is its own spec.

---

## Cross-cutting concerns

These get picked up along the way, not as their own phases:

- **Categories mapping** — supplier categories → customer storefront categories. Plan exists: `2026-04-24-sanmar-category-import-archive-mappings.md`. Touch in Phase 6 or 7.
- **Markup engine extension** — tier-based markup (different markup per quantity tier), currency, tax. Current `markup` module is basic. Touch in Phase 8 (when push uses it) or Phase 11.
- **Search** — cross-supplier search on `products`. Postgres FTS first, Meilisearch if needed. Touch in Phase 6 (catalog views).
- **Bulk actions** — push 50 products at once, bulk-archive, bulk-decoration-template. Touch in Phase 8 (push) or Phase 9 (orchestration).

---

## Phase ordering

```
Phase 6 ──┬─→ Phase 7 ─┬─→ Phase 8
          │            │
          │            │
          └─→ Phase 9 ─┘
                       │
                       ↓
                   Phase 10 ─→ Phase 11
                       │
                       ↓
                   Phase 12 ─→ Phase 13
```

- 6 unblocks 7 and 9 (parallel)
- 7 unblocks 8 (decoration → push)
- 8 + 9 close the curation loop (push works, syncs run)
- 10 expands data sources (suppliers)
- 11 fills out the data (images)
- 12 productizes (auth, SaaS)
- 13 ships (deployment + hardening)

Recommended ship cadence: 1 phase per ~2-week sprint, parallelizing where the graph allows.

---

## Decision log

Decisions made during 2026-04-30 brainstorm that shape this roadmap:

| Decision | Choice | Reason |
|---|---|---|
| Customer model | Single-tenant operator now, multi-tenant later | Christian explicitly said "current is single-tenant"; multi-tenant added in Phase 12 |
| Selection table | Build with `customer_id` from Phase 6 | Avoids Phase 12 refactor pain; cheap if added now |
| Decoration storage | Separate `customer_product_decorations` table, not extension of `print_details` | Decoration is per-customer; print_details is per-product |
| Compare tool (Printdeed vs staging) | Not built — manual QA only | Printdeed was reference example, not a product feature |
| Internal name prefix | Configurable per (supplier, customer), defaults to supplier initials | Allows customer to override `VG-` if they want |
| Push routing logic | Branch on supplier capability ("has_decoration_overlay") not on supplier_type | More extensible than hard-coded supplier checks |

---

## Next action

Brainstorm Phase 6 (the next ship) using superpowers:brainstorming. Spec → writing-plans → execute. Repeat per phase.

This roadmap doc lives at `docs/superpowers/plans/2026-04-30-post-mvp-roadmap.md` as a portfolio guide. Update it as phases complete or priorities shift.

---

## Phase Dependency Table

> **Legend:** ✅ = hard dependency (cannot start without) | ⚠️ = soft dependency (can start, but limited without) | 🔑 = external gate (credentials, decisions, infra)

| Phase | Hard Depends On | Soft / Parallel | External Gates | Notes |
|-------|-----------------|-----------------|----------------|-------|
| **6** Customer Catalog | Phase 1 ✅ | — | — | `customers` table already exists; unblocked now |
| **7** Decoration Overlay | Phase 1 ✅, Phase 3 ✅, Phase 6 ✅ | — | — | Cannot start until Phase 6 ships customer context |
| **8** Push Polish | Phase 6 ✅, Phase 7 ✅ | — | OPS GraphQL error codes 🔑 | Light lift if 7 is clean; push_log + push_mappings already exist |
| **9** Sync Orchestration | Phase 2 ✅, Phase 3 ⚠️ | Phase 7 (parallel-safe) | n8n cron design 🔑 | Phase 2 partial — DELTA ingest must be completed here first |
| **10** More Suppliers | Phase 3 ✅ | Phase 11 (parallel-safe) | S&S / Alphabroder / 4Over credentials 🔑 | Each supplier is independently unblocked once creds arrive |
| **11** Image Pipeline | Phase 1 ✅, Phase 3 ✅ | Phase 10 (parallel-safe) | S3 bucket / CDN setup 🔑, SanMar FTP access 🔑 | Cost model must be approved before S3 provisioning |
| **12** Multi-Tenant SaaS | Phase 6 ✅ | — | Auth provider choice 🔑, billing vendor 🔑 | All selection/decoration rows already customer-scoped — Phase 12 layers auth only |
| **13** Production Hardening | All above ✅ | — | AWS account 🔑, pen-test vendor 🔑 | AWS plan already exists; Alembic migration needs prod DB snapshot |

**Critical path to ship:** 6 → 7 → 8 → 12 → 13 (no parallel shortcuts on this spine).

**Best parallelism windows:**
- After Phase 6 ships: start Phase 7 + Phase 9 simultaneously (different teams/workers).
- After Phase 9 ships: start Phase 10 per supplier independently.
- Phase 11 can start alongside Phase 10 (different file surfaces).

---

## Frontend vs Backend Task Breakdown (Phases 6–13)

### Phase 6 — Customer-curated catalog views

| Layer | Tasks |
|-------|-------|
| **Backend** | New `customer_product_selections` table (customer_id, product_id, status, added_at, pushed_at) |
| **Backend** | State machine: `selected → pushed → stale` (detect stale via `last_synced > pushed_at`) |
| **Backend** | `GET /api/customers/{id}/catalog` — returns selected products with status |
| **Backend** | `POST /api/customers/{id}/catalog/{product_id}` — add product to customer catalog |
| **Backend** | `DELETE /api/customers/{id}/catalog/{product_id}` — remove selection |
| **Frontend** | Customer dropdown in admin top nav (populates from existing `customers` API) |
| **Frontend** | "Available Catalog" view — all imported products, add-to-customer button per card |
| **Frontend** | "Customer Catalog" view — filtered to selected products for active customer |
| **Frontend** | Status badges per product card: Available / Selected / Pushed / Stale |
| **Frontend** | Supplier filter working on both catalog views (verify existing filter covers this) |

**Audit note:** Stale detection rule (`last_synced > pushed_at`) must be locked in spec before backend starts — wrong rule here breaks Phase 8 push state.

---

### Phase 7 — Decoration overlay model

| Layer | Tasks |
|-------|-------|
| **Backend** | New `customer_product_decorations` table (customer_id, product_id, decoration_options JSONB, updated_at) |
| **Backend** | Reuse Phase 1 `OptionIngest` schema for decoration_options shape |
| **Backend** | `GET /api/customers/{id}/products/{product_id}/decorations` |
| **Backend** | `PUT /api/customers/{id}/products/{product_id}/decorations` — upsert decoration options |
| **Backend** | Validation rule: SanMar products require decoration before push (gate in push pipeline) |
| **Backend** | Integration with `master_options` module (if templated approach chosen — see open question) |
| **Frontend** | "Add Decoration" tab on SanMar product detail page |
| **Frontend** | Decoration option editor UI (imprint method, location, color, etc.) |
| **Frontend** | Visual indicator on product card: "Needs Decoration" warning badge |

**Audit note:** The open question (free-form vs templated decorations) must be resolved in spec before any backend or frontend work starts. This is the highest-risk design call in the roadmap.

---

### Phase 8 — Push pipeline polish

| Layer | Tasks |
|-------|-------|
| **Backend** | Push routing in `modules/ops_push/`: branch on `has_decoration_overlay` supplier capability flag |
| **Backend** | Decoration merge: combine base apparel options + `customer_product_decorations` at push time |
| **Backend** | Configurable internal name prefix per (supplier, customer) — store in supplier/customer config |
| **Backend** | Verify `push_mappings` retry path is idempotent (query OPS before re-creating) |
| **Backend** | Handle OPS "already exists" error codes gracefully (query-first or catch + update) |
| **Backend** | Update `customer_product_selections.status` → `pushed` after successful push |
| **Frontend** | Push history view per (customer, product) — renders existing `push_log` data |
| **Frontend** | "Push" button on Customer Catalog product cards (wired to push endpoint) |
| **Frontend** | Push status feedback: in-progress spinner, success toast, error message |

**Audit note:** OPS GraphQL error codes for "product already exists" must be documented before backend push routing is written. Get this from Christian or OPS Postman collection.

---

### Phase 9 — Sync orchestration via n8n

| Layer | Tasks |
|-------|-------|
| **Backend** | Complete DELTA ingest (missing from Phase 2 — `last_synced` delta queries) |
| **Backend** | Ensure `POST /api/suppliers/{id}/import?mode={delta\|full\|closeouts}` covers all modes |
| **Backend** | `last_full_sync` / `last_delta_sync` column updates on successful import |
| **Backend** | Sync status API: `GET /api/suppliers/{id}/sync-status` (last run, error count, throughput) |
| **Backend** | Slack/email alert integration on consecutive failures (webhook or SMTP) |
| **n8n** | Cron workflow template per sync_type (catalog/inventory/pricing/closeouts) |
| **n8n** | Parameterize workflow by supplier_id from DB — one template, not one workflow per supplier |
| **n8n** | Schedule: catalog weekly, inventory hourly, pricing daily, closeouts monthly |
| **Frontend** | Sync dashboard: per-supplier last-success timestamp, error count, throughput table |
| **Frontend** | Alert config UI (optional): where to send failure notifications |

**Audit note:** n8n is its own layer — treat it as "orchestration" separate from frontend/backend. Workflow sprawl is the stated risk; the one-template-parameterized-by-supplier_id pattern must be enforced from the start.

---

### Phase 10 — More suppliers

| Layer | Tasks |
|-------|-------|
| **Backend** | `SSAdapter` — PromoStandards REST, subclass of `PromoStandardsAdapter` from Phase 3 |
| **Backend** | `AlphabroderAdapter` — PromoStandards SOAP, same parent class |
| **Backend** | `FourOverAdapter` — REST + HMAC auth, new auth path in adapter framework |
| **Backend** | DB rows for each supplier (adapter_class, auth_config, endpoint) — no router changes |
| **Backend** | Per-supplier fixture sets in `backend/tests/fixtures/` |
| **Backend** | "How to add a supplier" one-pager in `docs/` |
| **Frontend** | None — existing catalog/push UI works without changes if adapter contract is respected |

**Audit note:** Frontend is a pure free ride here only if each adapter returns the same normalized schema as Phase 1. Verify normalization output in tests before marking complete.

---

### Phase 11 — Image pipeline

| Layer | Tasks |
|-------|-------|
| **Backend** | SanMar FTP image pull script (separate from PS API) |
| **Backend** | S3 upload job — idempotent (skip if `product_images.url` already set to CDN URL) |
| **Backend** | CDN configuration in front of S3 (CloudFront or equivalent) |
| **Backend** | `product_images.url` update after upload — write CDN URL back to DB |
| **Backend** | Color-to-image mapping: `variant.color` → `image.color` match logic |
| **Backend** | Image type taxonomy enforcement: `front \| back \| side \| detail \| lifestyle` |
| **Backend** | Background job runner (Celery task, n8n trigger, or FastAPI BackgroundTask) |
| **Frontend** | Color-aware image display on PDP: clicking color swatch swaps product image |
| **Frontend** | Image type tabs or carousel on PDP: Front / Back / Side / Detail / Lifestyle |

**Audit note:** At ~50-100K images, the pull strategy (bulk vs lazy-pull on first view) must be cost-modeled before any S3 provisioning. This is the biggest cost risk in the roadmap.

---

### Phase 12 — Multi-tenant SaaS

| Layer | Tasks |
|-------|-------|
| **Backend** | Customer auth: email + password (bcrypt) or OAuth (NextAuth / Auth.js compatible) |
| **Backend** | JWT or session token issuance + refresh |
| **Backend** | RBAC middleware: `vg_admin` (all customers) vs `customer_admin` (own only) |
| **Backend** | Scoped query guards on all routes: inject `customer_id` from token |
| **Backend** | Customer onboarding endpoints: signup, verify email, connect OPS storefront |
| **Backend** | Billing integration: Stripe webhook handlers, subscription status check |
| **Backend** | Settings endpoints: update OPS auth, markup rules, supplier toggles per customer |
| **Frontend** | Login / signup pages |
| **Frontend** | Role-based nav: VG admin sees customer switcher; customer admin sees only own data |
| **Frontend** | Customer onboarding wizard UI |
| **Frontend** | Settings page: OPS auth config, markup rule editor, supplier access toggles |
| **Frontend** | Billing / subscription status UI (Stripe Customer Portal embed or custom) |

**Audit note:** Scoping audit required — every existing query in `catalog`, `push_log`, `markup` must be reviewed to confirm `customer_id` filter is applied. Missing one is a data-leak bug.

---

### Phase 13 — Production hardening

| Layer | Tasks |
|-------|-------|
| **Backend** | AWS deployment (follow `2026-04-24-aws-deployment-readiness.md`) |
| **Backend** | Alembic adoption — snapshot prod schema, baseline migration, apply going forward |
| **Backend** | Audit log table + middleware: every write records (user, table, row_id, before, after, timestamp) |
| **Backend** | Rate limiting per customer (FastAPI middleware or API Gateway throttle) |
| **Backend** | Secret rotation: `SECRET_KEY` (Fernet) + `INGEST_SHARED_SECRET` — automated via AWS Secrets Manager |
| **Backend** | Backup strategy: automated RDS snapshots, RPO/RTO targets documented |
| **Backend** | Penetration test findings remediation |
| **Frontend** | Monitoring dashboards: integrate Grafana/Datadog iframe or redirect to dashboard URL |
| **Frontend** | Error boundary pages (500, 403, 404) with actionable messages |
| **Frontend** | (Optional) Admin audit log viewer — searchable table of recent writes |

**Audit note:** Alembic migration from `_SCHEMA_UPGRADES` is the riskiest backend step — take a prod DB snapshot first. Pen test cannot start until Phase 12 auth is complete.

---

## Task Count Summary

| Phase | Backend Tasks | Frontend Tasks | n8n Tasks | Total |
|-------|:---:|:---:|:---:|:---:|
| 6 — Customer Catalog | 5 | 5 | 0 | **10** |
| 7 — Decoration Overlay | 5 | 3 | 0 | **8** |
| 8 — Push Polish | 6 | 3 | 0 | **9** |
| 9 — Sync Orchestration | 5 | 2 | 3 | **10** |
| 10 — More Suppliers | 6 | 0 | 0 | **6** |
| 11 — Image Pipeline | 7 | 2 | 0 | **9** |
| 12 — Multi-Tenant SaaS | 8 | 5 | 0 | **13** |
| 13 — Production Hardening | 8 | 3 | 0 | **11** |
| **TOTAL** | **50** | **23** | **3** | **76** |

> Backend is ~66% of the remaining work. Frontend is ~30%. n8n orchestration is a small but blocking slice in Phase 9.
