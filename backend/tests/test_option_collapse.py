"""Tests for the variant→option collapse pass."""
import pytest
from sqlalchemy import delete, select

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


# ─── Task 1 tests ─────────────────────────────────────────────────────────────

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


# ─── Task 2 tests — pure helpers ──────────────────────────────────────────────

@pytest.mark.no_db
def test_distinct_normalizes_and_dedups():
    from modules.catalog.option_collapse import _distinct
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


# ─── Task 3 tests — derive_options ────────────────────────────────────────────

def _matrix(colors, sizes):
    return [(c, s) for c in colors for s in sizes]


@pytest.mark.asyncio
async def test_matrix_collapse(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    colors = ["Red", "Navy", "Black", "White", "Royal", "Green", "Maroon", "Gold"]
    sizes = ["S", "M", "L", "XL", "2XL", "3XL"]
    p = await _mk_product(db, seed_supplier, _matrix(colors, sizes))

    res = await derive_options(db, p.id)

    assert (res.colors, res.sizes) == (1, 1)
    assert (res.color_attrs, res.size_attrs) == (8, 6)
    opts = await _options(db, p.id)
    assert set(opts) == {"color", "size"}
    assert opts["color"].options_type == "swatch"
    assert opts["size"].options_type == "dropdown"
    assert len(await _attrs(db, opts["color"].id)) == 8
    assert len(await _attrs(db, opts["size"].id)) == 6
    from modules.catalog.models import ProductSize
    sizes_rows = (await db.execute(
        select(ProductSize).where(ProductSize.product_id == p.id)
    )).scalars().all()
    assert sizes_rows == []


@pytest.mark.asyncio
async def test_enabled_and_status_set(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, [("Red", "M")])
    await derive_options(db, p.id)
    opts = await _options(db, p.id)
    for o in opts.values():
        assert o.enabled is True
        assert o.status == 1


@pytest.mark.asyncio
async def test_required_symmetric(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, [("Red", "M"), ("Navy", "L")])
    await derive_options(db, p.id)
    opts = await _options(db, p.id)
    assert opts["color"].required is True
    assert opts["size"].required is True


@pytest.mark.asyncio
async def test_normalize_then_dedup(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, [("Red", "M"), ("RED ", "M"), ("red", "M")])
    res = await derive_options(db, p.id)
    assert res.color_attrs == 1


@pytest.mark.asyncio
async def test_mixed_nulls(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, [("Red", None), (None, "M"), ("Navy", "L")])
    res = await derive_options(db, p.id)
    assert res.color_attrs == 2
    assert res.size_attrs == 2


@pytest.mark.asyncio
async def test_size_ordering_persisted(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, [("Red", s) for s in ["XL", "S", "2XL", "M"]])
    await derive_options(db, p.id)
    opts = await _options(db, p.id)
    titles = [a.title for a in await _attrs(db, opts["size"].id)]
    assert titles == ["S", "M", "XL", "2XL"]


@pytest.mark.asyncio
async def test_noop_when_no_color_or_size(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, [(None, None), (None, None)])
    res = await derive_options(db, p.id)
    assert (res.colors, res.sizes) == (0, 0)
    assert await _options(db, p.id) == {}


@pytest.mark.asyncio
async def test_idempotent(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, _matrix(["Red", "Navy"], ["S", "M"]))
    r1 = await derive_options(db, p.id)
    r2 = await derive_options(db, p.id)
    assert (r1.color_attrs, r1.size_attrs) == (r2.color_attrs, r2.size_attrs) == (2, 2)
    opts = await _options(db, p.id)
    assert len(await _attrs(db, opts["color"].id)) == 2
    assert len(await _attrs(db, opts["size"].id)) == 2


# ─── Task 4 tests — prune ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_prune_removed_color(db, seed_supplier):
    """8 colors then 6 — the 2 dropped colors disappear."""
    from modules.catalog.option_collapse import derive_options
    eight = ["Red", "Navy", "Black", "White", "Royal", "Green", "Maroon", "Gold"]
    p = await _mk_product(db, seed_supplier, [(c, "M") for c in eight])
    await derive_options(db, p.id)
    opts = await _options(db, p.id)
    assert len(await _attrs(db, opts["color"].id)) == 8

    await db.execute(
        delete(ProductVariant).where(
            ProductVariant.product_id == p.id,
            ProductVariant.color.in_(["Maroon", "Gold"]),
        )
    )
    await db.commit()
    await derive_options(db, p.id)
    opts = await _options(db, p.id)
    assert len(await _attrs(db, opts["color"].id)) == 6


@pytest.mark.asyncio
async def test_prune_axis_emptied(db, seed_supplier):
    """Color option removed entirely when all color variants gone."""
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, [("Red", "M"), ("Navy", "L")])
    await derive_options(db, p.id)
    assert "color" in await _options(db, p.id)

    await db.execute(
        ProductVariant.__table__.update()
        .where(ProductVariant.product_id == p.id)
        .values(color=None)
    )
    await db.commit()
    await derive_options(db, p.id)
    opts = await _options(db, p.id)
    assert "color" not in opts
    assert "size" in opts


# ─── Task 5 tests — derive_options_bulk ───────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_backfill_one_supplier(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options_bulk
    await _mk_product(db, seed_supplier, [("Red", "M")], sku="A", name="A")
    await _mk_product(db, seed_supplier, [("Navy", "L"), ("Navy", "XL")], sku="B", name="B")

    totals = await derive_options_bulk(db, supplier_id=seed_supplier.id)

    assert totals["products"] == 2
    assert totals["color_options"] == 2
    assert totals["size_options"] == 2


# ─── Task 6 tests — trigger routes ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_route_derive_single_product(client, db, seed_supplier):
    p = await _mk_product(db, seed_supplier, [("Red", "M"), ("Navy", "L")])
    r = await client.post(f"/api/products/{p.id}/derive-options")
    assert r.status_code == 200
    body = r.json()
    assert body["colors"] == 1 and body["sizes"] == 1
    assert body["color_attrs"] == 2 and body["size_attrs"] == 2


@pytest.mark.asyncio
async def test_route_derive_bulk(client, db, seed_supplier):
    await _mk_product(db, seed_supplier, [("Red", "M")], sku="A", name="A")
    r = await client.post(f"/api/products/derive-options?supplier_id={seed_supplier.id}")
    assert r.status_code == 200
    assert r.json()["products"] >= 1
