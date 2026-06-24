"""Connect→Manage catalog push endpoint.

POST /api/manage-push/{supplier_id} — build each of a supplier's products into a cost-only
ConnectProductPush and post them to GraphX-Manage via ManageClient. Returns per-product ok/error
counts. Never raises on a Manage 5xx (degrades gracefully — ManageClient returns ok=False).
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import Depends

from database import get_db
from modules.auth.dependencies import VGAdmin
from modules.catalog.models import Product, ProductOption, ProductVariant
from modules.manage_client import ManageClient
from modules.suppliers.models import Supplier

from .builder import build_connect_product_push

router = APIRouter(prefix="/api/manage-push", tags=["manage_push"])


@router.post("/{supplier_id}")
async def push_supplier_to_manage(
    supplier_id: UUID,
    _: VGAdmin,
    sku: str | None = Query(None, description="Push only this supplier_sku (else all, up to limit)"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, "supplier not found")
    slug = supplier.slug

    q = (
        select(Product)
        .where(Product.supplier_id == supplier_id)
        .options(
            selectinload(Product.variants).selectinload(ProductVariant.prices),
            selectinload(Product.options).selectinload(ProductOption.attributes),
        )
        .order_by(Product.supplier_sku)
    )
    if sku:
        q = q.where(Product.supplier_sku == sku)
    q = q.limit(limit)
    products = (await db.execute(q)).scalars().all()

    if not products:
        return {"supplier": slug, "pushed": 0, "failed": 0, "results": []}

    results: list[dict] = []
    pushed = 0
    failed = 0
    async with ManageClient.from_env() as mc:
        if not mc.configured:
            raise HTTPException(503, "MANAGE_INGEST_URL / MANAGE_INGEST_TOKEN not configured")
        # One push per product so a single bad product can't fail the batch, and each gets its
        # own ok/error line.
        for p in products:
            payload = build_connect_product_push(p, slug)
            res = await mc.push_products({"products": [payload]})
            ok = res.ok and bool((res.data or {}).get("ok"))
            if ok:
                pushed += 1
            else:
                failed += 1
            results.append({
                "supplier_sku": p.supplier_sku,
                "ok": ok,
                "status": res.status,
                "error": res.error,
                "manage": (res.data or {}).get("results"),
            })

    return {"supplier": slug, "pushed": pushed, "failed": failed, "results": results}
