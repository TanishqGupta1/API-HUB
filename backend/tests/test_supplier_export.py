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


@pytest.mark.asyncio
async def test_push_products_to_graphx(db, seed_supplier, monkeypatch):
    """Builds the envelope, posts to GRAPHX_INGEST_URL with x-ingest-secret,
    skips products that have no options yet."""
    from modules.catalog.exporter import push_products_to_graphx
    from modules.catalog.option_collapse import derive_options

    monkeypatch.setenv("GRAPHX_INGEST_URL", "http://graphx.test/api/ingest/supplier-products")
    monkeypatch.setenv("GRAPHX_INGEST_SECRET", "s3cret")

    # one product WITH options (derived), one WITHOUT
    p_yes = await _mk_product_with_variants(db, seed_supplier, sku="WITH", name="With")
    await derive_options(db, p_yes.id)
    p_no = await _mk_product_with_variants(db, seed_supplier, sku="WITHOUT", name="Without")
    # do NOT derive on p_no — should be skipped

    captured = {}

    class _Resp:
        status_code = 200
        headers = {"content-type": "application/json"}
        def json(self):  # noqa: D401 — mimic httpx
            return {"created": 1}

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, *, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _Resp()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    result = await push_products_to_graphx(db, supplier_id=seed_supplier.id)

    assert result["sent"] == 1
    assert result["skipped"] == 1
    assert captured["url"] == "http://graphx.test/api/ingest/supplier-products"
    assert captured["headers"]["x-ingest-secret"] == "s3cret"
    body = captured["json"]
    assert body["tenant_slug"] == "vg"
    assert body["supplier_key"] == seed_supplier.slug
    assert len(body["products"]) == 1
    assert body["products"][0]["supplier_sku"] == "WITH"


class _FakePushResp:
    status_code = 200
    headers = {"content-type": "application/json"}
    def json(self): return {"created": 1}


class _FakePushClient:
    captured: dict = {}
    def __init__(self, *a, **kw): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def post(self, url, *, headers, json):
        _FakePushClient.captured = {"url": url, "headers": headers, "json": json}
        return _FakePushResp()


@pytest.mark.asyncio
async def test_route_push_single_product(client, db, seed_supplier, monkeypatch):
    import httpx
    from modules.catalog.option_collapse import derive_options

    monkeypatch.setenv("GRAPHX_INGEST_URL", "http://graphx.test/api/ingest/supplier-products")
    monkeypatch.setenv("GRAPHX_INGEST_SECRET", "s3cret")
    monkeypatch.setattr(httpx, "AsyncClient", _FakePushClient)

    p = await _mk_product_with_variants(db, seed_supplier, sku="ONE", name="One")
    await derive_options(db, p.id)

    r = await client.post(f"/api/products/{p.id}/push-to-graphx")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == 200


@pytest.mark.asyncio
async def test_route_push_by_supplier(client, db, seed_supplier, monkeypatch):
    import httpx
    from modules.catalog.option_collapse import derive_options

    monkeypatch.setenv("GRAPHX_INGEST_URL", "http://graphx.test/api/ingest/supplier-products")
    monkeypatch.setenv("GRAPHX_INGEST_SECRET", "s3cret")
    monkeypatch.setattr(httpx, "AsyncClient", _FakePushClient)

    p = await _mk_product_with_variants(db, seed_supplier, sku="SUP", name="Sup")
    await derive_options(db, p.id)

    r = await client.post(f"/api/suppliers/{seed_supplier.id}/push-to-graphx")
    assert r.status_code == 200
    body = r.json()
    assert body["sent"] >= 1


@pytest.mark.asyncio
async def test_export_includes_options(client, db, seed_supplier):
    """GET /export now returns options as well."""
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product_with_variants(db, seed_supplier, sku="EXP", name="Exp")
    await derive_options(db, p.id)

    r = await client.get(f"/api/products/{p.id}/export")
    assert r.status_code == 200
    body = r.json()
    assert "options" in body
    keys = {o["option_key"] for o in body["options"]}
    assert keys == {"color", "size"}


@pytest.mark.asyncio
async def test_push_products_to_graphx_raises_on_non_2xx(db, seed_supplier, monkeypatch):
    """Regression (review MEDIUM): a non-2xx from graphx is a FAILED push — it must
    raise 502, not be silently returned and counted as `sent`."""
    import httpx
    from fastapi import HTTPException
    from modules.catalog.exporter import push_products_to_graphx
    from modules.catalog.option_collapse import derive_options

    monkeypatch.setenv("GRAPHX_INGEST_URL", "http://graphx.test/api/ingest/supplier-products")
    monkeypatch.setenv("GRAPHX_INGEST_SECRET", "s3cret")

    p = await _mk_product_with_variants(db, seed_supplier, sku="ERR", name="Err")
    await derive_options(db, p.id)

    class _Resp500:
        status_code = 500
        headers = {"content-type": "application/json"}
        def json(self):
            return {"error": "boom"}

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, *, headers, json):
            return _Resp500()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    with pytest.raises(HTTPException) as exc:
        await push_products_to_graphx(db, supplier_id=seed_supplier.id)
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_push_products_to_graphx_503_when_unconfigured(db, seed_supplier, monkeypatch):
    """Regression (review LOW): missing GRAPHX_INGEST_URL/SECRET → clean 503, not a
    KeyError/500."""
    from fastapi import HTTPException
    from modules.catalog.exporter import push_products_to_graphx

    monkeypatch.delenv("GRAPHX_INGEST_URL", raising=False)
    monkeypatch.delenv("GRAPHX_INGEST_SECRET", raising=False)

    with pytest.raises(HTTPException) as exc:
        await push_products_to_graphx(db, supplier_id=seed_supplier.id)
    assert exc.value.status_code == 503
