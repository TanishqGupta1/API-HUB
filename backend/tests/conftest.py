"""Shared pytest fixtures for the backend test suite.

Strategy: each fixture/session is short-lived. Test data is inserted with
a fresh session, committed, and then cleaned up by the autouse cleanup
fixture after each test. This avoids asyncpg "another operation in progress"
errors that occur when the same session is shared between the test and the
FastAPI app's request handler.
"""
import os
from pathlib import Path

import pytest_asyncio
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

os.environ["INGEST_SHARED_SECRET"] = "test-secret-do-not-use-in-prod"

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from database import Base, async_session, engine  # noqa: E402
from main import app  # noqa: E402

TEST_SUPPLIER_SLUGS = ("vg-ops-test", "vg-ops-inactive")


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


async def _cleanup_test_suppliers() -> None:
    """Delete any lingering rows created by test fixtures.

    Cleans sync_jobs, then cascades through products/variants/images/categories
    via each test-supplier's FK, then the supplier rows themselves.
    """
    from modules.catalog.models import Category, Product, ProductImage, ProductVariant
    from modules.suppliers.models import Supplier
    from modules.sync_jobs.models import SyncJob

    async with async_session() as s:
        supplier_ids = (
            await s.execute(
                select(Supplier.id).where(Supplier.slug.in_(TEST_SUPPLIER_SLUGS))
            )
        ).scalars().all()
        if not supplier_ids:
            await s.commit()
            return

        product_ids = (
            await s.execute(
                select(Product.id).where(Product.supplier_id.in_(supplier_ids))
            )
        ).scalars().all()

        if product_ids:
            await s.execute(
                delete(ProductVariant).where(ProductVariant.product_id.in_(product_ids))
            )
            await s.execute(
                delete(ProductImage).where(ProductImage.product_id.in_(product_ids))
            )
        await s.execute(delete(Product).where(Product.supplier_id.in_(supplier_ids)))
        await s.execute(delete(Category).where(Category.supplier_id.in_(supplier_ids)))
        await s.execute(delete(SyncJob).where(SyncJob.supplier_id.in_(supplier_ids)))
        await s.execute(delete(Supplier).where(Supplier.id.in_(supplier_ids)))
        await s.commit()


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_around_test():
    await _cleanup_test_suppliers()
    yield
    await _cleanup_test_suppliers()


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """Short-lived session for test-side assertions. Never shared with app."""
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """ASGI client. App opens its own sessions via get_db — no override."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def seed_supplier():
    from modules.suppliers.models import Supplier

    async with async_session() as s:
        supplier = Supplier(
            name="VG OPS Test",
            slug="vg-ops-test",
            protocol="ops_graphql",
            base_url="https://vg.onprintshop.test",
            auth_config={"n8n_credential_id": "test", "store_url": "https://vg.onprintshop.test"},
            is_active=True,
        )
        s.add(supplier)
        await s.commit()
        await s.refresh(supplier)
        # Expunge so the returned object stays usable after the session closes.
        s.expunge(supplier)
    return supplier


@pytest_asyncio.fixture
async def inactive_supplier():
    from modules.suppliers.models import Supplier

    async with async_session() as s:
        supplier = Supplier(
            name="VG OPS Inactive",
            slug="vg-ops-inactive",
            protocol="ops_graphql",
            auth_config={},
            is_active=False,
        )
        s.add(supplier)
        await s.commit()
        await s.refresh(supplier)
        s.expunge(supplier)
    return supplier
