"""Shared pytest fixtures for the backend test suite."""
import os
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import load_dotenv
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Tests run without an arq worker process — keep enqueue_push on the
# in-process fallback path so BackgroundTasks executes inline as before.
# Production deploys leave this unset (or =1) to use the durable Redis queue.
os.environ["OPS_PUSH_DURABLE_QUEUE"] = "0"

_test_db_url = os.environ.get("TEST_DATABASE_URL")
if _test_db_url:
    os.environ["POSTGRES_URL"] = _test_db_url

# Default to a fake URL so the conftest module can be imported in
# environments without a running Postgres. The engine itself is lazy —
# no connection until a fixture or test queries it. Hermetic tests
# (marked `@pytest.mark.no_db`) skip the autouse fixtures below.
os.environ.setdefault(
    "POSTGRES_URL",
    "postgresql+asyncpg://hermetic:hermetic@127.0.0.1:5432/hermetic_unused",
)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
engine = create_async_engine(os.environ["POSTGRES_URL"], poolclass=NullPool)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "no_db: hermetic test — autouse DB schema/cleanup fixtures skip it",
    )

os.environ["INGEST_SHARED_SECRET"] = "test-secret-do-not-use-in-prod"

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from database import Base
import database
database.engine = engine
database.async_session = async_session
from main import app  # noqa: E402

# Inject a vg_admin mock for all JWT-protected routes so the test suite
# doesn't need real credentials. Ingest-secret routes are unaffected.
import uuid as _uuid_mod
from modules.auth.dependencies import get_current_user as _get_current_user
from modules.auth.models import User as _AuthUser

_TEST_ADMIN = _AuthUser(
    id=_uuid_mod.uuid4(),
    email="test-admin@vg.test",
    hashed_password="x",
    role="vg_admin",
    is_active=True,
)
app.dependency_overrides[_get_current_user] = lambda: _TEST_ADMIN

TEST_SUPPLIER_SLUGS = ("vg-ops-test", "vg-ops-inactive")
TEST_CUSTOMER_OPS_URLS = (
    "https://test.ops.com",
    "https://test1.ops.com",   # CPS Archived/Failed/Recovered/Unique test factories
    "https://test2.ops.com",
    "https://test3.ops.com",
    "https://mock.ops",        # generic "Test Customer" factory — most common leak
    "http://ops.test",         # alternate "Test Customer" factory
)

_SCHEMA_CREATED = False

@pytest_asyncio.fixture(autouse=True)
async def _create_schema(request):
    """Ensure schema exists. Only runs DDL once per process.

    Skipped for tests marked `no_db` so hermetic suites don't require Postgres.
    """
    if request.node.get_closest_marker("no_db"):
        yield
        return
    global _SCHEMA_CREATED
    if not _SCHEMA_CREATED:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _SCHEMA_CREATED = True
    yield


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
    from modules.catalog.models import (
        Category,
        Product,
        ProductImage,
        ProductVariant,
        CustomerProductSelection
    )
    from modules.suppliers.models import Supplier
    from modules.sync_jobs.models import SyncJob

    async with async_session() as s:
        # Sweep every prefix used by test factories so rows don't leak
        # into the dev DB across pytest runs (which was clogging the
        # /suppliers admin page with 30+ phantom rows).
        #
        # Sources of each prefix:
        #   cps-test-%     test_customer_catalog
        #   t7-% .. t10-%  test_phase1_task{7..10}.py
        #   test-%         test_persist_product.py
        #   test-slug-%    test_ops_push_failure.py
        #   auth-leak-test test_supplier_auth_no_leak.py (explicit)
        supplier_ids = (
            await s.execute(
                select(Supplier.id).where(
                    Supplier.slug.in_(TEST_SUPPLIER_SLUGS + ("auth-leak-test",))
                    | Supplier.slug.like("cps-test-%")
                    | Supplier.slug.like("t7-%")
                    | Supplier.slug.like("t8-%")
                    | Supplier.slug.like("t9-%")
                    | Supplier.slug.like("t10-%")
                    | Supplier.slug.like("test-%")
                )
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
                delete(CustomerProductSelection).where(CustomerProductSelection.product_id.in_(product_ids))
            )
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
async def _cleanup_around_test(request):
    """Automatically cleans up test data before and after every test.

    Skipped for tests marked `no_db`.
    """
    if request.node.get_closest_marker("no_db"):
        yield
        return
    await _cleanup_test_customers()
    await _cleanup_test_suppliers()
    yield
    await _cleanup_test_customers()
    await _cleanup_test_suppliers()
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
