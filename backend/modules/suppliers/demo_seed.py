from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Supplier


_VG_OPS_SUPPLIER: dict = {
    "name": "Visual Graphics OPS",
    "slug": "vg-ops",
    "protocol": "ops_graphql",
    "promostandards_code": None,
    "base_url": "https://vg.onprintshop.com",
    "auth_config": {
        "n8n_credential_id": "PLACEHOLDER_CREDENTIAL_ID",
        "store_url": "https://vg.onprintshop.com",
    },
    # The n8n workflows treat inactive suppliers as a "gate". In local dev, it’s
    # less surprising if the row exists and is runnable by default.
    "is_active": True,
}


async def ensure_vg_ops_supplier(db: AsyncSession) -> Supplier:
    existing = (
        await db.execute(select(Supplier).where(Supplier.slug == _VG_OPS_SUPPLIER["slug"]))
    ).scalar_one_or_none()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            await db.commit()
        return existing

    supplier = Supplier(**_VG_OPS_SUPPLIER)
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier
