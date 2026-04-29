from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.catalog.models import Category, Product, ProductImage, ProductVariant
from modules.sync_jobs.models import SyncJob

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
    payload = body.model_dump()

    existing = (
        await db.execute(select(Supplier).where(Supplier.slug == payload["slug"]))
    ).scalar_one_or_none()

    # "Activate" flow is idempotent in the UI: if the supplier already exists,
    # update credentials/config instead of failing with a unique constraint 500.
    if existing:
        for key, val in payload.items():
            setattr(existing, key, val)
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        data = SupplierRead.model_validate(existing)
        data.product_count = (
            await db.execute(
                select(func.count()).select_from(Product).where(Product.supplier_id == existing.id)
            )
        ).scalar() or 0
        return data

    supplier = Supplier(**payload)
    db.add(supplier)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Supplier with this slug already exists")
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

    # Delete child rows before the supplier to satisfy FK constraints
    product_ids = (
        await db.execute(select(Product.id).where(Product.supplier_id == supplier_id))
    ).scalars().all()
    if product_ids:
        await db.execute(delete(ProductVariant).where(ProductVariant.product_id.in_(product_ids)))
        await db.execute(delete(ProductImage).where(ProductImage.product_id.in_(product_ids)))
    await db.execute(delete(Product).where(Product.supplier_id == supplier_id))
    await db.execute(delete(Category).where(Category.supplier_id == supplier_id))
    await db.execute(delete(SyncJob).where(SyncJob.supplier_id == supplier_id))

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
@router.post("/test")
async def test_supplier_connection(body: dict):
    """Test connection to a supplier before adding it.
    
    If it's a PromoStandards supplier, we check if the code exists in the directory.
    If it's a custom REST supplier, we could do a ping.
    """
    protocol = body.get("protocol")
    if protocol == "promostandards":
        code = body.get("promostandards_code")
        if not code:
            return {"ok": False, "error": "Missing PromoStandards code"}
        
        # Check if company exists in directory
        from modules.ps_directory.client import get_ps_companies
        try:
            companies = await get_ps_companies()
            exists = any(c.get("Code") == code for c in companies)
            if exists:
                return {"ok": True, "message": f"Supplier {code} found in PromoStandards directory"}
            else:
                return {"ok": False, "error": f"Supplier {code} not found in directory"}
        except Exception as e:
            return {"ok": False, "error": f"Directory check failed: {str(e)}"}
    
    # For custom REST/HMAC, we just return OK if creds are present for now,
    # but we've removed the frontend hardcode.
    if body.get("auth_config", {}).get("id") and body.get("auth_config", {}).get("password"):
        return {"ok": True, "message": "Credentials format valid"}
        
    return {"ok": False, "error": "Invalid configuration or missing credentials"}
