"""T3 regression: POST /api/suppliers/test runs a real SOAP probe for PromoStandards
suppliers (SanMar etc.). Old behavior only checked directory existence — admin
saw green, import then failed. Probe must call a real SOAP method with the
provided credentials and surface auth/connectivity failures clearly.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest


_INGEST_HEADER = {"X-Ingest-Secret": "test-secret-do-not-use-in-prod"}

_SAMPLE_PS_ENDPOINTS = [
    {
        "URL": "https://ws.sanmar.com:8080/promostandards/ProductDataServiceBinding?WSDL",
        "Service": {
            "ServiceType": {"Name": "Product Data"},
            "Version": "2.0.0",
        },
    },
    {
        "URL": "https://ws.sanmar.com:8080/promostandards/InventoryServiceBinding?WSDL",
        "Service": {
            "ServiceType": {"Name": "Inventory"},
            "Version": "2.0.0",
        },
    },
]


@pytest.mark.asyncio
async def test_promostandards_probe_succeeds_with_valid_creds(client):
    """A successful SOAP probe returns ok=True plus a product count."""
    with patch(
        "modules.suppliers.routes.get_ps_endpoints",
        new=AsyncMock(return_value=_SAMPLE_PS_ENDPOINTS),
    ), patch(
        "modules.suppliers.routes.PromoStandardsClient.get_sellable_product_ids",
        new=AsyncMock(return_value=["PC61", "PC54", "K500"]),
    ):
        resp = await client.post(
            "/api/suppliers/test",
            json={
                "protocol": "promostandards",
                "promostandards_code": "SANMAR",
                "auth_config": {"id": "12345", "password": "real-password"},
            },
            headers=_INGEST_HEADER,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True, body
    assert body.get("product_count") == 3
    assert "SANMAR" in body.get("message", "") or "sanmar" in body.get("message", "").lower()


@pytest.mark.asyncio
async def test_promostandards_probe_fails_on_bad_credentials(client):
    """SOAP auth-fault must surface as ok=False with the upstream message."""

    class _AuthFault(Exception):
        pass

    with patch(
        "modules.suppliers.routes.get_ps_endpoints",
        new=AsyncMock(return_value=_SAMPLE_PS_ENDPOINTS),
    ), patch(
        "modules.suppliers.routes.PromoStandardsClient.get_sellable_product_ids",
        new=AsyncMock(side_effect=_AuthFault("Authentication failed: invalid id or password")),
    ):
        resp = await client.post(
            "/api/suppliers/test",
            json={
                "protocol": "promostandards",
                "promostandards_code": "SANMAR",
                "auth_config": {"id": "12345", "password": "wrong"},
            },
            headers=_INGEST_HEADER,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is False, body
    assert "auth" in body["error"].lower() or "invalid" in body["error"].lower()


@pytest.mark.asyncio
async def test_promostandards_probe_fails_fast_when_creds_missing(client):
    """Missing id/password must NOT trigger a directory lookup or SOAP call."""
    directory = AsyncMock(return_value=_SAMPLE_PS_ENDPOINTS)
    soap = AsyncMock(return_value=[])
    with patch("modules.suppliers.routes.get_ps_endpoints", new=directory), patch(
        "modules.suppliers.routes.PromoStandardsClient.get_sellable_product_ids", new=soap
    ):
        resp = await client.post(
            "/api/suppliers/test",
            json={
                "protocol": "promostandards",
                "promostandards_code": "SANMAR",
                "auth_config": {},
            },
            headers=_INGEST_HEADER,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is False
    assert "credentials" in body["error"].lower() or "password" in body["error"].lower()
    directory.assert_not_awaited()
    soap.assert_not_awaited()


@pytest.mark.asyncio
async def test_promostandards_probe_fails_when_code_unknown_in_directory(client):
    """A 404 from the PS directory must surface as a clear actionable message."""
    fake_request = httpx.Request("GET", "https://example.com")
    fake_response = httpx.Response(404, request=fake_request)
    with patch(
        "modules.suppliers.routes.get_ps_endpoints",
        new=AsyncMock(
            side_effect=httpx.HTTPStatusError("not found", request=fake_request, response=fake_response)
        ),
    ):
        resp = await client.post(
            "/api/suppliers/test",
            json={
                "protocol": "promostandards",
                "promostandards_code": "BOGUS",
                "auth_config": {"id": "1", "password": "x"},
            },
            headers=_INGEST_HEADER,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is False
    assert "directory" in body["error"].lower() or "not found" in body["error"].lower()


@pytest.mark.asyncio
async def test_promostandards_probe_fails_when_no_product_data_endpoint(client):
    """Directory returns rows but no Product Data WSDL — must report cleanly."""
    inventory_only = [
        {
            "URL": "https://ws.example.com/Inventory?WSDL",
            "Service": {"ServiceType": {"Name": "Inventory"}, "Version": "2.0.0"},
        }
    ]
    with patch(
        "modules.suppliers.routes.get_ps_endpoints",
        new=AsyncMock(return_value=inventory_only),
    ):
        resp = await client.post(
            "/api/suppliers/test",
            json={
                "protocol": "promostandards",
                "promostandards_code": "PARTIAL",
                "auth_config": {"id": "1", "password": "x"},
            },
            headers=_INGEST_HEADER,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is False
    assert "product data" in body["error"].lower() or "endpoint" in body["error"].lower()


@pytest.mark.asyncio
async def test_rest_probe_path_unchanged(client):
    """Non-PS protocols keep the existing credential-shape check."""
    resp = await client.post(
        "/api/suppliers/test",
        json={
            "protocol": "rest",
            "auth_config": {"id": "user", "password": "secret"},
        },
        headers=_INGEST_HEADER,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
