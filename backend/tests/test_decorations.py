"""Phase 7 — decoration overlay tests."""
from __future__ import annotations
import pytest


# ---------------------------------------------------------------------------
# Task 1: suppliers.has_decoration_overlay column
# ---------------------------------------------------------------------------

def test_supplier_model_has_decoration_overlay_column():
    from modules.suppliers.models import Supplier
    cols = {c.name for c in Supplier.__table__.columns}
    assert "has_decoration_overlay" in cols


# ---------------------------------------------------------------------------
# Task 2: CustomerProductDecoration ORM model
# ---------------------------------------------------------------------------

def test_customer_product_decoration_model_has_required_columns():
    from modules.decorations.models import CustomerProductDecoration
    cols = {c.name for c in CustomerProductDecoration.__table__.columns}
    assert "customer_id" in cols
    assert "product_id" in cols
    assert "decoration_options" in cols
    assert "updated_at" in cols


# ---------------------------------------------------------------------------
# Task 3: Pydantic schemas
# ---------------------------------------------------------------------------

def test_decoration_create_validates_options_list():
    from modules.decorations.schemas import DecorationCreate
    from pydantic import ValidationError

    ok = DecorationCreate(decoration_options=[
        {
            "option_key": "imprint_method",
            "title": "Imprint Method",
            "options_type": "radio",
            "sort_order": 1,
            "master_option_id": 42,
            "required": True,
            "attributes": [
                {"title": "Screen Print", "sort_order": 0, "master_attribute_id": 101}
            ],
        }
    ])
    assert len(ok.decoration_options) == 1
    assert ok.decoration_options[0].option_key == "imprint_method"

    with pytest.raises(ValidationError):
        DecorationCreate(decoration_options=[])  # empty list not allowed


def test_decoration_read_serializes_from_attributes():
    from modules.decorations.schemas import DecorationRead
    import uuid
    import datetime
    r = DecorationRead(
        customer_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        decoration_options=[],
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )
    assert r.decoration_options == []


# ---------------------------------------------------------------------------
# Task 4: decoration_required() service helper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decoration_required_true_for_sanmar_supplier(seed_supplier, db):
    from modules.decorations.service import decoration_required
    from modules.catalog.models import Product
    from modules.suppliers.models import Supplier
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from database import async_session

    async with async_session() as s:
        sup = await s.get(Supplier, seed_supplier.id)
        sup.has_decoration_overlay = True
        await s.commit()

    async with async_session() as s:
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="DEC-TEST-1",
            product_name="Decoration Required Test",
            product_type="apparel",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        await s.commit()

    async with async_session() as s:
        product = await s.get(Product, pid)
        result = await decoration_required(product, s)
        assert result is True


@pytest.mark.asyncio
async def test_decoration_required_false_for_non_overlay_supplier(seed_supplier, db):
    from modules.decorations.service import decoration_required
    from modules.catalog.models import Product
    from modules.suppliers.models import Supplier
    from database import async_session
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async with async_session() as s:
        sup = await s.get(Supplier, seed_supplier.id)
        sup.has_decoration_overlay = False
        await s.commit()

    async with async_session() as s:
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="NO-DEC-1",
            product_name="No Decoration Needed",
            product_type="print",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        await s.commit()

    async with async_session() as s:
        product = await s.get(Product, pid)
        result = await decoration_required(product, s)
        assert result is False


