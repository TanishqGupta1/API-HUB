import asyncio, json, sys
sys.path.insert(0, '/app')

async def main():
    from database import async_session
    from sqlalchemy import select
    from modules.customers.models import Customer
    from modules.ops_client.client import OpsAuth, OpsGraphQLClient

    async with async_session() as db:
        c = (await db.execute(select(Customer).where(Customer.id == 'a2b91bac-10a0-4c0a-b284-cbac991250bf'))).scalars().first()
        auth = OpsAuth(base_url=c.ops_base_url, token_url=c.ops_token_url,
                       client_id=c.ops_client_id, client_secret=(c.ops_auth_config or {}).get('client_secret'))

    SET_ADD = """
    mutation SetAdditionalOption($inputs: [AdditionalOptionInput!]!) {
      setAdditionalOption(inputs: $inputs) { result message id }
    }"""

    SET_ASSIGN = """
    mutation SetAssignOptions($inputs: [AssignOptionsInput!]!) {
      setAssignOptions(inputs: $inputs) { result message id }
    }"""

    async with OpsGraphQLClient(auth) as ops:
        # Step 1 - create option row with hire_designer_option set
        r1 = await ops.execute(SET_ADD, variables={'inputs': [{
            'prod_add_opt_id': 0,
            'products_id': 612,
            'master_option_id': 50,
            'title': 'Print Sides',
            'options_type': 'drop_down',
            'hire_designer_option': '0',
            'price_calculate_type': '0',
            'sort_order': 0,
            'status': '1',
            'display_in_calculator': '1',
        }]})
        resp1 = ((r1.data or {}).get('setAdditionalOption') or [{}])
        if isinstance(resp1, list): resp1 = resp1[0]
        print('Step1 setAdditionalOption:', resp1)
        prod_add_opt_id = resp1.get('id')
        if not prod_add_opt_id:
            print('FAILED at step 1')
            return

        print(f'Got prod_add_opt_id={prod_add_opt_id}')

        # Step 2 - UPDATE with setAssignOptions using product_option_id
        r2 = await ops.execute(SET_ASSIGN, variables={'inputs': [{
            'product_option_id': prod_add_opt_id,
            'products_id': 612,
            'master_option_id': 50,
            'sort_order': 0,
            'attribute_ids': [{'attrid': 132}, {'attrid': 1017}],
        }]})
        resp2 = ((r2.data or {}).get('setAssignOptions') or [{}])
        if isinstance(resp2, list): resp2 = resp2[0]
        print('Step2 setAssignOptions:', resp2)

asyncio.run(main())
