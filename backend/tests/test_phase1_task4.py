"""TDD tests for Task 4: SyncJob model update."""
import pytest
from modules.sync_jobs.models import SyncJob


@pytest.mark.asyncio
async def test_task4_sync_job_columns(db):
    """Verify that SyncJob has the new errors JSONB column."""
    cols = {c.name for c in SyncJob.__table__.columns}
    assert "errors" in cols
