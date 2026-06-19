"""T9 — SanMar → OPS end-to-end smoke test.

Seeds a minimal SanMar-like product (supplier + 1 variant + markup rule +
customer) and runs a dry-run push through the full pipeline:

  preflight → payload build → FakeOpsClient execution → step_results write

Network-bound preflight checks (OAuth2 token fetch, image HEAD requests) are
patched to return pass so the test runs offline.  Everything else — markup
resolution, variant checks, required-fields, push payload builder,
FakeOpsClient, step_results shape — runs for real.
"""
from __future__ import annotations

import hashlib
import secrets
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from database import async_session
from modules.catalog.models import Product, ProductVariant, CustomerProductSelection
from modules.customers.models import Customer
from modules.integrations.models import IntegrationKey
from modules.markup.models import MarkupRule
from modules.ops_push.preflight import CheckResult
from modules.push_log.models import ProductPushLog
from modules.push_mappings.models import PushMapping
from modules.suppliers.models import Supplier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _passing(name: str) -> CheckResult:
    return CheckResult(name, True, "patched for smoke test")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def smoke_key():
    raw = secrets.token_urlsafe(24)
    key_id = f"smoke-key-{uuid4().hex[:8]}"
    async with async_session() as s:
        k = IntegrationKey(
            id=key_id,
            key_hash=hashlib.sha256(raw.encode()).hexdigest(),
            name="T9 smoke key",
        )
        s.add(k)
        await s.commit()
    try:
        yield raw
    finally:
        async with async_session() as s:
            await s.execute(delete(IntegrationKey).where(IntegrationKey.id == key_id))
            await s.commit()


@pytest_asyncio.fixture
async def smoke_scaffold():
    """Supplier + product + variant + customer + markup rule — all in one fixture."""
    supplier_slug = f"sanmar-smoke-{uuid4().hex[:6]}"
    async with async_session() as s:
        supplier = Supplier(
            name="SanMar Smoke",
            slug=supplier_slug,
            protocol="promostandards",
            promostandards_code="SANMAR",
            base_url="https://promostandards.org/api",
            auth_config={"id": "test", "password": "test"},
            is_active=True,
            has_decoration_overlay=False,
        )
        s.add(supplier)
        await s.flush()

        product = Product(
            supplier_id=supplier.id,
            supplier_sku="PC61-SMOKE",
            product_name="Port & Company Essential Tee",
            product_type="apparel",
            category="T-Shirts",
        )
        s.add(product)
        await s.flush()

        variant = ProductVariant(
            product_id=product.id,
            sku="PC61-SMOKE-NVY-M",
            color="Navy",
            size="M",
            base_price=Decimal("3.99"),
            inventory=120,
        )
        s.add(variant)

        customer = Customer(
            name="Smoke Test Co",
            ops_base_url="https://smoke.ops.test",
            ops_token_url="https://smoke.ops.test/oauth/token",
            ops_client_id="smoke-client",
            ops_auth_config={"client_secret": "smoke-secret"},
            is_active=True,
            # category_id is required by OPS; preflight now blocks pushes for
            # customers with no resolvable category (check_category_resolvable).
            default_ops_category_id=46,
        )
        s.add(customer)
        await s.flush()

        rule = MarkupRule(
            customer_id=customer.id,
            scope="all",
            markup_pct=Decimal("20.00"),
        )
        s.add(rule)

        await s.commit()
        await s.refresh(supplier)
        await s.refresh(product)
        await s.refresh(customer)
        s.expunge_all()

    try:
        yield {"supplier": supplier, "product": product, "customer": customer}
    finally:
        async with async_session() as s:
            await s.execute(delete(PushMapping).where(PushMapping.customer_id == customer.id))
            await s.execute(delete(ProductPushLog).where(ProductPushLog.customer_id == customer.id))
            await s.execute(
                delete(CustomerProductSelection).where(
                    CustomerProductSelection.customer_id == customer.id
                )
            )
            await s.execute(delete(MarkupRule).where(MarkupRule.customer_id == customer.id))
            await s.execute(delete(Customer).where(Customer.id == customer.id))
            await s.execute(delete(ProductVariant).where(ProductVariant.product_id == product.id))
            await s.execute(delete(Product).where(Product.id == product.id))
            await s.execute(delete(Supplier).where(Supplier.id == supplier.id))
            await s.commit()


