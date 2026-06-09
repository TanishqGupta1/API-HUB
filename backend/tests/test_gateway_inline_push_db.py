"""Inline push DB path: product upserted then pushed (dry_run).

Task 2 of the n8n inline-push plan: when PushRequest.product is present,
prepare_push_intent upserts it via persist_product (ON CONFLICT) before the
existing resolve-from-catalog step, then the normal push path runs over it.
"""
from __future__ import annotations

import hashlib
import secrets
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from database import async_session
from modules.catalog.models import Product, ProductVariant, ProductImage
from modules.customers.models import Customer
from modules.integrations.models import IntegrationKey
from modules.push_log.models import ProductPushLog


@pytest.fixture(autouse=True)
def _mock_preflight_ok():
    ok = MagicMock()
    ok.ok = True
    ok.warnings = []
    with patch("modules.ops_push.gateway.run_preflight", new=AsyncMock(return_value=ok)):
        yield


@pytest_asyncio.fixture
async def key_and_customer(seed_supplier):
    raw = secrets.token_urlsafe(24)
    key_id = f"inline-key-{uuid4().hex[:8]}"
    async with async_session() as s:
        s.add(IntegrationKey(id=key_id, key_hash=hashlib.sha256(raw.encode()).hexdigest(), name="inline"))
        cust = Customer(
            name="Inline Co", ops_base_url="https://t.ops", ops_token_url="https://t.ops/tok",
            ops_client_id="x", ops_auth_config={"client_secret": "x"}, is_active=True,
        )
        s.add(cust)
        await s.commit()
        await s.refresh(cust)
        cid = cust.id
    try:
        yield {"raw": raw, "customer_id": cid, "supplier": seed_supplier}
    finally:
        async with async_session() as s:
            await s.execute(delete(ProductPushLog).where(ProductPushLog.customer_id == cid))
            await s.execute(delete(Product).where(Product.supplier_id == seed_supplier.id, Product.supplier_sku == "INLINE-1"))
            await s.execute(delete(Customer).where(Customer.id == cid))
            await s.execute(delete(IntegrationKey).where(IntegrationKey.id == key_id))
            await s.commit()


@pytest.mark.asyncio
async def test_inline_dry_run_upserts_and_pushes(client, key_and_customer):
    ctx = key_and_customer
    body = {
        "target": {"customer_id": str(ctx["customer_id"])},
        "source": {"supplier_slug": ctx["supplier"].slug},
        "product": {
            "supplier_sku": "INLINE-1",
            "product_name": "Inline One",
            "product_type": "apparel",
            "apparel_details": {"fabric": "cotton"},
        },
        "dry_run": True,
    }
    r = await client.post("/api/integrations/v1/push-requests", json=body,
                          headers={"X-Orchestrator-Key": ctx["raw"]})
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "dry_run_pushed"
    # Catalog upsert happened
    async with async_session() as s:
        prod = (await s.execute(
            select(Product).where(Product.supplier_id == ctx["supplier"].id,
                                   Product.supplier_sku == "INLINE-1")
        )).scalar_one_or_none()
    assert prod is not None and prod.product_name == "Inline One"


@pytest.mark.asyncio
async def test_inline_accept_includes_warnings_field(client, key_and_customer):
    """Task 3: non-blocking preflight warnings surface in the 202 body.

    Uses dry_run=True, so the route rebuilds PushRequestAccepted from the
    terminal push_log — warnings must survive that rebuild.
    """
    ctx = key_and_customer
    # Use a REAL CheckResult (run_preflight returns these, not dicts) so this
    # test exercises the .to_dict() serialization in the gateway — a dict mock
    # would silently pass even if serialization were broken.
    from modules.ops_push.preflight import CheckResult
    warning = CheckResult(name="markup", ok=True, detail="no rule; using passthrough")
    with patch("modules.ops_push.gateway.run_preflight", new=AsyncMock(
        return_value=MagicMock(ok=True, warnings=[warning])
    )):
        body = {
            "target": {"customer_id": str(ctx["customer_id"])},
            "source": {"supplier_slug": ctx["supplier"].slug},
            "product": {"supplier_sku": "INLINE-1", "product_name": "I1",
                        "product_type": "apparel", "apparel_details": {"fabric": "cotton"}},
            "dry_run": True,
        }
        r = await client.post("/api/integrations/v1/push-requests", json=body,
                              headers={"X-Orchestrator-Key": ctx["raw"]})
    assert r.status_code == 202, r.text
    assert r.json()["warnings"] == [
        {"name": "markup", "ok": True, "detail": "no rule; using passthrough",
         "field": None, "suggestion": None, "warn": False}
    ]


