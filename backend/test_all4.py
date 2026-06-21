import asyncio, json, sys
sys.path.insert(0, '/app')

MASTER_OPTIONS = [
    (50, 'Print Sides', [132, 1017]),
    (52, 'Production Time', [137, 138, 139, 205]),
    (112, 'Ink Finish', [184, 185, 186]),
    (146, 'Ink Type', [287, 288, 289, 1414]),
]

async def main():
    from database import async_session
    from sqlalchemy import select
    from modules.customers.models import Customer
    from modules.ops_client.client import OpsAuth, OpsGraphQLClient

    async with async_session() as db:
        c = (await db.execute(select(Customer).where(Customer.id == 'a2b91bac-10a0-4c0a-b284-cbac991250bf'))).scalars().first()
        auth = OpsAuth(base_url=c.ops_base_url, token_url=c.ops_token_url,
                       client_id=c.ops_client_id, client_secret=(c.ops_auth_config or {}).get('client_secret'))

    SET_ADD = "mutation SetAdditionalOption($inputs: [AdditionalOptionInput!]!) { setAdditionalOption(inputs: $inputs) { result message id } }"
    SET_ASSIGN = "mutation SetAssignOptions($inputs: [AssignOptionsInput!]!) { setAssignOptions(inputs: $inputs) { result message id } }"

    # First retire prod_add_opt_id=9292 (Print Sides already created above)
    async with OpsGraphQLClient(auth) as ops:
        for i, (mo_id, title, attr_ids) in enumerate(MASTER_OPTIONS):
            print(f'\n--- {title} (master_option_id={mo_id}) ---')
            r1 = await ops.execute(SET_ADD, variables={'inputs': [{
                'prod_add_opt_id': 0,
                'products_id': 612,
                'master_option_id': mo_id,
                'title': title,
                'options_type': 'drop_down',
                'hire_designer_option': '0',
                'price_calculate_type': '0',
                'sort_order': i,
                'status': '1',
                'display_in_calculator': '1',
            }]})
            resp1 = ((r1.data or {}).get('setAdditionalOption') or [{}])
            if isinstance(resp1, list): resp1 = resp1[0]
            print(f'  setAdditionalOption: result={resp1.get("result")} id={resp1.get("id")} msg={resp1.get("message")}')
            prod_add_opt_id = resp1.get('id')
            if not prod_add_opt_id:
                continue

            r2 = await ops.execute(SET_ASSIGN, variables={'inputs': [{
                'product_option_id': prod_add_opt_id,
                'products_id': 612,
                'master_option_id': mo_id,
                'sort_order': i,
                'attribute_ids': [{'attrid': a} for a in attr_ids],
            }]})
            resp2 = ((r2.data or {}).get('setAssignOptions') or [{}])
            if isinstance(resp2, list): resp2 = resp2[0]
            print(f'  setAssignOptions:    result={resp2.get("result")} id={resp2.get("id")} msg={resp2.get("message")}')

asyncio.run(main())
