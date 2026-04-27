from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import PushMapping, PushMappingOption
from .schemas import PushMappingUpsert


async def upsert_push_mapping(db: AsyncSession, data: PushMappingUpsert) -> UUID:
    now = datetime.now(timezone.utc)
    
    stmt = (
        pg_insert(PushMapping)
        .values(
            source_system=data.source_system,
            source_product_id=data.source_product_id,
            source_supplier_sku=data.source_supplier_sku,
            customer_id=data.customer_id,
            target_ops_base_url=data.target_ops_base_url,
            target_ops_product_id=data.target_ops_product_id,
            pushed_at=now,
            updated_at=now,
            status="active"
        )
        .on_conflict_do_update(
            index_elements=["source_product_id", "customer_id"],
            set_={
                "target_ops_product_id": data.target_ops_product_id,
                "target_ops_base_url": data.target_ops_base_url,
                "updated_at": now,
                "status": "active"
            }
        )
        .returning(PushMapping.id)
    )
    
    mapping_id = (await db.execute(stmt)).scalar_one()
    
    # Options handling: replace-all pattern
    await db.execute(
        delete(PushMappingOption).where(PushMappingOption.push_mapping_id == mapping_id)
    )
    
    for opt in data.options:
        db.add(
            PushMappingOption(
                push_mapping_id=mapping_id,
                source_master_option_id=opt.source_master_option_id,
                source_master_attribute_id=opt.source_master_attribute_id,
                source_option_key=opt.source_option_key,
                source_attribute_key=opt.source_attribute_key,
                target_ops_option_id=opt.target_ops_option_id,
                target_ops_attribute_id=opt.target_ops_attribute_id,
                title=opt.title,
                price=opt.price,
                sort_order=opt.sort_order,
                created_at=now
            )
        )
    
    await db.commit()
    return mapping_id


async def get_push_mappings(
    db: AsyncSession, customer_id: UUID = None, source_product_id: UUID = None
) -> list[PushMapping]:
    stmt = select(PushMapping).options(selectinload(PushMapping.options))
    
    if customer_id:
        stmt = stmt.where(PushMapping.customer_id == customer_id)
    if source_product_id:
        stmt = stmt.where(PushMapping.source_product_id == source_product_id)
        
    return (await db.execute(stmt)).scalars().all()


async def soft_delete_push_mapping(db: AsyncSession, mapping_id: UUID) -> bool:
    stmt = select(PushMapping).where(PushMapping.id == mapping_id)
    mapping = (await db.execute(stmt)).scalar_one_or_none()
    
    if not mapping:
        return False
        
    mapping.status = "deleted"
    mapping.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return True
