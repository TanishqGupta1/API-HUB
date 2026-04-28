"""Shared pytest fixtures for the backend test suite.

Strategy: each fixture/session is short-lived. Test data is inserted with
a fresh session, committed, and then cleaned up by the autouse cleanup
fixture after each test. This avoids asyncpg "another operation in progress"
errors that occur when the same session is shared between the test and the
FastAPI app's request handler.

Database selection: by default we load the dev .env so engineers can run the
suite locally against the same Postgres they're already running. Set
TEST_DATABASE_URL to point pytest at a separate database (recommended for CI).
"""
import os
from pathlib import Path

import pytest_asyncio
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# If TEST_DATABASE_URL is set, override POSTGRES_URL before `database` is imported
# so the engine is built against the test DB.
_test_db_url = os.environ.get("TEST_DATABASE_URL")
if _test_db_url:
    os.environ["POSTGRES_URL"] = _test_db_url

os.environ["INGEST_SHARED_SECRET"] = "test-secret-do-not-use-in-prod"

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from database import Base, async_session, engine  # noqa: E402
from main import app  # noqa: E402

TEST_SUPPLIER_SLUGS = ("vg-ops-test", "vg-ops-inactive")
TEST_CUSTOMER_OPS_URLS = (
    "https://test.ops.com",
    "https://test2.ops.com",
    "https://test3.ops.com",
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


async def _cleanup_test_customers() -> None:
    """Delete sentinel Customer rows + everything that cascades from them.

    `customers.id` has ON DELETE CASCADE FKs from push_mappings, markup_rules,
    and push_log, so a single DELETE on customers cleans the whole tree.
    """
    from modules.customers.models import Customer

    async with async_session() as s:
        await s.execute(
            delete(Customer).where(
                Customer.ops_base_url.in_(TEST_CUSTOMER_OPS_URLS)
            )
        )
        await s.commit()


async def _cleanup_test_suppliers() -> None:
    """Delete any lingering supplier rows + their owned products / variants /
    images / categories / sync_jobs."""
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
    await _cleanup_test_customers()
    await _cleanup_test_suppliers()
    yield
    await _cleanup_test_customers()
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
