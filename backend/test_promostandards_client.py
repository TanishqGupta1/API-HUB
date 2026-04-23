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

async def test_inventory_flat_quantity_still_parses():
    """Backwards compat: flat-int quantityAvailable + location-name-only shape.

    Historically the client capped at 500; that cap is removed (SanMar reports
    up to 3000 per warehouse × 8 warehouses). Location metadata with no qty
    falls back to top-level quantityAvailable; warehouse_name comes from the
    first location entry.
    """
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
                        quantityAvailable=99999,
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
    # Cap removed — SanMar reports up to 3000 per warehouse × 8 warehouses.
    assert by_part["PC61-NVY-L"].quantity_available == 99999
    assert by_part["PC61-NVY-L"].warehouse_code is None


async def test_inventory_reads_nested_quantity_value():
    """SanMar wraps inventory qty as <quantityAvailable><Quantity><value>N</value></Quantity></quantityAvailable>."""
    svc = FakeService()
    svc.responses[("getInventoryLevels", "K420")] = NS(
        Inventory=NS(
            productId="K420",
            PartInventoryArray=NS(
                PartInventory=[
                    NS(
                        partId="92032",
                        quantityAvailable=NS(Quantity=NS(uom="EA", value="1045")),
                        InventoryLocationArray=None,
                    )
                ]
            ),
        )
    )
    levels = await _client(svc).get_inventory(["K420"])
    assert len(levels) == 1
    assert levels[0].part_id == "92032"
    assert levels[0].quantity_available == 1045


async def test_inventory_aggregates_per_warehouse_and_picks_primary():
    """Sum per-warehouse quantities; warehouse_code = highest-stock location."""
    svc = FakeService()
    svc.responses[("getInventoryLevels", "K420")] = NS(
        Inventory=NS(
            productId="K420",
            PartInventoryArray=NS(
                PartInventory=[
                    NS(
                        partId="92032",
                        quantityAvailable=None,
                        InventoryLocationArray=NS(
                            InventoryLocation=[
                                NS(
                                    inventoryLocationId="1",
                                    inventoryLocationName="Seattle",
                                    inventoryLocationQuantity=NS(
                                        Quantity=NS(value="200")
                                    ),
                                ),
                                NS(
                                    inventoryLocationId="3",
                                    inventoryLocationName="Dallas",
                                    inventoryLocationQuantity=NS(
                                        Quantity=NS(value="500")
                                    ),
                                ),
                                NS(
                                    inventoryLocationId="4",
                                    inventoryLocationName="Reno",
                                    inventoryLocationQuantity=NS(
                                        Quantity=NS(value="161")
                                    ),
                                ),
                            ]
                        ),
                    )
                ]
            ),
        )
    )
    levels = await _client(svc).get_inventory(["K420"])
    assert len(levels) == 1
    assert levels[0].quantity_available == 861  # 200 + 500 + 161
    assert levels[0].warehouse_code == "Dallas"  # highest-stock


async def test_inventory_prefers_top_level_when_locations_empty():
    """If top-level qty is set and no per-location qty, use top-level."""
    svc = FakeService()
    svc.responses[("getInventoryLevels", "PC61")] = NS(
        Inventory=NS(
            productId="PC61",
            PartInventoryArray=NS(
                PartInventory=[
                    NS(
                        partId="PC61-M",
                        quantityAvailable=NS(Quantity=NS(value="42")),
                        InventoryLocationArray=None,
                    )
                ]
            ),
        )
    )
    levels = await _client(svc).get_inventory(["PC61"])
    assert levels[0].quantity_available == 42


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


# ---------------------------------------------------------------------------
# Task 1: localization params on getProduct
# ---------------------------------------------------------------------------

async def test_get_product_sends_localization_defaults():
    """SanMar requires localizationCountry + localizationLanguage on getProduct."""
    svc = FakeService()
    svc.responses[("getProduct", "PC61")] = NS(
        Product=NS(productId="PC61", productName="Tee")
    )
    await _client(svc).get_product("PC61")
    _, kwargs = svc.calls[-1]
    assert kwargs["localizationCountry"] == "us"
    assert kwargs["localizationLanguage"] == "en"


async def test_get_product_accepts_explicit_locale():
    svc = FakeService()
    svc.responses[("getProduct", "PC61")] = NS(
        Product=NS(productId="PC61")
    )
    await _client(svc).get_product(
        "PC61", localization_country="ca", localization_language="fr"
    )
    _, kwargs = svc.calls[-1]
    assert kwargs["localizationCountry"] == "ca"
    assert kwargs["localizationLanguage"] == "fr"


