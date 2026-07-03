import asyncio, sys, json
sys.path.insert(0, '/app')

K420_PRODUCT_ID = '22f47b56-60ce-420e-8d08-350c823a38e6'


async def main():
    from database import async_session
    from sqlalchemy import select, text
    from modules.catalog.models import ProductOption, ProductOptionAttribute
    from modules.master_options.models import MasterOption
    import uuid

    product_id = uuid.UUID(K420_PRODUCT_ID)

    async with async_session() as db:
        # K420's current ProductOption rows
        pos = (await db.execute(
            select(ProductOption)
            .where(ProductOption.product_id == product_id)
        )).scalars().all()

        # All available MasterOptions
        mos = (await db.execute(
            select(MasterOption).order_by(MasterOption.sort_order, MasterOption.title)
        )).scalars().all()

    print(f'\n=== K420 ProductOption rows ({len(pos)}) ===')
    for po in pos:
        print(f'  id={po.id}  option_key={po.option_key!r}  master_option_id={po.master_option_id}  enabled={po.enabled}  sort={po.sort_order}')

    print(f'\n=== Available MasterOptions ({len(mos)}) ===')
    for mo in mos:
        print(f'  id={mo.id}  ops_master_option_id={mo.ops_master_option_id}  title={mo.title!r}  option_key={mo.option_key!r}  enabled_count_from_product_options=?')

    print('\nDone.')


asyncio.run(main())
