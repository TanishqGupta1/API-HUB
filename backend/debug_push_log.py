import asyncio, sys, json
sys.path.insert(0, '/app')

async def main():
    from database import async_session
    from sqlalchemy import select
    from modules.push_log.models import ProductPushLog
    import uuid
    async with async_session() as db:
        logs = (await db.execute(
            select(ProductPushLog)
            .where(ProductPushLog.product_id == uuid.UUID('22f47b56-60ce-420e-8d08-350c823a38e6'))
            .order_by(ProductPushLog.pushed_at.desc())
            .limit(2)
        )).scalars().all()
        for log in logs:
            print(f'Log {log.id}: status={log.status} ops_product_id={log.ops_product_id}')
            steps = log.step_results or []
            for s in steps:
                mut = s.get('mutation', '?')
                st = s.get('status', '?')
                num = s.get('step', '?')
                if mut == 'setAssignOptions':
                    print(f'  step {num} {mut}: status={st}')
                    vars_json = json.dumps(s.get('variables', {}))
                    resp_json = json.dumps(s.get('response', {}))
                    print(f'    variables: {vars_json[:600]}')
                    print(f'    response: {resp_json[:300]}')
                else:
                    print(f'  step {num} {mut}: status={st}')

asyncio.run(main())
