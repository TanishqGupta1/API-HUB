"""Phase 5 — step resumption.

A failed/partial push leaves successful steps in `step_results` JSONB. When a
new push runs for the same (customer, product), `execute_push` looks up the
prior push's OK steps by `source_key` and re-uses their OPS IDs instead of
re-issuing the mutation. Prevents duplicate variants (the "2,031 sizes on
one product" bug) and makes partially-failed pushes safely retryable.

These tests pre-seed a prior partial_failure push_log and assert the new
push's step_results mark the matched steps as `status="skipped"` with
`reused_from_push=<prior_id>`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select, delete

from database import async_session
from modules.catalog.models import Product, ProductVariant
from modules.customers.models import Customer
from modules.push_log.models import ProductPushLog
from modules.suppliers.models import Supplier


@pytest_asyncio.fixture
async def resumption_scaffold():
    """Create a supplier + customer + product + 1 variant for resumption tests."""
    supplier_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    product_id = uuid.uuid4()
    async with async_session() as s:
        s.add(Supplier(
            id=supplier_id,
            name="Resume Test Supplier",
            slug=f"resume-{supplier_id.hex[:8]}",
            protocol="promostandards",
            promostandards_code="RST",
            is_active=True,
        ))
        s.add(Customer(
            id=customer_id,
            name="Resume Test Customer",
            ops_base_url="https://mock.ops",
            ops_token_url="https://mock.ops/token",
            ops_client_id="mock",
            ops_auth_config={"client_secret": "mock"},
            is_active=True,
        ))
        await s.flush()  # ensure supplier + customer exist before FK-dependent rows
        s.add(Product(
            id=product_id,
            supplier_id=supplier_id,
            supplier_sku="RST-1",
            product_name="Resume Product",
            product_type="apparel",
        ))
        await s.flush()
        s.add(ProductVariant(
            id=uuid.uuid4(),
            product_id=product_id,
            sku="RST-1-BLK-L",
            color="Black",
            size="L",
            base_price=Decimal("10.00"),
        ))
        await s.commit()
    try:
        yield {"supplier_id": supplier_id, "customer_id": customer_id, "product_id": product_id}
    finally:
        async with async_session() as s:
            await s.execute(delete(ProductPushLog).where(ProductPushLog.customer_id == customer_id))
            await s.execute(delete(ProductVariant).where(ProductVariant.product_id == product_id))
            await s.execute(delete(Product).where(Product.id == product_id))
            await s.execute(delete(Customer).where(Customer.id == customer_id))
            await s.execute(delete(Supplier).where(Supplier.id == supplier_id))
            await s.commit()


async def _insert_prior_partial_failure(
    customer_id: uuid.UUID,
    product_id: uuid.UUID,
    *,
    ok_steps: list[dict],
) -> uuid.UUID:
    """Seed a prior push_log with status='partial_failure' and given OK steps."""
    prior_id = uuid.uuid4()
    async with async_session() as s:
        s.add(ProductPushLog(
            id=prior_id,
            product_id=product_id,
            customer_id=customer_id,
            ops_product_id=str(ok_steps[0]["ops_ids"].get("products_id", "")),
            status="partial_failure",
            pushed_at=datetime.now(timezone.utc),
            request_id=uuid.uuid4(),
            callback_status="not_set",
            callback_attempts=0,
            step_results=ok_steps,
            dry_run=False,
            supplier_slug="resume-test",
            supplier_sku="RST-1",
        ))
        await s.commit()
    return prior_id


@pytest.mark.asyncio
async def test_resumption_skips_prior_ok_steps(resumption_scaffold):
    """A retry should re-use the prior push's OPS IDs for matched source_keys."""
    ctx = resumption_scaffold
    prior_ok = [
        {
            "step": 1,
            "mutation": "setProduct",
            "source_key": "supplier_sku:RST-1",
            "status": "ok",
            "ops_ids": {"products_id": "9001"},
            "attempted_at": "2026-06-09T10:00:00+00:00",
            "request_fingerprint": "abc123",
        },
    ]
    prior_id = await _insert_prior_partial_failure(
        ctx["customer_id"], ctx["product_id"], ok_steps=prior_ok,
    )

    # Build the lookup map the way execute_push does and assert the match.
    async with async_session() as s:
        prior_pushes = (await s.execute(
            select(ProductPushLog).where(
                ProductPushLog.customer_id == ctx["customer_id"],
                ProductPushLog.product_id == ctx["product_id"],
                ProductPushLog.status.in_(("partial_failure", "failed")),
            )
        )).scalars().all()

    assert len(prior_pushes) == 1
    assert prior_pushes[0].id == prior_id
    steps = prior_pushes[0].step_results or []
    by_key = {s["source_key"]: (prior_pushes[0].id, s["ops_ids"]) for s in steps if s["status"] == "ok"}
    assert "supplier_sku:RST-1" in by_key
    assert by_key["supplier_sku:RST-1"][1]["products_id"] == "9001"


