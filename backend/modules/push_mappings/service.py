from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.catalog.models import Product, ProductOption
from modules.customers.models import Customer

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


# ─────────────────────────────────────────────────────────────────────────────
# Bug 5 fix — auto-resolve push_mapping_options from product_options.
#
# Before this, every new (customer, product) push hit the preflight check
# "missing target_ops_option_id for: <option_key>" because nothing pre-populated
# push_mapping_options. The data the operator needed was already on the
# ProductOption row (ops_option_id was filled at import time when master_options
# matched). This function just copies those known IDs into push_mapping_options
# in one round-trip so the first push for any customer works without manual
# seeding.
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ResolveSummary:
    push_mapping_id: UUID
    created_or_updated: bool
    options_resolved: int
    attributes_resolved: int
    missing_option_keys: list[str]
    missing_attribute_keys: list[str]


async def resolve_push_mappings(
    db: AsyncSession,
    customer_id: UUID,
    product_id: UUID,
) -> ResolveSummary:
    """Auto-populate push_mapping_options from already-known ops_*_id fields
    on the product's options. Idempotent — running twice produces the same
    set of rows.
    """
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise ValueError(f"Customer {customer_id} not found")
    product = await db.get(Product, product_id)
    if product is None:
        raise ValueError(f"Product {product_id} not found")

    product_options = (
        await db.execute(
            select(ProductOption)
            .where(ProductOption.product_id == product_id)
            .options(selectinload(ProductOption.attributes))
        )
    ).scalars().all()

    now = datetime.now(timezone.utc)
    target_ops_base_url = customer.ops_base_url or ""

    # Find or create the PushMapping shell. target_ops_product_id is 0 until
    # the first real push fills it in; that field is mandatory in the schema
    # so we use 0 as a sentinel meaning "not yet pushed".
    upsert_stmt = (
        pg_insert(PushMapping)
        .values(
            source_system="api_hub",
            source_product_id=product_id,
            source_supplier_sku=product.supplier_sku,
            customer_id=customer_id,
            target_ops_base_url=target_ops_base_url,
            target_ops_product_id=0,
            pushed_at=now,
            updated_at=now,
            status="active",
        )
        .on_conflict_do_update(
            index_elements=["source_product_id", "customer_id"],
            set_={"updated_at": now, "status": "active"},
        )
        .returning(PushMapping.id)
    )
    mapping_id = (await db.execute(upsert_stmt)).scalar_one()

    # Drop existing rows so the resolve is fully deterministic — operators
    # who later override target_ops_*_id values manually should hit the
    # upsert endpoint instead of this one.
    await db.execute(
        delete(PushMappingOption).where(
            PushMappingOption.push_mapping_id == mapping_id
        )
    )

    options_resolved = 0
    attributes_resolved = 0
    missing_option_keys: list[str] = []
    missing_attribute_keys: list[str] = []

    for opt in product_options:
        if opt.ops_option_id is None:
            missing_option_keys.append(opt.option_key)
            continue
        # One row per attribute carries the option_id too; if no attributes,
        # write a single option-level row so the option_key counts as "mapped".
        attrs_with_id = [a for a in opt.attributes if a.ops_attribute_id is not None]
        if not attrs_with_id:
            db.add(
                PushMappingOption(
                    push_mapping_id=mapping_id,
                    source_master_option_id=opt.master_option_id,
                    source_option_key=opt.option_key,
                    target_ops_option_id=opt.ops_option_id,
                    title=opt.title,
                    sort_order=opt.sort_order,
                    created_at=now,
                )
            )
            options_resolved += 1
            for a in opt.attributes:
                missing_attribute_keys.append(f"{opt.option_key}/{a.attribute_key or a.title}")
            continue

        options_resolved += 1
        for attr in opt.attributes:
            if attr.ops_attribute_id is None:
                missing_attribute_keys.append(
                    f"{opt.option_key}/{attr.attribute_key or attr.title}"
                )
                continue
            db.add(
                PushMappingOption(
                    push_mapping_id=mapping_id,
                    source_master_option_id=opt.master_option_id,
                    source_master_attribute_id=attr.master_attribute_id,
                    source_option_key=opt.option_key,
                    source_attribute_key=attr.attribute_key or attr.title,
                    target_ops_option_id=opt.ops_option_id,
                    target_ops_attribute_id=attr.ops_attribute_id,
                    title=attr.title,
                    price=attr.price,
                    sort_order=attr.sort_order,
                    created_at=now,
                )
            )
            attributes_resolved += 1

    await db.commit()

    return ResolveSummary(
        push_mapping_id=mapping_id,
        created_or_updated=True,
        options_resolved=options_resolved,
        attributes_resolved=attributes_resolved,
        missing_option_keys=missing_option_keys,
        missing_attribute_keys=missing_attribute_keys,
    )
