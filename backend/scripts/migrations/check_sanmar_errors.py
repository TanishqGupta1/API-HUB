import asyncio
import uuid
from sqlalchemy import select
from database import async_session
from modules.sync_jobs.models import SyncJob

async def main():
    async with async_session() as session:
        # Get the 5 most recent failed SanMar jobs
        stmt = (
            select(SyncJob)
            .where(SyncJob.supplier_name == 'SanMar', SyncJob.status == 'failed')
            .order_by(SyncJob.started_at.desc())
            .limit(5)
        )
        result = await session.execute(stmt)
        jobs = result.scalars().all()
        
        if not jobs:
            print("No failed SanMar jobs found.")
            return

        for job in jobs:
            print(f"--- Job ID: {job.id} ---")
            print(f"Started: {job.started_at}")
            print(f"Error Log: {job.error_log}")
            print(f"Errors (JSON): {job.errors}")
            print("-" * 30)

if __name__ == "__main__":
    asyncio.run(main())
