"""Seed demo supplier and product data for local development."""

import asyncio
from pathlib import Path

# Load .env before importing database (which reads os.getenv at import time)
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from database import Base, async_session, engine
from modules.catalog.models import Product, ProductVariant
from modules.suppliers.models import Supplier

# Import all models so create_all registers them
import modules.suppliers.models  # noqa: F401
import modules.catalog.models  # noqa: F401

SUPPLIERS = [
    {
        "name": "SanMar",
        "slug": "sanmar",
        "protocol": "soap",
        "promostandards_code": "SANMAR",
        "base_url": "https://ws.sanmar.com:8080/SanMarWebService/SanMarWebServicePort",
        "auth_config": {"username": "demo_user", "password": "demo_pass"},
    },
    {
        "name": "S&S Activewear",
        "slug": "ss-activewear",
        "protocol": "rest",
        "promostandards_code": "SSACT",
        "base_url": "https://api.ssactivewear.com/v2",
        "auth_config": {"account_number": "demo_acct", "key": "demo_key"},
    },
    {
        "name": "4Over",
        "slug": "4over",
        "protocol": "rest",
        "promostandards_code": None,
        "base_url": "https://api.4over.com",
        "auth_config": {"api_key": "demo_4over_key"},
    },
]

DEMO_PRODUCTS = [
    {
        "supplier_slug": "sanmar",
        "supplier_sku": "PC61",
        "product_name": "Port & Company Essential Tee",
        "brand": "Port & Company",
        "description": "A customer favorite, this value-priced tee hits the mark on quality and comfort.",
        "product_type": "apparel",
        "image_url": "https://www.sanmar.com/imgindex/PC61_NAVY_front.jpg",
        "variants": [
            {"color": "Navy", "size": "S", "sku": "PC61-NAV-S", "base_price": "3.99", "inventory": 250},
            {"color": "Navy", "size": "M", "sku": "PC61-NAV-M", "base_price": "3.99", "inventory": 500},
            {"color": "Navy", "size": "L", "sku": "PC61-NAV-L", "base_price": "3.99", "inventory": 480},
            {"color": "White", "size": "M", "sku": "PC61-WHT-M", "base_price": "3.99", "inventory": 320},
        ],
    },
    {
        "supplier_slug": "sanmar",
        "supplier_sku": "K500",
        "product_name": "Port Authority Silk Touch Polo",
        "brand": "Port Authority",
        "description": "Our best-selling polo, with a touch of class for everyday corporate wear.",
        "product_type": "apparel",
        "image_url": "https://www.sanmar.com/imgindex/K500_BLACK_front.jpg",
        "variants": [
            {"color": "Black", "size": "S", "sku": "K500-BLK-S", "base_price": "12.99", "inventory": 100},
            {"color": "Black", "size": "M", "sku": "K500-BLK-M", "base_price": "12.99", "inventory": 200},
            {"color": "Black", "size": "L", "sku": "K500-BLK-L", "base_price": "12.99", "inventory": 180},
        ],
    },
    {
        "supplier_slug": "ss-activewear",
        "supplier_sku": "AA1070",
        "product_name": "Alternative Eco-Jersey Crew",
        "brand": "Alternative Apparel",
        "description": "Sustainably made eco-jersey tee, super soft and great for print.",
        "product_type": "apparel",
        "image_url": None,
        "variants": [
            {"color": "Smoke", "size": "XS", "sku": "AA1070-SMK-XS", "base_price": "8.50", "inventory": 75},
            {"color": "Smoke", "size": "S",  "sku": "AA1070-SMK-S",  "base_price": "8.50", "inventory": 150},
            {"color": "Smoke", "size": "M",  "sku": "AA1070-SMK-M",  "base_price": "8.50", "inventory": 200},
        ],
    },
]


async def seed():
    # Ensure all tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # Build slug -> supplier map
        slug_to_supplier: dict[str, Supplier] = {}

        for s_data in SUPPLIERS:
            from sqlalchemy import select
            existing = (
                await db.execute(
                    select(Supplier).where(Supplier.slug == s_data["slug"])
                )
            ).scalar_one_or_none()

            if existing:
                print(f"  [skip] Supplier already exists: {s_data['name']}")
                slug_to_supplier[s_data["slug"]] = existing
            else:
                supplier = Supplier(**s_data)
                db.add(supplier)
                await db.flush()  # get id before commit
                print(f"  [add]  Supplier: {s_data['name']}")
                slug_to_supplier[s_data["slug"]] = supplier

        await db.commit()

        # Seed products
        for p_data in DEMO_PRODUCTS:
            supplier = slug_to_supplier.get(p_data["supplier_slug"])
            if not supplier:
                continue

            from sqlalchemy import select
            from decimal import Decimal
            existing_product = (
                await db.execute(
                    select(Product).where(
                        Product.supplier_id == supplier.id,
                        Product.supplier_sku == p_data["supplier_sku"],
                    )
                )
            ).scalar_one_or_none()

            if existing_product:
                print(f"  [skip] Product already exists: {p_data['product_name']}")
                continue

            product = Product(
                supplier_id=supplier.id,
                supplier_sku=p_data["supplier_sku"],
                product_name=p_data["product_name"],
                brand=p_data["brand"],
                description=p_data["description"],
                product_type=p_data["product_type"],
                image_url=p_data["image_url"],
            )
            db.add(product)
            await db.flush()

            for v in p_data["variants"]:
                variant = ProductVariant(
                    product_id=product.id,
                    color=v["color"],
                    size=v["size"],
                    sku=v["sku"],
                    base_price=Decimal(v["base_price"]),
                    inventory=v["inventory"],
                )
                db.add(variant)

            print(f"  [add]  Product: {p_data['product_name']} ({len(p_data['variants'])} variants)")

        await db.commit()

    print("\nSeed complete!")
    await engine.dispose()


if __name__ == "__main__":
    print("Seeding demo data...\n")
    asyncio.run(seed())
