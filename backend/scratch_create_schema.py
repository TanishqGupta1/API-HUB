import asyncio
from database import engine, Base
import modules.catalog.models
import modules.suppliers.models
import modules.customers.models
import modules.markup.models
import modules.push_log.models
import modules.sync_jobs.models
import modules.master_options.models
import modules.push_mappings.models
import modules.ops_config.models

async def create_schema():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("Successfully created schema")
    except Exception as e:
        print(f"Failed to create schema: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(create_schema())
