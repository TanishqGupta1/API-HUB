"""Show current ProductOption+ProductOptionAttribute rows for K420."""
import asyncio, sys, json
sys.path.insert(0, '/app')

K420_PRODUCT_ID = '22f47b56-60ce-420e-8d08-350c823a38e6'

async def main():
    from database import async_session
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from modules.catalog.models import ProductOption, ProductOptionAttribute
    import uuid

    async with async_session() as db:
        pos = (await db.execute(
            select(ProductOption)
            .where(ProductOption.product_id == uuid.UUID(K420_PRODUCT_ID))
            .options(selectinload(ProductOption.attributes))
            .order_by(ProductOption.sort_order)
        )).scalars().all()

        print(f'K420 has {len(pos)} ProductOption rows:')
        for po in pos:
            print(f'  PO id={po.id} master_option_id={po.master_option_id} title={po.title!r}')
            for a in sorted(po.attributes, key=lambda x: x.sort_order or 0):
                print(f'    attr ops_attribute_id={a.ops_attribute_id} title={a.title!r} sort={a.sort_order}')

asyncio.run(main())
