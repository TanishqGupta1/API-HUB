"""
SanMar PromoStandards Smoke Test

Verifies the existing PromoStandardsClient works against real SanMar production SOAP
endpoints for a handful of known SKUs. Scope is narrow: auth + WSDL reachable +
parser handles SanMar-specific response shapes.
"""

import argparse
import asyncio
import logging
import sys
import os
from pathlib import Path

# Load .env before importing database
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from database import async_session
from sqlalchemy import select
from modules.suppliers.models import Supplier
from modules.promostandards.client import PromoStandardsClient

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

PROD_WSDLS = {
    "product": "https://ws.sanmar.com:8080/promostandards/ProductDataServiceV2.xml?wsdl",
    "inventory": "https://ws.sanmar.com:8080/promostandards/InventoryServiceBindingV2final?WSDL",
    "media": "https://ws.sanmar.com:8080/promostandards/MediaContentServiceBinding?wsdl",
    "pricing": "https://ws.sanmar.com:8080/promostandards/PricingAndConfigurationServiceBinding?WSDL",
}

TEST_WSDLS = {
    "product": "https://test-ws.sanmar.com:8080/promostandards/ProductDataServiceV2.xml?wsdl",
    "inventory": "https://test-ws.sanmar.com:8080/promostandards/InventoryServiceBindingV2final?WSDL",
    "media": "https://test-ws.sanmar.com:8080/promostandards/MediaContentServiceBinding?wsdl",
    "pricing": "https://test-ws.sanmar.com:8080/promostandards/PricingAndConfigurationServiceBinding?WSDL",
}


async def main():
    parser = argparse.ArgumentParser(description="SanMar PromoStandards Smoke Test")
    parser.add_argument("--test", action="store_true", help="Use test-ws.sanmar.com endpoints")
    parser.add_argument("skus", nargs="*", default=["PC61", "K420", "LPC61", "MM1000"], help="SKUs to test")
    args = parser.parse_args()

    wsdls = TEST_WSDLS if args.test else PROD_WSDLS

    async with async_session() as db:
        supplier = (
            await db.execute(select(Supplier).where(Supplier.slug == "sanmar"))
        ).scalar_one_or_none()

    if not supplier:
        print("ERROR: SanMar supplier not found in DB. Run seed_demo.py first.")
        sys.exit(1)

    auth_config = supplier.auth_config or {}
    
    # Override with env vars if present
    env_id = os.getenv("SANMAR_ID")
    env_password = os.getenv("SANMAR_PASSWORD")
    if env_id and env_password:
        auth_config = {"id": env_id, "password": env_password}

    if "id" not in auth_config or "password" not in auth_config:
        print("ERROR: SanMar auth_config missing 'id' or 'password'.")
        print("Please set SANMAR_ID and SANMAR_PASSWORD in your .env file.")
        sys.exit(1)

    print(f"Loaded credentials for: {auth_config['id']}")
    print(f"Using {'TEST' if args.test else 'PROD'} endpoints")
    print(f"Testing SKUs: {', '.join(args.skus)}\n")

    prod_client = PromoStandardsClient(wsdls["product"], auth_config)
    inv_client = PromoStandardsClient(wsdls["inventory"], auth_config)
    media_client = PromoStandardsClient(wsdls["media"], auth_config)
    ppc_client = PromoStandardsClient(wsdls["pricing"], auth_config)

    passed_count = 0

    for sku in args.skus:
        print(f"--- SKU: {sku} ---")
        sku_success = True

        # 1. Product Data
        try:
            prod_data = await prod_client.get_product(sku)
            if not prod_data:
                print(f"  [EMPTY] getProduct returned no data.")
                sku_success = False
            else:
                print(f"  Product: {prod_data.product_name} | Brand: {prod_data.brand}")
                print(f"  Categories: {', '.join(prod_data.categories[:3])}")
                print(f"  Parts count: {len(prod_data.parts)}")
        except Exception as e:
            print(f"  [ERROR] getProduct failed: {e}")
            if "User authenticating failed" in str(e):
                print("Auth failed. Aborting.")
                sys.exit(1)
            sku_success = False

        # 2. Inventory
        try:
            inv_data = await inv_client.get_inventory([sku])
            if not inv_data:
                print(f"  [EMPTY] getInventory returned no data.")
                sku_success = False
            else:
                print(f"  Inventory parts returned: {len(inv_data)}")
                first = inv_data[0]
                print(f"  Sample part: {first.part_id} -> Qty: {first.quantity_available} at {first.warehouse_code}")
        except Exception as e:
            print(f"  [ERROR] getInventory failed: {e}")
            sku_success = False

        # 3. Media
        try:
            media_data = await media_client.get_media([sku], media_type="Image")
            if not media_data:
                print(f"  [EMPTY] getMedia returned no data.")
                sku_success = False
            else:
                print(f"  Media URLs returned: {len(media_data)}")
                for m in media_data[:3]:
                    print(f"  - {m.url} ({m.media_type})")
        except Exception as e:
            print(f"  [ERROR] getMedia failed: {e}")
            sku_success = False

        # 4. Pricing
        try:
            pricing_data = await ppc_client.get_pricing([sku])
            if not pricing_data:
                print(f"  [EMPTY] getPricing returned no data.")
                sku_success = False
            else:
                net_prices = [p for p in pricing_data if p.price_type.lower() == "net"]
                print(f"  Pricing points returned: {len(pricing_data)} ({len(net_prices)} Net)")
                if net_prices:
                    first_price = net_prices[0]
                    print(f"  Sample price (Net): {first_price.part_id} -> {first_price.price} (Min: {first_price.quantity_min})")
        except Exception as e:
            print(f"  [ERROR] getPricing failed: {e}")
            sku_success = False

        if sku_success:
            passed_count += 1
            print("  -> PASS\n")
        else:
            print("  -> FAIL\n")

    print(f"Summary: {passed_count}/{len(args.skus)} SKUs passed.")
    if passed_count < len(args.skus):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
