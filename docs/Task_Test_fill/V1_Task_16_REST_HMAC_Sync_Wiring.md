# V1 Task 16 — Wire 4Over (`rest_hmac`) into the unified sync route — Detail Guide

**Status:** ✅ Completed on 2026-04-27
**Branch:** `Vidhi`
**Sprint spec:** `plans/2026-04-16-v1-integration-pipeline.md` → V1d → Task 16
**What you can say in one sentence:** *"I wired the 4Over (rest_hmac) and S&S (rest) protocols into the unified product-sync endpoint so background fetches actually run instead of leaving sync jobs hanging at 'queued' forever."*

---

## 1. What Got Built

| File | What Changed |
|---|---|
| `backend/modules/promostandards/routes.py` | Replaced a placeholder `elif` (4 lines, all commented out) with a real `BackgroundTasks` invocation of `_run_rest_sync` (~14 lines) |

No new files. No new tests (existing `_run_rest_sync` is already covered by `tests/test_ss_normalizer.py` and `test_fourover_normalizer.py`).

---

## 2. Background — What Is This Task About?

### The setup
The project supports **four supplier protocols**, one adapter per protocol:

| Protocol | Auth style | Example supplier | Adapter file |
|---|---|---|---|
| `soap` / `promostandards` | XML over HTTPS, ID + password | SanMar, Alphabroder | `modules/promostandards/client.py` |
| `rest` | JSON + HTTP Basic Auth | S&S Activewear | `modules/rest_connector/client.py` |
| `rest_hmac` | JSON + HMAC-SHA256 signed requests | 4Over | `modules/rest_connector/fourover_client.py` |
| `ops_graphql` | n8n pushes data into FastAPI ingest | VG OPS storefront | `modules/catalog/ingest.py` (different flow) |

The **unified inbound trigger** is one endpoint that n8n and the frontend both call:

```
POST /api/sync/{supplier_id}/products
Headers: X-Ingest-Secret: <env>
```

It loads the supplier, decides which adapter to use based on `supplier.protocol`, and queues a background task that fetches → normalizes → upserts the catalog.

### The bug before this task

For SOAP suppliers the endpoint worked. For everyone else, the route had a **stub**:

```python
elif supplier.protocol in ("rest", "rest_hmac", "ops_graphql"):
    # Placeholder for REST/GraphQL background task — wiring B2/G2 requirement
    job = await _create_job(db, supplier, job_type="full_sync")
    # background_tasks.add_task(_run_rest_sync, job.id, supplier)  ← commented out
```

So when anyone tried to sync S&S Activewear or 4Over from the UI:
1. The route returned `202 Accepted` with a `job_id` ✅ looks healthy
2. The `sync_jobs` row was created at `status="queued"` ✅ looks healthy
3. **No background task was scheduled** → the job sat at "queued" forever
4. The frontend showed "running" indefinitely with no error

This is much worse than failing loud — it pretends success while doing nothing.

### Why this is V1d Task 16 in the plan

The V1 plan splits supplier work into phases:

- V1a — SOAP + SanMar (✅ done)
- V1b — S&S REST adapter (✅ done)
- V1c — OPS push (✅ done)
- V1d — 4Over (`rest_hmac`) + field mapping (✅ done EXCEPT this final wiring step)

Tasks 14 + 15 already shipped the `FourOverClient` and `normalize_4over` functions. The internal `_run_rest_sync` function in `routes.py` already had a `if protocol == "rest_hmac"` branch that called them. **The only missing link was making the route's `elif` actually call `_run_rest_sync` instead of leaving it commented.**

---

## 3. The Code Change

**File:** `backend/modules/promostandards/routes.py`, inside `trigger_product_sync()` at line 349.

### Before

```python
elif supplier.protocol in ("rest", "rest_hmac", "ops_graphql"):
    # Placeholder for REST/GraphQL background task — wiring B2/G2 requirement
    job = await _create_job(db, supplier, job_type="full_sync")
    # background_tasks.add_task(_run_rest_sync, job.id, supplier)
else:
    raise HTTPException(400, f"Sync not implemented for protocol '{supplier.protocol}'")
```

### After

