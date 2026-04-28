"""Tests for the SanMar category methods added to PromoStandardsClient.

No network — FakeService harness matches the pattern used in
``backend/test_promostandards_client.py``.
"""

from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from modules.promostandards.client import (
    SANMAR_CATEGORIES,
    PromoStandardsClient,
)


class FakeService:
    """Minimal stub matching zeep service-proxy behavior for category calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.responses: dict[str, object] = {}
        self.raise_for: dict[str, Exception] = {}

    def _dispatch(self, name: str, kwargs: dict):
        self.calls.append((name, kwargs))
        if name in self.raise_for:
            raise self.raise_for[name]
        return self.responses.get(name)

    def getProductInfoByCategory(self, **kw):
        return self._dispatch("getProductInfoByCategory", kw)


def _client(service: FakeService | None = None) -> PromoStandardsClient:
    return PromoStandardsClient(
        "https://fake.example.com/ProductData?wsdl",
        {"id": "acct-1", "password": "secret"},
        service=service,
    )


# ---------------------------------------------------------------------------
# get_categories
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_categories_returns_sanmar_list():
    """No SOAP call — returns the embedded SANMAR_CATEGORIES constant."""
    cats = await _client().get_categories()
    assert len(cats) == len(SANMAR_CATEGORIES)
    assert all(c.name in SANMAR_CATEGORIES for c in cats)
    # Well-known categories present
    names = [c.name for c in cats]
    assert "T-Shirts" in names
    assert "Caps" in names
    assert "Bags" in names


@pytest.mark.asyncio
async def test_get_categories_entries_have_empty_metadata():
    """PSCategoryData fields default to None when catalog lacks preview data."""
    cats = await _client().get_categories()
    for c in cats:
        assert c.slug is None
        assert c.product_count is None
        assert c.preview_image_url is None


# ---------------------------------------------------------------------------
# get_products_by_category
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_products_by_category_parses_array():
    svc = FakeService()
    svc.responses["getProductInfoByCategory"] = NS(
        ProductArray=NS(
            Product=[
                NS(productId="PC61", productName="Essential Tee"),
                NS(productId="PC54", productName="Core Tee"),
            ]
        )
    )
    products = await _client(svc).get_products_by_category("T-Shirts", limit=10)
    assert len(products) == 2
    assert products[0].product_id == "PC61"
    assert products[0].product_name == "Essential Tee"
    assert products[1].product_id == "PC54"

    # Auth + category name passed to SOAP call
    assert len(svc.calls) == 1
    op, kwargs = svc.calls[0]
    assert op == "getProductInfoByCategory"
    assert kwargs["category"] == "T-Shirts"
    assert kwargs["wsVersion"] == "2.0.0"
    assert kwargs["id"] == "acct-1"
    assert kwargs["password"] == "secret"
    assert kwargs["localizationCountry"] == "us"
    assert kwargs["localizationLanguage"] == "en"


@pytest.mark.asyncio
async def test_get_products_by_category_respects_limit():
    svc = FakeService()
    svc.responses["getProductInfoByCategory"] = NS(
        ProductArray=NS(
            Product=[NS(productId=f"PC{i:03d}") for i in range(20)]
        )
    )
    products = await _client(svc).get_products_by_category("T-Shirts", limit=5)
    assert len(products) == 5
    assert [p.product_id for p in products] == ["PC000", "PC001", "PC002", "PC003", "PC004"]


@pytest.mark.asyncio
async def test_get_products_by_category_handles_lowercase_wrapper():
    """Some PS suppliers return lowerCamelCase element names — walker tolerates."""
    svc = FakeService()
    svc.responses["getProductInfoByCategory"] = NS(
        productArray=NS(
            product=[NS(productId="PC61")]
        )
    )
    products = await _client(svc).get_products_by_category("Caps", limit=10)
    assert len(products) == 1
    assert products[0].product_id == "PC61"


@pytest.mark.asyncio
async def test_get_products_by_category_empty_when_no_products():
    svc = FakeService()
    svc.responses["getProductInfoByCategory"] = NS(ProductArray=NS(Product=[]))
    products = await _client(svc).get_products_by_category("T-Shirts", limit=50)
    assert products == []


@pytest.mark.asyncio
async def test_get_products_by_category_swallows_soap_exceptions():
    """Per client convention: log + return empty list, don't crash the sync."""
    svc = FakeService()
    svc.raise_for["getProductInfoByCategory"] = RuntimeError("SanMar 503")
    products = await _client(svc).get_products_by_category("T-Shirts")
    assert products == []


@pytest.mark.asyncio
async def test_get_products_by_category_limit_zero_returns_all():
    """limit=0 conventionally means 'no cap' — return everything."""
    svc = FakeService()
    svc.responses["getProductInfoByCategory"] = NS(
        ProductArray=NS(
            Product=[NS(productId=f"PC{i}") for i in range(12)]
        )
    )
    products = await _client(svc).get_products_by_category("T-Shirts", limit=0)
    assert len(products) == 12
