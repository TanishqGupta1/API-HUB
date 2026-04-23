from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db

from .models import MasterOption
from .schemas import MasterOptionRead, OptionConfigItem, SyncStatus
from .service import (
    delete_product_option,
    load_product_config,
    save_product_config,
    save_product_option,
)

router = APIRouter(prefix="/api/master-options", tags=["master_options"])


@router.get("", response_model=list[MasterOptionRead])
async def list_master_options(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MasterOption)
        .options(selectinload(MasterOption.attributes))
        .order_by(MasterOption.sort_order, MasterOption.title)
    )
    return result.scalars().all()


@router.get("/sync-status", response_model=SyncStatus)
async def sync_status(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(MasterOption.id)))).scalar_one()
    last_synced = (await db.execute(select(func.max(MasterOption.synced_at)))).scalar_one()
    return SyncStatus(
        total=total or 0,
        last_synced_at=last_synced.isoformat() if last_synced else None,
    )


@router.get("/{master_option_id}", response_model=MasterOptionRead)
async def get_master_option(master_option_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MasterOption)
        .where(MasterOption.id == master_option_id)
        .options(selectinload(MasterOption.attributes))
    )
    mo = result.scalar_one_or_none()
    if not mo:
        raise HTTPException(404, "Master option not found")
    return mo


product_config_router = APIRouter(prefix="/api/products", tags=["master_options"])


@product_config_router.get("/{product_id}/options-config", response_model=list[OptionConfigItem])
async def get_product_options_config(product_id: UUID, db: AsyncSession = Depends(get_db)):
    from modules.catalog.models import Product
    exists = (await db.execute(select(Product.id).where(Product.id == product_id))).scalar_one_or_none()
    if not exists:
        raise HTTPException(404, "Product not found")
    return await load_product_config(db, product_id)


@product_config_router.put("/{product_id}/options-config")
async def put_product_options_config(
    product_id: UUID,
    body: list[OptionConfigItem],
    db: AsyncSession = Depends(get_db),
):
    from modules.catalog.models import Product
    exists = (await db.execute(select(Product.id).where(Product.id == product_id))).scalar_one_or_none()
    if not exists:
        raise HTTPException(404, "Product not found")
    await save_product_config(db, product_id, body)
    return {"saved": len(body), "status": "ok"}


@product_config_router.patch("/{product_id}/options-config/{master_option_id}")
async def patch_product_option(
    product_id: UUID,
    master_option_id: UUID,
    body: OptionConfigItem,
    db: AsyncSession = Depends(get_db),
):
    if body.master_option_id != master_option_id:
        raise HTTPException(400, "Path master_option_id must match body")
    await save_product_option(db, product_id, body)
    await db.commit()
    return {"status": "ok"}


@product_config_router.delete("/{product_id}/options-config/{master_option_id}")
async def delete_product_option_route(
    product_id: UUID,
    master_option_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    await delete_product_option(db, product_id, master_option_id)
    return {"status": "deleted"}


@product_config_router.post("/{product_id}/options-config/duplicate-from/{src_product_id}")
async def duplicate_from(
    product_id: UUID,
    src_product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    from modules.catalog.models import Product
    for pid in (product_id, src_product_id):
        exists = (await db.execute(select(Product.id).where(Product.id == pid))).scalar_one_or_none()
        if not exists:
            raise HTTPException(404, f"Product {pid} not found")
    from .service import duplicate_product_config
    copied = await duplicate_product_config(db, src_product_id, product_id)
    return {"copied": copied, "status": "ok"}


@router.post("/sync")
async def trigger_sync():
    """Trigger the n8n master options pull workflow."""
    import httpx
    workflow_id = "ops-master-options-pull-001"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"http://localhost:8000/api/n8n/workflows/{workflow_id}/trigger",
            json={},
        )
    if r.status_code >= 300:
        raise HTTPException(502, f"n8n trigger failed: {r.text[:200]}")
    return r.json()
