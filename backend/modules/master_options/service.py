from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.catalog.models import Product, ProductOption, ProductOptionAttribute

from .models import MasterOption, MasterOptionAttribute
from .schemas import AttributeConfigItem, OptionConfigItem


async def load_product_config(db: AsyncSession, product_id: UUID) -> list[OptionConfigItem]:
    """Build the card-grid payload for the product.

    For each master option (global catalog), merge in the product's saved
    override if any. Products that have never saved a config get defaults
    (enabled=False, prices from master_option_attributes.default_price).
    """
    # 1. Load all master options with their attributes
    mos = (
        await db.execute(
            select(MasterOption)
            .options(selectinload(MasterOption.attributes))
            .order_by(MasterOption.sort_order, MasterOption.title)
        )
    ).scalars().all()

    # 2. Load product's existing overrides
    po_rows = (
        await db.execute(
            select(ProductOption)
            .where(ProductOption.product_id == product_id)
            .options(selectinload(ProductOption.attributes))
        )
    ).scalars().all()
    po_by_mo: dict[int, ProductOption] = {
        po.master_option_id: po for po in po_rows if po.master_option_id is not None
    }

    out: list[OptionConfigItem] = []
    for mo in mos:
        po = po_by_mo.get(mo.ops_master_option_id)
        po_attrs_by_ops_id: dict[int, ProductOptionAttribute] = {}
        if po:
            po_attrs_by_ops_id = {
                a.ops_attribute_id: a for a in po.attributes if a.ops_attribute_id is not None
            }

        attrs: list[AttributeConfigItem] = []
        for ma in sorted(mo.attributes, key=lambda a: a.sort_order):
            poa = po_attrs_by_ops_id.get(ma.ops_attribute_id)
            # raw_json (for master attributes pulled from OPS) may carry attribute_key
            raw = ma.raw_json or {}
            attr_key = raw.get("attribute_key") if isinstance(raw, dict) else None
            attrs.append(
                AttributeConfigItem(
                    attribute_id=poa.id if poa else None,
                    ops_attribute_id=ma.ops_attribute_id,
                    title=ma.title,
                    attribute_key=attr_key,
                    enabled=poa.enabled if poa else False,
                    price=poa.price if (poa and poa.price is not None) else (ma.default_price or 0),
                    numeric_value=poa.numeric_value if (poa and poa.numeric_value is not None) else 0,
                    sort_order=poa.overridden_sort if (poa and poa.overridden_sort is not None) else ma.sort_order,
                )
            )

        out.append(
            OptionConfigItem(
                master_option_id=mo.id,
                ops_master_option_id=mo.ops_master_option_id,
                title=mo.title,
                option_key=mo.option_key,
                options_type=mo.options_type,
                master_option_tag=mo.master_option_tag,
                enabled=po.enabled if po else False,
                attributes=attrs,
            )
        )
    return out


async def save_product_option(
    db: AsyncSession,
    product_id: UUID,
    item: OptionConfigItem,
) -> None:
    """Upsert one master option assignment for a product."""
    mo = (
        await db.execute(select(MasterOption).where(MasterOption.id == item.master_option_id))
    ).scalar_one_or_none()
    if not mo:
        return

    stmt = (
        pg_insert(ProductOption)
        .values(
            product_id=product_id,
            option_key=mo.option_key or f"mo_{mo.ops_master_option_id}",
            title=mo.title,
            options_type=mo.options_type,
            sort_order=mo.sort_order,
            master_option_id=mo.ops_master_option_id,
            required=False,
            status=1,
            enabled=item.enabled,
        )
        .on_conflict_do_update(
            index_elements=["product_id", "option_key"],
            set_={
                "title": mo.title,
                "options_type": mo.options_type,
                "master_option_id": mo.ops_master_option_id,
                "enabled": item.enabled,
            },
        )
        .returning(ProductOption.id)
    )
    po_id: UUID = (await db.execute(stmt)).scalar_one()

    # Replace attributes
    await db.execute(
        delete(ProductOptionAttribute).where(ProductOptionAttribute.product_option_id == po_id)
    )
    for attr in item.attributes:
        db.add(
            ProductOptionAttribute(
                product_option_id=po_id,
                ops_attribute_id=attr.ops_attribute_id,
                title=attr.title,
                sort_order=attr.sort_order,
                status=1,
                enabled=attr.enabled,
                price=attr.price,
                numeric_value=attr.numeric_value,
                overridden_sort=attr.sort_order,
            )
        )


async def save_product_config(
    db: AsyncSession,
    product_id: UUID,
    items: list[OptionConfigItem],
) -> None:
    for item in items:
        await save_product_option(db, product_id, item)
    await db.commit()


async def duplicate_product_config(
    db: AsyncSession, src_product_id: UUID, dest_product_id: UUID
) -> int:
    """Copy src product's options + attributes to dest product. Returns count copied."""
    src_cfg = await load_product_config(db, src_product_id)
    enabled_items = [item for item in src_cfg if item.enabled]
    for item in enabled_items:
        await save_product_option(db, dest_product_id, item)
    await db.commit()
    return len(enabled_items)


async def delete_product_option(
    db: AsyncSession,
    product_id: UUID,
    master_option_id: UUID,
) -> None:
    mo = (
        await db.execute(select(MasterOption).where(MasterOption.id == master_option_id))
    ).scalar_one_or_none()
    if not mo:
        return
    await db.execute(
        delete(ProductOption).where(
            ProductOption.product_id == product_id,
            ProductOption.master_option_id == mo.ops_master_option_id,
        )
    )
    await db.commit()
