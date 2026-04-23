from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.catalog.ingest import require_ingest_secret

from .models import MasterOption, MasterOptionAttribute
from .schemas import MasterOptionIngest

router = APIRouter(prefix="/api/ingest", tags=["master_options_ingest"])


@router.post(
    "/master-options",
    dependencies=[Depends(require_ingest_secret)],
)
async def ingest_master_options(
    batch: list[MasterOptionIngest],
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    for item in batch:
        stmt = (
            pg_insert(MasterOption)
            .values(
                ops_master_option_id=item.ops_master_option_id,
                title=item.title,
                option_key=item.option_key,
                options_type=item.options_type,
                pricing_method=item.pricing_method,
                status=item.status,
                sort_order=item.sort_order,
                description=item.description,
                master_option_tag=item.master_option_tag,
                raw_json=item.raw_json,
                synced_at=now,
            )
            .on_conflict_do_update(
                index_elements=["ops_master_option_id"],
                set_={
                    "title": item.title,
                    "option_key": item.option_key,
                    "options_type": item.options_type,
                    "pricing_method": item.pricing_method,
                    "status": item.status,
                    "sort_order": item.sort_order,
                    "description": item.description,
                    "master_option_tag": item.master_option_tag,
                    "raw_json": item.raw_json,
                    "synced_at": now,
                },
            )
            .returning(MasterOption.id)
        )
        mo_id: UUID = (await db.execute(stmt)).scalar_one()

        await db.execute(
            delete(MasterOptionAttribute).where(MasterOptionAttribute.master_option_id == mo_id)
        )
        for attr in item.attributes:
            db.add(
                MasterOptionAttribute(
                    master_option_id=mo_id,
                    ops_attribute_id=attr.ops_attribute_id,
                    title=attr.title,
                    sort_order=attr.sort_order,
                    default_price=attr.default_price,
                )
            )

    await db.commit()
    return {"records_processed": len(batch), "status": "completed"}
