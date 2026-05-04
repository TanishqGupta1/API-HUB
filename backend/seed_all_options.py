import asyncio
import uuid
from sqlalchemy import select
from database import async_session
from modules.catalog.models import Product, ProductOption, ProductOptionAttribute
from seed_demo_options import SEED_DATA

async def seed_all_products():
    async with async_session() as db:
        try:
            # Get all products that don't have options
            result = await db.execute(select(Product))
            products = result.scalars().all()
            
            print(f"Found {len(products)} products in catalog")

            for p in products:
                # Check if product already has options
                opts_check = await db.execute(select(ProductOption).where(ProductOption.product_id == p.id).limit(1))
                if opts_check.scalar():
                    continue
                
                print(f"Seeding options for: {p.product_name} ({p.id})")
                
                for opt_data in SEED_DATA:
                    opt = ProductOption(
                        id=uuid.uuid4(),
                        product_id=p.id,
                        option_key=opt_data["option_key"],
                        title=opt_data["title"],
                        options_type="select",
                        sort_order=opt_data["sort_order"],
                        required=True,
                        status=1,
                        enabled=opt_data["enabled"]
                    )
                    db.add(opt)
                    await db.flush()

                    for attr_data in opt_data["attributes"]:
                        attr = ProductOptionAttribute(
                            product_option_id=opt.id,
                            title=attr_data["title"],
                            price=attr_data["price"],
                            sort_order=attr_data["sort_order"],
                            status=1,
                            enabled=attr_data["enabled"]
                        )
                        db.add(attr)
            
            await db.commit()
            print("Successfully seeded options for all products")

        except Exception as e:
            print(f"Error seeding: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(seed_all_products())
