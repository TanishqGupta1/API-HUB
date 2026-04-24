"""Tests for category-import endpoints.

Exercises the route layer + error paths. Background worker is validated
manually via E2E (requires real SanMar SOAP creds).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from database import async_session
from main import app


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    from modules.suppliers.models import Supplier

    async with async_session() as s:
        await s.execute(delete(Supplier).where(Supplier.slug.like("cat-test-%")))
        await s.commit()


async def _seed_supplier(
    slug: str,
    protocol: str,
    endpoints: list[dict] | None = None,
    promostandards_code: str | None = None,
) -> uuid.UUID:
    """Create a test supplier row. ``endpoints`` is stored in the JSONB
    ``endpoint_cache`` column (the resolver reads from there).

    If ``promostandards_code`` is None for PS protocols,
    ``get_cached_endpoints`` short-circuits to [] without hitting the live PS
    directory — lets tests run offline.
    """
    from datetime import datetime, timezone

    from modules.suppliers.models import Supplier

    async with async_session() as s:
        sup = Supplier(
            name=f"Test-{slug}",
            slug=slug,
            protocol=protocol,
            promostandards_code=promostandards_code,
            auth_config={"id": "test", "password": "test"},
            endpoint_cache=endpoints,
            endpoint_cache_updated_at=(
                datetime.now(timezone.utc) if endpoints else None
            ),
        )
        s.add(sup)
        await s.commit()
        await s.refresh(sup)
        return sup.id


def _product_data_endpoint(wsdl_url: str) -> dict:
    """Shape matching what the PS Directory returns for product_data service."""
    return {
        "ServiceType": "Product Data",
        "ProductionURL": wsdl_url,
        "TestURL": None,
        "Version": "2.0.0",
        "Name": "Product Data",
        "Status": "Active",
    }


# ---------------------------------------------------------------------------
# GET /api/suppliers/{id}/categories
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_categories_returns_sanmar_list_for_soap_supplier():
    sid = await _seed_supplier("cat-test-soap", "soap")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/suppliers/{sid}/categories")
    assert r.status_code == 200, r.text
    data = r.json()
    # At least the well-known SanMar categories
    names = [c["name"] for c in data]
    assert "T-Shirts" in names
    assert "Caps" in names


@pytest.mark.asyncio
async def test_list_categories_rejects_non_ps_supplier():
    sid = await _seed_supplier("cat-test-rest", "rest")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/suppliers/{sid}/categories")
    assert r.status_code == 400
    assert "rest" in r.json()["detail"]


@pytest.mark.asyncio
async def test_list_categories_404_for_unknown_supplier():
    fake_id = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/suppliers/{fake_id}/categories")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/suppliers/{id}/import-category
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_import_category_202_for_soap_supplier():
    sid = await _seed_supplier(
        "cat-test-import",
        "soap",
        endpoints=[_product_data_endpoint("https://ws.sanmar.com/ProductData?wsdl")],
        promostandards_code="TEST_CODE",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            f"/api/suppliers/{sid}/import-category",
            json={"category_name": "T-Shirts", "limit": 5},
        )
    assert r.status_code == 202, r.text
    data = r.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["category_name"] == "T-Shirts"
    assert data["limit"] == 5


@pytest.mark.asyncio
async def test_import_category_400_for_non_ps_supplier():
    sid = await _seed_supplier("cat-test-reject", "rest")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            f"/api/suppliers/{sid}/import-category",
            json={"category_name": "T-Shirts", "limit": 5},
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_import_category_502_when_no_wsdl_cached():
    sid = await _seed_supplier("cat-test-nowsdl", "soap")
    # Do NOT seed endpoints
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            f"/api/suppliers/{sid}/import-category",
            json={"category_name": "T-Shirts", "limit": 5},
        )
    assert r.status_code == 502
    assert "WSDL" in r.json()["detail"]


@pytest.mark.asyncio
async def test_import_category_validates_limit_range():
    sid = await _seed_supplier(
        "cat-test-limit",
        "soap",
        endpoints=[_product_data_endpoint("https://fake/ProductData?wsdl")],
        promostandards_code="TEST_CODE",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # limit > 500 should 422
        r = await c.post(
            f"/api/suppliers/{sid}/import-category",
            json={"category_name": "T-Shirts", "limit": 501},
        )
        assert r.status_code == 422
        # limit < 1 should 422
        r = await c.post(
            f"/api/suppliers/{sid}/import-category",
            json={"category_name": "T-Shirts", "limit": 0},
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_import_category_validates_category_name():
    sid = await _seed_supplier(
        "cat-test-name",
        "soap",
        endpoints=[_product_data_endpoint("https://fake/ProductData?wsdl")],
        promostandards_code="TEST_CODE",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            f"/api/suppliers/{sid}/import-category",
            json={"category_name": "", "limit": 5},
        )
    assert r.status_code == 422
