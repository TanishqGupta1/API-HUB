import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from main import app
from database import async_session


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    from modules.customers.models import Customer
    from modules.catalog.models import Product
    from modules.suppliers.models import Supplier
    from modules.master_options.models import MasterOption

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.supplier_sku.like("OPO-%")))
        await s.execute(delete(Customer).where(Customer.name.like("OPO-%")))
        await s.execute(delete(Supplier).where(Supplier.slug.like("vg-ops-test%")))
        await s.execute(
            delete(MasterOption).where(MasterOption.ops_master_option_id >= 9000)
        )
        await s.commit()


@pytest.mark.asyncio
async def test_ops_options_returns_product_scoped_shape():
    """Core shape has no master_option_id / ops_attribute_id — only source_* fields."""
    secret = os.environ["INGEST_SHARED_SECRET"]

    from modules.suppliers.models import Supplier
    from modules.catalog.models import Product
    from modules.customers.models import Customer

    async with async_session() as s:
        sup = Supplier(
            name="OPO-Sup",
            slug="vg-ops-test",
            protocol="soap",
            auth_config={},
        )
        s.add(sup)
        await s.commit()
        await s.refresh(sup)

        prod = Product(supplier_id=sup.id, supplier_sku="OPO-1", product_name="P")
        cust = Customer(
            name="OPO-Cust",
            ops_base_url="x",
            ops_token_url="x",
            ops_client_id="c",
            ops_auth_config={"s": "s"},
        )
        s.add(prod)
        s.add(cust)
        await s.commit()
        await s.refresh(prod)
        await s.refresh(cust)
        pid, cid = prod.id, cust.id

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        # Seed master option
        r = await c.post(
            "/api/ingest/master-options",
            headers={"X-Ingest-Secret": secret},
            json=[
                {
                    "ops_master_option_id": 9001,
                    "title": "Ink Finish",
                    "option_key": "inkFinish",
                    "options_type": "combo",
                    "attributes": [
                        {
                            "ops_attribute_id": 9991,
                            "title": "Gloss",
                            "sort_order": 1,
                            "default_price": 0,
                            "raw_json": {"attribute_key": "Gloss"},
                        },
                    ],
                }
            ],
        )
        assert r.status_code in (200, 201), r.text

        # Enable it on this product
        r = await c.get(f"/api/products/{pid}/options-config")
        assert r.status_code == 200, r.text
        cfg = r.json()
        target = next(
            i for i, mo in enumerate(cfg) if mo["ops_master_option_id"] == 9001
        )
        cfg[target]["enabled"] = True
        cfg[target]["attributes"][0]["enabled"] = True
        cfg[target]["attributes"][0]["price"] = "5.00"
        r = await c.put(f"/api/products/{pid}/options-config", json=cfg)
        assert r.status_code in (200, 204), r.text

        r = await c.get(
            f"/api/push/{cid}/product/{pid}/ops-options",
            headers={"X-Ingest-Secret": secret},
        )

    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 1
    opt = data[0]
    assert opt["option_key"] == "inkFinish"
    assert opt["title"] == "Ink Finish"
    # Core push fields strip master_option_id / ops_attribute_id
    assert "master_option_id" not in opt
    assert "ops_attribute_id" not in opt
    # But source trace fields are retained
    assert opt["source_master_option_id"] == 9001

    assert len(opt["attributes"]) == 1
    attr = opt["attributes"][0]
    assert attr["title"] == "Gloss"
    assert float(attr["price"]) == 5.0
    assert "master_attribute_id" not in attr
    assert "ops_attribute_id" not in attr
    assert attr["source_master_attribute_id"] == 9991


@pytest.mark.asyncio
async def test_ops_options_empty_when_nothing_enabled():
    """Returns [] not 404 when product has no enabled options."""
    secret = os.environ["INGEST_SHARED_SECRET"]

    from modules.suppliers.models import Supplier
    from modules.catalog.models import Product
    from modules.customers.models import Customer

    async with async_session() as s:
        sup = Supplier(
            name="OPO-Sup2",
            slug="vg-ops-test2",
            protocol="soap",
            auth_config={},
        )
        s.add(sup)
        await s.commit()
        await s.refresh(sup)

        prod = Product(supplier_id=sup.id, supplier_sku="OPO-2", product_name="P2")
        cust = Customer(
            name="OPO-Cust2",
            ops_base_url="x",
            ops_token_url="x",
            ops_client_id="c",
            ops_auth_config={"s": "s"},
        )
        s.add(prod)
        s.add(cust)
        await s.commit()
        await s.refresh(prod)
        await s.refresh(cust)
        pid, cid = prod.id, cust.id

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get(
            f"/api/push/{cid}/product/{pid}/ops-options",
            headers={"X-Ingest-Secret": secret},
        )

    assert r.status_code == 200
    assert r.json() == []
