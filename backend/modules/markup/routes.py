from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from modules.catalog.ingest import require_ingest_secret
from modules.catalog.models import ProductOption, ProductOptionAttribute
from modules.master_options.models import MasterOption, MasterOptionAttribute

from .engine import calculate_price
from .models import MarkupRule
from .schemas import (
    MarkupRuleCreate,
    MarkupRuleRead,
    PushPayload,
    OPSProductSizeInput,
    OPSProductPriceEntry,
    OPSVariantsBundle,
    OPSProductOptionSchema,
    OPSProductAttributeSchema,
)

router = APIRouter(prefix="/api/markup-rules", tags=["markup"])
push_router = APIRouter(prefix="/api/push", tags=["markup"])


@push_router.get(
    "/{customer_id}/product/{product_id}/payload",
    response_model=PushPayload,
    dependencies=[Depends(require_ingest_secret)],
)
async def push_payload(
    customer_id: UUID, product_id: UUID, db: AsyncSession = Depends(get_db)
):
    """OPS-ready payload for a product under a customer's markup rules.

    n8n calls this before invoking OPS `setProduct`/`setProductPrice` mutations.
    """
    return await calculate_price(db, customer_id, product_id)


@push_router.get(
    "/{customer_id}/product/{product_id}/ops-variants",
    response_model=OPSVariantsBundle,
    dependencies=[Depends(require_ingest_secret)],
)
async def ops_variants_bundle(
    customer_id: UUID,
    product_id: UUID,
    ops_products_id: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Return sizes + prices aligned by index for n8n OPS push loop."""
    payload = await calculate_price(db, customer_id, product_id)
    variants = payload["variants"]

    sizes = [
        OPSProductSizeInput(
            products_id=ops_products_id,
            size_name=v["size"],
            color_name=v["color"],
            products_sku=v["sku"],
        )
        for v in variants
    ]
    prices = [
        OPSProductPriceEntry(
            products_id=ops_products_id,
            price=v["final_price"] or 0.0,
            vendor_price=v["base_price"] or 0.0,
        )
        for v in variants
    ]
    return OPSVariantsBundle(sizes=sizes, prices=prices)


@push_router.get(
    "/{customer_id}/product/{product_id}/ops-options",
    response_model=list[OPSProductOptionSchema],
    dependencies=[Depends(require_ingest_secret)],
)
async def ops_product_options(
    customer_id: UUID,
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return product-scoped option shape for OPS push.

    Converts hub's master-option-based config into a product-scoped shape.
    Output intentionally excludes master_option_id + ops_attribute_id from the
    core push body — those are kept only as source_* fields for traceability
    in push_mappings.
    """
    # Load enabled product options with attributes
    po_rows = (
        await db.execute(
            select(ProductOption)
            .where(
                ProductOption.product_id == product_id,
                ProductOption.enabled == True,  # noqa: E712
            )
            .options(selectinload(ProductOption.attributes))
        )
    ).scalars().all()

    # Lookup master option attribute_keys via raw_json on MasterOptionAttribute
    mo_ids = {po.master_option_id for po in po_rows if po.master_option_id is not None}
    moa_map: dict[tuple[int, int], Optional[str]] = {}
    if mo_ids:
        rows = (
            await db.execute(
                select(MasterOption, MasterOptionAttribute)
                .join(
                    MasterOptionAttribute,
                    MasterOption.id == MasterOptionAttribute.master_option_id,
                )
                .where(MasterOption.ops_master_option_id.in_(mo_ids))
            )
        ).all()
        for mo, ma in rows:
            raw = ma.raw_json or {}
            attr_key = raw.get("attribute_key") if isinstance(raw, dict) else None
            moa_map[(mo.ops_master_option_id, ma.ops_attribute_id)] = attr_key

    out: list[OPSProductOptionSchema] = []
    for po in po_rows:
        enabled_attrs = [a for a in po.attributes if a.enabled]
        if not enabled_attrs:
            continue
        attrs_out = [
            OPSProductAttributeSchema(
                title=a.title,
                price=float(a.price or 0),
                numeric_value=float(a.numeric_value or 0),
                sort_order=(
                    a.overridden_sort if a.overridden_sort is not None else a.sort_order
                ),
                source_master_attribute_id=a.ops_attribute_id,
                source_attribute_key=moa_map.get(
                    (po.master_option_id, a.ops_attribute_id)
                ),
            )
            for a in sorted(enabled_attrs, key=lambda x: x.sort_order)
        ]
        out.append(
            OPSProductOptionSchema(
                option_key=po.option_key,
                title=po.title or "",
                options_type=po.options_type,
                attributes=attrs_out,
                source_master_option_id=po.master_option_id,
            )
        )
    return out


@router.get("/{customer_id}", response_model=list[MarkupRuleRead])
async def list_markup_rules(customer_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MarkupRule)
        .where(MarkupRule.customer_id == customer_id)
        .order_by(MarkupRule.priority.desc())
    )
    return result.scalars().all()


@router.post("", response_model=MarkupRuleRead, status_code=201)
async def create_markup_rule(body: MarkupRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = MarkupRule(**body.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
async def delete_markup_rule(rule_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MarkupRule).where(MarkupRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Markup rule not found")
    await db.delete(rule)
    await db.commit()
    return {"deleted": True}
