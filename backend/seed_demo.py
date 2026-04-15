import asyncio

from database import async_session
from modules.catalog.models import Product, ProductVariant
from modules.suppliers.models import Supplier


async def seed():
    async with async_session() as db:
        # Demo supplier
        demo = Supplier(
            name="Demo Supplier (Mock)",
            slug="demo-supplier",
            protocol="promostandards",
            promostandards_code="DEMO",
            auth_config={"id": "demo", "password": "demo"},
            is_active=True,
        )
        db.add(demo)
        await db.flush()

        # Demo product with variants
        product = Product(
            supplier_id=demo.id,
            supplier_sku="DEMO-TEE-001",
            product_name="Demo Essential Tee",
            brand="Demo Brand",
            description="A high-quality demo product for testing the integration hub.",
            product_type="apparel",
            image_url="https://via.placeholder.com/400x400.png?text=Demo+Tee",
        )
        db.add(product)
        await db.flush()

        for color in ["Navy", "Black", "White"]:
            for size in ["S", "M", "L", "XL"]:
                variant = ProductVariant(
                    product_id=product.id,
                    color=color,
                    size=size,
                    sku=f"DEMO-TEE-{color[:3].upper()}-{size}",
                    base_price=9.99,
                    inventory=100,
                    warehouse="Demo Warehouse",
                )
                db.add(variant)

        await db.commit()
        print("Seeded: 1 supplier, 1 product, 12 variants")


if __name__ == "__main__":
    asyncio.run(seed())
