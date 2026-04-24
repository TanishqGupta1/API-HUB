"""Smoke-script unit tests — mocks the four PromoStandardsClient calls and
verifies the runner prints a summary block per SKU and exits zero on
all-success, non-zero on any failure.
"""
from __future__ import annotations

from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from modules.promostandards.schemas import (
    PSInventoryLevel,
    PSMediaItem,
    PSPricePoint,
    PSProductData,
    PSProductPart,
)
from scripts import sanmar_smoke


@pytest.fixture
def happy_path(monkeypatch):
    def fake_client_factory(wsdl: str, auth: dict):
        stub = NS()
        stub.get_product = AsyncMock(
            return_value=PSProductData(
                product_id="PC61",
                product_name="Essential Tee",
                brand="Port & Company",
                categories=["T-Shirts"],
                parts=[PSProductPart(part_id="PC61-NVY-M", color_name="Navy", size_name="M")],
            )
        )
        stub.get_inventory = AsyncMock(
            return_value=[
                PSInventoryLevel(
                    product_id="PC61",
                    part_id="PC61-NVY-M",
                    quantity_available=120,
                    warehouse_code="Seattle",
                )
            ]
        )
        stub.get_media = AsyncMock(
            return_value=[
                PSMediaItem(
                    product_id="PC61",
                    url="https://cdnm.sanmar.com/catalog/images/PC61.jpg",
                    media_type="Front",
                )
            ]
        )
        stub.get_pricing = AsyncMock(
            return_value=[
                PSPricePoint(
                    product_id="PC61",
                    part_id="PC61-NVY-M",
                    price=3.99,
                    quantity_min=1,
                )
            ]
        )
        return stub

    monkeypatch.setattr(sanmar_smoke, "PromoStandardsClient", fake_client_factory)

    async def fake_load_auth():
        return {"id": "user", "password": "pass"}

    monkeypatch.setattr(sanmar_smoke, "load_sanmar_auth", fake_load_auth)


async def test_smoke_prints_all_four_services_per_sku(happy_path, capsys):
    code = await sanmar_smoke.run_smoke(["PC61"], sanmar_smoke.PROD_WSDLS)
    out = capsys.readouterr().out
    assert code == 0
    assert "[PRODUCT]" in out
    assert "[INVENTORY]" in out
    assert "[MEDIA]" in out
    assert "[PRICING]" in out
    assert "PC61" in out
    assert "4/4 calls passed" in out


async def test_smoke_returns_nonzero_when_auth_missing(monkeypatch, capsys):
    async def empty_auth():
        return {}

    monkeypatch.setattr(sanmar_smoke, "load_sanmar_auth", empty_auth)
    code = await sanmar_smoke.run_smoke(["PC61"], sanmar_smoke.PROD_WSDLS)
    assert code == 1


async def test_smoke_counts_failures(monkeypatch, capsys):
    def client_with_one_failing_service(wsdl: str, auth: dict):
        stub = NS()
        stub.get_product = AsyncMock(return_value=None)  # counts as failure
        stub.get_inventory = AsyncMock(return_value=[])   # empty counts as failure
        stub.get_media = AsyncMock(return_value=[])
        stub.get_pricing = AsyncMock(return_value=[])
        return stub

    monkeypatch.setattr(
        sanmar_smoke, "PromoStandardsClient", client_with_one_failing_service
    )

    async def fake_auth():
        return {"id": "u", "password": "p"}

    monkeypatch.setattr(sanmar_smoke, "load_sanmar_auth", fake_auth)

    code = await sanmar_smoke.run_smoke(["PC61"], sanmar_smoke.PROD_WSDLS)
    out = capsys.readouterr().out
    assert code == 1
    assert "0/4 calls passed" in out
