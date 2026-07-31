import asyncio, sys, json
sys.path.insert(0, '/app')

Q = """
query GetProduct($id: Int!) {
  productsDetails(products_id: $id) {
    products {
      product_id
      product_size {
        size_id
        size_title
        size_unit
      }
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

    auth = OpsAuth(
        base_url=c.ops_base_url,
        token_url=c.ops_token_url,
        client_id=c.ops_client_id,
        client_secret=(c.ops_auth_config or {}).get('client_secret'),
    )
    async with OpsGraphQLClient(auth) as ops:
        res = await ops.execute(Q, variables={'id': 606})

    if not res.ok:
        print('OPS error:', res.ops_error_message)
        return

    products = (res.data or {}).get('productsDetails', {}).get('products', [])
    if not products:
        print('No products. data=', json.dumps(res.data)[:500])
        return

    p = products[0]
    print('product_id:', p.get('product_id'))
    sizes = p.get('product_size') or []
    print(f'product_size count: {len(sizes)}')
    for s in sizes:
        print(' ', json.dumps(s))


asyncio.run(main())
