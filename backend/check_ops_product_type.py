import asyncio, sys, json
sys.path.insert(0, '/app')

Q = """
query GetProducts($id: Int!) {
  productsDetails(products_id: $id) {
    products {
      product_id
      products_title
      product_type
      predefined_product_type
      price_defining_method
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
        for pid in [606, 361]:
            res = await ops.execute(Q, variables={'id': pid})
            if not res.ok:
                print(f'product {pid}: OPS error:', res.ops_error_message)
                continue
            products = (res.data or {}).get('productsDetails', {}).get('products', [])
            if not products:
                print(f'product {pid}: not found')
                continue
            p = products[0]
            print(f'product {pid}: product_type={p.get("product_type")!r}  predefined_product_type={p.get("predefined_product_type")!r}  price_defining_method={p.get("price_defining_method")!r}  title={p.get("products_title")!r}')


asyncio.run(main())
