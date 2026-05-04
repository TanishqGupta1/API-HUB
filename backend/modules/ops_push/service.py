from __future__ import annotations

import os
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import async_session

from modules.catalog.models import CustomerProductSelection, Product, ProductOption
from modules.customers.models import Customer
from modules.decorations.models import CustomerProductDecoration
from modules.decorations.service import DecorationMissingError, assert_decoration_ready
from modules.push_log.models import ProductPushLog
from modules.suppliers.models import Supplier


async def prepare_push_payload(
    customer_id: uuid_mod.UUID,
    product_id: uuid_mod.UUID,
    db: AsyncSession,
) -> dict[str, Any]:
    """Build the n8n push payload for a product+customer pair.

    Raises DecorationMissingError if supplier requires decoration but none is saved.
    Raises ValueError if product or customer not found.
    """
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.options).selectinload(ProductOption.attributes))
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise ValueError(f"Product {product_id} not found")

    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise ValueError(f"Customer {customer_id} not found")

    supplier = await db.get(Supplier, product.supplier_id)
    if supplier is None:
        raise ValueError(f"Supplier {product.supplier_id} not found")

    await assert_decoration_ready(customer_id, product, db)

    # Apply name prefix (P8-BE-3)
    prefix = supplier.push_name_prefix or ""
    display_name = f"{prefix}{product.product_name}" if prefix else product.product_name

    # Base options from product
    base_options = [
        {
            "option_key": opt.option_key,
            "title": opt.title,
            "options_type": opt.options_type,
            "sort_order": opt.sort_order,
            "required": opt.required,
            "enabled": opt.enabled,
            "attributes": [
                {
                    "attribute_key": attr.attribute_key,
                    "title": attr.title,
                    "price": float(attr.price) if attr.price is not None else None,
                    "sort_order": attr.sort_order,
                    "enabled": attr.enabled,
                }
                for attr in opt.attributes
            ],
        }
        for opt in product.options
    ]

    # Decoration options overlay (P8-BE-2)
    dec_row = await db.get(CustomerProductDecoration, (customer_id, product_id))
    decoration_options: list[dict] = dec_row.decoration_options if dec_row else []

    # Build merged options: decoration options appended after base product options.
    # n8n is responsible for the final merge strategy when calling OPS.
    merged_options = base_options + decoration_options

    return {
        "customer_id": str(customer_id),
        "product_id": str(product_id),
        "product_name": display_name,
        "supplier_sku": product.supplier_sku,
        "supplier_slug": supplier.slug,
        "options": merged_options,
        "customer_ops_base_url": customer.ops_base_url,
        "customer_ops_token_url": customer.ops_token_url,
        "customer_ops_client_id": customer.ops_client_id,
        "customer_ops_client_secret": (customer.ops_auth_config or {}).get("client_secret", ""),
    }


async def execute_push(
    customer_id: uuid_mod.UUID,
    product_id: uuid_mod.UUID,
    db: AsyncSession,
) -> tuple[ProductPushLog, dict[str, Any]]:
    """Validate, prepare, log and fire n8n push.

    Returns (push_log, payload). Raises DecorationMissingError / ValueError on failure.
    """
    payload = await prepare_push_payload(customer_id, product_id, db)

    # Create ProductPushLog with status="pending"
    log = ProductPushLog(
        product_id=product_id,
        customer_id=customer_id,
        status="pending",
        pushed_at=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.flush()  # get log.id before commit

    payload["push_log_id"] = str(log.id)

    # Upsert CustomerProductSelection → status "pushed" (P8-BE-6)
    now = datetime.now(timezone.utc)
    stmt = pg_insert(CustomerProductSelection).values(
        customer_id=customer_id,
        product_id=product_id,
        status="pushed",
        added_at=now,
        pushed_at=now,
    ).on_conflict_do_update(
        constraint="uq_customer_product_selection",
        set_={"status": "pushed", "pushed_at": now},
    )
    await db.execute(stmt)

    await db.commit()
    await db.refresh(log)

    try:
        await trigger_n8n_push(payload)
    except Exception as exc:
        async with async_session() as update_db:
            log_row = await update_db.get(ProductPushLog, log.id)
            if log_row:
                log_row.status = "failed"
                log_row.error = str(exc)
                await update_db.commit()

    return log, payload


async def trigger_n8n_push(payload: dict[str, Any]) -> None:
    """POST payload to N8N_PUSH_WEBHOOK_URL if configured. Raises on failure."""
    webhook_url = os.getenv("N8N_PUSH_WEBHOOK_URL")
    if not webhook_url:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(webhook_url, json=payload)
