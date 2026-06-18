"""Tests for the supplier catalog handoff payload + pusher."""
import pytest
from decimal import Decimal

from modules.catalog.models import (
    Product,
    ProductVariant,
    VariantPrice,
)


async def _mk_product_with_variants(db, supplier, *, sku="PC54", name="Core Tee"):
    p = Product(supplier_id=supplier.id, supplier_sku=sku, product_name=name,
                brand="Port & Co", description="Tee", product_type="apparel")
    db.add(p)
    await db.commit()
    await db.refresh(p)
    for color, size in [("Red", "S"), ("Navy", "M")]:
        v = ProductVariant(
            product_id=p.id, color=color, size=size,
            part_id=f"{color}-{size}", sku=f"{sku}-{color}-{size}",
            base_price=Decimal("5.50"),
        )
        db.add(v)
        await db.commit()
        await db.refresh(v)
        db.add(VariantPrice(
            variant_id=v.id, price_type="net",
            quantity_min=1, quantity_max=11, price=Decimal("5.50"),
        ))
    await db.commit()
    return p


@pytest.mark.asyncio
async def test_build_supplier_payload(db, seed_supplier):
    from modules.catalog.exporter import build_supplier_product
    from modules.catalog.option_collapse import derive_options

    p = await _mk_product_with_variants(db, seed_supplier)
    await derive_options(db, p.id)

    out = await build_supplier_product(db, p.id)

    assert out["supplier_sku"] == "PC54"
    assert out["name"] == "Core Tee"
    keys = {o["option_key"] for o in out["options"]}
    assert keys == {"color", "size"}
    assert any(v["color"] == "Red" for v in out["variants"])
    # variant prices propagate
    red_s = next(v for v in out["variants"] if v["color"] == "Red" and v["size"] == "S")
    assert any(pr["price_type"] == "net" and pr["price"] == 5.5 for pr in red_s["prices"])


@pytest.mark.asyncio
async def test_build_supplier_payload_missing(db, seed_supplier):
    """Unknown product id raises 404."""
    from uuid import uuid4
    from fastapi import HTTPException
    from modules.catalog.exporter import build_supplier_product
    with pytest.raises(HTTPException) as exc:
        await build_supplier_product(db, uuid4())
    assert exc.value.status_code == 404
