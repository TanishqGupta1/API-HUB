"""Task 20 — Collapse `/payload` + `/ops-variants` + `/ops-options` into one.

The single `/api/push/{customer_id}/product/{product_id}/payload` endpoint
now returns everything callers used to get from three separate routes:

  - product + variants + images + markup_rule (original /payload shape)
  - ops_variants (sizes[] + prices[] bundle for OPS setProductSize / setProductPrice)
  - options (product-scoped OPS option shape, master_option_id stripped)

Hermetic — mocks calculate_price and the DB session.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _build_app():
    """Build a FastAPI app with the markup push router + a mock DB."""
    from modules.markup.routes import push_router
    from modules.catalog.ingest import require_ingest_secret
    from database import get_db

    app = FastAPI()
    app.include_router(push_router)

    # Bypass ingest-secret auth in tests.
    async def fake_auth() -> None:
        return None

    async def fake_db():
        db = AsyncMock()
        # Default: no enabled product options
        result = AsyncMock()
        result.scalars = lambda: SimpleNamespace(all=lambda: [])
        result.all = lambda: []
        db.execute = AsyncMock(return_value=result)
        yield db

    app.dependency_overrides[require_ingest_secret] = fake_auth
    app.dependency_overrides[get_db] = fake_db
    return app


# Sample shape calculate_price returns
_FAKE_PAYLOAD = {
    "product": {
        "supplier_sku": "PC61",
        "name": "Port & Company Essential Tee",
        "brand": "Port & Company",
        "category": "T-Shirts",
    },
    "variants": [
        {
            "sku": "PC61-NAV-S",
            "color": "Navy",
            "size": "S",
            "base_price": 3.99,
            "final_price": 5.99,
            "inventory": 250,
        },
        {
            "sku": "PC61-NAV-M",
            "color": "Navy",
            "size": "M",
            "base_price": 3.99,
            "final_price": 5.99,
            "inventory": 500,
        },
    ],
    "images": [
        {"url": "https://www.sanmar.com/imgindex/PC61_NAVY_front.jpg", "image_type": "front"}
    ],
    "markup_rule": {
        "id": "33333333-3333-3333-3333-333333333333",
        "scope": "global",
        "markup_pct": 50.0,
        "markup_amount": None,
        "priority": 0,
    },
}


def test_payload_includes_legacy_fields():
    """Original shape preserved — product, variants, images, markup_rule."""
    app = _build_app()
    with patch(
        "modules.markup.routes.calculate_price",
        AsyncMock(return_value=_FAKE_PAYLOAD),
    ):
        client = TestClient(app)
        r = client.get(
            "/api/push/11111111-1111-1111-1111-111111111111/product/22222222-2222-2222-2222-222222222222/payload"
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["product"]["supplier_sku"] == "PC61"
    assert len(body["variants"]) == 2
    assert body["variants"][0]["final_price"] == 5.99
    assert len(body["images"]) == 1
    assert body["markup_rule"]["markup_pct"] == 50.0


def test_payload_includes_ops_variants_bundle():
    """Used to live at /ops-variants; now collapsed into /payload."""
    app = _build_app()
    with patch(
        "modules.markup.routes.calculate_price",
        AsyncMock(return_value=_FAKE_PAYLOAD),
    ):
        client = TestClient(app)
        r = client.get(
            "/api/push/11111111-1111-1111-1111-111111111111/product/22222222-2222-2222-2222-222222222222/payload"
        )
    body = r.json()
    assert "ops_variants" in body, "ops_variants section missing from unified payload"
    bundle = body["ops_variants"]
    assert "sizes" in bundle and "prices" in bundle
    assert len(bundle["sizes"]) == 2
    assert bundle["sizes"][0]["size_name"] == "S"
    assert bundle["sizes"][0]["color_name"] == "Navy"
    assert bundle["sizes"][0]["products_sku"] == "PC61-NAV-S"
    assert len(bundle["prices"]) == 2
    assert bundle["prices"][0]["price"] == 5.99
    assert bundle["prices"][0]["vendor_price"] == 3.99


def test_payload_includes_options_section():
    """Used to live at /ops-options; now collapsed into /payload.

    With no enabled product options (default mock), the section is an
    empty list — not absent, not null. Same field, consistent shape.
    """
    app = _build_app()
    with patch(
        "modules.markup.routes.calculate_price",
        AsyncMock(return_value=_FAKE_PAYLOAD),
    ):
        client = TestClient(app)
        r = client.get(
            "/api/push/11111111-1111-1111-1111-111111111111/product/22222222-2222-2222-2222-222222222222/payload"
        )
    body = r.json()
    assert "options" in body, "options section missing from unified payload"
    assert isinstance(body["options"], list)
    assert body["options"] == []


def test_old_ops_variants_route_is_gone():
    """The /ops-variants route was deleted. Hit returns 404."""
    app = _build_app()
    client = TestClient(app)
    r = client.get(
        "/api/push/11111111-1111-1111-1111-111111111111/product/22222222-2222-2222-2222-222222222222/ops-variants"
    )
    assert r.status_code == 404


def test_old_ops_options_route_is_gone():
    """The /ops-options route was deleted. Hit returns 404."""
    app = _build_app()
    client = TestClient(app)
    r = client.get(
        "/api/push/11111111-1111-1111-1111-111111111111/product/22222222-2222-2222-2222-222222222222/ops-options"
    )
    assert r.status_code == 404
