from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.catalog.ingest import require_ingest_secret

from . import service
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
    customer_id: UUID = Query(None),
    source_product_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_push_mappings(db, customer_id, source_product_id)


@router.delete("/{id}")
async def delete_mapping(
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    success = await service.soft_delete_push_mapping(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return {"status": "ok"}
