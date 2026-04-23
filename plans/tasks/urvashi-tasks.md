# Urvashi — Sprint Tasks

**Sprint:** OPS Push Pipeline — Backend Orchestration  
**Spec:** `docs/superpowers/specs/2026-04-22-remaining-tasks-design.md`  
**Full code reference:** `docs/superpowers/plans/2026-04-20-ops-push.md` Phase B  
**Branch per task:** `urvashi/<task-slug>` → one PR per task

---

## Overview

9 tasks. Tasks 1, 6, 9 were already done against the codebase. Tasks 2, 3, 4, 5, 7 are now complete (commits merged or PRs open). Only Task 8 remains — and it needs a small backend change (see Step 3 under Task 8).

---

## ✅ Task 1 — Dashboard Wired to Real API — DONE

`frontend/src/app/(admin)/page.tsx` already calls `/api/stats`, `/api/sync-jobs`, `/api/suppliers`. Health badges, auto-refresh every 30s, per-supplier sync health all implemented. No action needed.

---

## ✅ Task 2 — Add `product_id` Filter to Push-Log GET (B1 fix) — DONE

Branch: `urvashi-push-log-product-filter` — implementation adds both `product_id` and `customer_id` filters, plus a `Query(le=200)` cap from the QA audit. Merge conflict with main resolved.

---

<details><summary>Original spec (for reference)</summary>

**File:** `backend/modules/push_log/routes.py`  
**Effort:** XS  
**Why:** `GET /api/push-log` exists but ignores `product_id` query param. Vidhi's PushHistory component calls `GET /api/push-log?product_id={id}&limit=20` — without this filter it returns all logs, not the product's logs.

Current signature (line 16–17):
```python
@router.get("/api/push-log", response_model=list[PushLogRead])
async def list_push_logs(limit: int = 20, db: AsyncSession = Depends(get_db)):
```

Replace with:
```python
from typing import Optional
from uuid import UUID

@router.get("/api/push-log", response_model=list[PushLogRead])
async def list_push_logs(
    product_id: Optional[UUID] = None,
    customer_id: Optional[UUID] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    from modules.catalog.models import Product
    from modules.suppliers.models import Supplier

    query = (
        select(
            ProductPushLog,
            Product.product_name,
            Customer.name.label("customer_name"),
            Supplier.name.label("supplier_name"),
        )
        .join(Product, ProductPushLog.product_id == Product.id)
        .join(Customer, ProductPushLog.customer_id == Customer.id)
        .join(Supplier, Product.supplier_id == Supplier.id)
        .order_by(ProductPushLog.pushed_at.desc())
    )
    if product_id:
        query = query.where(ProductPushLog.product_id == product_id)
    if customer_id:
        query = query.where(ProductPushLog.customer_id == customer_id)
    query = query.limit(limit)

    rows = (await db.execute(query)).all()
    out = []
    for log, prod_name, cust_name, supp_name in rows:
        data = PushLogRead.model_validate(log)
        data.product_name = prod_name
        data.customer_name = cust_name
        data.supplier_name = supp_name
        out.append(data)
    return out
```

**Smoke test:**
```bash
PROD=$(curl -s "http://localhost:8000/api/products?limit=1" | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["id"])')
curl -s "http://localhost:8000/api/push-log?product_id=$PROD&limit=5" | python3 -m json.tool
```

**Acceptance:** `GET /api/push-log?product_id=<uuid>` returns only logs for that product.

</details>

---

## ✅ Task 3 — `push_candidates` Module (B2) — DONE

