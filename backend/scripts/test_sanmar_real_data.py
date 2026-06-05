"""Pull real SanMar data for known SKUs to validate the pipeline end-to-end.

Covers product detail, pricing, and inventory for a small list of well-known
styles. No DB writes — read-only sanity check.

Run from backend/ with the venv active:
    python scripts/test_sanmar_real_data.py
"""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal
from uuid import UUID

from database import async_session
from modules.promostandards.client import PromoStandardsClient
from modules.promostandards.sanmar_adapter import SANMAR_WSDLS
from modules.suppliers.models import Supplier


SANMAR_SUPPLIER_ID = UUID("a73a8445-2f08-4293-9625-b3e480ddc1da")

# Well-known SanMar SKUs we want to verify
KNOWN_SKUS = ["PC61", "L500", "ST350", "PC54", "PC78H"]


async def fetch_one(client, sku: str) -> dict:
    """Pull product detail + pricing for one SKU. Returns a summary dict."""
    detail = await client.get_product(sku)
    if detail is None:
        return {"sku": sku, "ok": False, "reason": "not found / no access"}

    summary = {
        "sku": sku,
        "ok": True,
        "name": detail.product_name,
        "brand": detail.brand,
        "categories": detail.categories,
        "n_parts": len(detail.parts) if detail.parts else 0,
        "first_part": None,
        "image_url": detail.primary_image_url,
    }
    if detail.parts:
        p = detail.parts[0]
        summary["first_part"] = {
            "part_id": p.part_id,
            "color": getattr(p, "color_name", None),
            "size": getattr(p, "size_name", None),
            "sku": getattr(p, "sku", None),
        }
    return summary


async def main() -> int:
    async with async_session() as db:
        supplier = await db.get(Supplier, SANMAR_SUPPLIER_ID)
        if supplier is None:
            print("ERROR: SanMar supplier missing", file=sys.stderr)
            return 2

        client = PromoStandardsClient(
            wsdl_url=SANMAR_WSDLS["PRODUCT"],
            auth_config=supplier.auth_config,
        )

        print(f"Pulling {len(KNOWN_SKUS)} known SanMar styles …\n")
        for sku in KNOWN_SKUS:
            print(f"━━━ {sku} ━━━")
            try:
                summary = await fetch_one(client, sku)
            except Exception as exc:  # noqa: BLE001
                print(f"  EXC: {type(exc).__name__}: {exc}")
                continue
            if not summary["ok"]:
                print(f"  ✗ {summary['reason']}")
                continue
            print(f"  ✓ {summary['name']}")
            print(f"    brand:    {summary['brand']}")
            print(f"    categories: {summary['categories']}")
            print(f"    variants: {summary['n_parts']}")
            if summary["first_part"]:
                fp = summary["first_part"]
                print(f"    first variant: color={fp['color']!r} size={fp['size']!r} part_id={fp['part_id']} sku={fp['sku']}")
            if summary["image_url"]:
                print(f"    image:    {summary['image_url']}")
            print()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
