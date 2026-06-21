import asyncio, sys, json
sys.path.insert(0, '/app')

async def main():
    from database import async_session
    import uuid
    product_id = uuid.UUID('22f47b56-60ce-420e-8d08-350c823a38e6')
    customer_id = uuid.UUID('a2b91bac-10a0-4c0a-b284-cbac991250bf')

    async with async_session() as db:
        from modules.ops_push.payload_builder import build_push_payload
        payload = await build_push_payload(db, customer_id, product_id)
        for step in payload.plan:
            if step.mutation == 'setAssignOptions':
                print(f'step {step.step} setAssignOptions:')
                print(f'  source_key: {step.source_key}')
                print(f'  variables: {json.dumps(step.variables)}')

asyncio.run(main())
