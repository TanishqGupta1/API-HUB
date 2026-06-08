# Pending Work — API-HUB

> Snapshot: 2026-06-08. Source: PR review + codebase exploration session.
> Focus is the OPS push pipeline (M1 gateway), which is **not production-ready**.

## Legend
- 🔴 Blocker (gates production) · 🟠 High · 🟡 Medium · ⚪ Debt/cleanup
- **Owner:** OPS = Christian / OnPrintShop side · DEV = our team

---

## 1. Blockers — production push dead until these clear

| # | Item | Owner | Detail |
|---|------|-------|--------|
| 🟡 1.1 | ~~`setProduct` returns `INTERNAL_SERVER_ERROR` on OPS staging for **every** payload~~ — **APPEARS RESOLVED (2026-06-08)** | OPS | Live push of L420 succeeded end-to-end: products_id **#547**, 98/98 mutations OK (1 setProduct + 48 sizes + 48 prices). The earlier 500s were our pre-#166 payload (missing required ProductInput fields / wrong contract), not an OPS resolver bug. Reconfirm with Christian whether anything changed server-side. See `docs/ops-staging-setproduct-issue.md`. |
| 🔴 1.2 | Gateway records OPS `result:false` as `ok` (silent failure) | DEV | `gateway.py` `_invoke` returns `data or {}` with no rejection check. OPS returns HTTP 200 + `result:false` on app-layer rejects → step logged success while data dropped (PC54 phantom id, 558 dropped prices). **Fix lives in unmerged PR #172.** |

---

## 2. Open PR

| # | PR | State | Action needed |
|---|-----|-------|---------------|
| 🟠 2.1 | **#172** (Vidhi) — default category + stock read-back + silent-failure guard | CONFLICTING, no migration | (a) Rebase onto main (conflicts w/ merged #169/#173 in `mutations.py`/`gateway.py`/`payload_builder.py`/`push.py` + 3 tests). (b) **Add Alembic migration** `0012_*` for `Customer.default_ops_category_id` — currently missing, breaks prod `alembic upgrade head`. (c) Resolve stock strategy vs merged #169 (deferred-by-default) — recommend deferral default + read-back behind the flag. Lands the **1.2 silent-failure guard** — highest value. |

---

## 3. Push pipeline feature gaps (on main, behind flags / disabled)

| # | Item | Owner | Detail |
|---|------|-------|--------|
| 🟠 3.1 | Apparel variant model is wrong | OPS + DEV | Uses `setProductSize`; OPS apparel wants `setAdditionalOption` + `setAdditionalOptionAttributes` (ref product 361). Products land but aren't properly shoppable. Plumbing half-built (`OptionStrategy` + builders exist in `payload_builder.py`, not wired for apparel). Needs Christian's confirm, then flip strategy. See `docs/backlog-ops-additional-options.md`. |
| 🟡 3.2 | Images OFF by default (`OPS_PUSH_INCLUDE_IMAGES=0`) | OPS + DEV | OPS GraphQL can't ingest image binaries — stores `products_large_image_name` string verbatim, never fetches URLs; no upload mutation; `/api/*` is GraphQL-only (no REST upload). Enable only once images uploaded into OPS media (admin URL-fetch or an upload API). |
| 🟡 3.3 | Stock OFF by default (`OPS_PUSH_INCLUDE_STOCK=0`) | DEV | OPS `updateProductStock` needs `stock_id`; OPS has no per-size SKU field + no API to create initial stock entries (admin must init via UI). #172's read-back resolves `stock_id` from a `productStocks` query — land behind the flag. |
| 🟡 3.4 | Wire `verify_pushed_product()` into gateway finalize | DEV | `modules/ops_push/verify.py` (merged via #173) is standalone. Wire into push-finalize so push status reflects what actually persisted in OPS, not mutation acks (B7). |

---

## 4. Tech debt — safe deletes / consolidation (no OPS dependency)

| # | Item | Detail |
|---|------|--------|
| ⚪ 4.1 | Delete legacy push path | **PARTIALLY DONE (2026-06-08):** deleted orphaned `modules/ops_client/push.py` (`push_apparel_product`, zero prod callers) + `tests/test_ops_client_push.py`; suite stays green (350 passed). **Remaining:** the `mutations.py` wrapper fns are NOT all dead — `get_product_by_sku` is live in `gateway.py` (dedup/verify) + `verify.py`. M1 gateway uses raw `_SET_*` query consts for the rest. Per-fn dead-code pass needed before removing the remaining wrappers + their `test_ops_mutations.py` cases; keep the query consts and `get_product_by_sku`. |
| ⚪ 4.2 | Consolidate duplicate `FakeOpsClient` | Two doubles: `ops_client/fake.py` (tests) + inline `gateway.py:211` (dry-run). They drift. Unify. |
| ⚪ 4.3 | Single-source the n8n node tree | `api-hub/n8n-nodes-onprintshop/` AND `../n8n-nodes-onprintshop/` both exist → drift risk. Symlink or submodule. |
| ⚪ 4.4 | Decide fate of n8n OnPrintShop node | Post-M1 pivot, OPS push is FastAPI-owned. Node's ops now duplicate gateway intent ("legacy flows" only). Archive or keep as documented fallback — don't dual-maintain. |

---

## 5. Process / infra

| # | Item | Detail |
|---|------|--------|
| 🟡 5.1 | No issue tracking | `gh issue list` is empty. File issues for §1–§3 so the team has a board. |
| 🟡 5.2 | REST delta-sync deferred | S&S + 4Over `discover_changed` fall back to full re-fetch. Optimize when volume justifies (not a blocker). |
| ⚪ 5.3 | Local DB not runnable here | api-hub Postgres can't start on this machine — port 5432 held by an unrelated project (`clarity-v2`). No api-hub pgdata volume exists. Push logs live on whatever env ran the pushes (remote/staging or a teammate), not locally. |

---

## Recommended sequence
1. **Chase 1.1** (OPS `setProduct` 500) — everything downstream is dead without it.
2. **Land #172** (rebase + migration + stock decision) → closes 1.2 silent-failure guard.
3. **Confirm 3.1** apparel model with Christian → flip `OptionStrategy`.
4. **Clear debt** 4.1–4.3 (cheap, local, removes the #173-style confusion).
5. **File issues** (5.1) so this list lives on the board, not just here.

---

## Recently shipped (this session — for context)
- #174 merged — ops-config authz dedupe + docstring fix.
- #169 merged — lazy-image removal, 4Over button, SafeImage, OAuth token flow, `adapter.execute` dedup fix, CI gate (Postgres + alembic), image gallery (deferred), stock (deferred).
- #173 merged — `price_defining_method` on M1 price step (live price fix), float coercion, `verify.py`.
- #175 closed — duplicate of #169.
