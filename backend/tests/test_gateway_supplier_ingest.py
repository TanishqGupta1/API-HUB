"""T17: POST /api/integrations/v1/suppliers/{slug}/products — catalog upsert.

Covers: X-Orchestrator-Key auth, supplier slug resolution, scope check,
batched ProductIngest upsert via persist_product, SyncJob bookkeeping,
and Idempotency-Key passthrough.
"""
from __future__ import annotations

import hashlib
import secrets
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from database import async_session
from modules.catalog.models import Product
from modules.integrations.models import IntegrationKey
from modules.sync_jobs.models import SyncJob


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def integration_key():
    raw = secrets.token_urlsafe(24)
    key_id = f"t17-key-{uuid4().hex[:8]}"
    async with async_session() as s:
        k = IntegrationKey(
            id=key_id,
            key_hash=hashlib.sha256(raw.encode()).hexdigest(),
            name="T17 test key",
        )
        s.add(k)
        await s.commit()
        await s.refresh(k)
        s.expunge(k)
    try:
        yield {"key": k, "raw": raw}
    finally:
        async with async_session() as s:
            await s.execute(delete(IntegrationKey).where(IntegrationKey.id == key_id))
            await s.commit()


@pytest_asyncio.fixture
async def scoped_key():
    """A key restricted to one supplier slug — for scope-check tests."""
    raw = secrets.token_urlsafe(24)
    key_id = f"t17-scoped-{uuid4().hex[:8]}"
    async with async_session() as s:
        k = IntegrationKey(
            id=key_id,
            key_hash=hashlib.sha256(raw.encode()).hexdigest(),
            name="T17 scoped key",
            allowed_supplier_slugs=["only-this-one"],
        )
        s.add(k)
        await s.commit()
        await s.refresh(k)
        s.expunge(k)
    try:
        yield {"key": k, "raw": raw}
    finally:
        async with async_session() as s:
            await s.execute(delete(IntegrationKey).where(IntegrationKey.id == key_id))
            await s.commit()


def _ingest_item(sku: str, name: str = "Test Product") -> dict:
    return {
        "supplier_sku": sku,
        "product_name": name,
        "product_type": "apparel",
        "variants": [
            {
                "part_id": f"{sku}-V1",
                "sku": f"{sku}-V1-SKU",
                "color": "Black",
                "size": "M",
                "base_price": "12.50",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_without_orchestrator_key_returns_401(client, seed_supplier):
    resp = await client.post(
        f"/api/integrations/v1/suppliers/{seed_supplier.slug}/products",
        json=[_ingest_item("T17-A")],
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_ingest_with_bad_orchestrator_key_returns_401(client, seed_supplier):
    resp = await client.post(
        f"/api/integrations/v1/suppliers/{seed_supplier.slug}/products",
        json=[_ingest_item("T17-A")],
        headers={"X-Orchestrator-Key": "not-a-real-key"},
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_ingest_with_scoped_key_blocks_other_suppliers(client, seed_supplier, scoped_key):
    resp = await client.post(
        f"/api/integrations/v1/suppliers/{seed_supplier.slug}/products",
        json=[_ingest_item("T17-A")],
        headers={"X-Orchestrator-Key": scoped_key["raw"]},
    )
    assert resp.status_code == 403, resp.text
    assert "KEY_NOT_ALLOWED" in resp.text


# ---------------------------------------------------------------------------
# Supplier resolution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_unknown_supplier_returns_404(client, integration_key):
    resp = await client.post(
        "/api/integrations/v1/suppliers/no-such-supplier/products",
        json=[_ingest_item("T17-A")],
        headers={"X-Orchestrator-Key": integration_key["raw"]},
    )
    assert resp.status_code == 404, resp.text
    assert "UNKNOWN_REF" in resp.text


@pytest.mark.asyncio
async def test_ingest_inactive_supplier_returns_409(
    client, inactive_supplier, integration_key
):
    resp = await client.post(
        f"/api/integrations/v1/suppliers/{inactive_supplier.slug}/products",
        json=[_ingest_item("T17-A")],
        headers={"X-Orchestrator-Key": integration_key["raw"]},
    )
    assert resp.status_code == 409, resp.text


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_persists_batch(client, seed_supplier, integration_key):
    """Batch should land as Product rows owned by the named supplier."""
    batch = [_ingest_item("T17-P1"), _ingest_item("T17-P2")]
    resp = await client.post(
        f"/api/integrations/v1/suppliers/{seed_supplier.slug}/products",
        json=batch,
        headers={"X-Orchestrator-Key": integration_key["raw"]},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["records_processed"] == 2
    assert body["supplier_slug"] == seed_supplier.slug
    assert body["sync_job_id"]

    async with async_session() as s:
        rows = (
            await s.execute(
                select(Product).where(
                    Product.supplier_id == seed_supplier.id,
                    Product.supplier_sku.in_(["T17-P1", "T17-P2"]),
                )
            )
        ).scalars().all()
        assert len(rows) == 2


@pytest.mark.asyncio
async def test_ingest_records_sync_job(client, seed_supplier, integration_key):
    resp = await client.post(
        f"/api/integrations/v1/suppliers/{seed_supplier.slug}/products",
        json=[_ingest_item("T17-J1")],
        headers={
            "X-Orchestrator-Key": integration_key["raw"],
            "Idempotency-Key": "t17-sync-job-001",
        },
    )
    assert resp.status_code == 202
    body = resp.json()

    async with async_session() as s:
        job = (
            await s.execute(select(SyncJob).where(SyncJob.id == body["sync_job_id"]))
        ).scalar_one_or_none()
        assert job is not None
        assert job.status == "completed"
        assert job.records_processed == 1
        assert job.supplier_id == seed_supplier.id


@pytest.mark.asyncio
async def test_ingest_is_idempotent_via_upsert(client, seed_supplier, integration_key):
    """Two posts with the same payload must not double-insert rows."""
    item = _ingest_item("T17-IDEM")
    for _ in range(2):
        resp = await client.post(
            f"/api/integrations/v1/suppliers/{seed_supplier.slug}/products",
            json=[item],
            headers={"X-Orchestrator-Key": integration_key["raw"]},
        )
        assert resp.status_code == 202

    async with async_session() as s:
        rows = (
            await s.execute(
                select(Product).where(
                    Product.supplier_id == seed_supplier.id,
                    Product.supplier_sku == "T17-IDEM",
                )
            )
        ).scalars().all()
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_ingest_empty_batch_succeeds(client, seed_supplier, integration_key):
    resp = await client.post(
        f"/api/integrations/v1/suppliers/{seed_supplier.slug}/products",
        json=[],
        headers={"X-Orchestrator-Key": integration_key["raw"]},
    )
    assert resp.status_code == 202
    assert resp.json()["records_processed"] == 0
