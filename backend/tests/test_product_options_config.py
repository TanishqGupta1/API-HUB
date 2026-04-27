import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from main import app
from database import async_session


def _unique_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    from modules.master_options.models import MasterOption
    from modules.catalog.models import Product, ProductOption, ProductOptionAttribute
    from modules.suppliers.models import Supplier
    async with async_session() as s:
        await s.execute(delete(ProductOptionAttribute))
        await s.execute(delete(ProductOption))
        await s.execute(delete(Product).where(Product.supplier_sku.like("%-test-%")))
        await s.execute(delete(Supplier).where(Supplier.slug.like("vg-ops-test-%")))
        await s.execute(delete(MasterOption))
        await s.commit()


async def _make_supplier_and_product(sku: str, slug_prefix: str = "vg-ops-test"):
    from modules.suppliers.models import Supplier
    from modules.catalog.models import Product

    async with async_session() as s:
        sup = Supplier(name=slug_prefix, slug=_unique_slug(slug_prefix), protocol="soap", auth_config={})
        s.add(sup)
        await s.commit()
        await s.refresh(sup)
        prod = Product(supplier_id=sup.id, supplier_sku=sku, product_name="P")
        s.add(prod)
        await s.commit()
        await s.refresh(prod)
        return prod.id


@pytest.mark.asyncio
async def test_get_product_options_config_defaults_to_disabled():
    secret = os.environ["INGEST_SHARED_SECRET"]
    pid = await _make_supplier_and_product("TS-test-1")

    payload = [{
        "ops_master_option_id": 601,
        "title": "Ink Finish",
        "options_type": "checkbox",
        "attributes": [
            {"ops_attribute_id": 7001, "title": "Gloss", "sort_order": 1, "default_price": 0},
            {"ops_attribute_id": 7002, "title": "Matte", "sort_order": 2, "default_price": 10},
        ],
    }]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/ingest/master-options", json=payload, headers={"X-Ingest-Secret": secret})
        r = await c.get(f"/api/products/{pid}/options-config")

    assert r.status_code == 200, r.text
    data = r.json()
    ink = [m for m in data if m["ops_master_option_id"] == 601][0]
    assert ink["enabled"] is False
    assert len(ink["attributes"]) == 2
    matte = [a for a in ink["attributes"] if a["ops_attribute_id"] == 7002][0]
    assert matte["enabled"] is False
    assert float(matte["price"]) == 10.0


@pytest.mark.asyncio
async def test_get_product_options_config_404_for_unknown_product():
    fake = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/products/{fake}/options-config")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_put_product_options_config_persists():
    secret = os.environ["INGEST_SHARED_SECRET"]
    pid = await _make_supplier_and_product("PUT-test-1")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/ingest/master-options", headers={"X-Ingest-Secret": secret}, json=[{
            "ops_master_option_id": 701,
            "title": "Put Option",
            "attributes": [{"ops_attribute_id": 7111, "title": "A", "sort_order": 1, "default_price": 0}],
        }])
        r = await c.get(f"/api/products/{pid}/options-config")
        cfg = r.json()
        target_idx = next(i for i, m in enumerate(cfg) if m["ops_master_option_id"] == 701)
        cfg[target_idx]["enabled"] = True
        cfg[target_idx]["attributes"][0]["enabled"] = True
        cfg[target_idx]["attributes"][0]["price"] = "5.50"
        r = await c.put(f"/api/products/{pid}/options-config", json=cfg)
        assert r.status_code == 200
        r = await c.get(f"/api/products/{pid}/options-config")
        data = r.json()

    item = [m for m in data if m["ops_master_option_id"] == 701][0]
    assert item["enabled"] is True
    assert item["attributes"][0]["enabled"] is True
    assert float(item["attributes"][0]["price"]) == 5.5


@pytest.mark.asyncio
async def test_delete_product_option():
    secret = os.environ["INGEST_SHARED_SECRET"]
    pid = await _make_supplier_and_product("DEL-test-1")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/ingest/master-options", headers={"X-Ingest-Secret": secret}, json=[{
            "ops_master_option_id": 801, "title": "DelOpt",
            "attributes": [{"ops_attribute_id": 8111, "title": "X", "sort_order": 1}],
        }])
        r = await c.get(f"/api/products/{pid}/options-config")
        cfg = r.json()
        target_idx = next(i for i, m in enumerate(cfg) if m["ops_master_option_id"] == 801)
        cfg[target_idx]["enabled"] = True
        await c.put(f"/api/products/{pid}/options-config", json=cfg)
        mo_id = cfg[target_idx]["master_option_id"]
        r = await c.delete(f"/api/products/{pid}/options-config/{mo_id}")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_duplicate_options_copies_enabled_cards():
    from modules.suppliers.models import Supplier
    from modules.catalog.models import Product

    secret = os.environ["INGEST_SHARED_SECRET"]
    async with async_session() as s:
        sup = Supplier(name="DupSup", slug=_unique_slug("vg-ops-test"), protocol="soap", auth_config={})
        s.add(sup); await s.commit(); await s.refresh(sup)
        src = Product(supplier_id=sup.id, supplier_sku="SRC-test-1", product_name="src")
        dst = Product(supplier_id=sup.id, supplier_sku="DST-test-1", product_name="dst")
        s.add(src); s.add(dst); await s.commit()
        await s.refresh(src); await s.refresh(dst)
        src_id, dst_id = src.id, dst.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/ingest/master-options", headers={"X-Ingest-Secret": secret}, json=[{
            "ops_master_option_id": 901, "title": "DupOpt",
            "attributes": [{"ops_attribute_id": 9111, "title": "A", "sort_order": 1}],
        }])
        r = await c.get(f"/api/products/{src_id}/options-config")
        cfg = r.json()
        target = next(i for i, c in enumerate(cfg) if c["ops_master_option_id"] == 901)
        cfg[target]["enabled"] = True
        cfg[target]["attributes"][0]["enabled"] = True
        await c.put(f"/api/products/{src_id}/options-config", json=cfg)
        r = await c.post(f"/api/products/{dst_id}/options-config/duplicate-from/{src_id}")
        assert r.status_code == 200
        assert r.json()["copied"] >= 1
        r = await c.get(f"/api/products/{dst_id}/options-config")
        data = r.json()
        dup = [m for m in data if m["ops_master_option_id"] == 901][0]
        assert dup["enabled"] is True
