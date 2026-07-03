import asyncio, sys
sys.path.insert(0, '/app')

_Q = """
query GetProduct($id: Int!) {
  productsDetails(products_id: $id) {
    products {
      product_id
      product_additional_options {
        prod_add_opt_id
        option_key
        attributes
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

    secret = (c.ops_auth_config or {}).get('client_secret')
    auth = OpsAuth(
        base_url=c.ops_base_url,
        token_url=c.ops_token_url,
        client_id=c.ops_client_id,
        client_secret=secret,
    )
    async with OpsGraphQLClient(auth) as ops:
        res = await ops.execute(_Q, variables={'id': 606})

    if not res.ok:
        print('OPS error:', res.ops_error_message)
        return

    wrapper = (res.data or {}).get('productsDetails') or {}
    products = wrapper.get('products') or []
    if not products:
        print("No products returned. data=", res.data)
        return
    product = products[0]
    import json
    print("Product ID:", product.get('product_id'))
    opts = product.get('product_additional_options') or []
    print("Additional options count:", len(opts))
    for opt in opts:
        attrs = opt.get('attributes') or []
        print(f"  opt key={opt.get('option_key')} attributes={json.dumps(attrs)[:200]}")

asyncio.run(main())
