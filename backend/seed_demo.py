"""Seed demo supplier and product data for local development."""

import asyncio
from pathlib import Path

# Load .env before importing database (which reads os.getenv at import time)
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from database import Base, async_session, engine
from modules.catalog.models import Product, ProductVariant
from modules.suppliers.models import Supplier

# Import all models so create_all registers them
import modules.suppliers.models  # noqa: F401
import modules.catalog.models  # noqa: F401

SUPPLIERS = [
    {
        "name": "SanMar Corporation",
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
        "auth_config": {"account_number": "demo_acct", "api_key": "demo_key"},
    },
    {
        "name": "Alphabroder",
        "slug": "alphabroder",
        "protocol": "soap",
        "promostandards_code": "ALPHA",
        "base_url": "https://pstandards.alphabroder.com/inventory/v1",
        "auth_config": {"id": "PLACEHOLDER_USER", "password": "PLACEHOLDER_PASS"},
        "is_active": False,  # flip to True when Christian provides real creds
    },
    {
        "name": "4Over",
        "slug": "4over",
        "protocol": "rest",
        "promostandards_code": None,
        "base_url": "https://api.4over.com",
        "auth_config": {"api_key": "demo_4over_key"},
    },
    {
        "name": "Visual Graphics OPS",
        "slug": "vg-ops",
        "protocol": "ops_graphql",
        "base_url": "https://vg.onprintshop.com",
        "auth_config": {
            "n8n_credential_id": "PLACEHOLDER_CREDENTIAL_ID",
            "store_url": "https://vg.onprintshop.com",
        },
        "is_active": False,  # flip to True once Christian provides real OPS OAuth creds
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
    {
        "supplier_slug": "vg-ops",
        "supplier_sku": "VG-101",
        "product_name": "Premium Cotton Polo",
        "brand": "VG Signature",
        "description": "High-quality cotton polo with reinforced stitching.",
        "product_type": "apparel",
        "image_url": "https://placehold.co/400x400/png?text=Polo",
        "variants": [
            {"color": "Royal Blue", "size": "M", "sku": "VG-101-RB-M", "base_price": "19.99", "inventory": 50},
            {"color": "Royal Blue", "size": "L", "sku": "VG-101-RB-L", "base_price": "19.99", "inventory": 45},
        ],
    },
    {
        "supplier_slug": "vg-ops",
        "supplier_sku": "VG-202",
        "product_name": "Performance Tech Hoodie",
        "brand": "VG Active",
        "description": "Moisture-wicking tech hoodie for all-day comfort.",
        "product_type": "apparel",
        "image_url": "https://placehold.co/400x400/png?text=Hoodie",
        "variants": [
            {"color": "Charcoal", "size": "L", "sku": "VG-202-CH-L", "base_price": "45.00", "inventory": 120},
        ],
    },
]


async def seed():
    # Ensure all tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        from sqlalchemy import select, delete
        from modules.customers.models import Customer
        from modules.push_log.models import ProductPushLog
        from datetime import datetime, timezone, timedelta

        # Build slug -> supplier map
        slug_to_supplier: dict[str, Supplier] = {}

        for s_data in SUPPLIERS:
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
                await db.flush()
                print(f"  [add]  Supplier: {s_data['name']}")
                slug_to_supplier[s_data["slug"]] = supplier

        await db.commit()

        # Seed "Operation" Customers to match prototype table
        OPS_NAMES = ["inventory_sync_v2", "pricing_update", "delta_product_ingest", "full_catalog_push"]
        name_to_customer = {}
        for name in OPS_NAMES:
            existing = (await db.execute(select(Customer).where(Customer.name == name))).scalar_one_or_none()
            if not existing:
                customer = Customer(
                    name=name,
                    ops_base_url="https://demo.ops.com",
                    ops_token_url="https://demo.ops.com/token",
                    ops_client_id="demo",
                    ops_auth_config={"client_secret": "demo"}
                )
                db.add(customer)
                await db.flush()
                name_to_customer[name] = customer
            else:
                name_to_customer[name] = existing
        
        await db.commit()

        # Seed categories for vg-ops
        from modules.catalog.models import Category
        vg_supplier = slug_to_supplier.get("vg-ops")
        cat_map: dict[str, Category] = {}
        if vg_supplier:
            demo_cats = [
                {"external_id": "cat_1", "name": "Apparel", "sort_order": 1},
                {"external_id": "cat_2", "name": "Outerwear", "sort_order": 2, "parent_external_id": "cat_1"},
                {"external_id": "cat_3", "name": "Polos", "sort_order": 3, "parent_external_id": "cat_1"},
            ]
            for c_data in demo_cats:
                parent_id = None
                if "parent_external_id" in c_data:
                    parent = cat_map.get(c_data["parent_external_id"])
                    if parent:
                        parent_id = parent.id
                
                existing_cat = (await db.execute(
                    select(Category).where(
                        Category.supplier_id == vg_supplier.id,
                        Category.external_id == c_data["external_id"]
                    )
                )).scalar_one_or_none()

                if not existing_cat:
                    cat = Category(
                        supplier_id=vg_supplier.id,
                        external_id=c_data["external_id"],
                        name=c_data["name"],
                        sort_order=c_data["sort_order"],
                        parent_id=parent_id
                    )
                    db.add(cat)
                    await db.flush()
                    cat_map[c_data["external_id"]] = cat
                    print(f"  [add]  Category: {c_data['name']}")
                else:
                    cat_map[c_data["external_id"]] = existing_cat
            
            await db.commit()

        # Seed products
        seeded_products = []
        from decimal import Decimal
        
        # Product to category mapping for VG
        vg_prod_cats = {
            "VG-101": "cat_3", # Polos
            "VG-202": "cat_2", # Outerwear
        }

        for p_data in DEMO_PRODUCTS:
            supplier = slug_to_supplier.get(p_data["supplier_slug"])
            if not supplier:
                continue

            existing_product = (
                await db.execute(
                    select(Product).where(
                        Product.supplier_id == supplier.id,
                        Product.supplier_sku == p_data["supplier_sku"],
                    )
                )
            ).scalar_one_or_none()

            # Assign category if it's a VG product
            category_id = None
            if p_data["supplier_slug"] == "vg-ops":
                cat_ext_id = vg_prod_cats.get(p_data["supplier_sku"])
                if cat_ext_id:
                    category_id = cat_map.get(cat_ext_id).id

            if existing_product:
                if category_id and not existing_product.category_id:
                    existing_product.category_id = category_id
                    await db.flush()
                seeded_products.append(existing_product)
                continue

            product = Product(
                supplier_id=supplier.id,
                supplier_sku=p_data["supplier_sku"],
                product_name=p_data["product_name"],
                brand=p_data["brand"],
                description=p_data["description"],
                product_type=p_data["product_type"],
                image_url=p_data["image_url"],
                category_id=category_id
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

            print(f"  [add]  Product: {p_data['product_name']}")
            seeded_products.append(product)

        await db.commit()

        # Seed Activity Logs
        await db.execute(delete(ProductPushLog))
        LOG_SPECS = [
            {"supp": "sanmar", "op": "inventory_sync_v2", "st": "complete", "rec": "12,450"},
            {"supp": "ss-activewear", "op": "pricing_update", "st": "complete", "rec": "8,201"},
            {"supp": "alphabroder", "op": "delta_product_ingest", "st": "complete", "rec": "11,800"},
            {"supp": "4over", "op": "full_catalog_push", "st": "error", "rec": "0"},
        ]

        for spec in LOG_SPECS:
            # Find a product for this supplier
            demo_prod = next((p for p in seeded_products if slug_to_supplier[spec["supp"]].id == p.supplier_id), seeded_products[0])
            customer = name_to_customer[spec["op"]]
            
            log = ProductPushLog(
                product_id=demo_prod.id,
                customer_id=customer.id,
                status="failed" if spec["st"] == "error" else "pushed",
                ops_product_id=spec["rec"],
                pushed_at=datetime.now(timezone.utc) - timedelta(minutes=10)
            )
            db.add(log)
        
        await db.commit()
        print(f"  [add]  Seeded {len(LOG_SPECS)} activity logs.")

    print("\nSeed complete!")
    await engine.dispose()

    print("\nSeed complete!")
    await engine.dispose()



if __name__ == "__main__":
    print("Seeding demo data...\n")
    asyncio.run(seed())
