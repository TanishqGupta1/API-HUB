import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from modules.auth.dependencies import VGAdmin

from .models import MasterOption, MasterOptionAttribute
from .schemas import MasterOptionRead, OptionConfigItem, SyncStatus
from .service import (
    delete_product_option,
    load_product_config,
    save_product_config,
    save_product_option,
)

log = logging.getLogger(__name__)

_QUERY_GET_MASTER_OPTIONS = """
query GetMasterOptions($limit: Int, $offset: Int) {
  getMasterOptions(limit: $limit, offset: $offset) {
    master_option_id
    title
    option_key
    options_type
    pricing_method
    status
    sort_order
    description
    master_option_tag
    attributes {
      attribute_id
      title
      sort_order
      price
      attribute_key
      master_attribute_id
    }
  }
}
""".strip()

router = APIRouter(prefix="/api/master-options", tags=["master_options"])


@router.get("", response_model=list[MasterOptionRead])
async def list_master_options(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MasterOption)
        .options(selectinload(MasterOption.attributes))
        .order_by(MasterOption.sort_order, MasterOption.title)
    )
    return result.scalars().all()


@router.get("/sync-status", response_model=SyncStatus)
async def sync_status(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(MasterOption.id)))).scalar_one()
    last_synced = (await db.execute(select(func.max(MasterOption.synced_at)))).scalar_one()
    return SyncStatus(
        total=total or 0,
        last_synced_at=last_synced.isoformat() if last_synced else None,
    )


