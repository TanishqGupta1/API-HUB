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

    Q = """query {
      productMasterOptions(master_option_id: 50, limit: 1, offset: 0) {
        productMasterOptions {
          master_option_id title hire_designer_option options_type
          display_in_calculator hide_from_calc sort_order
          price_calculate_type setup_cost
          presentation_settings { option_position desc_position display_above_size prod_add_opt_group_id }
        }
      }
    }"""
    async with OpsGraphQLClient(auth) as ops:
        r = await ops.execute(Q, variables={})
        if not r.ok:
            print('ERR', r.ops_error_message)
        else:
            mos = (r.data or {}).get('productMasterOptions', {}).get('productMasterOptions', [])
            print(json.dumps(mos, indent=2))

asyncio.run(main())
