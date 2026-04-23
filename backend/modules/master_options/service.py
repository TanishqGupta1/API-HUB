from uuid import UUID

from sqlalchemy import select
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
            attrs.append(
                AttributeConfigItem(
                    attribute_id=poa.id if poa else None,
                    ops_attribute_id=ma.ops_attribute_id,
                    title=ma.title,
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
                options_type=mo.options_type,
                master_option_tag=mo.master_option_tag,
                enabled=po.enabled if po else False,
                attributes=attrs,
            )
        )
    return out