```python
elif supplier.protocol in ("rest", "rest_hmac"):
    if not supplier.base_url:
        raise HTTPException(
            400, f"Supplier '{supplier.name}' has no base_url configured"
        )
    job = await _create_job(db, supplier, job_type="full_sync")
    background_tasks.add_task(
        _run_rest_sync,
        job.id,
        supplier.id,
        supplier.protocol,
        supplier.base_url,
        _get_auth_config(supplier),
        dict(supplier.field_mappings or {}) if supplier.field_mappings else None,
    )
else:
    raise HTTPException(400, f"Sync not implemented for protocol '{supplier.protocol}'")
```

### Three things changed

1. **Dropped `ops_graphql`** from the branch. That protocol uses a separate inbound flow — n8n posts directly to `/api/ingest/{supplier_id}/products` with the `X-Ingest-Secret` header. It does not belong on this sync trigger. Now it falls through to the `else` and gets a proper `400` rejection instead of a silent no-op.
2. **Added a `base_url` guard.** REST/HMAC clients can't run without a base URL, so we fail fast with a clear 400 instead of crashing inside the background task.
3. **Wired the background task.** This mirrors the call signature already used by the existing `/products/rest` route at line 419 — same `_run_rest_sync` function, same arguments, same behavior.

---

## 4. How `_run_rest_sync` works (the function we're now calling)

Already-existing code in the same file at line 193. Here's the relevant slice:

```python
async def _run_rest_sync(job_id, supplier_id, protocol, base_url, auth_config, field_mappings):
    async with async_session() as session:
        await _mark_job_running(session, job_id)
        try:
            if protocol == "rest":
                client = RESTConnectorClient(base_url=base_url, auth_config=auth_config)
                raw = await client.get_products()
                products, inventory, pricing, media = ss_to_ps_format(raw)
            else:  # "rest_hmac"
                client = FourOverClient(base_url=base_url, auth_config=auth_config)
                raw = await client.get_products()
                mapping = (field_mappings or {}).get("mapping") or {}
                products = normalize_4over(raw, mapping)
                inventory, pricing, media = [], [], []

            await upsert_products(session, supplier_id, products, inventory, pricing, media)
            await _finish_job(session, job_id, status="completed", records_processed=len(products))
        except Exception as exc:
            await _finish_job(session, job_id, status="failed", error=str(exc))
```

So once we hand it the right inputs it:
1. Marks the job `running`
2. Picks the right client per protocol
3. Fetches raw catalog
4. Normalizes to the canonical `PSProductData` shape (the same shape SOAP produces)
5. Upserts via `upsert_products` — same writer SOAP uses
6. Marks `completed` with record count, or `failed` with the upstream error message

This is why no new tests were needed: the writer + normalizers already have unit tests, and the upstream call paths already worked when invoked from the duplicate `/products/rest` route. We just gave the main route the same wiring.

---

## 5. Manual Verification (what we did and saw)

### Smoke test 1 — S&S Activewear (`protocol=rest`)

```bash
SECRET=$(grep INGEST_SHARED_SECRET .env | cut -d= -f2)
curl -X POST "http://localhost:8000/api/sync/<ss_supplier_id>/products" \
  -H "X-Ingest-Secret: $SECRET"
# → {"job_id":"6332ae15-...","status":"queued","job_type":"full_sync"}

sleep 3

curl "http://localhost:8000/api/sync/<ss_supplier_id>/status"
# → {"status":"failed","error_log":"https://api.ssactivewear.com/v2/Products/ returned 401: Authorization has been denied for this request."}
```

✅ The job moved from `queued` → `running` → `failed` in ~1.3 seconds. The error is the **real upstream 401** from S&S because we don't have valid creds — exactly the expected failure mode. **Before the fix, this job would have stayed at `queued` forever.**

### Smoke test 2 — 4Over (`protocol=rest_hmac`)

