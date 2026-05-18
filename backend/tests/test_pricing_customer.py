"""Customer-aware pricing — markup + storefront overrides."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import delete


@pytest.mark.asyncio
async def test_customer_quote_applies_customer_markup(db, seed_supplier):
    """A 25% all-scope markup raises a $12.50 unit price to $15.63."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, VariantIngest, VariantPriceIngest, ApparelDetailsIngest
    from modules.catalog.models import Product, ProductVariant
    from modules.customers.models import Customer
    from modules.markup.models import MarkupRule
    from modules.pricing.customer_quote import resolve_customer_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session
    from sqlalchemy import select

    payload = ProductIngest(
        supplier_sku="CMK-1",
        product_name="customer markup",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="CMK-V1",
                color="Black",
                size="L",
                base_price=Decimal("8.00"),
                prices=[
                    VariantPriceIngest(price_type="Net", quantity_min=1, quantity_max=2147483647, price=Decimal("12.50")),
                ],
            ),
        ],
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        customer = Customer(
            name="Acme",
            ops_base_url="https://test.ops.com",
            ops_token_url="https://test.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(customer)
        await s.flush()
        rule = MarkupRule(
            customer_id=customer.id,
            scope="all",
            markup_pct=Decimal("25.00"),
            rounding="none",
            priority=0,
        )
        s.add(rule)
        await s.commit()
        vid = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()
        cid = customer.id

    async with async_session() as s:
        result = await resolve_customer_quote(
            QuoteRequest(product_id=pid, variant_id=vid, qty=1),
            cid,
            s,
        )
        assert result.base_unit_price == Decimal("12.50")
        assert result.unit_price == Decimal("15.63")
        assert result.markup_pct == Decimal("25.00")
        assert result.storefront_override_applied is False

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == pid))
        await s.execute(delete(Customer).where(Customer.id == cid))
        await s.commit()


@pytest.mark.asyncio
async def test_customer_quote_falls_back_when_no_markup(db, seed_supplier):
    """No markup rules — unit_price equals base, markup_pct is None."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, VariantIngest, VariantPriceIngest, ApparelDetailsIngest
    from modules.catalog.models import Product, ProductVariant
    from modules.customers.models import Customer
    from modules.pricing.customer_quote import resolve_customer_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session
    from sqlalchemy import select

    payload = ProductIngest(
        supplier_sku="NO-MK",
        product_name="no markup",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="NMV1",
                color="W",
                size="M",
                base_price=Decimal("9.99"),
                prices=[
                    VariantPriceIngest(price_type="Net", quantity_min=1, quantity_max=2147483647, price=Decimal("9.99")),
                ],
            ),
        ],
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        customer = Customer(
            name="No Markup Co",
            ops_base_url="https://test.ops.com",
            ops_token_url="https://test.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(customer)
        await s.commit()
        vid = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()
        cid = customer.id

    async with async_session() as s:
        result = await resolve_customer_quote(
            QuoteRequest(product_id=pid, variant_id=vid, qty=1),
            cid,
            s,
        )
        assert result.base_unit_price == Decimal("9.99")
        assert result.unit_price == Decimal("9.99")
        assert result.markup_pct is None

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == pid))
        await s.execute(delete(Customer).where(Customer.id == cid))
        await s.commit()


@pytest.mark.asyncio
async def test_storefront_override_replaces_unit_price(db, seed_supplier):
    """A fixed_unit_price override replaces both base price and markup."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, VariantIngest, VariantPriceIngest, ApparelDetailsIngest
    from modules.catalog.models import Product, ProductVariant
    from modules.customers.models import Customer
    from modules.markup.models import MarkupRule
    from modules.ops_config.models import ProductStorefrontConfig
    from modules.pricing.customer_quote import resolve_customer_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session
    from sqlalchemy import select

    payload = ProductIngest(
        supplier_sku="OVR-1",
        product_name="storefront override",
        product_type="apparel",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="OVR-V1",
                color="Red",
                size="S",
                base_price=Decimal("12.50"),
                prices=[
                    VariantPriceIngest(price_type="Net", quantity_min=1, quantity_max=2147483647, price=Decimal("12.50")),
                ],
            ),
        ],
    )
    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, payload)
        customer = Customer(
            name="Override Co",
            ops_base_url="https://test3.ops.com",
            ops_token_url="https://test3.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(customer)
        await s.flush()
        s.add(MarkupRule(
            customer_id=customer.id,
            scope="all",
            markup_pct=Decimal("25.00"),
            rounding="none",
            priority=0,
        ))
        s.add(ProductStorefrontConfig(
            product_id=pid,
            customer_id=customer.id,
            ops_category_id="999",
            option_mappings={},
            pricing_overrides={"fixed_unit_price": "20.00"},
        ))
        await s.commit()
        vid = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()
        cid = customer.id

    async with async_session() as s:
        result = await resolve_customer_quote(
            QuoteRequest(product_id=pid, variant_id=vid, qty=2),
            cid,
            s,
        )
        assert result.base_unit_price == Decimal("12.50")
        assert result.unit_price == Decimal("20.00")
        assert result.total == Decimal("40.00")
        assert result.storefront_override_applied is True

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == pid))
        await s.execute(delete(Customer).where(Customer.id == cid))
        await s.commit()


@pytest.mark.asyncio
async def test_customer_quote_endpoint_happy_path(db, seed_supplier):
    """POST /api/customers/{id}/pricing/quote applies markup and returns CustomerQuoteResult."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, VariantIngest, VariantPriceIngest, ApparelDetailsIngest
    from modules.catalog.models import Product, ProductVariant
    from modules.customers.models import Customer
    from modules.markup.models import MarkupRule
    from database import async_session
    from sqlalchemy import select, delete
    from httpx import AsyncClient, ASGITransport
    import main

    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, ProductIngest(
            supplier_sku="EP-CMK-T7",
            product_name="task7 happy",
            product_type="apparel",
            apparel_details=ApparelDetailsIngest(),
            variants=[VariantIngest(
                part_id="T7V1",
                color="Black",
                size="L",
                prices=[VariantPriceIngest(price_type="Net", quantity_min=1, quantity_max=2147483647, price=Decimal("10.00"))],
            )],
        ))
        customer = Customer(
            name="Task7 Co",
            ops_base_url="https://t7.ops.com",
            ops_token_url="https://t7.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(customer)
        await s.flush()
        s.add(MarkupRule(customer_id=customer.id, scope="all", markup_pct=Decimal("50.00"), rounding="none", priority=0))
        await s.commit()
        vid = (await s.execute(select(ProductVariant.id).where(ProductVariant.product_id == pid))).scalar_one()
        cid = customer.id

    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.post(f"/api/customers/{cid}/pricing/quote", json={
            "product_id": str(pid), "variant_id": str(vid), "qty": 4,
        }, headers={"X-Ingest-Secret": "test-secret-do-not-use-in-prod"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["base_unit_price"] == "10.00"
    assert body["unit_price"] == "15.00"
    assert body["total"] == "60.00"
    assert Decimal(body["markup_pct"]) == Decimal("50")
    assert body["storefront_override_applied"] is False

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == pid))
        await s.execute(delete(Customer).where(Customer.id == cid))
        await s.commit()


@pytest.mark.asyncio
async def test_customer_quote_endpoint_unknown_customer(db, seed_supplier):
    """POST /api/customers/{unknown_id}/pricing/quote returns 404 mentioning 'customer'."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest, VariantIngest, VariantPriceIngest, ApparelDetailsIngest
    from modules.catalog.models import Product, ProductVariant
    from database import async_session
    from sqlalchemy import select, delete
    from httpx import AsyncClient, ASGITransport
    import main

    async with async_session() as s:
        pid = await persist_product(s, seed_supplier.id, ProductIngest(
            supplier_sku="EP-UNK-T7",
            product_name="task7 unknown customer",
            product_type="apparel",
            apparel_details=ApparelDetailsIngest(),
            variants=[VariantIngest(
                part_id="T7V2",
                prices=[VariantPriceIngest(price_type="Net", quantity_min=1, quantity_max=2147483647, price=Decimal("9.99"))],
            )],
        ))
        await s.commit()
        vid = (await s.execute(select(ProductVariant.id).where(ProductVariant.product_id == pid))).scalar_one()

    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
        resp = await client.post(
            "/api/customers/00000000-0000-0000-0000-000000000000/pricing/quote",
            json={"product_id": str(pid), "variant_id": str(vid), "qty": 1},
            headers={"X-Ingest-Secret": "test-secret-do-not-use-in-prod"},
        )
    assert resp.status_code == 404
    assert "customer" in resp.text.lower()

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()
