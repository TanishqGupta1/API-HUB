import asyncio
import uuid
from sqlalchemy import select, delete
from database import async_session
from modules.catalog.models import Product, ProductOption, ProductOptionAttribute

SEED_DATA = [
    {
        "option_key": "substrate_class", "title": "Substrate Class", "sort_order": 1, "enabled": True,
        "attributes": [
            {"title": "Roll", "price": 0, "sort_order": 1, "enabled": True},
            {"title": "Sheet", "price": 0, "sort_order": 2, "enabled": False},
        ],
    },
    {
        "option_key": "print_sides", "title": "Print Sides", "sort_order": 2, "enabled": True,
        "attributes": [
            {"title": "Single", "price": 0, "sort_order": 1, "enabled": True},
            {"title": "Double", "price": 0, "sort_order": 2, "enabled": False},
            {"title": "Double - Same Art (x)", "price": 0, "sort_order": 3, "enabled": False},
            {"title": "Double - Different Art (x)", "price": 0, "sort_order": 4, "enabled": False},
        ],
    },
    {
        "option_key": "ink_type", "title": "Ink Type", "sort_order": 3, "enabled": True,
        "attributes": [
            {"title": "CMYK", "price": 0, "sort_order": 1, "enabled": True},
            {"title": "CMYK + White", "price": 0, "sort_order": 2, "enabled": False},
            {"title": "White Only", "price": 0, "sort_order": 3, "enabled": False},
            {"title": "No Print", "price": 0, "sort_order": 4, "enabled": False},
        ],
    },
    {
        "option_key": "ink_finish", "title": "Ink Finish", "sort_order": 4, "enabled": True,
        "attributes": [
            {"title": "Gloss", "price": 0, "sort_order": 1, "enabled": True},
            {"title": "Matte", "price": 0, "sort_order": 2, "enabled": True},
            {"title": "FLX+", "price": 10, "sort_order": 3, "enabled": True},
        ],
    },
    {
        "option_key": "white_ink", "title": "White Ink", "sort_order": 5, "enabled": True,
        "attributes": [
            {"title": "None", "price": 0, "sort_order": 1, "enabled": True},
            {"title": "Full Flood", "price": 10, "sort_order": 2, "enabled": False},
            {"title": "Undercolor", "price": 10, "sort_order": 3, "enabled": False},
            {"title": "Spot White", "price": 10, "sort_order": 4, "enabled": False},
            {"title": "Day Night", "price": 10, "sort_order": 5, "enabled": False},
            {"title": "Dual View", "price": 10, "sort_order": 6, "enabled": False},
        ],
    },
    {
        "option_key": "printer", "title": "Printer", "sort_order": 6, "enabled": True,
        "attributes": [
            {"title": "Canon Colorado M-Series", "price": 0, "sort_order": 1, "enabled": True},
            {"title": "FluidColor Z126H (x)", "price": 0, "sort_order": 2, "enabled": False},
            {"title": "Vanguard VK300D-HS", "price": 0, "sort_order": 3, "enabled": False},
            {"title": "Canon Colorado 1650", "price": 0, "sort_order": 4, "enabled": False},
            {"title": "Inkesh 5-Head DTF", "price": 0, "sort_order": 5, "enabled": False},
        ],
    },
    {
        "option_key": "print_mode", "title": "Print Mode", "sort_order": 7, "enabled": True,
        "attributes": [
            {"title": "Gloss - High Quality", "price": 0, "sort_order": 2, "enabled": True},
            {"title": "Matte - High Quality", "price": 0, "sort_order": 7, "enabled": True},
            {"title": "FLX+", "price": 4, "sort_order": 5, "enabled": True},
            {"title": "Gloss - High Key", "price": 0, "sort_order": 0, "enabled": False},
            {"title": "Gloss - Production", "price": 0, "sort_order": 1, "enabled": False},
            {"title": "Gloss - Premium", "price": 0, "sort_order": 3, "enabled": False},
            {"title": "Gloss - Specialty", "price": 0, "sort_order": 4, "enabled": False},
            {"title": "Matte - Speed", "price": 0, "sort_order": 5, "enabled": False},
            {"title": "Matte - Production", "price": 0, "sort_order": 6, "enabled": False},
            {"title": "Matte - Premium", "price": 0, "sort_order": 8, "enabled": False},
        ],
    },
    {
        "option_key": "print_mode_x", "title": "Print Mode (x)", "sort_order": 8, "enabled": True,
        "attributes": [
            {"title": "4-Pass", "price": 0, "sort_order": 2, "enabled": True},
            {"title": "3-Pass", "price": 0, "sort_order": 1, "enabled": False},
            {"title": "6-Pass", "price": 0, "sort_order": 3, "enabled": False},
            {"title": "9-Pass", "price": 0, "sort_order": 4, "enabled": False},
            {"title": "12-Pass", "price": 0, "sort_order": 5, "enabled": False},
        ],
    },
    {
        "option_key": "material", "title": "Material", "sort_order": 9, "enabled": True,
        "attributes": [
            {"title": "Arlon - 510 MT", "price": 0, "sort_order": 0, "enabled": True},
            {"title": "Customer Supplied", "price": 25, "sort_order": -1, "enabled": False},
            {"title": "GF - 230 Automark", "price": 0, "sort_order": 2, "enabled": False},
            {"title": "Oracal - 3651 Clear", "price": 0, "sort_order": 3, "enabled": False},
            {"title": "Avery - MPI 1105EZRS", "price": 0, "sort_order": 4, "enabled": False},
            {"title": "Avery - MPI 1405EZRS", "price": 0, "sort_order": 4, "enabled": False},
            {"title": "GF - 201HTAP", "price": 0, "sort_order": 5, "enabled": False},
            {"title": "GF - 201HTAPAE", "price": 0, "sort_order": 6, "enabled": False},
            {"title": "Avery - MPI 1106HTEZ", "price": 0, "sort_order": 7, "enabled": False},
        ],
    },
    {
        "option_key": "laminate", "title": "Laminate", "sort_order": 10, "enabled": True,
        "attributes": [
            {"title": "None", "price": 0, "sort_order": 1, "enabled": True},
            {"title": "Gloss, 3M - 8348", "price": 0, "sort_order": 2, "enabled": False},
        ],
    },
    {
        "option_key": "laminator", "title": "Laminator", "sort_order": 11, "enabled": True,
        "attributes": [
            {"title": "None", "price": 0, "sort_order": 1, "enabled": True},
            {"title": "GFP 663TH, No-Heat", "price": 0, "sort_order": 1, "enabled": False},
        ],
    },
    {
        "option_key": "cutting", "title": "Cutting", "sort_order": 12, "enabled": True,
        "attributes": [
            {"title": "Yes", "price": 0, "sort_order": 1, "enabled": True},
            {"title": "No", "price": 0, "sort_order": 1, "enabled": False},
        ],
    },
]

async def seed_options():
    async with async_session() as db:
        try:
            # Find the Performance Tech Hoodie
            result = await db.execute(select(Product).where(Product.product_name.ilike("%Performance Tech Hoodie%")))
            product = result.scalar_one_or_none()
            
            if not product:
                print("Performance Tech Hoodie not found")
                return

            print(f"Found product: {product.product_name} ({product.id})")

            # Clear existing options if any
            await db.execute(delete(ProductOption).where(ProductOption.product_id == product.id))

            for opt_data in SEED_DATA:
                opt = ProductOption(
                    id=uuid.uuid4(),
                    product_id=product.id,
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
            print(f"Successfully seeded {len(SEED_DATA)} industrial option groups for Performance Tech Hoodie")

        except Exception as e:
            print(f"Error seeding: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(seed_options())
