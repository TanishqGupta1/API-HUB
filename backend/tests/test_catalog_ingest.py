"""Behavior tests for /api/ingest/{supplier_id}/* endpoints."""
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

SECRET = {"X-Ingest-Secret": "test-secret-do-not-use-in-prod"}


@pytest.mark.asyncio
async def test_ingest_rejects_missing_secret(client: AsyncClient, seed_supplier):
    r = await client.post(f"/api/ingest/{seed_supplier.id}/products", json=[])
    assert r.status_code == 401
    assert "secret" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ingest_rejects_wrong_secret(client: AsyncClient, seed_supplier):
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        headers={"X-Ingest-Secret": "wrong"},
        json=[],
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_ingest_accepts_correct_secret_empty_body(client: AsyncClient, seed_supplier):
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        headers=SECRET,
        json=[],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["records_processed"] == 0
    assert body["status"] == "completed"


def test_ingest_schemas_importable():
    from modules.catalog.schemas import (
        CategoryIngest,
        ImageIngest,
        IngestResult,
        InventoryIngest,
        PriceIngest,
        ProductIngest,
        VariantIngest,
    )

    p = ProductIngest(supplier_sku="X", product_name="X")
    assert p.variants == [] and p.images == []

    v = VariantIngest(part_id="p", base_price=None)
    assert v.base_price is None


# ─── Task A1: Category model roundtrip ──────────────────────────────────────

@pytest.mark.asyncio
async def test_category_model_roundtrip(db, seed_supplier):
    from modules.catalog.models import Category

    root = Category(supplier_id=seed_supplier.id, external_id="root", name="Root")
    db.add(root)
    await db.commit()
    await db.refresh(root)

    child = Category(
        supplier_id=seed_supplier.id, external_id="root.a", name="A", parent_id=root.id
    )
    db.add(child)
    await db.commit()
    await db.refresh(child)

    assert child.parent_id == root.id


# ─── Task A2-A4: Categories endpoint ────────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_categories_creates_rows(client: AsyncClient, db, seed_supplier):
    from modules.catalog.models import Category

    batch = [
        {"external_id": "apparel", "name": "Apparel"},
        {"external_id": "apparel.shirts", "name": "Shirts", "parent_external_id": "apparel"},
        {"external_id": "apparel.pants", "name": "Pants", "parent_external_id": "apparel"},
    ]
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/categories",
        headers=SECRET,
        json=batch,
    )
    assert r.status_code == 200
    assert r.json()["records_processed"] == 3

    rows = (
        await db.execute(select(Category).where(Category.supplier_id == seed_supplier.id))
    ).scalars().all()
    by_ext = {c.external_id: c for c in rows}
    assert set(by_ext) == {"apparel", "apparel.shirts", "apparel.pants"}
    assert by_ext["apparel.shirts"].parent_id == by_ext["apparel"].id
    assert by_ext["apparel.pants"].parent_id == by_ext["apparel"].id


@pytest.mark.asyncio
async def test_ingest_categories_is_idempotent(client: AsyncClient, db, seed_supplier):
    from modules.catalog.models import Category

    batch = [{"external_id": "apparel", "name": "Apparel"}]
    r1 = await client.post(
        f"/api/ingest/{seed_supplier.id}/categories", headers=SECRET, json=batch
    )
    assert r1.status_code == 200

    batch[0]["name"] = "Apparel Updated"
    r2 = await client.post(
        f"/api/ingest/{seed_supplier.id}/categories", headers=SECRET, json=batch
    )
    assert r2.status_code == 200

    rows = (
        await db.execute(select(Category).where(Category.supplier_id == seed_supplier.id))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].name == "Apparel Updated"


@pytest.mark.asyncio
async def test_ingest_categories_rejects_inactive_supplier(
    client: AsyncClient, inactive_supplier
):
    r = await client.post(
        f"/api/ingest/{inactive_supplier.id}/categories",
        headers=SECRET,
        json=[{"external_id": "x", "name": "X"}],
    )
    assert r.status_code == 409
    assert "not active" in r.json()["detail"].lower()


