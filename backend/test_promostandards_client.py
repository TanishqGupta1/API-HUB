"""Unit tests for PromoStandardsClient.

No network: a fake zeep ``service`` is injected via the constructor. The fakes
use ``types.SimpleNamespace`` to mimic the nested attribute access zeep hands
back after parsing a SOAP response. The walkers in ``client.py`` deliberately
try multiple attribute paths, so each test exercises one of those paths.

Run with: pytest backend/test_promostandards_client.py
"""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from modules.promostandards.client import PromoStandardsClient


# ---------------------------------------------------------------------------
# Fake service — records every call, returns whatever you set up.
# ---------------------------------------------------------------------------

class FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.responses: dict[str, object] = {}
        self.raise_for: dict[str, Exception] = {}

    def _dispatch(self, name: str, kwargs: dict):
        self.calls.append((name, kwargs))
        if name in self.raise_for:
            raise self.raise_for[name]
        # For per-product calls, support keying by productId too.
        pid = kwargs.get("productId")
        if pid is not None and (name, pid) in self.responses:
            return self.responses[(name, pid)]
        return self.responses.get(name)

    def getProductSellable(self, **kw):
        return self._dispatch("getProductSellable", kw)

    def getProduct(self, **kw):
        return self._dispatch("getProduct", kw)

    def getInventoryLevels(self, **kw):
        return self._dispatch("getInventoryLevels", kw)

    def getConfigurationAndPricing(self, **kw):
        return self._dispatch("getConfigurationAndPricing", kw)

    def getMediaContent(self, **kw):
        return self._dispatch("getMediaContent", kw)


def _client(service: FakeService, auth: dict | None = None) -> PromoStandardsClient:
    return PromoStandardsClient(
        "https://fake.example.com/service?wsdl",
        auth or {"id": "acct-1", "password": "secret"},
        service=service,
    )


# ---------------------------------------------------------------------------
# get_sellable_product_ids
# ---------------------------------------------------------------------------

async def test_sellable_ids_extracts_and_filters():
    svc = FakeService()
    svc.responses["getProductSellable"] = NS(
        ProductSellableArray=NS(
            ProductSellable=[
                NS(productId="PC61", isSellable=True),
                NS(productId="PC90H", isSellable=True),
                NS(productId="DISCONTINUED", isSellable=False),
                NS(productId="MISSING_FLAG"),  # no isSellable → treat as sellable
            ]
        )
    )

    ids = await _client(svc).get_sellable_product_ids()
    assert ids == ["PC61", "PC90H", "MISSING_FLAG"]

    # Credentials forwarded on the request.
    name, kwargs = svc.calls[0]
    assert name == "getProductSellable"
    assert kwargs["id"] == "acct-1"
    assert kwargs["password"] == "secret"
    assert kwargs["wsVersion"] == "2.0.0"


async def test_sellable_ids_tolerates_empty_response():
    svc = FakeService()
    svc.responses["getProductSellable"] = NS(ProductSellableArray=None)
    assert await _client(svc).get_sellable_product_ids() == []


async def test_sellable_ids_handles_lowercase_variant():
    svc = FakeService()
    svc.responses["getProductSellable"] = NS(
        productSellableArray=NS(
            productSellable=NS(productId="X")  # single item, not a list
        )
    )
    assert await _client(svc).get_sellable_product_ids() == ["X"]


# ---------------------------------------------------------------------------
# get_product / get_products_batch
# ---------------------------------------------------------------------------

async def test_get_product_parses_nested_shape():
    svc = FakeService()
    svc.responses[("getProduct", "PC61")] = NS(
        Product=NS(
            productId="PC61",
            productName="Essential Tee",
            description="100% cotton",
            productBrand="Port & Company",
            ProductCategoryArray=NS(
                ProductCategory=[
                    NS(productCategory="T-Shirts"),
                    NS(productCategory="Apparel"),
                ]
            ),
            primaryImageURL="https://img.example.com/pc61.jpg",
            productPartArray=NS(
                productPart=[
                    NS(
                        partId="PC61-NVY-M",
                        ColorArray=NS(Color=NS(colorName="Navy")),
                        ApparelSize=NS(labelSize="M"),
                    ),
                    NS(
                        partId="PC61-NVY-L",
                        ColorArray=NS(Color=NS(colorName="Navy")),
                        ApparelSize=NS(labelSize="L"),
                    ),
                ]
            ),
        )
    )

    product = await _client(svc).get_product("PC61")
    assert product is not None
    assert product.product_id == "PC61"
    assert product.product_name == "Essential Tee"
    assert product.brand == "Port & Company"
    assert product.categories == ["T-Shirts", "Apparel"]
    assert product.primary_image_url == "https://img.example.com/pc61.jpg"
    assert len(product.parts) == 2
    assert product.parts[0].part_id == "PC61-NVY-M"
    assert product.parts[0].color_name == "Navy"
    assert product.parts[0].size_name == "M"