@pytest.mark.asyncio
async def test_inline_push_persists_variants_and_runs_mutation_sequence(client, key_and_customer):
    """Deep check: an inline product WITH variants+image must (a) persist all of
    it via persist_product and (b) actually run the OPS mutation chain — not just
    upsert a bare row. Covers the e2e-spec acceptance the shallow test skipped:
    'FakeOpsClient records setProduct -> setProductSize xN -> setProductPrice xN'.
    """
    ctx = key_and_customer
    body = {
        "target": {"customer_id": str(ctx["customer_id"])},
        "source": {"supplier_slug": ctx["supplier"].slug},
        "product": {
            "supplier_sku": "INLINE-1",
            "product_name": "Inline With Variants",
            "product_type": "apparel",
            "apparel_details": {"pricing_method": "tiered_variant"},
            "images": [
                {"url": "https://placehold.co/600x600", "image_type": "front", "sort_order": 0},
            ],
            "variants": [
                {"part_id": "IV-BLK-L", "color": "Black", "size": "L", "base_price": "10.00",
                 "inventory": 25,
                 "prices": [{"price_type": "Net", "quantity_min": 1, "quantity_max": 2147483647, "price": "10.00"}]},
                {"part_id": "IV-BLK-XL", "color": "Black", "size": "XL", "base_price": "11.00",
                 "inventory": 15,
                 "prices": [{"price_type": "Net", "quantity_min": 1, "quantity_max": 2147483647, "price": "11.00"}]},
            ],
        },
        "dry_run": True,
    }
    r = await client.post("/api/integrations/v1/push-requests", json=body,
                          headers={"X-Orchestrator-Key": ctx["raw"]})
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "dry_run_pushed", r.text
    push_log_id = r.json()["push_log_id"]

    # (a) Full inline product persisted — product + 2 variants + 1 image.
    async with async_session() as s:
        prod = (await s.execute(
            select(Product).where(Product.supplier_id == ctx["supplier"].id,
                                   Product.supplier_sku == "INLINE-1")
        )).scalar_one_or_none()
        assert prod is not None, "inline product not upserted"
        variant_count = len((await s.execute(
            select(ProductVariant).where(ProductVariant.product_id == prod.id)
        )).scalars().all())
        image_count = len((await s.execute(
            select(ProductImage).where(ProductImage.product_id == prod.id)
        )).scalars().all())
        push_log = await s.get(ProductPushLog, push_log_id)

    assert variant_count == 2, f"expected 2 variants persisted, got {variant_count}"
    assert image_count == 1, f"expected 1 image persisted, got {image_count}"

    # (b) The push actually ran the mutation chain (not just an upsert).
    steps = push_log.step_results or []
    mutations = [s.get("mutation") for s in steps if isinstance(s, dict)]
    assert "setProduct" in mutations, f"setProduct not in sequence: {mutations}"
    assert mutations.count("setProductSize") >= 2, f"expected >=2 setProductSize: {mutations}"
    assert mutations.count("setProductPrice") >= 2, f"expected >=2 setProductPrice: {mutations}"
    assert all(s.get("status") == "ok" for s in steps if isinstance(s, dict)), \
        f"some dry-run steps not ok: {steps}"
