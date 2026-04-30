"""POST /api/suppliers/{id}/import endpoint tests."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_import_request_validates_mode_and_limit():
    from pydantic import ValidationError
    from modules.import_jobs.schemas import ImportRequest

    ok = ImportRequest(mode="full", limit=10)
    assert ok.mode == "full"
    assert ok.limit == 10

    explicit = ImportRequest(mode="explicit_list", explicit_list=["131", "262"])
    assert explicit.explicit_list == ["131", "262"]

    with pytest.raises(ValidationError):
        ImportRequest(mode="not_a_mode")

    with pytest.raises(ValidationError):
        # explicit_list mode requires list
        ImportRequest(mode="explicit_list")

    with pytest.raises(ValidationError):
        # negative limit
        ImportRequest(mode="first_n", limit=-1)


import json
from pathlib import Path

import httpx
import respx
from sqlalchemy import select

from database import async_session
from modules.import_jobs.base import BaseAdapter, ProductRef
from modules.import_jobs.registry import register_adapter
from modules.suppliers.models import Supplier
from modules.sync_jobs.models import SyncJob


@pytest.mark.asyncio
async def test_import_endpoint_rejects_unknown_supplier(client):
    import uuid
    fake_id = uuid.uuid4()
    resp = await client.post(f"/api/suppliers/{fake_id}/import", json={"mode": "full"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_import_endpoint_rejects_supplier_without_adapter(client, seed_supplier):
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = None
        await s.commit()

    resp = await client.post(
        f"/api/suppliers/{seed_supplier.id}/import", json={"mode": "full"}
    )
    assert resp.status_code == 409
    assert "adapter_class" in resp.text


@pytest.mark.asyncio
async def test_import_endpoint_returns_real_sync_job_id_that_appears_in_db(
    client, seed_supplier,
):
    class _NoopAdapter(BaseAdapter):
        product_type = "print"

        async def discover(self, mode, *, limit=None, explicit_list=None):
            return []   # discover returns empty -> success

        async def hydrate_product(self, ref):
            from modules.catalog.schemas import PrintDetailsIngest, ProductIngest
            return ProductIngest(
                supplier_sku=ref.supplier_sku,
                product_name="x",
                product_type="print",
                print_details=PrintDetailsIngest(),
            )

        async def discover_changed(self, since):
            return []

    register_adapter("NoopAdapter", _NoopAdapter)
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "NoopAdapter"
        await s.commit()

    resp = await client.post(
        f"/api/suppliers/{seed_supplier.id}/import",
        json={"mode": "full"},
    )
    assert resp.status_code == 202
    job_id = resp.json()["sync_job_id"]

    async with async_session() as s:
        job = await s.get(SyncJob, job_id)
        assert job is not None
        # Either the bg task already ran (status success) or it is still running.
        assert job.status in ("running", "success", "queued")
        assert str(job.supplier_id) == str(seed_supplier.id)


@pytest.mark.asyncio
async def test_import_endpoint_rejects_when_running_job_exists_same_mode(
    client, seed_supplier,
):
    """409 if a 'running' or 'queued' job already exists for this supplier+mode."""
    from datetime import datetime, timezone

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "NoopAdapter"
        await s.commit()

        running = SyncJob(
            supplier_id=seed_supplier.id,
            supplier_name=seed_supplier.name,
            job_type="import:full",
            status="running",
            records_processed=0,
        )
        running.started_at = datetime.now(timezone.utc)
        s.add(running)
        await s.commit()

    resp = await client.post(
        f"/api/suppliers/{seed_supplier.id}/import",
        json={"mode": "full"},
    )
    assert resp.status_code == 409
    assert "already running" in resp.text.lower()


@pytest.mark.asyncio
async def test_e2e_ops_import_persists_decals_via_endpoint(client, seed_supplier):
    """Hits POST /api/suppliers/{id}/import, drives OPSAdapter against mocked
    GraphQL serving the on-disk Decals fixture, then asserts persisted shape."""
    from modules.catalog.models import (
        PrintDetails,
        Product,
        ProductOption,
        ProductSize,
    )
    from modules.sync_jobs.models import SyncJob
    import json
    from pathlib import Path
    import asyncio
    import respx
    import httpx

    base_url = "https://vg.onprintshop.test"
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "OPSAdapter"
        loaded.base_url = base_url
        loaded.auth_config = {"auth_token": "tok-e2e"}
        await s.commit()

    fixtures_dir = Path(__file__).parent / "fixtures"
    raw_list = json.loads((fixtures_dir / "ops_decals.json").read_text())

    list_response = {
        "data": {
            "listProducts": [
                {"product_id": p["product_id"]} for p in raw_list
            ]
        }
    }

    def get_product_response(product_id: int) -> dict:
        match = next(p for p in raw_list if p["product_id"] == product_id)
        return {"data": {"getProduct": match}}

    with respx.mock as router:
        def _route(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            q = payload["query"]
            if q.startswith("query ListProducts"):
                return httpx.Response(200, json=list_response)
            if q.startswith("query GetProduct"):
                pid = int(payload["variables"]["id"])
                return httpx.Response(200, json=get_product_response(pid))
            return httpx.Response(400, json={"errors": [{"message": "unknown"}]})

        router.route().mock(side_effect=_route)

        resp = await client.post(
            f"/api/suppliers/{seed_supplier.id}/import",
            json={"mode": "first_n", "limit": len(raw_list)},
        )

        assert resp.status_code == 202, resp.text
        job_id = resp.json()["sync_job_id"]

        for _ in range(20):
            async with async_session() as s:
                job = await s.get(SyncJob, job_id)
                if job and job.status in ("success", "partial_success", "failed"):
                    break
            await asyncio.sleep(0.2)

    async with async_session() as s:
        job = await s.get(SyncJob, job_id)
        assert job.status == "success", f"errors: {job.errors}"
        assert job.records_processed == len(raw_list)

        products = (await s.execute(
            select(Product).where(Product.supplier_id == seed_supplier.id)
        )).scalars().all()
        assert len(products) == len(raw_list)
        for p in products:
            assert p.product_type == "print"
            assert str(p.ops_product_id) == str(p.supplier_sku)

            details = await s.get(PrintDetails, p.id)
            assert details is not None

            sizes = (await s.execute(
                select(ProductSize).where(ProductSize.product_id == p.id)
            )).scalars().all()
            assert len(sizes) >= 1

            options = (await s.execute(
                select(ProductOption).where(ProductOption.product_id == p.id)
            )).scalars().all()
            assert len(options) >= 30
