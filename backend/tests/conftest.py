"""Shared pytest fixtures for the backend test suite.

Each test function runs inside a transaction that rolls back on teardown,
so test data never persists. Fixtures are async because the app is async.

NOTE: Tests run against the same Postgres the app uses. Schema is additive
(create_all is idempotent) and data is rolled back per test. If a separate
test DB is needed later, override POSTGRES_URL before importing `database`.
"""
import os
from pathlib import Path

import pytest_asyncio
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

os.environ.setdefault("INGEST_SHARED_SECRET", "test-secret-do-not-use-in-prod")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from database import Base, async_session, engine, get_db  # noqa: E402
from main import app  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncClient:
    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_supplier(db: AsyncSession):
    from modules.suppliers.models import Supplier

    supplier = Supplier(
        name="VG OPS Test",
        slug="vg-ops-test",
        protocol="ops_graphql",
        base_url="https://vg.onprintshop.test",
        auth_config={"n8n_credential_id": "test", "store_url": "https://vg.onprintshop.test"},
        is_active=True,
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@pytest_asyncio.fixture
async def inactive_supplier(db: AsyncSession):
    from modules.suppliers.models import Supplier

    supplier = Supplier(
        name="VG OPS Inactive",
        slug="vg-ops-inactive",
        protocol="ops_graphql",
        auth_config={},
        is_active=False,
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier
