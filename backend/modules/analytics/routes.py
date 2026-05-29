"""Margin analytics — per-customer markup summary + push volume stats."""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.auth.dependencies import VGAdmin
from modules.catalog.models import Product, ProductVariant
from modules.customers.models import Customer
from modules.markup.engine import apply_markup, resolve_rule
from modules.markup.models import MarkupRule
from modules.push_log.models import ProductPushLog

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# ─── Response schemas ─────────────────────────────────────────────────────────

class CustomerMarginRow(BaseModel):
    customer_id: str
    customer_name: str
    is_active: bool
    active_rules: int
    default_markup_pct: Optional[float]
    default_markup_amount: Optional[float]
    pushed_all_time: int
    pushed_last_30d: int
    push_success_rate: Optional[float]   # 0–1; None if no pushes yet
    last_push_at: Optional[datetime]
    # Weighted-average real margin % across all variant prices of pushed products
    estimated_avg_markup_pct: Optional[float]


class MarginSummary(BaseModel):
    total_customers: int
    active_customers: int
    customers_with_rules: int
    total_active_rules: int
    pushed_last_30d: int
    pushed_all_time: int
    overall_success_rate: Optional[float]


class MarginsResponse(BaseModel):
    generated_at: datetime
    summary: MarginSummary
    customers: list[CustomerMarginRow]


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.get("/margins", response_model=MarginsResponse)
async def get_margins(_: VGAdmin, db: AsyncSession = Depends(get_db)) -> MarginsResponse:
    """Return per-customer margin analytics.

    Includes markup rule config, push-volume counts, success rates, and a
    weighted-average estimated markup % computed from pushed product variants.
    Restricted to vg_admin.
    """
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # ── Load all customers ──
    customers = (await db.execute(
        select(Customer).order_by(Customer.name)
    )).scalars().all()

    # ── Push log — all rows, aggregate in Python ──
    all_logs = (await db.execute(
        select(
            ProductPushLog.customer_id,
            ProductPushLog.product_id,
            ProductPushLog.supplier_slug,
            ProductPushLog.supplier_sku,
            ProductPushLog.status,
            ProductPushLog.pushed_at,
        )
    )).all()

    logs_by_cust: dict[uuid.UUID, list] = defaultdict(list)
    for row in all_logs:
        logs_by_cust[row.customer_id].append(row)

    # ── Active markup rules ──
    all_rules = (await db.execute(
        select(MarkupRule).where(MarkupRule.is_active.is_(True))
    )).scalars().all()

    rules_by_cust: dict[uuid.UUID, list[MarkupRule]] = defaultdict(list)
    for r in all_rules:
        rules_by_cust[r.customer_id].append(r)

    # ── Distinct (customer, product) pairs for pushed products ──
    pushed_pairs = (await db.execute(
        select(
            ProductPushLog.customer_id,
            ProductPushLog.product_id,
            ProductPushLog.supplier_slug,
        )
        .where(ProductPushLog.status == "pushed")
        .distinct()
    )).all()

    pushed_product_ids = list({row.product_id for row in pushed_pairs})

    # ── Batch-load variants + product metadata ──
    variants_by_product: dict[uuid.UUID, list[ProductVariant]] = defaultdict(list)
    products_by_id: dict[uuid.UUID, Product] = {}

    if pushed_product_ids:
        variants = (await db.execute(
            select(ProductVariant).where(
                ProductVariant.product_id.in_(pushed_product_ids)
            )
        )).scalars().all()
        for v in variants:
            variants_by_product[v.product_id].append(v)

        prods = (await db.execute(
            select(Product).where(Product.id.in_(pushed_product_ids))
        )).scalars().all()
        products_by_id = {p.id: p for p in prods}

    # ── Build per-customer rows ──
    rows: list[CustomerMarginRow] = []
    global_total = 0
    global_30d = 0
    global_success = 0

    for customer in customers:
        cid = customer.id
        logs = logs_by_cust.get(cid, [])
        rules = rules_by_cust.get(cid, [])

        pushed_all = len(logs)
        pushed_30d = sum(
            1 for lg in logs
            if lg.pushed_at is not None and lg.pushed_at >= thirty_days_ago
        )
        successes = sum(1 for lg in logs if lg.status in ("pushed", "dry_run_pushed"))
        last_push = max(
            (lg.pushed_at for lg in logs if lg.pushed_at is not None),
            default=None,
        )
        success_rate = (successes / pushed_all) if pushed_all > 0 else None

        global_total += pushed_all
        global_30d += pushed_30d
        global_success += successes

        # Default rule (scope='all') for headline display
        default_rule = next((r for r in rules if r.scope == "all"), None)
        default_pct = (
            float(default_rule.markup_pct)
            if default_rule and default_rule.markup_pct is not None
            else None
        )
        default_amt = (
            float(default_rule.markup_amount)
            if default_rule and default_rule.markup_amount is not None
            else None
        )

        # Weighted-average real markup % across all variant prices of pushed products
        markup_pcts: list[float] = []
        for pair in pushed_pairs:
            if pair.customer_id != cid:
                continue
            product = products_by_id.get(pair.product_id)
            if product is None:
                continue
            rule = resolve_rule(
                rules,
                product.supplier_sku,
                product.category,
                pair.supplier_slug,
            )
            if rule is None:
                continue
            for v in variants_by_product.get(pair.product_id, []):
                if v.base_price is None:
                    continue
                base = Decimal(str(v.base_price))
                final = apply_markup(base, rule)
                if final is not None and base > 0:
                    markup_pcts.append(float((final - base) / base * 100))

        est_markup = (
            round(sum(markup_pcts) / len(markup_pcts), 1)
            if markup_pcts
            else None
        )

        rows.append(CustomerMarginRow(
            customer_id=str(cid),
            customer_name=customer.name,
            is_active=customer.is_active,
            active_rules=len(rules),
            default_markup_pct=default_pct,
            default_markup_amount=default_amt,
            pushed_all_time=pushed_all,
            pushed_last_30d=pushed_30d,
            push_success_rate=round(success_rate, 3) if success_rate is not None else None,
            last_push_at=last_push,
            estimated_avg_markup_pct=est_markup,
        ))

    overall_success_rate = (
        round(global_success / global_total, 3) if global_total > 0 else None
    )

    summary = MarginSummary(
        total_customers=len(customers),
        active_customers=sum(1 for c in customers if c.is_active),
        customers_with_rules=sum(1 for c in customers if rules_by_cust.get(c.id)),
        total_active_rules=len(all_rules),
        pushed_last_30d=global_30d,
        pushed_all_time=global_total,
        overall_success_rate=overall_success_rate,
    )

    return MarginsResponse(
        generated_at=now,
        summary=summary,
        customers=rows,
    )