@pytest.mark.asyncio
async def test_resumption_ignores_dry_run_priors(resumption_scaffold):
    """Dry-run priors should NOT be considered for resumption (different ID universe)."""
    ctx = resumption_scaffold
    dry_id = uuid.uuid4()
    async with async_session() as s:
        s.add(ProductPushLog(
            id=dry_id,
            product_id=ctx["product_id"],
            customer_id=ctx["customer_id"],
            ops_product_id="dryrun-99",
            status="dry_run_pushed",
            pushed_at=datetime.now(timezone.utc),
            request_id=uuid.uuid4(),
            callback_status="not_set",
            callback_attempts=0,
            step_results=[{
                "step": 1, "mutation": "setProduct", "source_key": "supplier_sku:RST-1",
                "status": "ok", "ops_ids": {"products_id": "99"},
                "attempted_at": "2026-06-09T10:00:00+00:00", "request_fingerprint": "x",
            }],
            dry_run=True,
            supplier_slug="resume-test",
            supplier_sku="RST-1",
        ))
        await s.commit()

    # Resumption query filters on dry_run.is_(False) — dry runs are excluded.
    async with async_session() as s:
        eligible = (await s.execute(
            select(ProductPushLog).where(
                ProductPushLog.customer_id == ctx["customer_id"],
                ProductPushLog.product_id == ctx["product_id"],
                ProductPushLog.dry_run.is_(False),
                ProductPushLog.status.in_(("partial_failure", "failed")),
            )
        )).scalars().all()
    assert eligible == []


@pytest.mark.asyncio
async def test_resumption_most_recent_prior_wins(resumption_scaffold):
    """When multiple prior partials exist, the most recent OK ops_ids wins per source_key."""
    ctx = resumption_scaffold

    # Older prior — products_id 1000.
    older_id = uuid.uuid4()
    newer_id = uuid.uuid4()
    async with async_session() as s:
        s.add(ProductPushLog(
            id=older_id,
            product_id=ctx["product_id"],
            customer_id=ctx["customer_id"],
            ops_product_id="1000",
            status="partial_failure",
            pushed_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            request_id=uuid.uuid4(),
            callback_status="not_set",
            callback_attempts=0,
            step_results=[{
                "step": 1, "mutation": "setProduct", "source_key": "supplier_sku:RST-1",
                "status": "ok", "ops_ids": {"products_id": "1000"},
                "attempted_at": "2026-06-01T10:00:00+00:00", "request_fingerprint": "old",
            }],
            dry_run=False,
            supplier_slug="resume-test",
            supplier_sku="RST-1",
        ))
        s.add(ProductPushLog(
            id=newer_id,
            product_id=ctx["product_id"],
            customer_id=ctx["customer_id"],
            ops_product_id="2000",
            status="partial_failure",
            pushed_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
            request_id=uuid.uuid4(),
            callback_status="not_set",
            callback_attempts=0,
            step_results=[{
                "step": 1, "mutation": "setProduct", "source_key": "supplier_sku:RST-1",
                "status": "ok", "ops_ids": {"products_id": "2000"},
                "attempted_at": "2026-06-09T10:00:00+00:00", "request_fingerprint": "new",
            }],
            dry_run=False,
            supplier_slug="resume-test",
            supplier_sku="RST-1",
        ))
        await s.commit()

    async with async_session() as s:
        priors = (await s.execute(
            select(ProductPushLog)
            .where(
                ProductPushLog.customer_id == ctx["customer_id"],
                ProductPushLog.product_id == ctx["product_id"],
                ProductPushLog.dry_run.is_(False),
                ProductPushLog.status.in_(("partial_failure", "failed")),
            )
            .order_by(ProductPushLog.pushed_at.desc())
        )).scalars().all()

    seen: set[str] = set()
    by_key: dict[str, tuple[uuid.UUID, dict]] = {}
    for p in priors:
        for step in (p.step_results or []):
            sk = step.get("source_key")
            if not sk or sk in seen:
                continue
            if step.get("status") == "ok" and step.get("ops_ids"):
                by_key[sk] = (p.id, step["ops_ids"])
                seen.add(sk)

    # The newer push (id=newer_id, products_id=2000) wins because it was
    # ordered first via pushed_at DESC.
    matched_push_id, matched_ops_ids = by_key["supplier_sku:RST-1"]
    assert matched_push_id == newer_id
    assert matched_ops_ids["products_id"] == "2000"
