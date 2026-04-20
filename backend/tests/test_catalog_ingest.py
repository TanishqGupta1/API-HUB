"""Behavior tests for /api/ingest/{supplier_id}/* endpoints."""
import pytest
from httpx import AsyncClient

SECRET = {"X-Ingest-Secret": "test-secret-do-not-use-in-prod"}


@pytest.mark.asyncio
async def test_ingest_rejects_missing_secret(client: AsyncClient, seed_supplier):
    r = await client.post(f"/api/ingest/{seed_supplier.id}/products", json=[])
    assert r.status_code == 401
    assert "secret" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ingest_rejects_wrong_secret(client: AsyncClient, seed_supplier):
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        headers={"X-Ingest-Secret": "wrong"},
        json=[],
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_ingest_accepts_correct_secret_empty_body(client: AsyncClient, seed_supplier):
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        headers=SECRET,
        json=[],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["records_processed"] == 0
    assert body["status"] == "completed"


def test_ingest_schemas_importable():
    from modules.catalog.schemas import (
        CategoryIngest,
        ImageIngest,
        IngestResult,
        InventoryIngest,
        PriceIngest,
        ProductIngest,
        VariantIngest,
    )

    p = ProductIngest(supplier_sku="X", product_name="X")
    assert p.variants == [] and p.images == []

    v = VariantIngest(part_id="p", base_price=None)
    assert v.base_price is None
