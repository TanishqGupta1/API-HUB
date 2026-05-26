"""Security regression: supplier API responses must never expose auth_config.

Covers GET /api/suppliers/, GET /api/suppliers/{id},
POST /api/suppliers/, and PATCH /api/suppliers/{id}.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


_SUPPLIER_PAYLOAD = {
    "name": "Auth-Leak Test Supplier",
    "slug": "auth-leak-test",
    "protocol": "promostandards",
    "promostandards_code": "TEST",
    "auth_config": {"id": "secret-username", "password": "hunter2"},
}


async def _create_supplier(client: AsyncClient) -> str:
    resp = await client.post("/api/suppliers", json=_SUPPLIER_PAYLOAD)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _assert_no_auth_config(body: dict | list) -> None:
    items = body if isinstance(body, list) else [body]
    for item in items:
        assert "auth_config" not in item, (
            f"auth_config leaked in response: {item}"
        )
        assert "password" not in str(item), (
            f"plaintext password found in response: {item}"
        )


@pytest.mark.asyncio
async def test_list_suppliers_omits_auth_config(client: AsyncClient):
    await _create_supplier(client)
    resp = await client.get("/api/suppliers")
    assert resp.status_code == 200
    _assert_no_auth_config(resp.json())


@pytest.mark.asyncio
async def test_get_supplier_omits_auth_config(client: AsyncClient):
    supplier_id = await _create_supplier(client)
    resp = await client.get(f"/api/suppliers/{supplier_id}")
    assert resp.status_code == 200
    _assert_no_auth_config(resp.json())
    assert resp.json()["has_credentials"] is True


@pytest.mark.asyncio
async def test_create_supplier_response_omits_auth_config(client: AsyncClient):
    resp = await client.post("/api/suppliers", json=_SUPPLIER_PAYLOAD)
    assert resp.status_code == 201
    _assert_no_auth_config(resp.json())
    assert resp.json()["has_credentials"] is True


@pytest.mark.asyncio
async def test_patch_supplier_response_omits_auth_config(client: AsyncClient):
    supplier_id = await _create_supplier(client)
    resp = await client.patch(
        f"/api/suppliers/{supplier_id}",
        json={"auth_config": {"id": "new-user", "password": "new-pass"}},
    )
    assert resp.status_code == 200
    _assert_no_auth_config(resp.json())
    assert resp.json()["has_credentials"] is True
