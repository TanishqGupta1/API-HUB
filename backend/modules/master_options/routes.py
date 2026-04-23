from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db

from .models import MasterOption
from .schemas import MasterOptionRead, OptionConfigItem, SyncStatus
from .service import load_product_config

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