# ─── Task A5-A7: Products endpoint ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_products_creates_product_with_variants(
    client: AsyncClient, db, seed_supplier
):
    from modules.catalog.models import Product, ProductImage, ProductVariant

    payload = [
        {
            "supplier_sku": "TSHIRT-100",
            "product_name": "Heavy Tee",
            "brand": "VG",
            "variants": [
                {
                    "part_id": "v1",
                    "color": "Black",
                    "size": "M",
                    "sku": "TSHIRT-100-BLK-M",
                    "base_price": "19.50",
                    "inventory": 42,
                },
                {
                    "part_id": "v2",
                    "color": "Black",
                    "size": "L",
                    "sku": "TSHIRT-100-BLK-L",
                    "base_price": "19.50",
                    "inventory": 11,
                },
            ],
            "images": [
                {"url": "https://cdn/vg/tshirt-100-front.jpg", "image_type": "front", "sort_order": 0},
                {"url": "https://cdn/vg/tshirt-100-back.jpg", "image_type": "back", "sort_order": 1},
            ],
        }
    ]
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/products", headers=SECRET, json=payload
    )
    assert r.status_code == 200
    assert r.json()["records_processed"] == 1

    prod = (
        await db.execute(select(Product).where(Product.supplier_sku == "TSHIRT-100"))
    ).scalar_one()
    assert prod.brand == "VG"

    variants = (
        await db.execute(
            select(ProductVariant).where(ProductVariant.product_id == prod.id)
        )
    ).scalars().all()
    assert {v.size for v in variants} == {"M", "L"}

    images = (
        await db.execute(select(ProductImage).where(ProductImage.product_id == prod.id))
    ).scalars().all()
    assert {i.image_type for i in images} == {"front", "back"}


@pytest.mark.asyncio
async def test_ingest_products_is_idempotent_and_updates(
    client: AsyncClient, db, seed_supplier
):
    from modules.catalog.models import Product

    payload = [{"supplier_sku": "P1", "product_name": "Original", "brand": "VG"}]
    await client.post(
        f"/api/ingest/{seed_supplier.id}/products", headers=SECRET, json=payload
    )

    payload[0]["product_name"] = "Renamed"
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/products", headers=SECRET, json=payload
    )
    assert r.status_code == 200

    rows = (
        await db.execute(
            select(Product).where(
                Product.supplier_id == seed_supplier.id,
                Product.supplier_sku == "P1",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].product_name == "Renamed"


@pytest.mark.asyncio
async def test_ingest_products_links_category_by_external_id(
    client: AsyncClient, db, seed_supplier
):
    from modules.catalog.models import Category, Product

    await client.post(
        f"/api/ingest/{seed_supplier.id}/categories",
        headers=SECRET,
        json=[{"external_id": "shirts", "name": "Shirts"}],
    )
    await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        headers=SECRET,
        json=[
            {
                "supplier_sku": "S1",
                "product_name": "Linked",
                "category_external_id": "shirts",
            }
        ],
    )
    cat = (
        await db.execute(
            select(Category).where(
                Category.supplier_id == seed_supplier.id,
                Category.external_id == "shirts",
            )
        )
    ).scalar_one()
    prod = (
        await db.execute(
            select(Product).where(
                Product.supplier_id == seed_supplier.id,
                Product.supplier_sku == "S1",
            )
        )
    ).scalar_one()
    assert prod.category_id == cat.id


@pytest.mark.asyncio
async def test_ingest_products_upserts_options_and_attributes(
    client: AsyncClient, db, seed_supplier
):
    from modules.catalog.models import Product, ProductOption, ProductOptionAttribute

    payload = [
        {
            "supplier_sku": "DECAL-131",
            "product_name": "Decals - General Performance",
            "options": [
                {
                    "option_key": "inkFinish",
                    "title": "Ink Finish",
                    "options_type": "Radio Button",
                    "sort_order": 3,
                    "master_option_id": 112,
                    "ops_option_id": 456,
                    "required": False,
                    "attributes": [
                        {"title": "Gloss", "sort_order": 0, "ops_attribute_id": None},
                        {"title": "Matte", "sort_order": 1, "ops_attribute_id": None},
                    ],
                }
            ],
        }
    ]
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/products", headers=SECRET, json=payload
    )
    assert r.status_code == 200

    prod = (
        await db.execute(
            select(Product).where(
                Product.supplier_id == seed_supplier.id,
                Product.supplier_sku == "DECAL-131",
            )
        )
    ).scalar_one()

    opt = (
        await db.execute(
            select(ProductOption).where(ProductOption.product_id == prod.id)
        )
    ).scalar_one()
    assert opt.option_key == "inkFinish"
    assert opt.title == "Ink Finish"
    assert opt.master_option_id == 112
    assert opt.ops_option_id == 456

    attrs = (
        await db.execute(
            select(ProductOptionAttribute).where(
                ProductOptionAttribute.product_option_id == opt.id
            )
        )
    ).scalars().all()
    assert [a.title for a in sorted(attrs, key=lambda a: a.sort_order)] == [
        "Gloss",
        "Matte",
    ]

    # Update attributes via JSON string payload; attributes should be replaced.
    payload[0]["options"][0]["attributes"] = '[{"title":"FLX+","sort_order":2}]'
    r2 = await client.post(
        f"/api/ingest/{seed_supplier.id}/products", headers=SECRET, json=payload
    )
    assert r2.status_code == 200

    attrs2 = (
        await db.execute(
            select(ProductOptionAttribute).where(
                ProductOptionAttribute.product_option_id == opt.id
            )
        )
    ).scalars().all()
    assert [a.title for a in attrs2] == ["FLX+"]


