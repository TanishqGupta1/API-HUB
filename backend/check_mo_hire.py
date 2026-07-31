import asyncio, sys
sys.path.insert(0, '/app')

QUERY = """
query GetMO($mo_id: Int) {
  productMasterOptions(master_option_id: $mo_id, limit: 5, offset: 0) {
    productMasterOptions {
      master_option_id
      title
      hire_designer_option
      options_type
    }
  }
}
""".strip()

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
        for mo_id in [50, 52, 112, 146]:
            res = await ops.execute(QUERY, variables={"mo_id": mo_id})
            for mo in (res.data or {}).get('productMasterOptions', {}).get('productMasterOptions', []):
                print(f"mo_id={mo['master_option_id']} {mo['title']!r:20} hire_designer_option={mo.get('hire_designer_option')!r}")

asyncio.run(main())