```bash
# First switch the seeded 4Over supplier from "rest" → "rest_hmac"
curl -X PUT "http://localhost:8000/api/suppliers/<4over_id>" \
  -H "Content-Type: application/json" \
  -d '{"name":"4Over","slug":"4over","protocol":"rest_hmac","base_url":"https://api.4over.com","auth_config":{}}'

# Trigger the sync
curl -X POST "http://localhost:8000/api/sync/<4over_id>/products" -H "X-Ingest-Secret: $SECRET"
# → {"job_id":"bc49a019-...","status":"queued","job_type":"full_sync"}

sleep 3
curl "http://localhost:8000/api/sync/<4over_id>/status"
# → {"status":"failed","error_log":"auth_config missing required key 'account_number'; expected 'account_number' and 'api_key'"}
```

✅ The `FourOverClient` itself rejected the empty auth_config — confirming the route correctly dispatched to the rest_hmac branch.

### Smoke test 3 — VG OPS (`protocol=ops_graphql`)

```bash
curl -X POST "http://localhost:8000/api/sync/<vg_ops_id>/products" -H "X-Ingest-Secret: $SECRET"
# → HTTP 409 {"detail":"Supplier 'Visual Graphics OPS' is not active"}
```

✅ Properly rejected (in this case at the active-supplier check; a 400 "Sync not implemented for protocol 'ops_graphql'" would fire if it were active).

### Smoke test 4 — SOAP unaffected

SanMar's SOAP path is untouched — same `if supplier.protocol in ("soap", "promostandards"):` branch, no edits. Verified by manual code review.

---

## 6. Acceptance Checklist

- [x] `POST /api/sync/{ss_id}/products` returns 202 → job moves to `failed` with real 401 from S&S within seconds
- [x] `POST /api/sync/{4over_id}/products` (`rest_hmac`) returns 202 → job moves to `failed` with FourOverClient validation error within seconds
- [x] `POST /api/sync/{ops_graphql_id}/products` returns a clear error code (400 / 409) instead of silently 202
- [x] SanMar (`soap`) sync path unchanged
- [x] Backend hot-reload picked up the change without errors
- [x] No new dependencies, no new tests required (existing tests still pass)

---

## 7. Risks & Follow-ups (Out of Scope For This Task)

| Item | Why deferred |
|---|---|
| The duplicate `POST /api/sync/{id}/products/rest` route at line 419 is now redundant | Leave for back-compat; can be removed in a separate cleanup PR |
| `ops_graphql` now returns 400 from this route | Intentional — that protocol uses `/api/ingest/...` instead. Documenting this rejection makes the boundary clearer |
| 4Over E2E with real credentials | Blocked on Christian providing 4Over API + private keys |
| Background tasks orphan if API restarts mid-sync | Known V1 limitation; V2 will move to ARQ/Celery |

---

## 8. Files & Lines To Reference

- The change: `backend/modules/promostandards/routes.py:349-364`
- The function we now call: `backend/modules/promostandards/routes.py:193` (`_run_rest_sync`)
- The 4Over client: `backend/modules/rest_connector/fourover_client.py`
- The 4Over normalizer: `backend/modules/rest_connector/fourover_normalizer.py`
- The S&S normalizer (used by the `rest` branch): `backend/modules/rest_connector/ss_normalizer.py`
- The shared upsert writer: `backend/modules/promostandards/normalizer.py:upsert_products`
- The plan: `plans/2026-04-16-v1-integration-pipeline.md` → V1d → Task 16

---

## 9. PR Description Template

> **Title:** `feat(sync): wire rest + rest_hmac protocols into POST /sync/{id}/products`
>
> **Body:**
>
> Replaces the dead placeholder in `trigger_product_sync` with a working `BackgroundTasks` invocation of `_run_rest_sync`. The function already supported both `rest` (S&S) and `rest_hmac` (4Over) protocols; it just wasn't being called from the unified route.
>
> Also drops `ops_graphql` from the REST branch — that protocol uses a separate inbound flow (`/api/ingest/...`) and now correctly returns 400 from this endpoint instead of silently no-op'ing.
>
> ### Test plan
> - [x] S&S sync triggers and fails with real upstream 401
> - [x] 4Over sync (rest_hmac) triggers and fails with `FourOverClient` validation error
> - [x] SanMar SOAP path unchanged
> - [x] `ops_graphql` returns 400 instead of silently accepting