# ---------------------------------------------------------------------------
# Helpers to patch network-bound preflight checks
# ---------------------------------------------------------------------------

def _patch_network_checks():
    """Context manager that stubs OAuth2 + image HEAD checks to pass."""
    return patch.multiple(
        "modules.ops_push.preflight",
        check_ops_oauth2_reachable=AsyncMock(return_value=_passing("ops_oauth2_reachable")),
        check_image_urls_reachable=AsyncMock(return_value=_passing("image_urls_reachable")),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dry_run_push_returns_dry_run_pushed(client, smoke_scaffold, smoke_key):
    """Full dry-run: preflight passes, FakeOpsClient runs, status=dry_run_pushed."""
    with _patch_network_checks():
        resp = await client.post(
            "/api/integrations/v1/push-requests",
            json={
                "source": {"supplier_slug": smoke_scaffold["supplier"].slug},
                "target": {"customer_id": str(smoke_scaffold["customer"].id)},
                "product_ref": {"supplier_sku": "PC61-SMOKE"},
                "dry_run": True,
            },
            headers={"X-Orchestrator-Key": smoke_key},
        )

    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "dry_run_pushed", body
    assert body["dry_run"] is True
    assert body["supplier_sku"] == "PC61-SMOKE"


@pytest.mark.asyncio
async def test_stale_mapping_auto_recovery(smoke_scaffold):
    """A live push whose push_mapping points to a now-deleted OPS product
    must auto-clear the stale mapping and recreate the product, instead of
    failing forever with 'Product with id N not found, skipping update'."""
    from modules.ops_client.fake import FakeOpsClient
    from modules.ops_push.gateway import execute_push

    product = smoke_scaffold["product"]
    customer = smoke_scaffold["customer"]
    STALE_OPS_ID = 556

    # Seed a stale mapping (product -> deleted OPS id) + an accepted live push.
    async with async_session() as s:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        s.add(PushMapping(
            source_system="api-hub",
            source_product_id=product.id,
            source_supplier_sku=product.supplier_sku,
            customer_id=customer.id,
            target_ops_base_url=customer.ops_base_url or "",
            target_ops_product_id=STALE_OPS_ID,
            pushed_at=now, updated_at=now, status="active",
        ))
        push_log = ProductPushLog(
            product_id=product.id,
            customer_id=customer.id,
            status="accepted",
            pushed_at=now,
            supplier_slug=smoke_scaffold["supplier"].slug,
            supplier_sku=product.supplier_sku,
            dry_run=False,
            callback_status="not_requested",
        )
        s.add(push_log)
        await s.commit()
        push_log_id = push_log.id

    # Live push, but inject a Fake client that rejects updates to 556 (deleted).
    fake = FakeOpsClient(deleted_ops_ids={STALE_OPS_ID})
    from modules.ops_push import gateway as _gw

    class _Adapter:
        is_dry_run = False
        def __init__(self, c): self._client = c
        async def aclose(self): pass
        def __getattr__(self, n): return getattr(self._client, n)

    with patch.object(_gw, "_build_live_client", return_value=_Adapter(fake)):
        await execute_push(push_log_id)

    # Push recovered: status pushed, stale mapping replaced with a fresh id.
    async with async_session() as s:
        pl = await s.get(ProductPushLog, push_log_id)
        assert pl.status == "pushed", pl.step_results
        step1 = pl.step_results[0]
        assert step1["mutation"] == "setProduct"
        assert step1["status"] == "ok"
        assert "recreated after stale-mapping cleanup" in step1.get("note", "")

        mapping = (await s.execute(
            select(PushMapping).where(PushMapping.source_product_id == product.id)
        )).scalar_one()
        assert mapping.target_ops_product_id != STALE_OPS_ID  # recreated, not the dead id


@pytest.mark.asyncio
async def test_auto_category_creates_and_reuses(smoke_scaffold):
    """Auto-category creates an OPS category for the product's category name on
    first push and reuses the cached mapping on the second (no duplicate)."""
    from modules.ops_client.fake import FakeOpsClient
    from modules.ops_push.gateway import _resolve_ops_category
    from modules.ops_config.models import OpsCategoryMapping

    product = smoke_scaffold["product"]   # category="T-Shirts"
    customer = smoke_scaffold["customer"]
    fake = FakeOpsClient()

    async with async_session() as s:
        cust = await s.get(Customer, customer.id)
        prod = await s.get(Product, product.id)
        # First call: no mapping → creates the OPS category + caches it.
        first = await _resolve_ops_category(s, fake, cust, prod, dry_run=False)
        await s.commit()
        assert first is not None

        rows = (await s.execute(
            select(OpsCategoryMapping).where(OpsCategoryMapping.customer_id == customer.id)
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].category_key == "t-shirts"  # normalized from "T-Shirts "

    async with async_session() as s:
        cust = await s.get(Customer, customer.id)
        prod = await s.get(Product, product.id)
        # Second call: reuses the cached id, creates no duplicate mapping.
        second = await _resolve_ops_category(s, fake, cust, prod, dry_run=False)
        assert second == first
        rows = (await s.execute(
            select(OpsCategoryMapping).where(OpsCategoryMapping.customer_id == customer.id)
        )).scalars().all()
        assert len(rows) == 1

    # Cleanup
    async with async_session() as s:
        await s.execute(
            delete(OpsCategoryMapping).where(OpsCategoryMapping.customer_id == customer.id)
        )
        await s.commit()


@pytest.mark.asyncio
async def test_auto_category_mapping_survives_caller_rollback(smoke_scaffold):
    """Regression (review HIGH): the OPS category is a LIVE side-effect, so its
    mapping must be durable even if the caller's transaction later aborts —
    otherwise a rolled-back mapping orphans the OPS category and the retry creates
    a DUPLICATE. Simulates execute_push failing after _resolve_ops_category:
    resolve (which now commits the mapping in its own transaction), roll the caller
    session back, then assert the mapping persists and a second resolve reuses it.

    This test FAILS against the old bare-`db.flush()` behaviour and passes with the
    own-transaction commit."""
    from modules.ops_client.fake import FakeOpsClient
    from modules.ops_push.gateway import _resolve_ops_category
    from modules.ops_config.models import OpsCategoryMapping

    product = smoke_scaffold["product"]   # category="T-Shirts"
    customer = smoke_scaffold["customer"]
    fake = FakeOpsClient()

    async with async_session() as s:
        cust = await s.get(Customer, customer.id)
        prod = await s.get(Product, product.id)
        first = await _resolve_ops_category(s, fake, cust, prod, dry_run=False)
        assert first is not None
        # Caller's transaction aborts AFTER the OPS category was created. The old
        # flush-only behaviour would lose the mapping right here.
        await s.rollback()

    async with async_session() as s:
        rows = (await s.execute(
            select(OpsCategoryMapping).where(OpsCategoryMapping.customer_id == customer.id)
        )).scalars().all()
        assert len(rows) == 1               # mapping survived the rollback
        assert rows[0].ops_category_id == first

        # Retry path: a second resolve reuses the cached mapping — no duplicate.
        cust = await s.get(Customer, customer.id)
        prod = await s.get(Product, product.id)
        second = await _resolve_ops_category(s, fake, cust, prod, dry_run=False)
        assert second == first
        rows = (await s.execute(
            select(OpsCategoryMapping).where(OpsCategoryMapping.customer_id == customer.id)
        )).scalars().all()
        assert len(rows) == 1

    async with async_session() as s:
        await s.execute(
            delete(OpsCategoryMapping).where(OpsCategoryMapping.customer_id == customer.id)
        )
        await s.commit()


@pytest.mark.asyncio
async def test_dry_run_step_results_shape(client, smoke_scaffold, smoke_key):
    """step_results entries must match OPSStepResult shape (T6 fix)."""
    with _patch_network_checks():
        resp = await client.post(
            "/api/integrations/v1/push-requests",
            json={
                "source": {"supplier_slug": smoke_scaffold["supplier"].slug},
                "target": {"customer_id": str(smoke_scaffold["customer"].id)},
                "product_ref": {"supplier_sku": "PC61-SMOKE"},
                "dry_run": True,
            },
            headers={"X-Orchestrator-Key": smoke_key},
        )

    assert resp.status_code == 202, resp.text
    push_log_id = resp.json()["push_log_id"]

    async with async_session() as s:
        row = await s.get(ProductPushLog, push_log_id)

    assert row is not None
    steps = row.step_results or []
    assert len(steps) >= 1, "expected at least one step_result entry"

    for step in steps:
        assert isinstance(step["step"], int), f"step must be int, got {step.get('step')!r}"
        assert isinstance(step["mutation"], str), "mutation must be str"
        # "warning" added as a valid status for non-blocking failures
        # (e.g. updateProductStock when OPS has no stock entry yet — Phase 6).
        assert step["status"] in ("ok", "failed", "warning"), f"unexpected status: {step.get('status')!r}"
        assert isinstance(step["ops_ids"], dict), "ops_ids must be dict"
        assert isinstance(step["attempted_at"], str), "attempted_at must be str"
        assert isinstance(step["request_fingerprint"], str), "request_fingerprint must be str"


@pytest.mark.asyncio
async def test_dry_run_plan_includes_set_product_and_set_product_size(client, smoke_scaffold, smoke_key):
    """Push plan must include setProduct (step 1) and setProductSize (for the 1 variant)."""
    with _patch_network_checks():
        resp = await client.post(
            "/api/integrations/v1/push-requests",
            json={
                "source": {"supplier_slug": smoke_scaffold["supplier"].slug},
                "target": {"customer_id": str(smoke_scaffold["customer"].id)},
                "product_ref": {"supplier_sku": "PC61-SMOKE"},
                "dry_run": True,
            },
            headers={"X-Orchestrator-Key": smoke_key},
        )

    assert resp.status_code == 202, resp.text
    push_log_id = resp.json()["push_log_id"]

    async with async_session() as s:
        row = await s.get(ProductPushLog, push_log_id)

    mutations = [s["mutation"] for s in (row.step_results or [])]
    assert "setProduct" in mutations, f"setProduct not in plan: {mutations}"
    assert "setProductSize" in mutations, f"setProductSize not in plan: {mutations}"


@pytest.mark.asyncio
async def test_dry_run_set_product_step_returns_products_id(client, smoke_scaffold, smoke_key):
    """FakeOpsClient returns a stub products_id in step 1's ops_ids dict."""
    with _patch_network_checks():
        resp = await client.post(
            "/api/integrations/v1/push-requests",
            json={
                "source": {"supplier_slug": smoke_scaffold["supplier"].slug},
                "target": {"customer_id": str(smoke_scaffold["customer"].id)},
                "product_ref": {"supplier_sku": "PC61-SMOKE"},
                "dry_run": True,
            },
            headers={"X-Orchestrator-Key": smoke_key},
        )

    assert resp.status_code == 202, resp.text
    push_log_id = resp.json()["push_log_id"]

    async with async_session() as s:
        row = await s.get(ProductPushLog, push_log_id)

    steps = row.step_results or []
    set_product_step = next((s for s in steps if s.get("mutation") == "setProduct"), None)
    assert set_product_step is not None, "setProduct step missing from step_results"
    assert "products_id" in set_product_step["ops_ids"], (
        f"setProduct step ops_ids missing products_id: {set_product_step['ops_ids']}"
    )


@pytest.mark.asyncio
async def test_preflight_blocks_when_variant_has_no_price(client, smoke_scaffold, smoke_key):
    """If base_price is missing, preflight must block with 422."""
    async with async_session() as s:
        result = await s.execute(
            select(ProductVariant).where(
                ProductVariant.product_id == smoke_scaffold["product"].id
            )
        )
        variant = result.scalar_one()
        variant.base_price = None
        await s.commit()

    try:
        with _patch_network_checks():
            resp = await client.post(
                "/api/integrations/v1/push-requests",
                json={
                    "source": {"supplier_slug": smoke_scaffold["supplier"].slug},
                    "target": {"customer_id": str(smoke_scaffold["customer"].id)},
                    "product_ref": {"supplier_sku": "PC61-SMOKE"},
                    "dry_run": True,
                },
                headers={"X-Orchestrator-Key": smoke_key},
            )
        assert resp.status_code == 422, resp.text
        assert "PREFLIGHT_BLOCKER" in resp.text
    finally:
        async with async_session() as s:
            result = await s.execute(
                select(ProductVariant).where(
                    ProductVariant.product_id == smoke_scaffold["product"].id
                )
            )
            variant = result.scalar_one()
            variant.base_price = Decimal("3.99")
            await s.commit()