# ─── Task A8: Inventory endpoint ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_inventory_updates_and_skips_unknown(
    client: AsyncClient, db, seed_supplier
):
    from modules.catalog.models import Product, ProductVariant

    await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        headers=SECRET,
        json=[
            {
                "supplier_sku": "INV-1",
                "product_name": "Inv Test",
                "variants": [
                    {"part_id": "v1", "sku": "INV-1-M", "size": "M", "inventory": 0}
                ],
            }
        ],
    )
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/inventory",
        headers=SECRET,
        json=[
            {
                "supplier_sku": "INV-1",
                "part_id": "INV-1-M",
                "quantity_available": 99,
                "warehouse": "CA",
            },
            {
                "supplier_sku": "INV-1",
                "part_id": "stale",
                "quantity_available": 500,
            },
        ],
    )
    assert r.status_code == 200

    prod = (
        await db.execute(select(Product).where(Product.supplier_sku == "INV-1"))
    ).scalar_one()
    variant = (
        await db.execute(
            select(ProductVariant).where(ProductVariant.product_id == prod.id)
        )
    ).scalar_one()
    assert variant.inventory == 99
    assert variant.warehouse == "CA"


# ─── Task A9: Pricing endpoint ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_pricing_updates_base_price(
    client: AsyncClient, db, seed_supplier
):
    from modules.catalog.models import Product, ProductVariant

    await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        headers=SECRET,
        json=[
            {
                "supplier_sku": "PX-1",
                "product_name": "Px",
                "variants": [
                    {
                        "part_id": "v1",
                        "sku": "PX-1-M",
                        "size": "M",
                        "base_price": "10.00",
                    }
                ],
            }
        ],
    )
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/pricing",
        headers=SECRET,
        json=[{"supplier_sku": "PX-1", "part_id": "PX-1-M", "base_price": "14.25"}],
    )
    assert r.status_code == 200

    prod = (
        await db.execute(select(Product).where(Product.supplier_sku == "PX-1"))
    ).scalar_one()
    v = (
        await db.execute(
            select(ProductVariant).where(ProductVariant.product_id == prod.id)
        )
    ).scalar_one()
    assert Decimal(str(v.base_price)) == Decimal("14.25")