@router.post("/sync", status_code=202)
async def sync_master_options(
    _: VGAdmin,
    customer_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Pull master options from an OPS customer and upsert them.

    Pass ?customer_id=<uuid> to target a specific storefront; omit to use the
    first active customer (legacy behaviour, non-deterministic with multiple
    storefronts).
    """
    from modules.customers.models import Customer
    from modules.ops_client.client import OpsAuth, OpsGraphQLClient

    if customer_id is not None:
        result = await db.execute(
            select(Customer).where(Customer.id == customer_id)
        )
        customer = result.scalars().first()
        if not customer:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found.")
    else:
        result = await db.execute(
            select(Customer).where(Customer.is_active.is_(True))
        )
        customer = result.scalars().first()

    if not customer:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No active OPS customer configured.")

    secret = (customer.ops_auth_config or {}).get("client_secret")
    if not customer.ops_base_url or not customer.ops_token_url or not customer.ops_client_id or not secret:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Customer missing OPS credentials.")

    auth = OpsAuth(
        base_url=customer.ops_base_url,
        token_url=customer.ops_token_url,
        client_id=customer.ops_client_id,
        client_secret=secret,
    )

    try:
        async with OpsGraphQLClient(auth) as ops:
            res = await ops.execute(_QUERY_GET_MASTER_OPTIONS, variables={"limit": 200, "offset": 0})
    except Exception as exc:
        log.warning("master_options sync OPS connection failed: %s", exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Could not connect to OPS storefront: {exc}",
        )

    if not res.ok:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"OPS error: {res.ops_error_code} — {res.ops_error_message}",
        )

    raw_options = (res.data or {}).get("getMasterOptions") or []
    if not raw_options:
        return {"synced": 0, "message": "OPS returned no master options."}

    now = datetime.now(timezone.utc)
    synced = 0
    for mo in raw_options:
        mo_id = mo.get("master_option_id")
        if mo_id is None:
            continue
        stmt = (
            pg_insert(MasterOption)
            .values(
                ops_master_option_id=int(mo_id),
                title=mo.get("title") or "",
                option_key=mo.get("option_key"),
                options_type=mo.get("options_type"),
                pricing_method=mo.get("pricing_method"),
                status=int(mo.get("status") or 1),
                sort_order=int(mo.get("sort_order") or 0),
                description=mo.get("description"),
                master_option_tag=mo.get("master_option_tag"),
                raw_json=mo,
                synced_at=now,
            )
            .on_conflict_do_update(
                index_elements=["ops_master_option_id"],
                set_={
                    "title": mo.get("title") or "",
                    "option_key": mo.get("option_key"),
                    "options_type": mo.get("options_type"),
                    "pricing_method": mo.get("pricing_method"),
                    "status": int(mo.get("status") or 1),
                    "sort_order": int(mo.get("sort_order") or 0),
                    "description": mo.get("description"),
                    "master_option_tag": mo.get("master_option_tag"),
                    "raw_json": mo,
                    "synced_at": now,
                },
            )
            .returning(MasterOption.id)
        )
        row = (await db.execute(stmt)).scalar_one()

        # Rebuild attributes (delete + reinsert)
        await db.execute(
            MasterOptionAttribute.__table__.delete().where(
                MasterOptionAttribute.master_option_id == row
            )
        )
        for attr in mo.get("attributes") or []:
            attr_id = attr.get("attribute_id")
            if attr_id is None:
                continue
            db.add(MasterOptionAttribute(
                master_option_id=row,
                ops_attribute_id=int(attr_id),
                title=attr.get("title") or "",
                sort_order=int(attr.get("sort_order") or 0),
                default_price=attr.get("price"),
                raw_json=attr,
            ))
        synced += 1

    await db.commit()
    log.info("master_options sync: upserted %d options", synced)
    return {"synced": synced, "status": "ok"}


@router.get("/{master_option_id}", response_model=MasterOptionRead)
async def get_master_option(master_option_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MasterOption)
        .where(MasterOption.id == master_option_id)
        .options(selectinload(MasterOption.attributes))
    )
    mo = result.scalar_one_or_none()
    if not mo:
        raise HTTPException(404, "Master option not found")
    return mo


product_config_router = APIRouter(prefix="/api/products", tags=["master_options"])


@product_config_router.get("/{product_id}/options-config", response_model=list[OptionConfigItem])
async def get_product_options_config(product_id: UUID, db: AsyncSession = Depends(get_db)):
    from modules.catalog.models import Product
    exists = (await db.execute(select(Product.id).where(Product.id == product_id))).scalar_one_or_none()
    if not exists:
        raise HTTPException(404, "Product not found")
    return await load_product_config(db, product_id)


@product_config_router.put("/{product_id}/options-config")
async def put_product_options_config(
    product_id: UUID,
    body: list[OptionConfigItem],
    db: AsyncSession = Depends(get_db),
):
    from modules.catalog.models import Product
    exists = (await db.execute(select(Product.id).where(Product.id == product_id))).scalar_one_or_none()
    if not exists:
        raise HTTPException(404, "Product not found")
    await save_product_config(db, product_id, body)
    return {"saved": len(body), "status": "ok"}


@product_config_router.patch("/{product_id}/options-config/{master_option_id}")
async def patch_product_option(
    product_id: UUID,
    master_option_id: UUID,
    body: OptionConfigItem,
    db: AsyncSession = Depends(get_db),
):
    if body.master_option_id != master_option_id:
        raise HTTPException(400, "Path master_option_id must match body")
    await save_product_option(db, product_id, body)
    await db.commit()
    return {"status": "ok"}


@product_config_router.delete("/{product_id}/options-config/{master_option_id}")
async def delete_product_option_route(
    product_id: UUID,
    master_option_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    await delete_product_option(db, product_id, master_option_id)
    return {"status": "deleted"}


@product_config_router.post("/{product_id}/options-config/duplicate-from/{src_product_id}")
async def duplicate_from(
    product_id: UUID,
    src_product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    from modules.catalog.models import Product
    for pid in (product_id, src_product_id):
        exists = (await db.execute(select(Product.id).where(Product.id == pid))).scalar_one_or_none()
        if not exists:
            raise HTTPException(404, f"Product {pid} not found")
    from .service import duplicate_product_config
    copied = await duplicate_product_config(db, src_product_id, product_id)
    return {"copied": copied, "status": "ok"}


# /sync route removed in T23 — the n8n master-options pull workflow it
# triggered (ops-master-options-pull.json) is deleted. Callers should use
# POST /api/integrations/v1/master-options/ingest with the gateway's
# X-Orchestrator-Key header to push a master-options snapshot directly.
