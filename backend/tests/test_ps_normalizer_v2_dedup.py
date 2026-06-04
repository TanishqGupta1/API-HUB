"""Regression tests for ps_normalizer_v2 price dedup (Bug 4).

SanMar's getProduct response packs multiple per-size MSRPs into a single
ProductPriceGroup, all with the same quantityMin=1, with no part_id
association. Broadcasting them all to every variant would violate the
uq_variant_price_type_qty DB constraint (one price per type+qty_min
per variant). These tests verify the normalizer dedupes correctly.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from modules.promostandards.ps_normalizer_v2 import (
    _dedupe_price_tiers,
    normalize_get_product_xml,
    merge_pricing,
)
from modules.catalog.schemas import VariantPriceIngest

pytestmark = [pytest.mark.no_db]


# ---------------------------------------------------------------------------
# _dedupe_price_tiers helper
# ---------------------------------------------------------------------------


def _tier(price_type: str, qmin: int, price: str) -> VariantPriceIngest:
    return VariantPriceIngest(
        price_type=price_type,
        quantity_min=qmin,
        price=Decimal(price),
    )


def test_dedupe_keeps_cheapest_when_keys_collide():
    """When 6 MSRPs all share (type=MSRP, qmin=1), keep only the cheapest."""
    tiers = [
        _tier("MSRP", 1, "10.42"),
        _tier("MSRP", 1, "13.88"),
        _tier("MSRP", 1, "6.90"),   # ← should win (cheapest)
        _tier("MSRP", 1, "6.24"),   # actually this one
        _tier("MSRP", 1, "9.34"),
        _tier("MSRP", 1, "12.96"),
    ]
    out = _dedupe_price_tiers(tiers)
    assert len(out) == 1
    assert out[0].price == Decimal("6.24")  # the cheapest of the six


def test_dedupe_preserves_distinct_qmin_tiers():
    """A real tier list with different quantity_min values must all survive."""
    tiers = [
        _tier("Net", 1, "10.00"),
        _tier("Net", 12, "9.00"),
        _tier("Net", 72, "8.00"),
        _tier("Net", 144, "7.00"),
    ]
    out = _dedupe_price_tiers(tiers)
    assert len(out) == 4
    # Ordering is dict insertion order — should match input
    assert [t.quantity_min for t in out] == [1, 12, 72, 144]


def test_dedupe_preserves_distinct_price_types():
    """MSRP and Net at the same qmin are different rows — keep both."""
    tiers = [
        _tier("MSRP", 1, "15.00"),
        _tier("Net", 1, "10.00"),
        _tier("Case", 1, "8.00"),
    ]
    out = _dedupe_price_tiers(tiers)
    assert len(out) == 3
    types = {t.price_type for t in out}
    assert types == {"MSRP", "Net", "Case"}


def test_dedupe_empty_list_returns_empty():
    assert _dedupe_price_tiers([]) == []


# ---------------------------------------------------------------------------
# normalize_get_product_xml on a realistic SanMar payload
# ---------------------------------------------------------------------------


_SANMAR_PC61_LIKE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
 <env:Body>
  <ns2:GetProductResponse xmlns:ns2="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/"
                          xmlns="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/">
   <Product>
    <productId>PC61</productId>
    <productName>Port &amp; Co Essential Tee</productName>
    <productBrand>Port &amp; Co</productBrand>
    <ProductCategoryArray>
      <ProductCategory><category>T-Shirts</category></ProductCategory>
    </ProductCategoryArray>
    <ProductPartArray>
      <ProductPart>
        <partId>P1</partId>
        <primaryColor><Color><colorName>Navy</colorName></Color></primaryColor>
        <ApparelSize><labelSize>M</labelSize></ApparelSize>
      </ProductPart>
      <ProductPart>
        <partId>P2</partId>
        <primaryColor><Color><colorName>Navy</colorName></Color></primaryColor>
        <ApparelSize><labelSize>L</labelSize></ApparelSize>
      </ProductPart>
      <ProductPart>
        <partId>P3</partId>
        <primaryColor><Color><colorName>Navy</colorName></Color></primaryColor>
        <ApparelSize><labelSize>2XL</labelSize></ApparelSize>
      </ProductPart>
    </ProductPartArray>
    <ProductPriceGroupArray>
      <ProductPriceGroup>
        <groupName>MSRP</groupName>
        <ProductPriceArray>
          <ProductPrice><quantityMin>1</quantityMin><price>10.42</price></ProductPrice>
          <ProductPrice><quantityMin>1</quantityMin><price>13.88</price></ProductPrice>
          <ProductPrice><quantityMin>1</quantityMin><price>6.90</price></ProductPrice>
          <ProductPrice><quantityMin>1</quantityMin><price>6.24</price></ProductPrice>
          <ProductPrice><quantityMin>1</quantityMin><price>9.34</price></ProductPrice>
          <ProductPrice><quantityMin>1</quantityMin><price>12.96</price></ProductPrice>
        </ProductPriceArray>
      </ProductPriceGroup>
    </ProductPriceGroupArray>
   </Product>
  </ns2:GetProductResponse>
 </env:Body>
</env:Envelope>"""


def test_sanmar_pc61_normalizes_without_duplicate_msrp_per_variant():
    """The bug: 6 MSRPs broadcast to 3 variants = 18 rows, all (variant, MSRP, qmin=1)
    duplicating downstream. Fixed: each variant gets exactly ONE MSRP row."""
    ingest = normalize_get_product_xml(_SANMAR_PC61_LIKE_XML)
    assert len(ingest.variants) == 3
    for v in ingest.variants:
        msrp_rows = [p for p in v.prices if p.price_type == "MSRP"]
        # Bug-4 invariant: at most one MSRP row per (variant, qmin=1)
        keys = {(p.price_type, p.quantity_min) for p in msrp_rows}
        assert len(keys) == len(msrp_rows), (
            f"variant part_id={v.part_id} has duplicate (price_type, qmin) keys"
        )
        # Specifically: exactly one MSRP @ qmin=1 (the cheapest = 6.24)
        assert len(msrp_rows) == 1
        assert msrp_rows[0].price == Decimal("6.24")
