"""Inline product push: PushRequest.product as ProductIngest + validator."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from modules.integrations.schemas import PushRequest

pytestmark = pytest.mark.no_db


def _ingest(sku="PC61-INLINE"):
    return {
        "supplier_sku": sku,
        "product_name": "Inline Tee",
        "product_type": "apparel",
        "apparel_details": {"fabric": "cotton"},
    }


def test_inline_product_parses_as_productingest():
    req = PushRequest.model_validate({
        "target": {"customer_id": "00000000-0000-0000-0000-000000000001"},
        "source": {"supplier_slug": "sanmar"},
        "product": _ingest(),
        "dry_run": True,
    })
    assert req.product is not None
    assert req.product.supplier_sku == "PC61-INLINE"
    # product_ref auto-derived from inline product
    assert req.product_ref.supplier_sku == "PC61-INLINE"


def test_neither_product_nor_ref_rejected():
    with pytest.raises(ValidationError):
        PushRequest.model_validate({
            "target": {"customer_id": "00000000-0000-0000-0000-000000000001"},
            "source": {"supplier_slug": "sanmar"},
        })


def test_both_product_and_ref_rejected():
    """Spec: exactly one of (product, product_ref). Both → ValidationError (422)."""
    with pytest.raises(ValidationError):
        PushRequest.model_validate({
            "target": {"customer_id": "00000000-0000-0000-0000-000000000001"},
            "source": {"supplier_slug": "sanmar"},
            "product": _ingest(),
            "product_ref": {"supplier_sku": "DIFFERENT-SKU"},
        })


def test_ref_only_still_valid():
    req = PushRequest.model_validate({
        "target": {"customer_id": "00000000-0000-0000-0000-000000000001"},
        "source": {"supplier_slug": "sanmar"},
        "product_ref": {"supplier_sku": "EXISTING-SKU"},
    })
    assert req.product is None
    assert req.product_ref.supplier_sku == "EXISTING-SKU"
