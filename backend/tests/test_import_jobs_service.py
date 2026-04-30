"""Import-job orchestrator tests. Auth = fatal abort. Per-product = log + continue."""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from modules.import_jobs.base import (
    AuthError,
    BaseAdapter,
    DiscoveryMode,
    ProductRef,
    SupplierError,
)
from modules.import_jobs.registry import register_adapter
from modules.import_jobs.service import run_import
from modules.suppliers.models import Supplier
from modules.sync_jobs.models import SyncJob


class _AuthFailAdapter(BaseAdapter):
    product_type = "print"

    async def discover(self, mode, *, limit=None, explicit_list=None):
        raise AuthError("bad creds", code="401")

    async def hydrate_product(self, ref):
        raise NotImplementedError

    async def discover_changed(self, since):
        return []


@pytest.mark.asyncio
async def test_run_import_auth_error_marks_job_failed(seed_supplier: Supplier):
    register_adapter("AuthFailAdapter", _AuthFailAdapter)
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "AuthFailAdapter"
        await s.commit()

    sync_job_id = await run_import(
        supplier_id=seed_supplier.id,
        mode=DiscoveryMode.FULL,
    )

    async with async_session() as s:
        job = await s.get(SyncJob, sync_job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.records_processed == 0
        assert job.errors and any(
            "bad creds" in (e.get("msg") or "") for e in job.errors
        )


class _MixedAdapter(BaseAdapter):
    product_type = "print"

    async def discover(self, mode, *, limit=None, explicit_list=None):
        return [
            ProductRef(supplier_sku="OK-1"),
            ProductRef(supplier_sku="BAD-1"),
            ProductRef(supplier_sku="OK-2"),
        ]

    async def hydrate_product(self, ref):
        from modules.catalog.schemas import (
            PrintDetailsIngest, ProductIngest,
        )
        if ref.supplier_sku == "BAD-1":
            raise SupplierError("not found", code="404")
        return ProductIngest(
            supplier_sku=ref.supplier_sku,
            product_name=f"product {ref.supplier_sku}",
            product_type="print",
            print_details=PrintDetailsIngest(pricing_method="formula"),
        )

    async def discover_changed(self, since):
        return []


@pytest.mark.asyncio
async def test_run_import_continues_after_per_product_error(seed_supplier: Supplier):
    register_adapter("MixedAdapter", _MixedAdapter)
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "MixedAdapter"
        await s.commit()

    sync_job_id = await run_import(
        supplier_id=seed_supplier.id, mode=DiscoveryMode.FULL,
    )

    async with async_session() as s:
        job = await s.get(SyncJob, sync_job_id)
        assert job.status == "partial_success"
        assert job.records_processed == 2
        assert job.errors is not None and len(job.errors) == 1
        assert job.errors[0]["ref"] == "BAD-1"


@pytest.mark.asyncio
async def test_run_import_success_when_no_errors(seed_supplier: Supplier):
    class _OkAdapter(BaseAdapter):
        product_type = "print"

        async def discover(self, mode, *, limit=None, explicit_list=None):
            return [ProductRef(supplier_sku="OK-1")]

        async def hydrate_product(self, ref):
            from modules.catalog.schemas import (
                PrintDetailsIngest, ProductIngest,
            )
            return ProductIngest(
                supplier_sku=ref.supplier_sku,
                product_name="ok",
                product_type="print",
                print_details=PrintDetailsIngest(pricing_method="formula"),
            )

        async def discover_changed(self, since):
            return []

    register_adapter("OkAdapter", _OkAdapter)
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "OkAdapter"
        await s.commit()

    sync_job_id = await run_import(
        supplier_id=seed_supplier.id, mode=DiscoveryMode.FULL,
    )

    async with async_session() as s:
        job = await s.get(SyncJob, sync_job_id)
        assert job.status == "success"
        assert job.records_processed == 1
        assert job.errors is None


class _EmptyDiscoverAdapter(BaseAdapter):
    product_type = "print"

    async def discover(self, mode, *, limit=None, explicit_list=None):
        return []

    async def hydrate_product(self, ref):
        raise NotImplementedError

    async def discover_changed(self, since):
        return []


@pytest.mark.asyncio
async def test_run_import_full_sets_last_full_sync_on_supplier(seed_supplier: Supplier):
    register_adapter("EmptyDiscoverAdapter", _EmptyDiscoverAdapter)
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "EmptyDiscoverAdapter"
        loaded.last_full_sync = None
        await s.commit()

    job_id = await run_import(
        supplier_id=seed_supplier.id, mode=DiscoveryMode.FULL,
    )

    async with async_session() as s:
        sup = await s.get(Supplier, seed_supplier.id)
        assert sup.last_full_sync is not None
        assert sup.last_delta_sync is None


@pytest.mark.asyncio
async def test_run_import_delta_sets_last_delta_sync(seed_supplier: Supplier):
    register_adapter("EmptyDiscoverAdapter", _EmptyDiscoverAdapter)
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "EmptyDiscoverAdapter"
        loaded.last_delta_sync = None
        await s.commit()

    job_id = await run_import(
        supplier_id=seed_supplier.id, mode=DiscoveryMode.DELTA,
    )
    async with async_session() as s:
        sup = await s.get(Supplier, seed_supplier.id)
        assert sup.last_delta_sync is not None
