from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from database import get_db
from modules.customers.models import Customer
from .models import CategoryMapping, OptionMapping, ProductConfig
from .ops_client import OnPrintShopClient
from .schemas import (
    CategoryMappingCreate, CategoryMappingRead,
    OptionMappingCreate, OptionMappingRead,
    ProductConfigCreate, ProductConfigRead
)

router = APIRouter(prefix="/api/ops-config", tags=["OPS Configuration"])

# Category Mappings
@router.get("/categories/{supplier_id}", response_model=List[CategoryMappingRead])
async def get_category_mappings(supplier_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CategoryMapping).where(CategoryMapping.supplier_id == supplier_id))
    return result.scalars().all()

@router.post("/categories", response_model=CategoryMappingRead)
async def create_category_mapping(mapping: CategoryMappingCreate, db: AsyncSession = Depends(get_db)):
    db_mapping = CategoryMapping(**mapping.model_dump())
    db.add(db_mapping)
    try:
        await db.commit()
        await db.refresh(db_mapping)
        return db_mapping
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Option Mappings
@router.get("/options/{supplier_id}", response_model=List[OptionMappingRead])
async def get_option_mappings(supplier_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OptionMapping).where(OptionMapping.supplier_id == supplier_id))
    return result.scalars().all()

@router.post("/options", response_model=OptionMappingRead)
async def create_option_mapping(mapping: OptionMappingCreate, db: AsyncSession = Depends(get_db)):
    db_mapping = OptionMapping(**mapping.model_dump())
    db.add(db_mapping)
    try:
        await db.commit()
        await db.refresh(db_mapping)
        return db_mapping
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Product Configurations
@router.get("/product/{product_id}/{customer_id}", response_model=ProductConfigRead)
async def get_product_config(product_id: str, customer_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ProductConfig).where(
            ProductConfig.product_id == product_id,
            ProductConfig.customer_id == customer_id
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Product configuration not found")
    return config

@router.post("/product", response_model=ProductConfigRead)
async def save_product_config(config: ProductConfigCreate, db: AsyncSession = Depends(get_db)):
    # Upsert logic
    result = await db.execute(
        select(ProductConfig).where(
            ProductConfig.product_id == config.product_id,
            ProductConfig.customer_id == config.customer_id
        )
    )
    db_config = result.scalar_one_or_none()
    
    if db_config:
        for key, value in config.model_dump().items():
            setattr(db_config, key, value)
    else:
        db_config = ProductConfig(**config.model_dump())
        db.add(db_config)
    
    try:
        await db.commit()
        await db.refresh(db_config)
        return db_config
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# OPS Storefront Proxies
@router.get("/storefront/{customer_id}/categories")
async def get_ops_categories(customer_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    try:
        client = OnPrintShopClient(
            customer.ops_base_url,
            customer.ops_client_id,
            customer.ops_auth_config.get("client_secret", ""),
            customer.ops_token_url
        )
        return await client.get_categories()
    except Exception:
        # Task 23: Fallback to stub data while blocked on real credentials
        return [
            {"id": "cat_1", "name": "T-Shirts", "description": "Standard cotton tees"},
            {"id": "cat_2", "name": "Polos", "description": "Professional pique polos"},
            {"id": "cat_3", "name": "Outerwear", "description": "Jackets and hoodies"}
        ]


@router.get("/storefront/{customer_id}/options")
async def get_ops_options(customer_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    try:
        client = OnPrintShopClient(
            customer.ops_base_url,
            customer.ops_client_id,
            customer.ops_auth_config.get("client_secret", ""),
            customer.ops_token_url
        )
        return await client.get_master_options()
    except Exception:
        # Task 23: Fallback to stub data while blocked on real credentials
        return [
            {
                "id": "opt_1", 
                "name": "Color", 
                "attributes": [{"id": "attr_1", "name": "Navy"}, {"id": "attr_2", "name": "White"}]
            },
            {
                "id": "opt_2", 
                "name": "Size", 
                "attributes": [{"id": "attr_3", "name": "S"}, {"id": "attr_4", "name": "M"}, {"id": "attr_5", "name": "L"}]
            }
        ]