# ---------------------------------------------------------------------------
# Task 5: PUT /api/customers/{id}/products/{id}/decorations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_put_decoration_creates_row(client, seed_supplier):
    from modules.catalog.models import Product
    from modules.customers.models import Customer
    from modules.decorations.models import CustomerProductDecoration
    from database import async_session
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async with async_session() as s:
        cust = Customer(
            name="Dec Co",
            ops_base_url="https://test.ops.com",
            ops_token_url="https://test.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(cust)
        await s.flush()
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="PUT-DEC-1",
            product_name="Put Dec Product",
            product_type="apparel",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        await s.commit()
        cid = cust.id

    body = {
        "decoration_options": [
            {
                "option_key": "imprint_method",
                "title": "Imprint Method",
                "options_type": "radio",
                "sort_order": 1,
                "master_option_id": 42,
                "required": True,
                "attributes": [
                    {"title": "Screen Print", "sort_order": 0, "master_attribute_id": 101}
                ],
            }
        ]
    }
    resp = await client.put(
        f"/api/customers/{cid}/products/{pid}/decorations",
        json=body,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["customer_id"] == str(cid)
    assert data["product_id"] == str(pid)
    assert len(data["decoration_options"]) == 1
    assert data["decoration_options"][0]["option_key"] == "imprint_method"

    async with async_session() as s:
        row = await s.get(CustomerProductDecoration, (cid, pid))
        assert row is not None
        assert len(row.decoration_options) == 1


@pytest.mark.asyncio
async def test_put_decoration_is_idempotent(client, seed_supplier):
    from modules.customers.models import Customer
    from modules.catalog.models import Product
    from database import async_session
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async with async_session() as s:
        cust = Customer(
            name="Dec Idem",
            ops_base_url="https://test2.ops.com",
            ops_token_url="https://test2.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(cust)
        await s.flush()
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="IDEM-DEC-1",
            product_name="Idem Dec Product",
            product_type="apparel",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        await s.commit()
        cid = cust.id

    def option(key):
        return {
            "option_key": key,
            "title": key,
            "options_type": "radio",
            "sort_order": 0,
            "required": False,
            "attributes": [{"title": "A", "sort_order": 0}],
        }

    await client.put(
        f"/api/customers/{cid}/products/{pid}/decorations",
        json={"decoration_options": [option("first")]},
    )
    resp = await client.put(
        f"/api/customers/{cid}/products/{pid}/decorations",
        json={"decoration_options": [option("second")]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["decoration_options"]) == 1
    assert data["decoration_options"][0]["option_key"] == "second"


# ---------------------------------------------------------------------------
# Task 6: GET /api/customers/{id}/products/{id}/decorations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_decoration_returns_existing(client, seed_supplier):
    from modules.customers.models import Customer
    from modules.catalog.models import Product
    from modules.decorations.models import CustomerProductDecoration
    from database import async_session
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from datetime import datetime, timezone

    async with async_session() as s:
        cust = Customer(
            name="Get Dec Co",
            ops_base_url="https://test3.ops.com",
            ops_token_url="https://test3.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(cust)
        await s.flush()
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="GET-DEC-1",
            product_name="Get Dec Product",
            product_type="apparel",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        s.add(CustomerProductDecoration(
            customer_id=cust.id,
            product_id=pid,
            decoration_options=[{
                "option_key": "location", "title": "Location",
                "options_type": "radio", "sort_order": 0,
                "required": False, "attributes": [],
            }],
            updated_at=datetime.now(timezone.utc),
        ))
        await s.commit()
        cid = cust.id

    resp = await client.get(f"/api/customers/{cid}/products/{pid}/decorations")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["decoration_options"][0]["option_key"] == "location"


@pytest.mark.asyncio
async def test_get_decoration_returns_404_when_none(client):
    import uuid
    fake_cid = uuid.uuid4()
    fake_pid = uuid.uuid4()
    resp = await client.get(f"/api/customers/{fake_cid}/products/{fake_pid}/decorations")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Task 7: DELETE /api/customers/{id}/products/{id}/decorations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_decoration_removes_row(client, seed_supplier):
    from modules.customers.models import Customer
    from modules.catalog.models import Product
    from modules.decorations.models import CustomerProductDecoration
    from database import async_session
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from datetime import datetime, timezone

    async with async_session() as s:
        cust = Customer(
            name="Del Dec Co",
            ops_base_url="https://test.ops.com",
            ops_token_url="https://test.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(cust)
        await s.flush()
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="DEL-DEC-1",
            product_name="Del Dec Product",
            product_type="apparel",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        s.add(CustomerProductDecoration(
            customer_id=cust.id,
            product_id=pid,
            decoration_options=[{
                "option_key": "loc", "title": "Loc",
                "options_type": "radio", "sort_order": 0,
                "required": False, "attributes": [],
            }],
            updated_at=datetime.now(timezone.utc),
        ))
        await s.commit()
        cid = cust.id

    resp = await client.delete(f"/api/customers/{cid}/products/{pid}/decorations")
    assert resp.status_code == 204

    async with async_session() as s:
        row = await s.get(CustomerProductDecoration, (cid, pid))
        assert row is None


# ---------------------------------------------------------------------------
# Task 8: assert_decoration_ready() push gate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assert_decoration_ready_raises_when_missing(seed_supplier):
    from modules.decorations.service import assert_decoration_ready, DecorationMissingError
    from modules.catalog.models import Product
    from modules.suppliers.models import Supplier
    from database import async_session
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    import uuid

    async with async_session() as s:
        sup = await s.get(Supplier, seed_supplier.id)
        sup.has_decoration_overlay = True
        await s.commit()

    async with async_session() as s:
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="GATE-1",
            product_name="Gate Product",
            product_type="apparel",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        await s.commit()

    fake_customer_id = uuid.uuid4()
    async with async_session() as s:
        product = await s.get(Product, pid)
        with pytest.raises(DecorationMissingError):
            await assert_decoration_ready(fake_customer_id, product, s)


@pytest.mark.asyncio
async def test_assert_decoration_ready_passes_when_present(seed_supplier):
    from modules.decorations.service import assert_decoration_ready
    from modules.decorations.models import CustomerProductDecoration
    from modules.catalog.models import Product
    from modules.customers.models import Customer
    from modules.suppliers.models import Supplier
    from database import async_session
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from datetime import datetime, timezone

    async with async_session() as s:
        sup = await s.get(Supplier, seed_supplier.id)
        sup.has_decoration_overlay = True
        cust = Customer(
            name="Gate Pass",
            ops_base_url="https://test.ops.com",
            ops_token_url="https://test.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(cust)
        await s.flush()
        stmt = pg_insert(Product).values(
            supplier_id=seed_supplier.id,
            supplier_sku="GATE-OK-1",
            product_name="Gate OK Product",
            product_type="apparel",
        ).on_conflict_do_nothing().returning(Product.id)
        pid = (await s.execute(stmt)).scalar_one()
        s.add(CustomerProductDecoration(
            customer_id=cust.id,
            product_id=pid,
            decoration_options=[{
                "option_key": "m", "title": "M",
                "options_type": "radio", "sort_order": 0,
                "required": True, "attributes": [],
            }],
            updated_at=datetime.now(timezone.utc),
        ))
        await s.commit()
        cid = cust.id

    async with async_session() as s:
        product = await s.get(Product, pid)
        await assert_decoration_ready(cid, product, s)  # must not raise
