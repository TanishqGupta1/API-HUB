"""Tests for product archive/restore + archived-filter on list endpoint."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from database import async_session
from main import app


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    from modules.catalog.models import Product
    from modules.suppliers.models import Supplier

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.supplier_sku.like("ARCH-%")))
        await s.execute(delete(Supplier).where(Supplier.slug.like("arch-test-%")))
        await s.commit()


async def _seed_product(sku: str) -> uuid.UUID:
    from modules.catalog.models import Product
    from modules.suppliers.models import Supplier

    async with async_session() as s:
        sup = Supplier(
            name=f"Arch-{sku}", slug=f"arch-test-{sku.lower()}",
            protocol="soap", auth_config={}
        )
        s.add(sup); await s.commit(); await s.refresh(sup)
        prod = Product(
            supplier_id=sup.id, supplier_sku=sku, product_name=f"Product {sku}"
        )
        s.add(prod); await s.commit(); await s.refresh(prod)
        return prod.id


@pytest.mark.asyncio
async def test_archive_sets_archived_at():
    pid = await _seed_product("ARCH-1")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(f"/api/products/{pid}/archive")
    assert r.status_code == 200
    body = r.json()
    assert body["archived"] is True
    assert body["archived_at"] is not None


@pytest.mark.asyncio
async def test_archive_is_idempotent():
    pid = await _seed_product("ARCH-2")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.post(f"/api/products/{pid}/archive")
        r2 = await c.post(f"/api/products/{pid}/archive")
    assert r1.json()["archived_at"] == r2.json()["archived_at"]


@pytest.mark.asyncio
async def test_restore_clears_archived_at():
    pid = await _seed_product("ARCH-3")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post(f"/api/products/{pid}/archive")
        r = await c.post(f"/api/products/{pid}/restore")
    assert r.status_code == 200
    assert r.json()["archived"] is False


@pytest.mark.asyncio
async def test_default_list_excludes_archived():
    pid = await _seed_product("ARCH-4")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Visible before archive
        r = await c.get("/api/products?limit=500")
        ids_before = [p["id"] for p in r.json()]
        assert str(pid) in ids_before
        # Archive
        await c.post(f"/api/products/{pid}/archive")
        # Hidden from default list
        r = await c.get("/api/products?limit=500")
        ids_after = [p["id"] for p in r.json()]
        assert str(pid) not in ids_after


@pytest.mark.asyncio
async def test_archived_true_lists_only_archived():
    pid = await _seed_product("ARCH-5")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post(f"/api/products/{pid}/archive")
        r = await c.get("/api/products?archived=true&limit=500")
    ids = [p["id"] for p in r.json()]
    assert str(pid) in ids


@pytest.mark.asyncio
async def test_archive_404_unknown():
    fake = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(f"/api/products/{fake}/archive")
    assert r.status_code == 404
