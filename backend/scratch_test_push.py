import asyncio
import uuid
from database import async_session
from sqlalchemy import select
from modules.catalog.models import Product
from modules.suppliers.models import Supplier
from modules.customers.models import Customer
from modules.ops_push.service import push_product

async def test_push():
    async with async_session() as db:
        # 1. Get SanMar supplier
        supplier_res = await db.execute(select(Supplier).where(Supplier.name == "SanMar"))
        supplier = supplier_res.scalar_one_or_none()
        if not supplier:
            print("SanMar supplier not found")
            return

        # 2. Get a SanMar product
        product_res = await db.execute(select(Product).where(Product.supplier_id == supplier.id).limit(1))
        product = product_res.scalar_one_or_none()
        if not product:
            print("No SanMar products found")
            return
        
        print(f"Testing push for product: {product.product_name} (ID: {product.id})")

        # 3. Get a storefront (e.g., pricing_update)
        customer_res = await db.execute(select(Customer).where(Customer.name == "pricing_update"))
        customer = customer_res.scalar_one_or_none()
        if not customer:
            # Fallback to any customer
            customer_res = await db.execute(select(Customer).limit(1))
            customer = customer_res.scalar_one_or_none()
        
        if not customer:
            print("No storefronts found")
            return
        
        print(f"Target Storefront: {customer.name} (ID: {customer.id})")

        # 4. Perform push
        try:
            result = await push_product(db, customer.id, product.id)
            print(f"Push Result: {result}")
        except Exception as e:
            print(f"Push Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_push())
