from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.auth.dependencies import (
    CurrentUser,
    _require_vg_admin,
    require_customer_access,
)
from modules.catalog.ingest import require_ingest_secret

from . import service
from .models import PushMapping
from .schemas import PushMappingRead, PushMappingUpsert

router = APIRouter(prefix="/api/push-mappings", tags=["push_mappings"])


@router.post("", response_model=dict, dependencies=[Depends(require_ingest_secret)])
async def upsert_mapping(
    data: PushMappingUpsert,
    db: AsyncSession = Depends(get_db),
):
    mapping_id = await service.upsert_push_mapping(db, data)
    return {"id": mapping_id, "status": "ok"}


@router.get("", response_model=list[PushMappingRead])
async def list_mappings(
    current_user: CurrentUser,
    customer_id: UUID = Query(None),
    source_product_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # customer_admin may only read their own tenant; reject a foreign customer_id.
    if current_user.role == "customer_admin":
        if customer_id is not None and customer_id != current_user.customer_id:
            raise HTTPException(403, "Not authorized for this customer")
        customer_id = current_user.customer_id
    return await service.get_push_mappings(db, customer_id, source_product_id)


@router.delete("/{id}")
async def delete_mapping(
    id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    # Tenant guard — fetch the mapping's owning customer_id and verify the
    # caller has access. Prevents cross-tenant deletion by UUID guessing.
    mapping = (
        await db.execute(select(PushMapping).where(PushMapping.id == id))
    ).scalar_one_or_none()
    if mapping is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    require_customer_access(mapping.customer_id, current_user)

    success = await service.soft_delete_push_mapping(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return {"status": "ok"}


# ─── Bug 5 fix: auto-resolve push_mapping_options ────────────────────────────


class ResolveRequest(BaseModel):
    customer_id: UUID
    product_id: UUID


class ResolveResponse(BaseModel):
    push_mapping_id: UUID
    options_resolved: int
    attributes_resolved: int
    missing_option_keys: list[str]
    missing_attribute_keys: list[str]


@router.post("/resolve", response_model=ResolveResponse, dependencies=[Depends(_require_vg_admin)])
async def resolve_mappings(
    body: ResolveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Auto-populate push_mapping_options for one (customer, product) pair.

    Reads ops_option_id and ops_attribute_id off the product's existing
    ProductOption / ProductOptionAttribute rows (populated at import time
    when master_options matched) and writes one PushMappingOption row per
    resolvable attribute.

    Operators only need to manually seed mappings for options where the
    ImportJob couldn't match a master_option — those show up in the
    response's missing_option_keys / missing_attribute_keys lists.

    Idempotent — running twice replaces the existing rows.
    """
    try:
        summary = await service.resolve_push_mappings(
            db, body.customer_id, body.product_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ResolveResponse(
        push_mapping_id=summary.push_mapping_id,
        options_resolved=summary.options_resolved,
        attributes_resolved=summary.attributes_resolved,
        missing_option_keys=summary.missing_option_keys,
        missing_attribute_keys=summary.missing_attribute_keys,
    )
