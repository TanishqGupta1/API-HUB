"""One-shot SanMar credential smoke test.

Loads the SanMar supplier from DB, decrypts auth_config, and calls
getProductSellable (the cheapest PromoStandards call) so we get a fast
yes/no on whether the credentials Christian provided actually work.

Run from backend/ with the venv active:
    python scripts/test_sanmar_creds.py

Prints the first 5 sellable product IDs on success, full error on failure.
"""
from __future__ import annotations

import asyncio
import sys
from uuid import UUID

from sqlalchemy import select

from database import async_session
from modules.promostandards.client import PromoStandardsClient
from modules.promostandards.sanmar_adapter import SANMAR_WSDLS
from modules.suppliers.models import Supplier


SANMAR_SUPPLIER_ID = UUID("a73a8445-2f08-4293-9625-b3e480ddc1da")


async def main() -> int:
    async with async_session() as db:
        supplier = await db.get(Supplier, SANMAR_SUPPLIER_ID)
        if supplier is None:
            print("ERROR: SanMar supplier row not found", file=sys.stderr)
            return 2

        ac = supplier.auth_config or {}
        # Don't print values — only confirm presence so a screen-share won't leak.
        present = {k: bool(ac.get(k)) for k in ("customer_number", "id", "password")}
        print(f"auth_config presence: {present}")
        if not all(present.values()):
            print("ERROR: one or more required credential fields are blank", file=sys.stderr)
            return 3

        client = PromoStandardsClient(
            wsdl_url=SANMAR_WSDLS["PRODUCT"],
            auth_config=ac,
        )

        # Force the zeep client to materialize so we can grab history
        svc, history = client.get_service_with_history()

        # Test 1: raw getProductSellable — dump the actual SOAP response
        print(f"\n[1] getProductSellable raw response …")
        try:
            response = svc.getProductSellable(isSellable=True, **client._auth("2.0.0"))
            print(f"  response object: {response!r}")
            print(f"  type: {type(response).__name__}")
        except Exception as exc:
            print(f"  EXC: {type(exc).__name__}: {exc}", file=sys.stderr)

        # Dump the last raw response XML (truncated)
        if history.last_received is not None:
            from lxml import etree
            xml = etree.tostring(history.last_received["envelope"], pretty_print=True).decode()
            print("\n  --- last received SOAP envelope (truncated to 2000 chars) ---")
            print(xml[:2000])
            print("  --- end ---")
        else:
            print("  no history.last_received — request may have failed before send")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
