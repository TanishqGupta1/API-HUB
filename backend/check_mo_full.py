import asyncio, sys
sys.path.insert(0, '/app')

QUERY = """
query GetMOFull($mo_id: Int) {
  productMasterOptions(master_option_id: $mo_id, limit: 5, offset: 0) {
    productMasterOptions {
      master_option_id title hire_designer_option options_type
      display_in_calculator hide_from_calc required sort_order
      allow_price_cal enable_assoc_qty
      presentation_settings { option_position desc_position display_above_size prod_add_opt_group_id }
    }
  }
}
"""

async def main():
    from database import async_session
    from sqlalchemy import select
    from modules.customers.models import Customer
    from modules.ops_client.client import OpsAuth, OpsGraphQLClient
    async with async_session() as db:
        c = (await db.execute(
            select(Customer).where(Customer.id == 'a2b91bac-10a0-4c0a-b284-cbac991250bf')
        )).scalars().first()
    auth = OpsAuth(base_url=c.ops_base_url, token_url=c.ops_token_url,
                   client_id=c.ops_client_id, client_secret=(c.ops_auth_config or {}).get('client_secret'))
    async with OpsGraphQLClient(auth) as ops:
        res = await ops.execute(QUERY, variables={"mo_id": 50})
        import json
        mos = (res.data or {}).get('productMasterOptions', {}).get('productMasterOptions', [])
        for mo in mos:
            print(json.dumps(mo, indent=2))

asyncio.run(main())
