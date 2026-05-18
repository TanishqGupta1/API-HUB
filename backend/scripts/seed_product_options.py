"""
Seed 12 master option groups with realistic price modifiers for the
Performance Tech Hoodie (OPS test product), then configure per-product
prices via the existing save_product_config service.

Run inside the api container:
  docker compose run --rm --no-deps \
    -e POSTGRES_URL='postgresql+asyncpg://vg_user:vg_pass@postgres:5432/vg_hub' \
    api python scripts/seed_product_options.py
"""
import asyncio
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from database import Base, async_session, engine

PRODUCT_ID_STR = "ed813af4-8e1c-429b-8044-4291ad4965c8"

# (ops_master_option_id, option_key, title, options_type, sort_order, attributes)
# attribute: (ops_attribute_id, title, sort_order, default_price)
OPTIONS = [
    (1000, "substrate_class", "Substrate Class", "select", 1, [
        (1001, "Roll",   1, Decimal("0.00")),
        (1002, "Sheet",  2, Decimal("2.50")),
    ]),
    (1001, "print_sides", "Print Sides", "select", 2, [
        (2001, "Single",                     1, Decimal("0.00")),
        (2002, "Double - Same Art (2)",      2, Decimal("5.00")),
        (2003, "Double - Different Art (2)", 3, Decimal("8.00")),
    ]),
    (1002, "ink_type", "Ink Type", "select", 3, [
        (3001, "CMYK",         1, Decimal("0.00")),
        (3002, "CMYK + White", 2, Decimal("3.00")),
        (3003, "White Only",   3, Decimal("2.50")),
        (3004, "No Print",     4, Decimal("0.00")),
    ]),
    (1003, "copy_finish", "Copy Finish", "select", 4, [
        (4001, "None",       1, Decimal("0.00")),
        (4002, "Full Head",  2, Decimal("1.50")),
        (4003, "Undercoat",  3, Decimal("2.00")),
        (4004, "Spot White", 4, Decimal("2.50")),
        (4005, "Day Night",  5, Decimal("3.00")),
        (4006, "Dual Matte", 6, Decimal("3.50")),
    ]),
    (1004, "white_ink", "White Ink", "select", 5, [
        (5001, "None",       1, Decimal("0.00")),
        (5002, "Full Flood", 2, Decimal("1.00")),
        (5003, "Full Head",  3, Decimal("2.00")),
        (5004, "Undercoat",  4, Decimal("1.50")),
        (5005, "Spot White", 5, Decimal("2.50")),
        (5006, "Day Night",  6, Decimal("2.00")),
        (5007, "Dual Matte", 7, Decimal("3.00")),
    ]),
    (1005, "printer", "Printer", "select", 6, [
        (6001, "Canon Colorado M-Series", 1, Decimal("0.00")),
        (6002, "FluidColor Z126H",        2, Decimal("5.00")),
        (6003, "Vanguard VK3200-HS",      3, Decimal("7.00")),
        (6004, "Canon Colorado 1650",     4, Decimal("4.00")),
        (6005, "Inkjet 5-Head DTF",       5, Decimal("6.00")),
    ]),
    (1006, "print_mode", "Print Mode", "select", 7, [
        (7001, "Gloss - High Quality", 1, Decimal("2.00")),
        (7002, "Matte - High Quality", 2, Decimal("2.00")),
        (7003, "Gloss - High Key",     3, Decimal("1.50")),
        (7004, "Gloss - Production",   4, Decimal("0.00")),
        (7005, "Gloss - Premium",      5, Decimal("3.00")),
        (7006, "Gloss - Specialty",    6, Decimal("3.50")),
        (7007, "Matte - Speed",        7, Decimal("0.00")),
        (7008, "Matte - Production",   8, Decimal("0.00")),
    ]),
    (1007, "print_mode_x", "Print Mode (x)", "select", 8, [
        (8001, "6-Pass",  1, Decimal("0.00")),
        (8002, "8-Pass",  2, Decimal("1.00")),
        (8003, "9-Pass",  3, Decimal("1.50")),
        (8004, "10-Pass", 4, Decimal("2.00")),
        (8005, "12-Pass", 5, Decimal("2.50")),
    ]),
    (1008, "material", "Material", "select", 9, [
        (9001, "Arlon - 510 MT",        1, Decimal("0.00")),
        (9002, "Customer Supplied",     2, Decimal("25.00")),
        (9003, "GF - 230 Automark",     3, Decimal("1.50")),
        (9004, "Oracal - 3651 Clear",   4, Decimal("2.00")),
        (9005, "Avery - MPI 1105EZRS",  5, Decimal("2.00")),
        (9006, "Avery - MPI 1405EZRS",  6, Decimal("2.50")),
        (9007, "GF - 201HTAP",          7, Decimal("2.00")),
        (9008, "GF - 201HTAPAE",        8, Decimal("1.50")),
    ]),
    (1009, "laminate", "Laminate", "select", 10, [
        (10001, "None",            1, Decimal("0.00")),
        (10002, "Gloss, 3M-8348",  2, Decimal("1.50")),
        (10003, "Matte, 3M-8349",  3, Decimal("1.50")),
        (10004, "Gloss 58-4027N",  4, Decimal("2.00")),
    ]),
    (1010, "laminator", "Laminator", "select", 11, [
        (11001, "None",              1, Decimal("0.00")),
        (11002, "GFP 663TH No-Heat", 2, Decimal("2.00")),
    ]),
    (1011, "cutting", "Cutting", "select", 12, [
        (12001, "Yes", 1, Decimal("1.00")),
        (12002, "No",  2, Decimal("0.00")),
    ]),
]


