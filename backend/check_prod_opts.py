import asyncio, sys
sys.path.insert(0, '/app')

QUERY = """
query GetOpts($pid: Int) {
  product_additional_options(products_id: $pid, limit: 50, offset: 0) {
    productAdditionalOptions {
      prod_add_opt_id
      title
      options_type
      master_option_id
    }
    totalProductAdditionalOptions
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
        res = await ops.execute(QUERY, variables={"pid": 612})
        if not res.ok:
            print("Error:", res.ops_error_message)
            return
        opts = (res.data or {}).get('product_additional_options', {}).get('productAdditionalOptions', [])
        print(f"Product 612 has {len(opts)} additional options:")
        for o in opts:
            print(f"  prod_add_opt_id={o['prod_add_opt_id']} master_option_id={o.get('master_option_id')} title={o['title']!r} type={o['options_type']}")

asyncio.run(main())
