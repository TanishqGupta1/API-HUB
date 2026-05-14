"""Seed demo supplier and product data for local development."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Load .env before importing database (which reads os.getenv at import time)
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from decimal import Decimal
from sqlalchemy import delete, select

from database import Base, async_session, engine
from modules.catalog.models import (
    Category,
    Product,
    ProductOption,
    ProductOptionAttribute,
    ProductSize,
    ProductVariant,
)
from modules.customers.models import Customer
from modules.master_options.models import MasterOption, MasterOptionAttribute
from modules.push_log.models import ProductPushLog
from modules.suppliers.models import Supplier

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DEMO_CUSTOMER_NAME = "Demo Showcase Customer"


def _load_fixture(filename: str) -> list[dict]:
    """Load a fixture JSON file's `products` array. Returns [] if missing/empty."""
    path = FIXTURES_DIR / filename
    if not path.exists():
        print(f"  [skip] Fixture not found: {filename}")
        return []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"  [warn] Fixture {filename} invalid JSON: {e}")
        return []
    products = data.get("products", []) if isinstance(data, dict) else []
    print(f"  [load] {filename}: {len(products)} product(s)")
    return products


def _load_master_options() -> list[dict]:
    """Load `fixtures/master_options.json` → list of master option dicts."""
    path = FIXTURES_DIR / "master_options.json"
    if not path.exists():
        print("  [skip] Fixture not found: master_options.json")
        return []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"  [warn] master_options.json invalid JSON: {e}")
        return []
    opts = data.get("master_options", []) if isinstance(data, dict) else []
    print(f"  [load] master_options.json: {len(opts)} master option(s)")
    return opts


