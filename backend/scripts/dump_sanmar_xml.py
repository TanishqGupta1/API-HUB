"""Dump the raw PriceGroup section of getProduct XML for one SKU.

Helps diagnose how SanMar associates prices with specific parts.
"""
from __future__ import annotations

import asyncio
import sys
from uuid import UUID

from lxml import etree

from database import async_session
from modules.promostandards.client import PromoStandardsClient
from modules.promostandards.sanmar_adapter import SANMAR_WSDLS
from modules.suppliers.models import Supplier


SANMAR_SUPPLIER_ID = UUID("a73a8445-2f08-4293-9625-b3e480ddc1da")
SKU = "PC61"


async def main() -> int:
    async with async_session() as db:
        s = await db.get(Supplier, SANMAR_SUPPLIER_ID)
        client = PromoStandardsClient(
            wsdl_url=SANMAR_WSDLS["PRODUCT"],
            auth_config=s.auth_config,
        )
        svc, history = client.get_service_with_history()
        try:
            svc.getProduct(
                productId=SKU,
                **client._auth("2.0.0", localization_country="us", localization_language="en"),
            )
        except Exception as exc:
            print(f"call failed: {exc}", file=sys.stderr)

        if history.last_received is None:
            print("no response captured", file=sys.stderr)
            return 1
        xml = history.last_received["envelope"]

        # Print ProductPriceGroupArray for inspection
        groups = xml.xpath("//*[local-name()='ProductPriceGroupArray']")
        if not groups:
            print("(no ProductPriceGroupArray in response)")
            print("first 1500 chars of full envelope:")
            print(etree.tostring(xml, pretty_print=True).decode()[:1500])
            return 0
        for g in groups:
            print(etree.tostring(g, pretty_print=True).decode())

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
