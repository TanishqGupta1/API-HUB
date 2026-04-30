"""Shared pytest fixtures for the backend test suite."""
import os
from pathlib import Path

import pytest_asyncio
from dotenv import load_dotenv
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv(Path(__file__).parent.parent.parent / ".env")

_test_db_url = os.environ.get("TEST_DATABASE_URL")
if _test_db_url:
    os.environ["POSTGRES_URL"] = _test_db_url

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
# Override engine globally for tests to avoid connection sharing issues on Windows
engine = create_async_engine(os.environ["POSTGRES_URL"], poolclass=NullPool)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

os.environ["INGEST_SHARED_SECRET"] = "test-secret-do-not-use-in-prod"

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from database import Base
import database
database.engine = engine
database.async_session = async_session
from main import app  # noqa: E402

TEST_SUPPLIER_SLUGS = ("vg-ops-test", "vg-ops-inactive")
TEST_CUSTOMER_OPS_URLS = (
    "https://test.ops.com",
    "https://test2.ops.com",
    "https://test3.ops.com",
)

_SCHEMA_CREATED = False

@pytest_asyncio.fixture(autouse=True)
async def _create_schema():
    """Ensure schema exists. Only runs DDL once per process."""
    global _SCHEMA_CREATED
    if not _SCHEMA_CREATED:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _SCHEMA_CREATED = True
    yield
    # No engine.dispose() here to avoid closing resources needed by other tests
    # in the same process/loop.


async def _cleanup_test_customers() -> None:
    from modules.customers.models import Customer
    async with async_session() as s:
        await s.execute(
            delete(Customer).where(
                Customer.ops_base_url.in_(TEST_CUSTOMER_OPS_URLS)
            )
        )
        await s.commit()


async def _cleanup_test_suppliers() -> None:
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
    """Automatically cleans up test data before and after every test."""
    await _cleanup_test_customers()
    await _cleanup_test_suppliers()
    yield
    await _cleanup_test_customers()
    await _cleanup_test_suppliers()
    # Force pool disposal to avoid connection leaks between tests
    await engine.dispose()


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    async with async_session() as session:
        yield session
        await session.close()


@pytest_asyncio.fixture
async def client() -> AsyncClient:
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
