# Plan — Green `main` + PR CI Gate + Branch Protection

**Date:** 2026-06-04
**Author:** Tanishq (PM/Tech Lead)
**Trigger:** PR #168 merged with 9 failing `test_payload_builder.py` tests. Root cause: no PR test gate, `main` unprotected, full suite not run pre-merge.

## Background / evidence

- #168 changed `payload_builder._build_setProduct_step` to the real OPS schema:
  `category_name` → `category_id` (Int, from `storefront_config.ops_category_id`, omitted when unmapped),
  `products_image` → `imagename`, dropped the `"Uncategorized"` fallback.
- It updated `test_preflight.py` and `test_gateway_inline_push_db.py` but **not** `test_payload_builder.py`.
- Verified **no prod bug**: `ProductStorefrontConfig` model HAS `ops_category_id` (`modules/ops_config/models.py:36`). Production passes a real ORM object; the builder code is correct.
- The 9 failures are **test-only**:
  - 5× `TestStorefrontOverridesInPush` → `AttributeError: 'types.SimpleNamespace' object has no attribute 'ops_category_id'` (test `_cfg()` helper builds a `SimpleNamespace` missing the attr; builder reads `ctx.storefront_config.ops_category_id`).
  - 4× stale assertions on the old `category_name` / `Uncategorized` / `products_image` contract.
- `arq` failures locally were env-only (`arq>=0.26.0` IS in `requirements.txt`; venv was stale). Queue suite passes once installed (13 passed).
- CI gap: only `deploy.yml` / `deploy-dev.yml` (deploy-time). No `pull_request` pytest/lint gate. `main` is **not** branch-protected.

---

## Phase A — Hotfix the 9 stale tests (test-only, no prod code)

**Branch:** `fix/payload-builder-tests-ops-schema`
**File:** `backend/tests/test_payload_builder.py`

### A1. `_cfg()` helper (fixes the 5 override tests)
The helper at the top of `TestStorefrontOverridesInPush` (≈ line 818) builds a `SimpleNamespace` with `pricing_overrides` only. Add `ops_category_id=None` so the namespace matches the real model shape the builder reads.

```python
# in _cfg(...)
return SimpleNamespace(pricing_overrides=overrides, ops_category_id=None)
```
Expected: all 5 `TestStorefrontOverridesInPush` tests green (builder hits `ctx.storefront_config.ops_category_id` → None → category omitted, price logic unchanged).

### A2. `test_single_front_image` (≈ line 582)
```python
-        assert setProduct.variables["input"]["products_image"] == "https://x/front.jpg"
+        assert setProduct.variables["input"]["imagename"] == "https://x/front.jpg"
```

### A3. `test_no_images` (≈ line 616) — clarity, currently passes
```python
-        assert "products_image" not in setProduct.variables["input"]
+        assert "imagename" not in setProduct.variables["input"]
```

### A4. `test_no_setProductCategory_step` (≈ line 395)
Default `_ctx` has `storefront_config=None` → category omitted. Update to the new contract:
```python
         assert not any(s.mutation == "setProductCategory" for s in payload.plan)
         setProduct = payload.plan[0]
-        # Category lives on setProduct.input instead.
-        assert "category_name" in setProduct.variables["input"]
+        # Category lives on setProduct.input as category_id (Int), and is omitted
+        # when no storefront mapping is configured (default ctx has none).
+        assert "category_name" not in setProduct.variables["input"]
+        assert "category_id" not in setProduct.variables["input"]
```

### A5. `test_category_name_present_in_set_product` (≈ line 755) → rename `test_category_id_present_when_mapped`
```python
    def test_category_id_present_when_mapped(self):
        """setProduct.input.category_id is the mapped OPS category (Int)."""
        ctx = _ctx(
            variants=[_variant("PC61-WHT-M")],
            product=_product(category="T-Shirts"),
            storefront_config=SimpleNamespace(pricing_overrides=None, ops_category_id="42"),
        )
        payload = _synthesize_payload(ctx)
        assert payload.plan[0].variables["input"]["category_id"] == 42
```
(Confirm `_ctx` accepts `storefront_config=` — it does, line 212/231. Import `SimpleNamespace` already used by `_cfg`.)

