"""Unit tests for fourover_normalizer.normalize_4over.

Runs offline, no DB, no HTTP. Standalone script:

    cd backend && source .venv/bin/activate
    python test_fourover_normalizer.py
"""

import sys
from pathlib import Path

# Allow `python test_fourover_normalizer.py` from backend/ without PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from modules.promostandards.schemas import PSProductData, PSProductPart  # noqa: E402
from modules.rest_connector.fourover_normalizer import normalize_4over  # noqa: E402


# Reusable sample mapping — mimics what a user would save via the Field
# Mapping UI for a 4Over supplier.
SAMPLE_MAPPING = {
    # product-level
    "uuid": "supplier_sku",
    "productName": "product_name",
    "productDescription": "description",
    "productBrand": "brand",
    "categoryName": "product_type",
    "imageUrl": "image_url",
    # variant-level
    "paperType": "color",
    "fold": "size",
}


def test_happy_path_three_products():
    raw = [
        {
            "uuid": "brochure-001",
            "productName": "Tri-Fold Brochure",
            "productDescription": "Premium tri-fold brochure",
            "productBrand": "4Over",
            "categoryName": "Brochures",
            "imageUrl": "https://cdn.4over.com/brochure-001.jpg",
            "variants": [
                {"partId": "001-glossy-tri", "paperType": "Glossy", "fold": "Tri"},
                {"partId": "001-matte-bi", "paperType": "Matte", "fold": "Bi"},
            ],
        },
        {
            "uuid": "card-001",
            "productName": "Business Card",
            "productDescription": "Standard business card",
            "productBrand": "4Over",
            "categoryName": "Business Cards",
            "imageUrl": "https://cdn.4over.com/card-001.jpg",
            "variants": [
                {"partId": "card-001-glossy", "paperType": "Glossy", "fold": "None"},
            ],
        },
        {
            "uuid": "poster-001",
            "productName": "Large Format Poster",
            "productDescription": "24x36 poster",
            "productBrand": "4Over",
            "categoryName": "Posters",
            "imageUrl": "https://cdn.4over.com/poster-001.jpg",
            "variants": [],
        },
    ]

    out = normalize_4over(raw, SAMPLE_MAPPING)

    assert len(out) == 3, f"expected 3 products, got {len(out)}"

    # Product #1
    p1 = out[0]
    assert isinstance(p1, PSProductData)
    assert p1.product_id == "brochure-001"
    assert p1.product_name == "Tri-Fold Brochure"
    assert p1.brand == "4Over"
    assert p1.description == "Premium tri-fold brochure"
    assert p1.primary_image_url == "https://cdn.4over.com/brochure-001.jpg"
    assert p1.product_type == "Brochures"
    assert p1.categories == ["Brochures"]
    assert len(p1.parts) == 2
    assert p1.parts[0].part_id == "001-glossy-tri"
    assert p1.parts[0].color_name == "Glossy"
    assert p1.parts[0].size_name == "Tri"

    # Product #3 has no variants → empty parts list, not an error
    p3 = out[2]
    assert p3.product_id == "poster-001"
    assert p3.parts == []

    print("  test_happy_path_three_products OK")


def test_variant_attributes_packed():
    """Variant fields not in the mapping get packed into PSProductPart.attributes."""
    raw = [
        {
            "uuid": "prod-A",
            "productName": "Product A",
            "variants": [
                {
                    "partId": "A-1",
                    "paperType": "Glossy",    # mapped → color
                    "fold": "Tri",            # mapped → size
                    "coating": "UV",          # UNMAPPED → attributes
                    "paper_weight": "100gsm", # UNMAPPED → attributes
                    "finish": "matte",        # UNMAPPED → attributes
                },
            ],
        }
    ]

    out = normalize_4over(raw, SAMPLE_MAPPING)

    assert len(out) == 1
    part = out[0].parts[0]
    assert part.color_name == "Glossy"
    assert part.size_name == "Tri"
    assert part.attributes == {
        "coating": "UV",
        "paper_weight": "100gsm",
        "finish": "matte",
    }
    print("  test_variant_attributes_packed OK")


def test_missing_supplier_sku_skipped():
    """A product whose SKU field isn't in the mapping is skipped silently."""
    raw = [
        {"uuid": "good-1", "productName": "Good Product", "variants": []},
        {"productName": "No UUID here", "variants": []},  # missing uuid — no supplier_sku
        {"uuid": "good-2", "productName": "Another Good", "variants": []},
    ]

    out = normalize_4over(raw, SAMPLE_MAPPING)

    assert len(out) == 2, f"expected 2 survivors, got {len(out)}"
    assert [p.product_id for p in out] == ["good-1", "good-2"]
    print("  test_missing_supplier_sku_skipped OK")


def test_empty_mapping_returns_empty_fields():
    """Minimal mapping → unmapped canonical fields default to None/empty."""
    minimal = {"uuid": "supplier_sku", "productName": "product_name"}
    raw = [
        {
            "uuid": "bare-1",
            "productName": "Bare Product",
            "productBrand": "4Over",      # present, but NOT in mapping
            "imageUrl": "http://x.png",   # present, but NOT in mapping
            "variants": [],
        }
    ]

    out = normalize_4over(raw, minimal)

    assert len(out) == 1
    p = out[0]
    assert p.product_id == "bare-1"
    assert p.product_name == "Bare Product"
    assert p.brand is None            # not mapped → default
    assert p.primary_image_url is None
    assert p.description is None
    assert p.categories == []
    assert p.product_type == "print"  # our chosen default for 4Over
    print("  test_empty_mapping_returns_empty_fields OK")


def test_empty_input():
    assert normalize_4over([], SAMPLE_MAPPING) == []
    print("  test_empty_input OK")


def test_attributes_default_for_sanmar_part():
    """Regression guard: PSProductPart still works with no attributes kwarg.

    Sinchana's SOAP normalizer (Tanishq's Task 4) never sets `attributes`.
    Our schema extension defaults it to {} so that codepath keeps working.
    """
    part = PSProductPart(part_id="PC61-NAVY-M", color_name="Navy", size_name="M")
    assert part.attributes == {}
    assert part.part_id == "PC61-NAVY-M"
    print("  test_attributes_default_for_sanmar_part OK")


def test_type_validation():
    """Bad input types raise TypeError, not some obscure AttributeError."""
    for bad in ("not a list", 42, None, {"not": "a list"}):
        try:
            normalize_4over(bad, SAMPLE_MAPPING)
        except TypeError:
            continue
        raise AssertionError(f"expected TypeError for raw_products={bad!r}")

    try:
        normalize_4over([], "not a dict")  # type: ignore[arg-type]
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError for field_mapping='not a dict'")
    print("  test_type_validation OK")


if __name__ == "__main__":
    print("Running FourOver normalizer tests…\n")

    test_happy_path_three_products()
    test_variant_attributes_packed()
    test_missing_supplier_sku_skipped()
    test_empty_mapping_returns_empty_fields()
    test_empty_input()
    test_attributes_default_for_sanmar_part()
    test_type_validation()

    print("\nAll 7 tests passed ✅")
