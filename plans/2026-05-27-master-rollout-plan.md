# Master Rollout Plan — Combine Security, PRs, Stabilization, Features

**Date:** 2026-05-27
**Author:** review + planning pass (Claude)
**Inputs:** project-state inventory, failure-point analysis, the 4 open PR reviews (#142/#138/#137/#136).

Goal: one coherent sequence that fixes the security blockers, lands the 4 open PRs, hardens the foundation, and only then ships features — ordered so each step unblocks the next instead of fighting it.

---

## 1. Why the tracks can't be done independently (the implications)

The four "tracks" I offered are entangled. Doing them in parallel re-introduces the same defects three times. The couplings:

- **`register → vg_admin` escalation lives in three PRs at once** (#138, #137, #136). If each PR fixes it its own way (or doesn't), we get merge conflicts and an inconsistent role policy. → **Fix the auth/role policy ONCE, on a base branch, before the PRs land. Everything rebases onto it.**
- **Tenant isolation (IDOR)** must be a single reusable ownership dependency. PR #136's portal already does tenant scoping correctly — that is the pattern to extract and apply everywhere. → **Build the guard once; #136 is the reference implementation.**
- **Portal is split across two PRs:** #136 *creates* `modules/portal` but never mounts it; #137 *imports* it and crashes because on its branch the module doesn't exist. → **They must land in order #136 → #137, both on the hardened base.**
- **SSE / real-time appears twice and contradictorily:** #138 *adds* an SSE endpoint; #142 *reverts* SSE→polling. Plus the Redis eval says a multi-instance backplane is needed for either. → **Decide the real-time strategy once** (don't add SSE in one PR while another rips it out).
- **Schema drift compounds:** `create_all` runs before `alembic upgrade` every boot, so missing migrations (`integration_keys`, `app_settings`, `customers.logo_url`) stay invisible until a fresh DB. #138 adds *another* unmigrated table (`app_settings`). → **Author the missing migrations before more schema-changing PRs merge.**
- **CI gate is non-blocking** (`pytest … || true`). Until that's fixed, none of the above is actually verified by merge. → **Make CI blocking early, or every later phase ships on faith.**
- **Token re-mint** (fresh OPS client per push) gets worse the moment the M1 query layer adds more calls. → **Redis token cache should precede heavy query/feature work.**

Net: there's a forced order. Foundation first, then portal, then the grab-bag PR, then real-time, then features.

---

## 2. Phase sequence

### Phase A — Hardening base branch `harden/auth-foundation` (do first, blocks all PRs)
A small, security-reviewed branch off `main` that the contributor PRs rebase onto.

- [ ] **Role policy, fixed once:** public `/api/auth/register` no longer mints `vg_admin`. Least-privilege default (`UserCreate.role` already defaults to `customer_admin`, `schemas.py:42`). `vg_admin` only via genuine zero-users bootstrap (`/setup`). Add `@limiter.limit` to `register` and `setup`.
- [ ] **`signup-status` hardening:** authenticated or coarse-grained; stop advertising the bootstrap window; index the `COUNT(*)`.
- [ ] **Tenant-ownership dependency:** extract a reusable `require_customer_access(customer_id)` FastAPI dependency (model it on #136's portal scoping). Apply to every `customer_id`-in-URL/body route in `customer_catalog`, `customers`, `markup`, `ops_config`, `decorations`, `pricing`.
- [ ] **Dead rate limiter:** `await _check_rate_limit(key)` (`integrations/auth.py:89`); hold a ref to the fire-and-forget `_update_last_used` task; narrow the bare `except`.
- [ ] **Missing migrations:** author Alembic revisions for `integration_keys`, `app_settings`, `customers.logo_url` so the chain matches the models. Stop relying on `create_all` to paper over drift.
- [ ] **CI gate blocking:** drop `|| true` in `deploy-dev.yml`; fail the build on test failure. Add a frontend lint/test job.
- **Exit:** branch green on blocking CI, security-reviewed (separate reviewer pass), merged to `main`.

### Phase B — Customer portal (combine #136 → #137, rebased on A)
- [ ] **#136 first:** mount the portal router in `main.py` (currently defined but never included → all portal endpoints 404). Keep its (correct) tenant scoping. Drop its register-role change (now handled in A).
- [ ] **#137 second:** remove the bare `from modules.portal …` top-level import crash; rebase so portal exists from #136. Keep the genuinely-good bits (refresh-token UUID validation, batch-push error redaction, dashboard states). Fix duplicate sidebar React keys, batch-push polling overlap, `Promise.allSettled`.
- [ ] Tests: portal tenant-isolation (A-cannot-read-B), register bootstrap-vs-signup-vs-closed.
- **Exit:** portal reachable, tenant-isolated, tested; #136 + #137 merged.

### Phase C — Decompose #138 (rebased on A; the +31.8k/102-file grab-bag)
Split per its own review; the register/`AppSetting` piece is already solved in A.
- [ ] **C1 — clean frontend fixes** (`next/image` patterns, login-error envelope, lint): merge.
- [ ] **C2 — n8n proxy, done right:** actually register the `n8n_proxy` router in `main.py` (the PR's titular fix is currently missing). Decide whether the n8n-compose removal + Workflows-page deletion are intended; if not, revert them.
- [ ] **C3 — SSE endpoint:** only if Phase D keeps SSE; add a connection-lifetime cap + bounded session use (current `while True` per client exhausts the pool).
- [ ] **C4 — committed `dist/**` artifacts:** `.gitignore` them.
- **Exit:** #138 closed; its value landed as 3–4 small reviewed PRs.

### Phase D — Real-time strategy decision (resolves #142 ↔ #138 conflict)
- [ ] Decide: SSE vs polling vs WebSocket for sync-job/push status. Debug *why* #142 reverted SSE→polling before re-adding SSE anywhere.
- [ ] Fix #142's Alembic blocker so it can merge; land its push/sync bug fixes + in-app alerting.
- [ ] If multi-instance (ECS DesiredCount>1): real-time needs a **Redis backplane** — fold into Phase E.
- **Exit:** one real-time approach, #142 merged.

### Phase E — Features + infra (only after foundation is solid)
- [ ] **Redis adoption** (per the eval): shared rate-limiter, OPS token cache, scheduler distributed-lock. Fixes the token re-mint before query load grows.
- [ ] **n8n node:** add the one missing mutation `setProductsImageGallery` (plan: `2026-05-27-ops-node-mutation-coverage.md`).
- [ ] **M1 query layer** in `ops_client` (read-back verification + pre-push dedup lookup → fixes duplicate-on-retry).
- [ ] **Markup UI** (currently a stub) + other STUB admin pages as prioritized.
- [ ] **arq** Redis-backed durable queue for push/sync (replaces lossy `asyncio.create_task`).
- [ ] Doc refresh: `OPS-NODE-GAP-ANALYSIS.md` + CLAUDE.md stale "22/33" line.

---

## 3. PR disposition

| PR | Author | Now | Disposition |
|---|---|---|---|
| **#136** customer-portal | sinchana | defined-but-unmounted; register escalation | Rebase on A (drop register change), mount router → **merge in Phase B (first)** |
| **#137** phase8-admin-ux | sinchana | crashes boot (portal import); register escalation | Rebase on A + B, fix import + nav keys + polling → **merge in Phase B (second)** |
| **#138** register/n8n/etc | urvashi | +31.8k/102f mislabeled; vg_admin factory; titular fix missing | **Close, split into C1–C4**; register/AppSetting already in A |
| **#142** alerting + bug fixes | vidhi | Alembic blocker; reverts SSE | Fix migration; resolve in Phase D → **merge** |

---

## 4. Risk & sequencing notes
- **Phase A is load-bearing.** Nothing else merges until the role policy + tenant guard + migrations + blocking CI are in. This is the single highest-leverage step.
- **Communicate to contributors** (sinchana, urvashi, vidhi): their branches will rebase onto `harden/auth-foundation`; the register-role change is being centralized, so they should drop their local versions.
- **Don't double-build real-time** — Phase D decides before Phase C3/E touch SSE.
- **Reviewer separation:** the security fixes in A need a distinct reviewer pass (not self-approved).
- Production deploy stays paused until Phase A + B land (escalation + IDOR are live-exploitable).

---

## 5. First action
Start **Phase A** on a fresh `harden/auth-foundation` branch:
1. `await _check_rate_limit` one-liner (trivial, isolated).
2. Register role-policy fix + rate limits.
3. Tenant-ownership dependency + apply to the IDOR routes.
4. Three missing migrations.
5. CI `|| true` removal.
Each as its own commit; push branch; open PR; request security review; then begin rebasing #136.
