import asyncio
from uuid import UUID
from database import async_session
from modules.suppliers.category_import import _run_category_import
from modules.sync_jobs.models import SyncJob
from modules.suppliers.models import Supplier
from sqlalchemy import select
from datetime import datetime, timezone

async def run():
    async with async_session() as session:
        # Find a SanMar supplier
        sup = (await session.execute(select(Supplier).where(Supplier.name.ilike('%sanmar%')))).scalar_one_or_none()
        if not sup:
            print("No SanMar supplier found.")
            return

        # Create a dummy job
        job = SyncJob(
            supplier_id=sup.id,
            supplier_name=sup.name,
            job_type="category:Caps",
            status="queued",
            started_at=datetime.now(timezone.utc),
            records_processed=0,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

        from modules.promostandards.client import SANMAR_EXT_WSDL
        print(f"Running job {job.id} for Caps")
        try:
            await _run_category_import(
                job.id,
                sup.id,
                sup.auth_config,
                "https://ws.sanmar.com:8080/promostandards/ProductDataServiceBinding?wsdl",
                "Caps",
                10,
                SANMAR_EXT_WSDL
            )
            print("Success")
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
