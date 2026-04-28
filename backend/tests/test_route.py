import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_push_log_routes_are_registered_under_api(client: AsyncClient):
    """Pin the public path of push_log endpoints — a refactor must not move them."""
    r = await client.get("/api/push-log?limit=1")
    assert r.status_code == 200, r.text

    r = await client.post("/api/push-log", json={})
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_push_status_route_is_registered_under_products(client: AsyncClient):
    r = await client.get(f"/api/products/{uuid.uuid4()}/push-status")
    assert r.status_code == 200, r.text
