#!/usr/bin/env python3
"""SanMar PromoStandards smoke test.

Runs getProduct / getInventoryLevels / getMediaContent / getConfigurationAndPricing
against SanMar endpoints for a curated SKU list and prints one summary block
per SKU. Exits non-zero on any failure.

Usage:
    cd api-hub/backend && source .venv/bin/activate
    python scripts/sanmar_smoke.py                          # prod, default SKUs
    python scripts/sanmar_smoke.py --test                   # test-ws.sanmar.com
    python scripts/sanmar_smoke.py --sku PC61 --sku K420
    python scripts/sanmar_smoke.py PC61 K420                # positional also works

Prerequisite: a Supplier row with slug='sanmar' must exist in the DB with
auth_config={"id": "<SanMar.com username>", "password": "<SanMar.com password>"}.
See docs/sanmar_smoke_runbook.md for setup. Alternatively, set SANMAR_ID +
SANMAR_PASSWORD in .env to override the DB value (useful for CI or ad-hoc runs).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from database import async_session  # noqa: E402
from modules.promostandards.client import PromoStandardsClient  # noqa: E402
from modules.suppliers.models import Supplier  # noqa: E402

log = logging.getLogger("sanmar_smoke")


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

DEFAULT_SKUS = ["PC61", "K420", "LPC61", "MM1000"]


async def load_sanmar_auth() -> dict:
    """Return the SanMar auth_config dict, preferring env overrides over DB."""
    env_id = os.getenv("SANMAR_ID")
    env_password = os.getenv("SANMAR_PASSWORD")
    if env_id and env_password:
        return {"id": env_id, "password": env_password}

    async with async_session() as db:
        supplier = (
            await db.execute(select(Supplier).where(Supplier.slug == "sanmar"))
        ).scalar_one_or_none()
    if supplier is None:
        raise RuntimeError(
            "Supplier slug='sanmar' not found. Create via /suppliers UI or "
            "set SANMAR_ID + SANMAR_PASSWORD in .env."
        )
    return dict(supplier.auth_config or {})


async def run_smoke(skus: list[str], wsdls: dict[str, str]) -> int:
    auth = await load_sanmar_auth()
    if not auth.get("id") or not auth.get("password"):
        print("[ERROR] auth_config missing id/password. Set via /suppliers UI or .env.")
        return 1

    pd_client = PromoStandardsClient(wsdls["product"], auth)
    inv_client = PromoStandardsClient(wsdls["inventory"], auth)
    media_client = PromoStandardsClient(wsdls["media"], auth)
    ppc_client = PromoStandardsClient(wsdls["pricing"], auth)

    total = len(skus) * 4
    failures = 0

    for sku in skus:
        print(f"\n=== {sku} ===")

        try:
            product = await pd_client.get_product(sku)
            if product is None:
                print("  [PRODUCT] empty / fault")
                failures += 1
            else:
                print(
                    f"  [PRODUCT] name={product.product_name!r} brand={product.brand!r} "
                    f"parts={len(product.parts)} cats={product.categories[:3]}"
                )
        except Exception as exc:  # noqa: BLE001
            print(f"  [PRODUCT] FAIL: {exc}")
            failures += 1
            if "User authenticating failed" in str(exc):
                print("Auth failed. Aborting.")
                return 1

        try:
            inv = await inv_client.get_inventory([sku])
            if not inv:
                print("  [INVENTORY] no records")
                failures += 1
            else:
                print(f"  [INVENTORY] {len(inv)} part-level records")
                for lvl in inv[:3]:
                    print(
                        f"    part={lvl.part_id} qty={lvl.quantity_available} "
                        f"primary_wh={lvl.warehouse_code!r}"
                    )
        except Exception as exc:  # noqa: BLE001
            print(f"  [INVENTORY] FAIL: {exc}")
            failures += 1

        try:
            media = await media_client.get_media([sku], media_type="Image")
            if not media:
                print("  [MEDIA] no urls")
                failures += 1
            else:
                print(f"  [MEDIA] {len(media)} urls")
                for m in media[:3]:
                    print(f"    {m.media_type}: {m.url}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [MEDIA] FAIL: {exc}")
            failures += 1

        try:
            prices = await ppc_client.get_pricing([sku])
            if not prices:
                print("  [PRICING] no price points")
                failures += 1
            else:
                print(f"  [PRICING] {len(prices)} price points")
                for p in prices[:3]:
                    print(
                        f"    part={p.part_id} price={p.price} min_qty={p.quantity_min}"
                    )
        except Exception as exc:  # noqa: BLE001
            print(f"  [PRICING] FAIL: {exc}")
            failures += 1

    print(f"\n=== Summary: {total - failures}/{total} calls passed ===")
    return 0 if failures == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="SanMar PromoStandards smoke test")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use test-ws.sanmar.com endpoints instead of production",
    )
    parser.add_argument(
        "--sku",
        action="append",
        dest="skus_named",
        default=[],
        help="SKU to test (repeatable). Combines with any positional SKUs.",
    )
    parser.add_argument(
        "skus_positional",
        nargs="*",
        help="Positional SKUs. If neither --sku nor positional given, defaults used.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    skus = args.skus_named + args.skus_positional or DEFAULT_SKUS
    wsdls = TEST_WSDLS if args.test else PROD_WSDLS
    return asyncio.run(run_smoke(skus, wsdls))


if __name__ == "__main__":
    sys.exit(main())