async def test_get_products_batch_propagates_locale():
    svc = FakeService()
    svc.responses["getProduct"] = NS(Product=NS(productId="X"))
    await _client(svc).get_products_batch(["A", "B"])
    for _, kwargs in svc.calls:
        assert kwargs["localizationCountry"] == "us"
        assert kwargs["localizationLanguage"] == "en"



# ---------------------------------------------------------------------------
# Task 2: product parser — SanMar <category> field + multi-description join
# ---------------------------------------------------------------------------

async def test_parse_product_reads_sanmar_category_field():
    """SanMar wraps category name in <category>, not <categoryName>."""
    svc = FakeService()
    svc.responses[("getProduct", "MM1000")] = NS(
        Product=NS(
            productId="MM1000",
            productName="Polo",
            ProductCategoryArray=NS(
                ProductCategory=[NS(category="Polos/Knits", subCategory="Cotton")]
            ),
        )
    )
    product = await _client(svc).get_product("MM1000")
    assert product is not None
    assert "Polos/Knits" in product.categories


async def test_parse_product_joins_multi_description():
    """SanMar returns several <description> elements; zeep yields a list."""
    svc = FakeService()
    svc.responses[("getProduct", "MM1000")] = NS(
        Product=NS(
            productId="MM1000",
            description=[
                "Crafted in heavier knit",
                "8.1-ounce fabric",
                "Moisture-wicking",
            ],
        )
    )
    product = await _client(svc).get_product("MM1000")
    assert product is not None
    assert product.description == (
        "Crafted in heavier knit\n8.1-ounce fabric\nMoisture-wicking"
    )


async def test_parse_product_single_description_still_works():
    """Backwards compat: suppliers returning one description string must still parse."""
    svc = FakeService()
    svc.responses[("getProduct", "PC61")] = NS(
        Product=NS(productId="PC61", description="100% cotton")
    )
    product = await _client(svc).get_product("PC61")
    assert product is not None
    assert product.description == "100% cotton"


# ---------------------------------------------------------------------------
# Task 3: Media service — v1.1.0 default + required mediaType
# ---------------------------------------------------------------------------

async def test_get_media_uses_v110_and_sends_mediatype_image():
    """SanMar requires wsVersion=1.1.0 and mediaType field."""
    svc = FakeService()
    svc.responses[("getMediaContent", "PC61")] = NS(MediaContentArray=None)
    await _client(svc).get_media(["PC61"])
    _, kwargs = svc.calls[-1]
    assert kwargs["wsVersion"] == "1.1.0"
    assert kwargs["mediaType"] == "Image"


async def test_get_media_accepts_document_media_type():
    svc = FakeService()
    svc.responses[("getMediaContent", "PC61")] = NS(MediaContentArray=None)
    await _client(svc).get_media(["PC61"], media_type="Document")
    _, kwargs = svc.calls[-1]
    assert kwargs["mediaType"] == "Document"


# ---------------------------------------------------------------------------
# Task 5: Pricing — required SanMar params
# ---------------------------------------------------------------------------

async def test_get_pricing_sends_required_sanmar_params():
    """SanMar PPC requires currency/fobId/priceType/localization/configurationType."""
    svc = FakeService()
    svc.responses[("getConfigurationAndPricing", "K500")] = NS(
        Configuration=NS(PartArray=None)
    )
    await _client(svc).get_pricing(["K500"])
    _, kwargs = svc.calls[-1]
    assert kwargs["currency"] == "USD"
    assert kwargs["fobId"] == "1"
    assert kwargs["priceType"] == "Net"
    assert kwargs["localizationCountry"] == "US"
    assert kwargs["localizationLanguage"] == "EN"
    assert kwargs["configurationType"] == "Blank"


async def test_get_pricing_accepts_explicit_overrides():
    svc = FakeService()
    svc.responses[("getConfigurationAndPricing", "K500")] = NS(
        Configuration=NS(PartArray=None)
    )
    await _client(svc).get_pricing(
        ["K500"],
        currency="CAD",
        fob_id="6",
        price_type="List",
        localization_country="CA",
        localization_language="FR",
        configuration_type="Configured",
    )
    _, kwargs = svc.calls[-1]
    assert kwargs["currency"] == "CAD"
    assert kwargs["fobId"] == "6"
    assert kwargs["priceType"] == "List"
    assert kwargs["localizationCountry"] == "CA"
    assert kwargs["localizationLanguage"] == "FR"
    assert kwargs["configurationType"] == "Configured"


