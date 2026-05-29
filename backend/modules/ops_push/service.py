import uuid
import logging
from typing import Optional

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.catalog.models import Product, CustomerProductSelection
from modules.customers.models import Customer
from modules.suppliers.models import Supplier
from modules.decorations.models import CustomerProductDecoration
from modules.integrations.admin_proxy import get_or_create_admin_proxy_key
from modules.integrations.schemas import (
    PushRequest,
    PushRequestProductRef,
    PushRequestSource,
    PushRequestTarget,
)
from modules.push_log.models import ProductPushLog
from modules.markup.engine import calculate_price
from .gateway import execute_push, prepare_push_intent
from .task_runner import run_push_task
from .merge import merge_product_with_decorations

logger = logging.getLogger(__name__)


async def push_product(
    db: AsyncSession,
    customer_id: uuid.UUID,
    product_id: uuid.UUID,
    background_tasks: Optional[BackgroundTasks] = None,
) -> dict:
    """Admin-UI push entry point — dispatches through the integration gateway.

    Response shape preserved for the admin UI: `{status, push_log_id, message, payload}`.
    The `payload` is the OPS-shape merge (admin preview pane reads this);
    everything else flows through `prepare_push_intent` + `execute_push` so
    the push_log row, idempotency ledger, preflight, and OPS mutation plan
    are all the same code paths an n8n orchestrator would take.

    Status string follows the gateway vocab now ('accepted' → 'processing' →
    'pushed' / 'failed' / 'partial_failure'). T22 updates the frontend
    status-map to render 'accepted'.
    """
    # Resolve product + supplier + customer for payload preview. The gateway
    # also resolves these internally, but we still build the merge payload
    # here so the admin UI preview pane keeps its current shape.
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
    if not supplier:
        raise ValueError(f"Supplier for product {product_id} not found")

    customer = (await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )).scalar_one_or_none()
    if not customer:
        raise ValueError(f"Customer {customer_id} not found")

    decoration = (await db.execute(
        select(CustomerProductDecoration).where(
            CustomerProductDecoration.customer_id == customer_id,
            CustomerProductDecoration.product_id == product_id,
        )
    )).scalar_one_or_none()
    dec_options = decoration.decoration_options if decoration else []

    priced = await calculate_price(db, customer_id, product_id)
    payload = merge_product_with_decorations(
        product, customer_id, dec_options, priced_variants=priced["variants"]
    )
    payload["markup_rule"] = priced.get("markup_rule")
    prefix = supplier.push_name_prefix or f"{supplier.slug[:2].upper()}-"
    payload["name"] = f"{prefix}{payload['name']}"

    # Dispatch through the gateway. Admin route is JWT-authed, not header-
    # authed, so we use the persisted synthetic IntegrationKey (is_synthetic=
    # True) — orchestrator auth filters those out at SQL level, so it cannot
    # be forged via X-Orchestrator-Key. The row satisfies push_log.key_id FK
    # + idempotency ledger keying.
    admin_key = await get_or_create_admin_proxy_key(db)
    req = PushRequest(
        target=PushRequestTarget(customer_id=customer_id),
        source=PushRequestSource(supplier_slug=supplier.slug),
        product_ref=PushRequestProductRef(product_id=product_id),
        dry_run=False,
    )
    accepted = await prepare_push_intent(req, admin_key, db, idempotency_key=None)

    # Live push → background-task execute_push so the admin UI gets its
    # response immediately. If the caller didn't pass BackgroundTasks (e.g.
    # invoked from a non-FastAPI context), fall back to awaiting inline so
    # the row doesn't stay in 'accepted' forever.
    if background_tasks is not None:
        background_tasks.add_task(run_push_task, accepted.push_log_id)
    else:
        await execute_push(accepted.push_log_id)
        await db.refresh(
            await db.get(ProductPushLog, accepted.push_log_id)
        )

    return {
        "status": accepted.status,
        "push_log_id": str(accepted.push_log_id),
        "message": "Push request accepted via integration gateway.",
        "payload": payload,
    }
