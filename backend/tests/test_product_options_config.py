import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from main import app
from database import async_session


@pytest.mark.asyncio
async def test_get_product_options_config_defaults_to_disabled():
    from modules.suppliers.models import Supplier
    from modules.catalog.models import Product

    secret = os.environ["INGEST_SHARED_SECRET"]

    async with async_session() as s:
        sup = Supplier(name="TestSup", slug="vg-ops-test", protocol="soap", auth_config={})
        s.add(sup)
        await s.commit()
        await s.refresh(sup)
        prod = Product(supplier_id=sup.id, supplier_sku="TS-1", product_name="Test")
        s.add(prod)
        await s.commit()
        await s.refresh(prod)
        pid = prod.id

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
