from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.catalog.models import Product

from .models import Supplier
from .schemas import SupplierCreate, SupplierRead
from .service import get_cached_endpoints

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("", response_model=list[SupplierRead])
async def list_suppliers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Supplier).order_by(Supplier.created_at.desc()))
    suppliers = result.scalars().all()
    out = []
    for s in suppliers:
        count = (
            await db.execute(
                select(func.count()).select_from(Product).where(Product.supplier_id == s.id)
            )
        ).scalar() or 0
        data = SupplierRead.model_validate(s)
        data.product_count = count
        out.append(data)
    return out


@router.post("", response_model=SupplierRead, status_code=201)
async def create_supplier(body: SupplierCreate, db: AsyncSession = Depends(get_db)):
    supplier = Supplier(**body.model_dump())
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    data = SupplierRead.model_validate(supplier)
    data.product_count = 0
    return data


@router.get("/{supplier_id}", response_model=SupplierRead)
async def get_supplier(supplier_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    count = (
        await db.execute(
            select(func.count()).select_from(Product).where(Product.supplier_id == supplier.id)
        )
    ).scalar() or 0
    data = SupplierRead.model_validate(supplier)
    data.product_count = count
    return data


@router.patch("/{supplier_id}", response_model=SupplierRead)
async def patch_supplier(
    supplier_id: UUID, body: dict, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    
    # Partial update from dict
    for key, val in body.items():
        if hasattr(supplier, key):
            setattr(supplier, key, val)
            
    await db.commit()
    await db.refresh(supplier)
    
    count = (
        await db.execute(
            select(func.count()).select_from(Product).where(Product.supplier_id == supplier.id)
        )
    ).scalar() or 0
    data = SupplierRead.model_validate(supplier)
    data.product_count = count
    return data


@router.delete("/{supplier_id}")
async def delete_supplier(supplier_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    await db.delete(supplier)
    await db.commit()
    return {"deleted": True}


@router.get("/{supplier_id}/endpoints")
async def get_supplier_endpoints(supplier_id: UUID, db: AsyncSession = Depends(get_db)):
    return await get_cached_endpoints(db, supplier_id)


@router.put("/{supplier_id}/mappings")
async def save_supplier_mappings(
    supplier_id: UUID, body: dict, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    supplier.field_mappings = body
    await db.commit()
    return {"saved": True, "supplier_id": str(supplier_id), "mappings": body}
