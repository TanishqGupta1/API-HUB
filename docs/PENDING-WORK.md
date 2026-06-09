# Pending Work — API-HUB

> Snapshot: 2026-06-08 (updated). Source: PR review + codebase exploration session.
> Focus is the OPS push pipeline (M1 gateway), which is **not production-ready**.

## Legend
- 🔴 Blocker (gates production) · 🟠 High · 🟡 Medium · ⚪ Debt/cleanup
- **Owner:** OPS = Christian / OnPrintShop side · DEV = our team

---

## 1. Blockers — production push dead until these clear

| # | Item | Owner | Detail |
|---|------|-------|--------|
| ✅ 1.1 | ~~`setProduct` returns `INTERNAL_SERVER_ERROR` on OPS staging~~ | OPS + DEV | **Resolved 2026-06-09.** Root cause was payload-shape gaps on our side, not an OPS server bug: missing required fields on `setProduct` (`enable_stock_management`, `product_type`) and on `setAdditionalOption` (`price_calculate_type`, `hire_designer_option`, `applicable_for`). After adding them, 5 live products (552–556) pushed cleanly to OPS staging via the gateway. |
| ✅ 1.2 | ~~Gateway records OPS `result:false` as `ok` (silent failure)~~ | DEV | Fixed in #172 + #177. `_invoke` now checks `result:false` and raises. `_check_result` + `TestCheckResult` unit tests added. Silent-failure guard closed. |

---

## 2. Open PRs

| # | PR | State | Notes |
|---|-----|-------|-------|
| ✅ 2.1 | **#172** (Vidhi) — default category + stock read-back + silent-failure guard | **MERGED** | Conflicts resolved, migration 0012 added, stock read-back behind `OPS_PUSH_INCLUDE_STOCK` flag. |
| ✅ — | **#177** — dead-code cleanup, verify wiring, migration 0012 | **MERGED** | Deleted `push.py` + orphaned wrapper fns, wired `_verify_b7_readback`, CI green. |

---

## 3. Push pipeline feature gaps (on main, behind flags / disabled)

| # | Item | Owner | Detail |
|---|------|-------|--------|
| 🟠 3.1 | Apparel variant model is wrong | OPS + DEV | Uses `setProductSize`; OPS apparel wants `setAdditionalOption` + `setAdditionalOptionAttributes` (ref product 361). Products land but aren't properly shoppable. Plumbing half-built (`OptionStrategy` + builders exist in `payload_builder.py`, not wired for apparel). Needs Christian's confirm, then flip strategy. See `docs/backlog-ops-additional-options.md`. |
| 🟡 3.2 | Images OFF by default (`OPS_PUSH_INCLUDE_IMAGES=0`) | OPS + DEV | OPS GraphQL can't ingest image binaries — stores `products_large_image_name` string verbatim, never fetches URLs; no upload mutation; `/api/*` is GraphQL-only (no REST upload). Enable only once images uploaded into OPS media (admin URL-fetch or an upload API). |
| 🟡 3.3 | Stock OFF by default (`OPS_PUSH_INCLUDE_STOCK=0`) | DEV | OPS `updateProductStock` needs `stock_id`; stock read-back via `productStocks` query is implemented (#172) and live behind the flag. Enable once OPS admin initialises stock entries for variants via UI. |
| ✅ 3.4 | ~~Wire `verify_pushed_product()` into gateway finalize~~ | DEV | Done in #177. `_verify_b7_readback` wired into `execute_push` finalize step. |

---

## 4. Tech debt — safe deletes / consolidation (no OPS dependency)

| # | Item | Detail |
|---|------|--------|
| ✅ 4.1 | ~~Delete legacy push path~~ | Done in #177. `push.py` deleted, 12 orphaned wrapper fns removed, query consts kept. |
| ✅ 4.2 | ~~Consolidate duplicate `FakeOpsClient`~~ | Done. Inline class removed from `gateway.py`; `ops_client/fake.py` is now the single canonical source with `is_dry_run` sentinel + full `execute()` routing. |
| ⚪ 4.3 | Single-source the n8n node tree | `api-hub/n8n-nodes-onprintshop/` AND `../n8n-nodes-onprintshop/` both exist → drift risk. Symlink or submodule. |
| ✅ 4.4 | ~~Decide fate of n8n OnPrintShop node~~ | Done by Sinchana (#168). Documented as legacy fallback; FastAPI gateway is the primary OPS push path. |

---

## 5. Process / infra

| # | Item | Detail |
|---|------|--------|
| ✅ 5.1 | ~~No issue tracking~~ | Done by Sinchana — issues filed on GitHub board. |
| ✅ 5.2 | ~~REST delta-sync deferred~~ | Done in #178 — `discover_changed` in `ss_adapter.py` + `fourover_adapter.py` now filters the full ref list against `Product.last_synced > since` before hydrating; APIs have no modified-since endpoint so full discovery is still needed, but hydration is skipped for fresh products. |
| — | 5.3 | Not actionable — local port conflict on the audit machine (5432 held by `clarity-v2`). No action needed. |

---

## Recommended next steps
1. **Merge PR #179** — FakeOpsClient consolidation + Phase 5 step resumption + default_ops_category_id UI + setProduct-500 repro script. Scope was narrowed per review (Phase 8 apparel rewrite split off into a dedicated PR).
2. **3.1 apparel-model PR** — confirm with Christian, sign off APPAREL_VOLUME_TIERS as pricing policy, then land Phase 8 + 6-tier curve as its own PR. Phase 8 commit (`0612991`) preserved in git history for the cherry-pick.
3. **Auto stale-mapping cleanup** — pre-check OPS for product existence before UPDATE mode; auto-clear stale mapping and fall back to CREATE. Removes the manual SQL we ran ~5× during today's testing.
4. **Hold** on 3.2 / 3.3 — gated on Christian's answers (image-fetch path, stock-init API).

---

## Shipped (closed this sprint)
- ✅ #178 merged — REST delta-sync optimisation + tech-debt closure (4.4, 5.1, 5.2)
- ✅ #172 merged — default category + stock read-back + silent-failure guard
- ✅ #177 merged — dead-code cleanup (`push.py`), B7 verify wiring, migration 0012
- ✅ #174 merged — ops-config authz dedupe + docstring fix
- ✅ #173 merged — `price_defining_method` on M1 price step, float coercion, `verify.py`
- ✅ #169 merged — lazy-image removal, 4Over button, SafeImage, OAuth token flow, dedup fix, CI gate
- ✅ #168 merged — Sinchana: n8n node fate decision, issue tracking