async def main():
    import uuid
    from modules.catalog.models import Product, ProductOption, ProductOptionAttribute
    from modules.master_options.models import MasterOption, MasterOptionAttribute
    from modules.master_options.schemas import AttributeConfigItem, OptionConfigItem
    from modules.master_options.service import save_product_config

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # Find the product
        product = (
            await db.execute(select(Product).where(Product.id == uuid.UUID(PRODUCT_ID_STR)))
        ).scalar_one_or_none()
        if not product:
            print(f"Product {PRODUCT_ID_STR} not found — run seed_demo.py first")
            return
        print(f"Product: {product.product_name}")

        # Clear existing test master options (ids 1000-1011) and product options
        await db.execute(
            delete(MasterOption).where(
                MasterOption.ops_master_option_id.in_([o[0] for o in OPTIONS])
            )
        )
        await db.execute(
            delete(ProductOption).where(ProductOption.product_id == product.id)
        )
        await db.commit()

        print(f"Seeding {len(OPTIONS)} master option groups...")

        # Create master options + attributes
        for ops_mo_id, option_key, title, opts_type, sort_order, attrs in OPTIONS:
            mo = MasterOption(
                ops_master_option_id=ops_mo_id,
                title=title,
                option_key=option_key,
                options_type=opts_type,
                status=1,
                sort_order=sort_order,
            )
            db.add(mo)
            await db.flush()

            for ops_attr_id, attr_title, attr_sort, default_price in attrs:
                db.add(MasterOptionAttribute(
                    master_option_id=mo.id,
                    ops_attribute_id=ops_attr_id,
                    title=attr_title,
                    sort_order=attr_sort,
                    default_price=default_price,
                ))
        await db.commit()
        print("  Master options created.")

        # Build OptionConfigItem list with prices enabled for all attributes
        # Re-load fresh to get UUIDs
        mos = (
            await db.execute(
                select(MasterOption)
                .options(selectinload(MasterOption.attributes))
                .where(MasterOption.ops_master_option_id.in_([o[0] for o in OPTIONS]))
                .order_by(MasterOption.sort_order)
            )
        ).scalars().all()

        price_map = {
            (ops_mo_id, ops_attr_id): price
            for ops_mo_id, _, _, _, _, attrs in OPTIONS
            for ops_attr_id, _, _, price in attrs
        }

        config_items = []
        for mo in mos:
            config_items.append(OptionConfigItem(
                master_option_id=mo.id,
                ops_master_option_id=mo.ops_master_option_id,
                title=mo.title,
                option_key=mo.option_key,
                options_type=mo.options_type,
                master_option_tag=None,
                enabled=True,
                attributes=[
                    AttributeConfigItem(
                        attribute_id=ma.id,
                        ops_attribute_id=ma.ops_attribute_id,
                        title=ma.title,
                        attribute_key=None,
                        enabled=True,
                        price=price_map.get((mo.ops_master_option_id, ma.ops_attribute_id), Decimal("0")),
                        numeric_value=Decimal("0"),
                        sort_order=ma.sort_order,
                    )
                    for ma in sorted(mo.attributes, key=lambda a: a.sort_order)
                ],
            ))

        # Save via service — creates product_options + attributes with ops_attribute_id
        await save_product_config(db, product.id, config_items)
        print("  Product options + prices configured.")

        print(f"\nDone! {len(OPTIONS)} option groups seeded with pricing.")
        print(f"Open: http://localhost:3000/storefront/vg/product/{PRODUCT_ID_STR}")
        print(f"Admin: http://localhost:3000/products/{PRODUCT_ID_STR}/options")


if __name__ == "__main__":
    asyncio.run(main())
