import asyncio
import traceback
from modules.suppliers.routes import list_suppliers
from database import engine
from sqlalchemy.ext.asyncio import AsyncSession

async def run():
    async with AsyncSession(engine) as db:
        try:
            res = await list_suppliers(db)
            print(res)
        except Exception as e:
            traceback.print_exc()

asyncio.run(run())
