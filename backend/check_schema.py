import asyncio, sys, json
sys.path.insert(0, '/app')

INTROSPECT = """
query IntrospectAssignOptionsInput {
  __type(name: "AssignOptionsInput") {
    name
    inputFields {
      name
      type { name kind ofType { name kind } }
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
        res = await ops.execute(INTROSPECT, variables={})
        t = (res.data or {}).get('__type', {})
        fields = t.get('inputFields', [])
        print(f"AssignOptionsInput has {len(fields)} fields:")
        for f in fields:
            print(f"  {f['name']}")

asyncio.run(main())
