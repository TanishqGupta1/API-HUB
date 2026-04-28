"""Regression test: tests must not leak customer rows into the DB."""
import pytest
from sqlalchemy import func, select

from database import async_session
from modules.customers.models import Customer


TEST_OPS_BASE_URLS = (
    "https://test.ops.com",
    "https://test2.ops.com",
    "https://test3.ops.com",
)


@pytest.mark.asyncio
async def test_test_customers_do_not_survive_cleanup():
    """If a previous test created a Test Customer, it must have been purged.

    This test runs after the autouse `_cleanup_around_test` fixture, so any
    sentinel rows visible here mean the cleanup is incomplete.
    """
    async with async_session() as s:
        count = (
            await s.execute(
                select(func.count())
                .select_from(Customer)
                .where(Customer.ops_base_url.in_(TEST_OPS_BASE_URLS))
            )
        ).scalar_one()
    assert count == 0, (
        f"Cleanup leak: {count} sentinel Test Customer rows still in DB. "
        "Update conftest._cleanup_test_customers."
    )
