"""Bug 5 fix — auto-resolve push_mapping_options from product_options.

The first push for any (customer, product) used to fail preflight with
"missing target_ops_option_id" because nothing pre-populated
push_mapping_options. ImportJob already filled ops_option_id /
ops_attribute_id on the ProductOption / ProductOptionAttribute rows;
``resolve_push_mappings`` just copies them into push_mapping_options.

These tests cover:
* options + attributes with known ops_*_id → rows created
* options with no master_option match → reported as missing, no row written
* idempotent — running twice produces the same row set
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import Product, ProductOption, ProductOptionAttribute
from modules.customers.models import Customer
from modules.push_mappings.models import PushMapping, PushMappingOption
from modules.push_mappings.service import resolve_push_mappings
from database import async_session


async def _seed_product_with_options(
    supplier_id: uuid.UUID,
    *,
    color_ops_id: int | None,
    size_ops_id: int | None,
    color_attrs: list[tuple[str, int | None]],
    size_attrs: list[tuple[str, int | None]],
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed a customer + product with two options (color, size).

    Returns (customer_id, product_id). Each option's ops_option_id and each
    attribute's ops_attribute_id can be None to simulate ImportJob not
    finding a master_option match.
    """
    async with async_session() as s:
        cust = Customer(
            name=f"resolve-test-{uuid.uuid4().hex[:8]}",
            ops_base_url="https://test.ops.com",
            ops_token_url="https://test.ops.com/token",
            ops_client_id="test-client",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(cust)
        await s.flush()

        prod = Product(
            supplier_id=supplier_id,
            supplier_sku=f"SKU-{uuid.uuid4().hex[:8]}",
            product_name="Resolve Test Product",
        )
        s.add(prod)
        await s.flush()

        color_opt = ProductOption(
            product_id=prod.id,
            option_key="color",
            title="Color",
            ops_option_id=color_ops_id,
            master_option_id=1,
            sort_order=0,
        )
        s.add(color_opt)
        await s.flush()
        for key, ops_id in color_attrs:
            s.add(ProductOptionAttribute(
                product_option_id=color_opt.id,
                attribute_key=key,
                title=key.title(),
                ops_attribute_id=ops_id,
                master_attribute_id=10 if ops_id else None,
                price=Decimal("0.00"),
                sort_order=0,
            ))

        size_opt = ProductOption(
            product_id=prod.id,
            option_key="size",
            title="Size",
            ops_option_id=size_ops_id,
            master_option_id=2,
            sort_order=1,
        )
        s.add(size_opt)
        await s.flush()
        for key, ops_id in size_attrs:
            s.add(ProductOptionAttribute(
                product_option_id=size_opt.id,
                attribute_key=key,
                title=key.upper(),
                ops_attribute_id=ops_id,
                master_attribute_id=20 if ops_id else None,
                price=Decimal("0.00"),
                sort_order=0,
            ))

        await s.commit()
        return cust.id, prod.id


@pytest.mark.asyncio
async def test_resolve_creates_rows_for_known_ops_ids(seed_supplier):
    cust_id, prod_id = await _seed_product_with_options(
        seed_supplier.id,
        color_ops_id=100, size_ops_id=200,
        color_attrs=[("Navy", 1001), ("Red", 1002)],
        size_attrs=[("S", 2001), ("M", 2002), ("L", 2003)],
    )

    async with async_session() as s:
        summary = await resolve_push_mappings(s, cust_id, prod_id)

    assert summary.options_resolved == 2
    assert summary.attributes_resolved == 5
    assert summary.missing_option_keys == []
    assert summary.missing_attribute_keys == []

    # Confirm the rows landed and carry the right OPS IDs.
    async with async_session() as s:
        rows = (await s.execute(
            select(PushMappingOption)
            .join(PushMapping, PushMappingOption.push_mapping_id == PushMapping.id)
            .where(PushMapping.source_product_id == prod_id, PushMapping.customer_id == cust_id)
            .order_by(PushMappingOption.source_option_key, PushMappingOption.source_attribute_key)
        )).scalars().all()
        assert len(rows) == 5
        navy = next(r for r in rows if r.source_attribute_key == "Navy")
        assert navy.target_ops_option_id == 100
        assert navy.target_ops_attribute_id == 1001


@pytest.mark.asyncio
async def test_resolve_reports_missing_when_master_option_unmatched(seed_supplier):
    # color has no ops_option_id at all → should be missing
    # size has ops_option_id but one attribute has no ops_attribute_id → that
    # specific (size, M) should be in missing_attribute_keys
    cust_id, prod_id = await _seed_product_with_options(
        seed_supplier.id,
        color_ops_id=None, size_ops_id=200,
        color_attrs=[("Navy", None)],
        size_attrs=[("S", 2001), ("M", None), ("L", 2003)],
    )

    async with async_session() as s:
        summary = await resolve_push_mappings(s, cust_id, prod_id)

    assert "color" in summary.missing_option_keys
    assert summary.options_resolved == 1                   # only size
    assert summary.attributes_resolved == 2                # only S + L
    assert "size/M" in summary.missing_attribute_keys


@pytest.mark.asyncio
async def test_resolve_is_idempotent(seed_supplier):
    cust_id, prod_id = await _seed_product_with_options(
        seed_supplier.id,
        color_ops_id=100, size_ops_id=200,
        color_attrs=[("Navy", 1001)],
        size_attrs=[("S", 2001)],
    )

    async with async_session() as s:
        first = await resolve_push_mappings(s, cust_id, prod_id)
        second = await resolve_push_mappings(s, cust_id, prod_id)

    assert first.push_mapping_id == second.push_mapping_id
    assert first.attributes_resolved == second.attributes_resolved == 2

    async with async_session() as s:
        count = len((await s.execute(
            select(PushMappingOption)
            .join(PushMapping, PushMappingOption.push_mapping_id == PushMapping.id)
            .where(PushMapping.source_product_id == prod_id, PushMapping.customer_id == cust_id)
        )).scalars().all())
        assert count == 2  # Not 4 — the second resolve replaces, doesn't accumulate


@pytest.mark.asyncio
async def test_resolve_404s_on_missing_customer(seed_supplier):
    # Real product, fake customer
    cust_id, prod_id = await _seed_product_with_options(
        seed_supplier.id,
        color_ops_id=100, size_ops_id=200,
        color_attrs=[("Navy", 1001)],
        size_attrs=[("S", 2001)],
    )
    bogus_customer = uuid.uuid4()

    async with async_session() as s:
        with pytest.raises(ValueError, match=f"Customer {bogus_customer} not found"):
            await resolve_push_mappings(s, bogus_customer, prod_id)
