from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from .models import ProductStorefrontConfig
from .schemas import ProductStorefrontConfigRead, ProductStorefrontConfigUpsert

router = APIRouter(prefix="/api/ops-config", tags=["ops_config"])

@router.get("/{customer_id}/product/{product_id}", response_model=ProductStorefrontConfigRead)
async def get_config(
    customer_id: UUID, 
    product_id: UUID, 
    db: AsyncSession = Depends(get_db)
):
    """Fetch the storefront-specific configuration for a product."""
    result = await db.execute(
        select(ProductStorefrontConfig).where(
            ProductStorefrontConfig.product_id == product_id,
            ProductStorefrontConfig.customer_id == customer_id
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        # Return a blank config instead of 404 to make frontend life easier
        return {
            "id": "00000000-0000-0000-0000-000000000000", # Dummy ID
            "product_id": product_id,
            "customer_id": customer_id,
            "ops_category_id": None,
            "option_mappings": {},
            "pricing_overrides": {}
        }
    return config

@router.post("", response_model=ProductStorefrontConfigRead)
async def upsert_config(
    data: ProductStorefrontConfigUpsert, 
    db: AsyncSession = Depends(get_db)
):
    """Create or update a storefront configuration mapping."""
    result = await db.execute(
        select(ProductStorefrontConfig).where(
            ProductStorefrontConfig.product_id == data.product_id,
            ProductStorefrontConfig.customer_id == data.customer_id
        )
    )
    config = result.scalar_one_or_none()
    
    if config:
        config.ops_category_id = data.ops_category_id
        config.option_mappings = data.option_mappings
        config.pricing_overrides = data.pricing_overrides
    else:
        config = ProductStorefrontConfig(**data.model_dump())
        db.add(config)
        
    await db.commit()
    await db.refresh(config)
    return config