Merged to main (PR #36, commit `8b356c1`). `GET /api/push/candidates/{customer_id}` live.

---

<details><summary>Original spec (for reference)</summary>

**Files to create:**
- `backend/modules/push_candidates/__init__.py` — empty
- `backend/modules/push_candidates/service.py` — new
- `backend/modules/push_candidates/routes.py` — new
- `backend/main.py` — add 2 lines

**Step 1 — `__init__.py`:** empty file.

**Step 2 — `service.py`:**
```python
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import Product
from modules.push_log.models import ProductPushLog


async def list_candidates(
    db: AsyncSession,
    customer_id: UUID,
    supplier_id: Optional[UUID] = None,
    only_never_pushed: bool = False,
    limit: int = 100,
) -> list[dict]:
    """Return products eligible to push for a given customer.

    Filters:
    - last_synced must not be null (product has been fetched from supplier)
    - if only_never_pushed=True, exclude products already pushed to this customer
    """
    query = select(Product).where(Product.last_synced.is_not(None))
    if supplier_id:
        query = query.where(Product.supplier_id == supplier_id)

    if only_never_pushed:
        pushed_subq = (
            select(ProductPushLog.product_id)
            .where(
                ProductPushLog.customer_id == customer_id,
                ProductPushLog.status == "pushed",
            )
            .scalar_subquery()
        )
        query = query.where(Product.id.not_in(pushed_subq))

    query = query.limit(limit).order_by(Product.product_name)
    rows = (await db.execute(query)).scalars().all()

    # Get latest push log per product for this customer
    log_result = await db.execute(
        select(ProductPushLog)
        .where(
            ProductPushLog.customer_id == customer_id,
            ProductPushLog.product_id.in_([p.id for p in rows]),
        )
        .order_by(ProductPushLog.pushed_at.desc())
    )
    logs_by_product: dict[UUID, str] = {}
    for log in log_result.scalars().all():
        if log.product_id not in logs_by_product:
            logs_by_product[log.product_id] = log.ops_product_id

    return [
        {
            "product_id": str(p.id),
            "supplier_sku": p.supplier_sku,
            "product_name": p.product_name,
            "ops_product_id": logs_by_product.get(p.id),
        }
        for p in rows
    ]
```

**Step 3 — `routes.py`:**
```python
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from .service import list_candidates

router = APIRouter(prefix="/api/push", tags=["push_candidates"])


@router.get("/candidates/{customer_id}")
async def get_push_candidates(
    customer_id: UUID,
    supplier_id: Optional[UUID] = Query(None),
    only_never_pushed: bool = Query(False),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await list_candidates(db, customer_id, supplier_id, only_never_pushed, limit)
```

**Step 4 — wire into `backend/main.py`:**

Find the block of `app.include_router(...)` calls (around line 70). Add after the existing push_router line:
```python
from modules.push_candidates.routes import router as push_candidates_router
# ...
app.include_router(push_candidates_router)
```

**Smoke test:**
```bash
CUST=$(curl -s "http://localhost:8000/api/customers" | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["id"])')
curl -s "http://localhost:8000/api/push/candidates/$CUST?limit=5" | python3 -m json.tool
```

**Acceptance:** Returns list of `{product_id, supplier_sku, product_name, ops_product_id}`. Empty list if no synced products — not a 500.

</details>

---

## ✅ Task 4 — Variant Bundle Endpoint for OPS (B4) — DONE

Merged to main (PR #37, commit `2657e29`). `GET /api/push/{customer_id}/product/{product_id}/ops-variants` live; ingest-secret protected.

---

<details><summary>Original spec (for reference)</summary>

**Files:**
- `backend/modules/markup/schemas.py` — append
- `backend/modules/markup/routes.py` — add endpoint to `push_router`

**Context:** n8n needs sizes + prices as two aligned lists to call `setProductSize` then `setProductPrice` for each variant. The existing `/payload` endpoint returns a free-form dict — this endpoint returns the OPS GraphQL-shaped inputs.

**Step 1 — append to `backend/modules/markup/schemas.py`:**
```python
class OPSProductSizeInput(BaseModel):
    product_size_id: int = 0        # 0 = create new
    products_id: int                # OPS products_id from prior setProduct call
    size_name: Optional[str]
    color_name: Optional[str]
    products_sku: Optional[str]
    visible: int = 1


class OPSProductPriceEntry(BaseModel):
    product_price_id: int = 0       # 0 = create new
    products_id: int
    qty: int = 1
    qty_to: int = 100
    price: float
    vendor_price: float
    size_id: int = 0                # filled in after setProductSize returns size_id
    visible: str = "1"


class OPSVariantsBundle(BaseModel):
    sizes: list[OPSProductSizeInput]
    prices: list[OPSProductPriceEntry]
```

**Step 2 — add endpoint in `backend/modules/markup/routes.py`** (after the existing `push_payload` endpoint, still on `push_router`):
```python
from .schemas import (
    MarkupRuleCreate, MarkupRuleRead, PushPayload,
    OPSProductSizeInput, OPSProductPriceEntry, OPSVariantsBundle,
)

@push_router.get(
    "/{customer_id}/product/{product_id}/ops-variants",
    response_model=OPSVariantsBundle,
    dependencies=[Depends(require_ingest_secret)],
)
async def ops_variants_bundle(
    customer_id: UUID, product_id: UUID,
    ops_products_id: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Return sizes + prices aligned by index for n8n OPS push loop."""
    payload = await calculate_price(db, customer_id, product_id)
    variants = payload["variants"]

    sizes = [
        OPSProductSizeInput(
            products_id=ops_products_id,
            size_name=v["size"],
            color_name=v["color"],
            products_sku=v["sku"],
        )
        for v in variants
    ]
    prices = [
        OPSProductPriceEntry(
            products_id=ops_products_id,
            price=v["final_price"] or 0.0,
            vendor_price=v["base_price"] or 0.0,
        )
        for v in variants
    ]
    return OPSVariantsBundle(sizes=sizes, prices=prices)
```

**Smoke test:**
```bash
CUST=$(curl -s "http://localhost:8000/api/customers" | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["id"])')
PROD=$(curl -s "http://localhost:8000/api/products?limit=1" | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["id"])')
curl -s -H "X-Ingest-Secret: $(grep INGEST_SHARED_SECRET .env | cut -d= -f2)" \
  "http://localhost:8000/api/push/$CUST/product/$PROD/ops-variants?ops_products_id=0" \
  | python3 -m json.tool
```

**Acceptance:** Returns `{sizes: [...], prices: [...]}` with same length. Each size has `size_name`, `color_name`, `products_sku`. Each price has `price` (with markup applied).

</details>

---

## ✅ Task 5 — Category OPS Input Endpoint (B5) — DONE

Merged to main (PR #38, commit `4ab2753`). `GET /api/categories/{category_id}/ops-input` live; falls back to a name-slug when `external_id` is missing.

---

<details><summary>Original spec (for reference)</summary>

**Files:**
- `backend/modules/catalog/schemas.py` — append
- `backend/modules/catalog/routes.py` — add to `categories_router`

**Step 1 — append to `backend/modules/catalog/schemas.py`:**
```python
class OPSCategoryInput(BaseModel):
    category_name: str
    parent_id: int = -1
    status: int = 1
    category_internal_name: str
```

**Step 2 — add to `backend/modules/catalog/routes.py`** (after the existing `get_category` endpoint at line ~163):
```python
from .schemas import ProductListRead, ProductRead, OPSCategoryInput

@categories_router.get("/{category_id}/ops-input", response_model=OPSCategoryInput)
async def get_category_ops_input(category_id: UUID, db: AsyncSession = Depends(get_db)):
    cat = await db.get(Category, category_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    return OPSCategoryInput(
        category_name=cat.name,
        parent_id=-1,
        status=1,
        category_internal_name=cat.external_id or cat.name.lower().replace(" ", "_"),
    )
```

**Smoke test:**
```bash
CAT=$(curl -s "http://localhost:8000/api/categories" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[0]["id"]) if d else print("none")')
curl -s "http://localhost:8000/api/categories/$CAT/ops-input" | python3 -m json.tool
```

**Acceptance:** Returns `{category_name, parent_id: -1, status: 1, category_internal_name}`. 404 for unknown ID.

</details>

---

## ✅ Task 6 — Image Pipeline Cache Header — DONE

`backend/modules/ops_push/routes.py` line 43 already returns `Cache-Control: public, max-age=86400`. No action needed. (`X-Processed-By` header was dropped from scope — not worth a PR.)

---

## ✅ Task 7 — Wire S&S + 4Over Protocols into Sync Dispatch (Gap G2) — DONE

Branch: `urvashi-task7-rest-sync-dispatch` (commit `366322b`) — `POST /api/sync/{supplier_id}/products/rest` dispatches REST/HMAC suppliers through the existing SyncJob helpers. Verified against S&S supplier in local dev: 202 + job_id → background worker flips status to `failed` with a readable error_log when creds are missing (no 500).

Two spec deviations forced by reality (the spec warned names might differ):
- Normalizers: `ss_to_ps_format` (not `ss_to_ps_products`) and `normalize_4over` (not `fourover_to_ps_products`).
- `upsert_products` lives in `modules.promostandards.normalizer`, not `modules.catalog.ingest`.

Also reused existing `_create_job`/`_ensure_no_active_job`/`_mark_job_running`/`_finish_job` helpers for consistency with the SOAP routes.

---

<details><summary>Original spec (for reference)</summary>

**File:** `backend/modules/promostandards/routes.py`

**Gap:** `_load_active_ps_supplier` (line 43) rejects any supplier whose protocol is not `"soap"` or `"promostandards"` with HTTP 400. S&S (`protocol = "rest"`) and 4Over (`protocol = "rest_hmac"`) adapters exist in `backend/modules/rest_connector/` but are never called.

**Step 1 — verify imports exist.** These files are confirmed present:
- `backend/modules/rest_connector/client.py` → `RESTConnectorClient`
- `backend/modules/rest_connector/ss_normalizer.py` → `ss_to_ps_products`
- `backend/modules/rest_connector/fourover_client.py` → `FourOverClient`
- `backend/modules/rest_connector/fourover_normalizer.py` → `fourover_to_ps_products`

Before writing any code, read those 4 files and verify exact class names and `get_products()` method signatures. The names above are from the plan — they may differ slightly.

**Step 2 — create a new sync route for REST protocols.** Add a new route instead of modifying `_load_active_ps_supplier` (which is tightly coupled to SOAP). At the bottom of `routes.py`, add:

```python
from modules.rest_connector.client import RESTConnectorClient
from modules.rest_connector.ss_normalizer import ss_to_ps_products


@router.post("/{supplier_id}/products/rest", status_code=202)
async def trigger_rest_sync(
    supplier_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    supplier = (
        await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    ).scalar_one_or_none()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    if supplier.protocol not in ("rest", "rest_hmac"):
        raise HTTPException(400, f"Use /sync/{supplier_id}/products for SOAP suppliers")

    job = SyncJob(
        supplier_id=supplier_id,
        job_type="full_sync",
        status="queued",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(_run_rest_sync, supplier_id, job.id)
    return {"job_id": str(job.id), "status": "queued"}


async def _run_rest_sync(supplier_id: UUID, job_id: UUID) -> None:
    from modules.catalog.ingest import upsert_products

    async with async_session() as db:
        supplier = (
            await db.execute(select(Supplier).where(Supplier.id == supplier_id))
        ).scalar_one_or_none()
        job = await db.get(SyncJob, job_id)
        if not supplier or not job:
            return
        try:
            job.status = "running"
            await db.commit()

            if supplier.protocol == "rest":
                client = RESTConnectorClient(
                    base_url=supplier.base_url,
                    auth_config=supplier.auth_config,
                )
                raw = await client.get_products()
                products = ss_to_ps_products(raw)
            else:
                from modules.rest_connector.fourover_client import FourOverClient
                from modules.rest_connector.fourover_normalizer import fourover_to_ps_products
                client = FourOverClient(
                    base_url=supplier.base_url,
                    auth_config=supplier.auth_config,
                )
                raw = await client.get_products()
                products = fourover_to_ps_products(raw)

            await upsert_products(db, supplier.id, products)
            job.status = "completed"
            job.finished_at = datetime.now(timezone.utc)
            job.records_processed = len(products)
        except Exception as exc:
            job.status = "failed"
            job.error_log = str(exc)
            job.finished_at = datetime.now(timezone.utc)
        await db.commit()
```

**Note:** `upsert_products` may be in `modules.catalog.ingest` — confirm that import path by reading the ingest module before writing.

**Acceptance:** `POST /api/sync/{ss_supplier_id}/products/rest` returns 202 and a job_id. `GET /api/sync-jobs/{job_id}` eventually shows `status: "completed"`. No 500 for S&S suppliers.

</details>

---

## Task 8 — Fix Supplier Form Protocol for SanMar

**Files:**
- `frontend/src/components/suppliers/reveal-form.tsx` — MODIFY (3 places)
- `backend/modules/suppliers/schemas.py` — MODIFY (1 line)

**Effort:** XS (frontend) + XS (backend)

`POPULAR_SUPPLIERS` (line 13–18) lists SanMar with `type: "ps"`. When clicked, `handleActivate` (line 65) resolves `protocol = "promostandards"` — wrong. SanMar uses SFTP.

**Step 1** — change SanMar entry (line 14):
```ts
{ name: "SanMar", code: "SANMAR", type: "sftp" },
```

**Step 2** — fix protocol resolution in `handleActivate`. Currently:
```ts
const protocol = isPS ? "promostandards" : (customType === "Secure API (signed requests)" ? "hmac" : "rest");
```
Replace with:
```ts
const popularEntry = POPULAR_SUPPLIERS.find(s => s.code === selectedPS?.Code);
const protocol = isCustom
  ? (customType === "Secure API (signed requests)" ? "hmac" : "rest")
  : (popularEntry?.type === "sftp" ? "sftp" : "promostandards");
```

**Step 3** — update the Popular Suppliers click handler (around line 158). Currently the `if (s.type === "ps")` branch is the only path that routes through the PS flow; any other `type` falls into a 4Over-specific ELSE branch (hardcoded `customUrl="https://api.4over.com"`, `customType="Secure API (signed requests)"`). Without this fix, clicking SanMar would populate it as a 4Over HMAC custom supplier. Change to:
```ts
if (s.type === "ps" || s.type === "sftp") {
```

**Step 4 — backend Literal.** `backend/modules/suppliers/schemas.py:7` currently reads:
```python
Protocol = Literal["soap", "rest", "hmac", "ops_graphql", "promostandards"]
```
The frontend will POST `protocol: "sftp"`, which gets rejected with 422 until this Literal accepts it. Update to:
```python
Protocol = Literal["soap", "rest", "hmac", "ops_graphql", "promostandards", "sftp"]
```
This is strictly additive — no migration needed; the column is VARCHAR per the project's "no PG ENUMs" rule.

**Acceptance:** Click SanMar → Activate → `POST /api/suppliers` returns 201 (not 422) → `GET /api/suppliers` shows SanMar row with `protocol: "sftp"`.

---

## ✅ Task 9 — Products API No-Supplier Filter — DONE

`backend/modules/catalog/routes.py` line 41 already has `supplier_id: Optional[UUID] = None`. The filter is already optional. No action needed.

---

## Files You Own

- `backend/modules/push_log/routes.py` — MODIFY (Task 2, add product_id filter)
- `backend/modules/push_candidates/__init__.py` — CREATE (Task 3)
- `backend/modules/push_candidates/service.py` — CREATE (Task 3)
- `backend/modules/push_candidates/routes.py` — CREATE (Task 3)
- `backend/main.py` — MODIFY (Task 3, add include_router)
- `backend/modules/markup/schemas.py` — MODIFY (Task 4)
- `backend/modules/markup/routes.py` — MODIFY (Task 4)
- `backend/modules/catalog/schemas.py` — MODIFY (Task 5)
- `backend/modules/catalog/routes.py` — MODIFY (Task 5)
- `backend/modules/promostandards/routes.py` — MODIFY (Task 7)
- `frontend/src/components/suppliers/reveal-form.tsx` — MODIFY (Task 8)
- `backend/modules/suppliers/schemas.py` — MODIFY (Task 8, add `"sftp"` to Protocol Literal)
