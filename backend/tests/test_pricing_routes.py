"""Pricing HTTP routes — POST /api/pricing/quote."""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_quote_route_apparel(db, seed_supplier):
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, VariantIngest, VariantPriceIngest, ApparelDetailsIngest
    from modules.catalog.models import Product, ProductVariant
    from database import async_session
    from sqlalchemy import select, delete
    import main

    payload = ProductIngest(
        supplier_sku="ROUTE-APPAREL",
        product_name="route apparel",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="V-ROUTE",
                color="Red",
                size="M",
                base_price=Decimal("10.00"),
                prices=[
                    VariantPriceIngest(price_type="Net", quantity_min=1, quantity_max=999, price=Decimal("10.00")),
                ],
            ),
        ],
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        await s.commit()
        variant_id = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()

    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.post("/api/pricing/quote", json={
            "product_id": str(pid),
            "variant_id": str(variant_id),
            "qty": 5,
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_price"] == "10.00"
    assert data["total"] == "50.00"

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_quote_route_returns_404_for_missing_product(db):
    import main
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.post("/api/pricing/quote", json={
            "product_id": "00000000-0000-0000-0000-000000000099",
            "qty": 1,
        })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_quote_route_returns_422_for_bounds_error(db, seed_supplier):
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, PrintDetailsIngest
    from modules.catalog.models import Product
    from database import async_session
    from sqlalchemy import delete
    import main

    payload = ProductIngest(
        supplier_sku="ROUTE-BOUNDS",
        product_name="bounded print route",
        product_type="print",
        print_details=PrintDetailsIngest(
            min_width=Decimal("6"),
            max_width=Decimal("48"),
            min_height=Decimal("6"),
            max_height=Decimal("48"),
            base_price_per_sq_unit=Decimal("0.10"),
        ),
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        await s.commit()

    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.post("/api/pricing/quote", json={
            "product_id": str(pid),
            "width": "1",
            "height": "10",
            "qty": 1,
        })
    assert resp.status_code == 422

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_customer_quote_applies_markup(db, seed_supplier):
    """Customer quote with 50% markup on a $10 apparel item → $15 unit."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, VariantIngest, VariantPriceIngest, ApparelDetailsIngest
    from modules.catalog.models import Product, ProductVariant
    from modules.customers.models import Customer
    from modules.markup.models import MarkupRule
    from database import async_session
    from sqlalchemy import select, delete
    import main

    async with async_session() as s:
        customer = Customer(
            name="Test Storefront",
            ops_base_url="https://test.ops.example.com",
            ops_token_url="https://test.ops.example.com/token",
            ops_client_id="test-client",
        )
        s.add(customer)
        await s.flush()  # populate customer.id
        rule = MarkupRule(customer_id=customer.id, scope="all", markup_pct=50, rounding="none")
        s.add(rule)
        await s.commit()
        cid = customer.id

    product_payload = ProductIngest(
        supplier_sku="CQ-APPAREL",
        product_name="customer quote apparel",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="V-CQ",
                color="Blue",
                size="L",
                base_price=Decimal("10.00"),
                prices=[
                    VariantPriceIngest(price_type="Net", quantity_min=1, quantity_max=999, price=Decimal("10.00")),
                ],
            ),
        ],
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, product_payload)
        await s.commit()
        variant_id = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()

    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.post(f"/api/customers/{cid}/pricing/quote", json={
            "product_id": str(pid),
            "variant_id": str(variant_id),
            "qty": 2,
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["base_unit_price"] == "10.00"
    assert data["unit_price"] == "15.00"
    assert data["total"] == "30.00"
    assert Decimal(data["markup_pct"]) == Decimal("50")
    assert data["storefront_override_applied"] is False

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == pid))
        await s.execute(delete(Customer).where(Customer.id == cid))
        await s.commit()