async def test_get_product_individual_failure_returns_none():
    svc = FakeService()
    svc.raise_for["getProduct"] = RuntimeError("SOAP 500")
    assert await _client(svc).get_product("X") is None


async def test_products_batch_skips_individual_failures():
    svc = FakeService()
    svc.responses[("getProduct", "A")] = NS(
        Product=NS(productId="A", productName="A-Tee", productPartArray=None)
    )
    svc.responses[("getProduct", "C")] = NS(
        Product=NS(productId="C", productName="C-Tee", productPartArray=None)
    )
    # "B" returns None from _dispatch because no response is registered;
    # _parse_product handles that by returning None.

    products = await _client(svc).get_products_batch(["A", "B", "C"], batch_size=10)
    assert [p.product_id for p in products] == ["A", "C"]


# ---------------------------------------------------------------------------
# get_inventory
# ---------------------------------------------------------------------------

async def test_inventory_cap_and_shape():
    svc = FakeService()
    svc.responses[("getInventoryLevels", "PC61")] = NS(
        Inventory=NS(
            productId="PC61",
            PartInventoryArray=NS(
                PartInventory=[
                    NS(
                        partId="PC61-NVY-M",
                        quantityAvailable=350,
                        InventoryLocationArray=NS(
                            InventoryLocation=[NS(inventoryLocationName="Seattle")]
                        ),
                    ),
                    NS(
                        partId="PC61-NVY-L",
                        quantityAvailable=99999,  # will be capped at 500
                        InventoryLocationArray=None,
                    ),
                ]
            ),
        )
    )

    levels = await _client(svc).get_inventory(["PC61"])
    by_part = {level.part_id: level for level in levels}

    assert by_part["PC61-NVY-M"].quantity_available == 350
    assert by_part["PC61-NVY-M"].warehouse_code == "Seattle"
    assert by_part["PC61-NVY-L"].quantity_available == 500  # capped
    assert by_part["PC61-NVY-L"].warehouse_code is None


# ---------------------------------------------------------------------------
# get_pricing
# ---------------------------------------------------------------------------

async def test_pricing_parses_tiers():
    svc = FakeService()
    svc.responses[("getConfigurationAndPricing", "PC61")] = NS(
        Configuration=NS(
            PartArray=NS(
                Part=[
                    NS(
                        partId="PC61-NVY-M",
                        PartPriceArray=NS(
                            PartPrice=[
                                NS(price="3.99", minQuantity=1, priceType="piece"),
                                NS(
                                    price="3.49",
                                    minQuantity=48,
                                    maxQuantity=143,
                                    priceType="piece",
                                ),
                            ]
                        ),
                    )
                ]
            )
        )
    )

    prices = await _client(svc).get_pricing(["PC61"])
    assert len(prices) == 2
    assert prices[0].price == pytest.approx(3.99)
    assert prices[0].quantity_min == 1
    assert prices[0].price_type == "piece"
    assert prices[1].quantity_min == 48
    assert prices[1].quantity_max == 143


async def test_pricing_skips_bad_rows():
    svc = FakeService()
    svc.responses[("getConfigurationAndPricing", "PC61")] = NS(
        Configuration=NS(
            PartArray=NS(
                Part=[
                    NS(
                        partId="PC61-NVY-M",
                        PartPriceArray=NS(
                            PartPrice=[
                                NS(price=None),  # bad
                                NS(price="not-a-number"),  # bad
                                NS(price="2.00"),  # good
                            ]
                        ),
                    )
                ]
            )
        )
    )

    prices = await _client(svc).get_pricing(["PC61"])
    assert len(prices) == 1
    assert prices[0].price == pytest.approx(2.00)


# ---------------------------------------------------------------------------
# get_media
# ---------------------------------------------------------------------------

async def test_media_parses_content():
    svc = FakeService()
    svc.responses[("getMediaContent", "PC61")] = NS(
        MediaContentArray=NS(
            MediaContent=[
                NS(
                    productId="PC61",
                    url="https://img.example.com/pc61-front.jpg",
                    mediaType="front",
                    color="Navy",
                ),
                NS(
                    url="https://img.example.com/pc61-swatch.jpg",
                    mediaType="swatch",
                ),
                NS(mediaType="broken", url=None),  # skipped — no url
            ]
        )
    )

    media = await _client(svc).get_media(["PC61"])
    assert len(media) == 2
    assert media[0].media_type == "front"
    assert media[0].color_name == "Navy"
    assert media[1].product_id == "PC61"  # falls back to request productId