def _to_decimal(value) -> Decimal | None:
    """Best-effort Decimal coercion; None on failure or empty."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


async def _seed_master_options(db) -> int:
    """Upsert MasterOption + MasterOptionAttribute from fixture. Returns count seeded/updated."""
    fixture = _load_master_options()
    if not fixture:
        return 0
    upserted = 0
    for mo in fixture:
        ops_id = mo.get("master_option_id")
        if ops_id is None:
            continue
        existing = (await db.execute(
            select(MasterOption).where(MasterOption.ops_master_option_id == ops_id)
        )).scalar_one_or_none()

        pricing = mo.get("pricing_method")
        pricing_str = None if pricing is None else str(pricing)

        if existing:
            existing.title = mo.get("title") or existing.title
            existing.option_key = mo.get("option_key") or existing.option_key
            existing.options_type = mo.get("options_type") or existing.options_type
            existing.pricing_method = pricing_str
            existing.status = int(mo.get("status", existing.status))
            existing.sort_order = int(mo.get("sort_order", existing.sort_order))
            existing.description = mo.get("description") or existing.description
            existing.raw_json = mo
            existing.synced_at = datetime.now(timezone.utc)
            master = existing
        else:
            master = MasterOption(
                ops_master_option_id=ops_id,
                title=mo.get("title") or mo.get("option_key") or f"option_{ops_id}",
                option_key=mo.get("option_key"),
                options_type=mo.get("options_type"),
                pricing_method=pricing_str,
                status=int(mo.get("status", 1)),
                sort_order=int(mo.get("sort_order", 0)),
                description=mo.get("description"),
                raw_json=mo,
                synced_at=datetime.now(timezone.utc),
            )
            db.add(master)
            await db.flush()

        existing_attr_ids = {a.ops_attribute_id for a in (
            (await db.execute(
                select(MasterOptionAttribute).where(
                    MasterOptionAttribute.master_option_id == master.id
                )
            )).scalars().all()
        )}
        for attr in mo.get("attributes", []):
            ops_attr_id = attr.get("master_attribute_id")
            if ops_attr_id is None or ops_attr_id in existing_attr_ids:
                continue
            db.add(MasterOptionAttribute(
                master_option_id=master.id,
                ops_attribute_id=ops_attr_id,
                title=attr.get("label") or attr.get("attribute_key") or f"attr_{ops_attr_id}",
                sort_order=int(attr.get("sort_order", 0)),
                default_price=_to_decimal(attr.get("setup_cost")),
                raw_json=attr,
            ))
        upserted += 1
    await db.commit()
    return upserted

# Import all models so create_all registers them
import modules.suppliers.models  # noqa: F401
import modules.catalog.models  # noqa: F401

# Active configured suppliers. Credentials are intentionally blank — the UI
# form is schema-driven (renders one input per auth_config key) so we seed
# the *keys* with empty strings so the operator can fill them in. Never seed
# real credentials here. PromoStandards-compatible suppliers beyond these
# two appear in the PromoStandards directory (modules/ps_directory).
SUPPLIERS = [
    {
        "name": "SanMar Corporation",
        "slug": "sanmar",
        "protocol": "soap",
        "promostandards_code": "SANMAR",
        "base_url": "https://ws.sanmar.com:8080/SanMarWebService/SanMarWebServicePort",
        "auth_config": {"id": "", "password": "", "customer_number": ""},
        "is_active": False,
    },
    {
        "name": "Visual Graphics OPS",
        "slug": "vg-ops",
        "protocol": "ops_graphql",
        "base_url": "",
        "auth_config": {
            "store_url": "",
            "client_id": "",
            "client_secret": "",
            "token_url": "",
        },
        "is_active": False,
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

    # Merge fixture-file products into DEMO_PRODUCTS so client-demo data
    # can be edited without touching this script. Fixtures upsert on
    # (supplier_slug, supplier_sku) — see Product unique constraint.
    extra_products: list[dict] = []
    extra_products.extend(_load_fixture("sanmar_hero_products.json"))
    extra_products.extend(_load_fixture("ops_demo_products.json"))
    for p in extra_products:
        p.setdefault("supplier_slug", "vg-ops")
        p.setdefault("brand", None)
        p.setdefault("description", None)
        p.setdefault("product_type", "apparel")
        p.setdefault("image_url", None)
        p.setdefault("category", None)
        p.setdefault("variants", [])
    DEMO_PRODUCTS.extend(extra_products)

    async with async_session() as db:
        # Master options come first — per-product options may reference them
        # via master_option_id / master_attribute_id integer fields.
        mo_count = await _seed_master_options(db)
        if mo_count:
            print(f"  [add]  Master options seeded/updated: {mo_count}")

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
            category_name = None
            if p_data["supplier_slug"] == "vg-ops":
                cat_ext_id = vg_prod_cats.get(p_data["supplier_sku"])
                if cat_ext_id:
                    cat_obj = cat_map.get(cat_ext_id)
                    category_id = cat_obj.id
                    category_name = cat_obj.name

            if existing_product:
                if category_id and not existing_product.category_id:
                    existing_product.category_id = category_id
                    existing_product.category = category_name
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
                category_id=category_id,
                category=category_name or p_data.get("category"),
                ops_product_id=p_data.get("ops_product_id"),
                external_catalogue=p_data.get("external_catalogue"),
                last_synced=datetime.now(timezone.utc),
            )
            db.add(product)
            await db.flush()

            for v in p_data.get("variants", []):
                variant = ProductVariant(
                    product_id=product.id,
                    color=v.get("color"),
                    size=v.get("size"),
                    sku=v.get("sku"),
                    base_price=_to_decimal(v.get("base_price")),
                    inventory=v.get("inventory"),
                )
                db.add(variant)

            for sz in p_data.get("sizes", []):
                w = _to_decimal(sz.get("width"))
                h = _to_decimal(sz.get("height"))
                if w is None or h is None:
                    continue
                db.add(ProductSize(
                    product_id=product.id,
                    width=w,
                    height=h,
                    unit=sz.get("unit", "in"),
                    label=sz.get("label"),
                ))

            for opt in p_data.get("options", []):
                option = ProductOption(
                    product_id=product.id,
                    ops_option_id=opt.get("ops_option_id"),
                    master_option_id=opt.get("master_option_id"),
                    option_key=opt.get("option_key") or f"opt_{opt.get('master_option_id', 'x')}",
                    title=opt.get("title") or opt.get("option_key") or "Option",
                    options_type=opt.get("options_type"),
                    sort_order=int(opt.get("sort_order", 0)),
                    required=bool(opt.get("required", False)),
                    status=int(opt.get("status", 1)),
                    enabled=bool(opt.get("enabled", True)),
                )
                db.add(option)
                await db.flush()
                seen_titles: set[str] = set()
                for attr in opt.get("attributes", []):
                    title = attr.get("title") or attr.get("attribute_key") or f"attr_{attr.get('ops_attribute_id', 'x')}"
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)
                    db.add(ProductOptionAttribute(
                        product_option_id=option.id,
                        ops_attribute_id=attr.get("ops_attribute_id"),
                        master_attribute_id=attr.get("master_attribute_id"),
                        attribute_key=attr.get("attribute_key"),
                        title=title,
                        sort_order=int(attr.get("sort_order", 0)),
                        status=int(attr.get("status", 1)),
                        enabled=bool(attr.get("enabled", True)),
                        price=_to_decimal(attr.get("price")),
                        setup_cost=_to_decimal(attr.get("setup_cost")),
                        multiplier=_to_decimal(attr.get("multiplier")),
                        numeric_value=_to_decimal(attr.get("numeric_value")),
                    ))

            print(f"  [add]  Product: {p_data['product_name']}")
            seeded_products.append(product)

        await db.commit()

        # Seed Activity Logs
        await db.execute(delete(ProductPushLog))
        LOG_SPECS = [
            {"supp": "sanmar", "op": "inventory_sync_v2", "st": "complete", "rec": "12,450"},
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

        # Demo Showcase Customer — links to every seeded product via push_log
        # so the customer catalog page (/customers/{id}) shows the full demo
        # catalog. Until real OPS push lands, this is how we surface the
        # "what the customer sees" view to clients.
        demo_customer = (await db.execute(
            select(Customer).where(Customer.name == DEMO_CUSTOMER_NAME)
        )).scalar_one_or_none()
        if not demo_customer:
            demo_customer = Customer(
                name=DEMO_CUSTOMER_NAME,
                ops_base_url="https://demo.onprintshop.com",
                ops_token_url="https://demo.onprintshop.com/oauth/token",
                ops_client_id="demo-showcase",
                ops_auth_config={"client_secret": "demo-showcase-secret"},
            )
            db.add(demo_customer)
            await db.flush()
            print(f"  [add]  Customer: {DEMO_CUSTOMER_NAME}")

        existing_links = set(
            (await db.execute(
                select(ProductPushLog.product_id).where(
                    ProductPushLog.customer_id == demo_customer.id
                )
            )).scalars().all()
        )
        new_links = 0
        for prod in seeded_products:
            if prod.id in existing_links:
                continue
            db.add(ProductPushLog(
                product_id=prod.id,
                customer_id=demo_customer.id,
                status="pushed",
                ops_product_id=f"demo-{prod.supplier_sku}",
                pushed_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            ))
            new_links += 1
        await db.commit()
        print(f"  [add]  Linked {new_links} product(s) to {DEMO_CUSTOMER_NAME} via push_log")

    print("\nSeed complete!")
    await engine.dispose()



if __name__ == "__main__":
    print("Seeding demo data...\n")
    asyncio.run(seed())
