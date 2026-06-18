"""Tests for the variant→option collapse pass."""
import pytest
from sqlalchemy import select

from modules.catalog.models import (
    Product,
    ProductVariant,
    ProductOption,
    ProductOptionAttribute,
)


async def _mk_product(db, supplier, variants, sku="PC54", name="Core Tee"):
    """Create a product + variants. `variants` = list of (color, size) tuples."""
    p = Product(supplier_id=supplier.id, supplier_sku=sku, product_name=name)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    for color, size in variants:
        db.add(
            ProductVariant(
                product_id=p.id, color=color, size=size,
                part_id=f"{color or 'x'}-{size or 'x'}",
            )
        )
    await db.commit()
    return p


async def _options(db, product_id):
    rows = (
        await db.execute(
            select(ProductOption).where(ProductOption.product_id == product_id)
        )
    ).scalars().all()
    return {o.option_key: o for o in rows}


async def _attrs(db, option_id):
    return (
        await db.execute(
            select(ProductOptionAttribute)
            .where(ProductOptionAttribute.product_option_id == option_id)
            .order_by(ProductOptionAttribute.sort_order)
        )
    ).scalars().all()


@pytest.mark.asyncio
async def test_optioningest_has_enabled_field():
    from modules.catalog.schemas import OptionIngest

    o = OptionIngest(option_key="color", title="Color")
    assert o.enabled is False  # backward-compatible default
    o2 = OptionIngest(option_key="color", title="Color", enabled=True)
    assert o2.enabled is True


@pytest.mark.asyncio
async def test_upsert_options_persists_enabled(db, seed_supplier):
    from modules.catalog.ingest import _upsert_options
    from modules.catalog.schemas import OptionIngest, OptionAttributeIngest

    p = await _mk_product(db, seed_supplier, [])
    await _upsert_options(
        db, p.id,
        [OptionIngest(
            option_key="color", title="Color", enabled=True,
            attributes=[OptionAttributeIngest(title="Red", attribute_key="red")],
        )],
    )
    await db.commit()
    opts = await _options(db, p.id)
    assert opts["color"].enabled is True


@pytest.mark.no_db
def test_distinct_normalizes_and_dedups():
    from modules.catalog.option_collapse import _distinct
    # "Red"/"RED "/"red" collapse to one; first display form wins; alpha sort
    assert _distinct(["Navy", "Red", "RED ", "red", None, "  "]) == ["Navy", "Red"]


@pytest.mark.no_db
def test_size_sort_order():
    from modules.catalog.option_collapse import _distinct, _size_sort_key
    out = _distinct(["XL", "S", "2XL", "M", "L", "XS"], sort_key=_size_sort_key)
    assert out == ["XS", "S", "M", "L", "XL", "2XL"]


@pytest.mark.no_db
def test_slug():
    from modules.catalog.option_collapse import _slug
    assert _slug("Forest Green") == "forest-green"
    assert _slug("  Heather/Grey ") == "heather-grey"