### A6. `test_category_falls_back_to_uncategorized` (≈ line 769) → rewrite `test_category_omitted_when_unmapped`
```python
    def test_category_omitted_when_unmapped(self):
        """No storefront mapping → no category_id in setProduct (no 'Uncategorized' fallback)."""
        ctx = _ctx(variants=[_variant("PC61-WHT-M")], product=_product(category=None))
        payload = _synthesize_payload(ctx)
        assert "category_id" not in payload.plan[0].variables["input"]
        assert "category_name" not in payload.plan[0].variables["input"]
```

### A7. Verify
```bash
cd backend && source .venv/bin/activate
pip install -r requirements.txt          # ensure arq etc. present
python -m pytest tests/test_payload_builder.py -q        # expect 61 passed
python -m pytest -q                                       # full suite (DB tests need postgres up)
```
- DB-backed tests (`test_gateway_inline_push_db.py`) need `docker compose up -d postgres`. Run before claiming full green.

### A8. Merge
Squash-merge `fix/payload-builder-tests-ops-schema` → `main`. Conventional title:
`test(payload-builder): align with OPS schema (category_id/imagename) — fixes red main`

---

## Phase C — PR test CI

**Branch:** `ci/pr-test-gate`
**File (new):** `.github/workflows/ci.yml`
**Trigger:** `on: pull_request: { branches: [main] }` (+ `push: { branches: [main] }` for post-merge signal).

### C1. Backend job
- `services: postgres:16` (env: `POSTGRES_USER/PASSWORD/DB` matching `POSTGRES_URL`), health-check.
- steps: checkout → `actions/setup-python@v5` (3.12) → `pip install -r backend/requirements.txt` → set `POSTGRES_URL`/`SECRET_KEY`/`INGEST_SHARED_SECRET` env → **`cd backend && alembic upgrade head`** → `cd backend && python -m pytest -q`.

> **Amendment (2026-06-05):** the original C1 omitted the schema-build step and
> CI failed with `relation "customers" does not exist`. A fresh CI Postgres is
> empty, and `conftest.py`'s `create_all` runs too late — the autouse
> `_cleanup_around_test` fixture issues `DELETE FROM customers` before
> `_create_schema` runs. The local suite only passed because the dev DB was
> pre-built (alembic + create_all). **Fix:** run `alembic upgrade head` (reads
> `POSTGRES_URL`, applies all 11 migrations) before pytest. Validated against a
> fresh DB: migrations + create_all → DB-backed tests green.

### C2. Frontend job
- checkout → `actions/setup-node@v4` (Node 20) → `cd frontend && npm ci` → `npm run lint` → `npm run build`.
- Provide build-time `NEXT_PUBLIC_API_URL` dummy env so `npm run build` doesn't fail.

### C3. Verify
- Open the PR; confirm both jobs run and pass on green code. Push a deliberately broken test to confirm the check goes red (then revert).
- Note the exact check job names (e.g. `backend-tests`, `frontend-build`) — needed for Phase D.

### C4. Merge
Squash-merge `ci/pr-test-gate` → `main`.

---

## Phase D — Branch protection on `main`

**After C is on `main` and the check has run at least once** (so GitHub knows the context names).

```bash
gh api -X PUT repos/VisualGraphxLLC/API-HUB/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f "required_status_checks[strict]=true" \
  -f "required_status_checks[contexts][]=backend-tests" \
  -f "required_status_checks[contexts][]=frontend-build" \
  -F "enforce_admins=false" \
  -F "required_pull_request_reviews=null" \
  -F "restrictions=null"
```
- **Decision (D):** `required_pull_request_reviews=null` → require the **passing CI check only, 0 required reviewers** (Tanishq is often sole reviewer; requiring a review would self-block). **Toggle:** to require 1 review later, set `required_pull_request_reviews[required_approving_review_count]=1`.
- `enforce_admins=false` → admin can still force-merge in a real emergency.
- Replace `backend-tests`/`frontend-build` with the actual job names from C3.

### D1. Verify
- `gh api repos/VisualGraphxLLC/API-HUB/branches/main/protection --jq .required_status_checks` → contexts present, `strict: true`.
- Open a throwaway PR with a failing test → confirm merge button is blocked until the check passes.

---

## Done criteria
- [ ] `main` full pytest suite green (postgres up) + frontend `lint`/`build` clean.
- [ ] `ci.yml` runs on every PR; red tests block visibly.
- [ ] `main` protection requires the CI check; merging over red is blocked for non-admins.

## Out of scope (follow-ups)
- PR #169 rebase + 2 HIGH regressions (separate review already commented).
- Adding `arq`/redis service depth to CI beyond what the queue tests mock.
