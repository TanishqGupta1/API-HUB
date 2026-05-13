import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database import async_session

from modules.catalog.models import Product
from modules.customers.models import Customer
from modules.suppliers.models import Supplier
from modules.decorations.models import CustomerProductDecoration
from modules.push_mappings.models import PushMapping
from modules.push_log.models import ProductPushLog
from modules.catalog.models import CustomerProductSelection
from modules.markup.engine import calculate_price
from .merge import merge_product_with_decorations

logger = logging.getLogger(__name__)


async def trigger_n8n_push(payload: dict[str, Any]) -> None:
    """POST payload to N8N_PUSH_WEBHOOK_URL.

    Silently skips in dev when the env var is unset.
    Raises in production if unset, or on any non-2xx response.
    """
    webhook_url = os.getenv("N8N_PUSH_WEBHOOK_URL", "").strip()
    if not webhook_url:
        if os.getenv("ENVIRONMENT", "development").lower() == "production":
            raise RuntimeError("N8N_PUSH_WEBHOOK_URL is required in production")
        return
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(webhook_url, json=payload)
        response.raise_for_status()

async def push_product(db: AsyncSession, customer_id: uuid.UUID, product_id: uuid.UUID) -> dict:
    """
    Push a product to OPS (Create or Update).
    Handles both ready products and decorated products.
    """
    # 1. Load product (with variants + images for full payload — Phase 8 Bug 3
    #    needs images[]; selectinload avoids the cartesian-product joinedload
    #    pitfall with two collections).
    product = (await db.execute(
        select(Product)
        .options(
            selectinload(Product.variants),
            selectinload(Product.images),
        )
        .where(Product.id == product_id)
    )).scalar_one_or_none()

    if not product:
        raise ValueError(f"Product {product_id} not found")

    supplier = (await db.execute(
        select(Supplier).where(Supplier.id == product.supplier_id)
    )).scalar_one_or_none()

    customer = (await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )).scalar_one_or_none()

    if not customer:
        raise ValueError(f"Customer {customer_id} not found")

    # 2. Check decorations
    decoration = (await db.execute(
        select(CustomerProductDecoration).where(
            CustomerProductDecoration.customer_id == customer_id,
            CustomerProductDecoration.product_id == product_id
        )
    )).scalar_one_or_none()

    dec_options = decoration.decoration_options if decoration else []

    # 3. Compute customer-specific pricing via the markup engine (Phase 8 Bug 2
    #    fix). Without this, the push silently bypassed every markup rule and
    #    OPS received the supplier wholesale price as the customer-facing price.
    priced = await calculate_price(db, customer_id, product_id)

    # 4. Route (ready vs decorated) & merge — pass the priced variants so the
    #    merge step uses markup-applied prices, not raw base_price.
    payload = merge_product_with_decorations(
        product, customer_id, dec_options, priced_variants=priced["variants"]
    )
    # Forward markup_rule context for downstream visibility (push_log, OPS
    # observability surfaces).
    payload["markup_rule"] = priced.get("markup_rule")

    # 5. Handle name conflict (Internal logic for now)
    desired_name = payload["name"]
    # Use supplier.push_name_prefix or fall back to slug-derived prefix
    prefix = supplier.push_name_prefix or f"{supplier.slug[:2].upper()}-"
    payload["name"] = f"{prefix}{desired_name}"

    # 5. Check push_mappings for idempotency
    mapping = (await db.execute(
        select(PushMapping).where(
            PushMapping.source_product_id == product_id,
            PushMapping.customer_id == customer_id
        )
    )).scalar_one_or_none()
    
    # 6. Prepare Log
    push_log = ProductPushLog(
        product_id=product_id,
        customer_id=customer_id,
        status="pending",
        pushed_at=datetime.now(timezone.utc)
    )
    db.add(push_log)
    
    try:
        # In production, n8n owns the actual OPS API call.
        # FastAPI prepares the payload and logs the intent.
        # REAL-PUSH-FIX: We do NOT write fake 99999 IDs to mappings.
        
        if mapping:
            # Update existing intent
            push_log.ops_product_id = str(mapping.target_ops_product_id)
            push_log.status = "pending"
        else:
            # Create new intent
            # Note: We do NOT create a PushMapping with a fake ID here.
            # Real ID will be back-filled by n8n callback.
            push_log.status = "pending"
            push_log.ops_product_id = "PENDING"
            
        await db.commit()
        await db.refresh(push_log)

        # 7. Trigger n8n webhook via trigger_n8n_push()
        # raise_for_status() inside trigger_n8n_push ensures n8n 5xx errors
        # propagate here so push_log flips to 'failed' instead of staying 'pending'.
        await trigger_n8n_push({
            "push_log_id": str(push_log.id),
            "customer_id": str(customer_id),
            "product_id": str(product_id),
            "payload": payload,
            "ops_auth": {
                "base_url": customer.ops_base_url,
                "token_url": customer.ops_token_url,
                "client_id": customer.ops_client_id,
                "client_secret": (customer.ops_auth_config or {}).get("client_secret")
            }
        })

        # 8. Phase 6 — mark the customer-catalog selection as pushed (optimistic).
        # Stale detection later runs in import_jobs._finalize_job: it flips
        # 'pushed' → 'stale' when product.last_synced > selection.pushed_at.
        # Auto-creates a selection in 'pushed' status if the push happened
        # without one (back-compat for admins who push directly from the
        # products page without first selecting).
        sel = (await db.execute(
            select(CustomerProductSelection).where(
                CustomerProductSelection.customer_id == customer_id,
                CustomerProductSelection.product_id == product_id,
            )
        )).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if sel is not None:
            sel.status = "pushed"
            sel.pushed_at = now
        else:
            db.add(CustomerProductSelection(
                customer_id=customer_id,
                product_id=product_id,
                status="pushed",
                added_at=now,
                pushed_at=now,
            ))
        await db.commit()

        return {
            "status": "pending",
            "push_log_id": str(push_log.id),
            "message": "Product payload prepared and queued for n8n push.",
            "payload": payload
        }
        
    except Exception as e:
        error_message = f"n8n trigger failed: {e}"
        # The pending push_log row was already committed on the happy-path
        # commit above, so we UPDATE it (instead of inserting a duplicate).
        # Use a fresh session because the outer transaction may be in a
        # rollback state.
        async with async_session() as audit_session:
            existing = await audit_session.get(ProductPushLog, push_log.id)
            if existing:
                existing.status = "failed"
                existing.error = error_message
                await audit_session.commit()
        return {"status": "failed", "message": error_message}
