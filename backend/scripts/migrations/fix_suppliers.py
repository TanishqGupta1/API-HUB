import asyncio
from database import async_session
from modules.suppliers.models import Supplier
from sqlalchemy import select

async def fix():
    async with async_session() as s:
        res = await s.execute(select(Supplier))
        for sup in res.scalars():
            if 'SanMar' in sup.name:
                sup.adapter_class = 'SanMarAdapter'
            elif 'OPS' in sup.name:
                sup.adapter_class = 'OPSAdapter'
            elif '4Over' in sup.name:
                sup.adapter_class = 'FourOverAdapter'
            elif not sup.adapter_class:
                sup.adapter_class = 'PromoStandardsAdapter'
            
            print(f"Updated {sup.name} to {sup.adapter_class}")
        await s.commit()

if __name__ == "__main__":
    asyncio.run(fix())
