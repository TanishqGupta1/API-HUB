import asyncio, sys, json
sys.path.insert(0, '/app')


async def main():
    from database import async_session
    from sqlalchemy import select
    from modules.push_log.models import ProductPushLog
    import uuid

    product_id = uuid.UUID('22f47b56-60ce-420e-8d08-350c823a38e6')

    async with async_session() as db:
        logs = (await db.execute(
            select(ProductPushLog)
            .where(ProductPushLog.product_id == product_id)
            .order_by(ProductPushLog.pushed_at.asc())
        )).scalars().all()

    for log in logs:
        steps = log.step_results or []
        if isinstance(steps, str):
            steps = json.loads(steps)
        ok_steps = [s for s in steps if s.get('status') == 'ok']
        print(f'log={log.id} status={log.status} ok_count={len(ok_steps)}')

        for target_step in [2, 26, 36]:
            s = next((x for x in steps if x.get('step') == target_step), None)
            if s:
                print(f'  step{target_step} mutation={s.get("mutation")} status={s.get("status")} ops_ids={json.dumps(s.get("ops_ids", {}))} error={s.get("error")}')


asyncio.run(main())
