#!/usr/bin/env python3
"""SanMar → OPS staging push spike (read-only).

Validates assumptions in docs/superpowers/specs/2026-05-08-sanmar-ops-staging-push-design.md
WITHOUT writing anything to OPS:

  1. SanMar creds work (auth_config in DB or SANMAR_ID/SANMAR_PASSWORD env).
  2. PC61 hydrates to a ProductIngest via the modern adapter path.
  3. Confirms the base_price=None bug — variants come back with no base_price set.
  4. Shows what min Net-tier backfill WOULD set base_price to (per spec fix).
  5. VG OPS staging customer row has all OAuth2 fields populated.
  6. OAuth2 client_credentials grant succeeds against ops_token_url.
  7. Prints a sample setProduct GraphQL mutation body that the new payload_builder
     would emit (NOT sent — preview only).

Usage:
    cd api-hub/backend && source .venv/bin/activate
    python scripts/sanmar_ops_spike.py                          # PC61, prod SanMar
    python scripts/sanmar_ops_spike.py --sku K420               # different SKU
    python scripts/sanmar_ops_spike.py --customer-name VG       # customer slug match

Exit codes:
    0 — every check passed (creds work, no GraphQL queries sent).
    1 — a check failed; see the printed summary.
    2 — bad CLI args or DB rows missing.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from decimal import Decimal
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from database import async_session  # noqa: E402
from modules.catalog.schemas import ProductIngest, VariantIngest, VariantPriceIngest  # noqa: E402
from modules.customers.models import Customer  # noqa: E402
from modules.import_jobs.base import ProductRef  # noqa: E402
from modules.promostandards.sanmar_adapter import SanMarAdapter  # noqa: E402
from modules.suppliers.models import Supplier  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")
log = logging.getLogger("spike")


def _hr(label: str) -> None:
    print(f"\n{'─' * 4} {label} {'─' * (74 - len(label))}")


def _pick_min_net(prices: list[VariantPriceIngest]) -> Decimal | None:
    """What ps_normalizer_v2.merge_pricing SHOULD do per spec fix.

    Pick the lowest qty_min Net-tier price. Mirrors legacy normalizer.py::_pick_base_price.
    """
    nets = [p for p in prices if p.price_type and p.price_type.lower() in ("net", "net price")]
    if not nets:
        return None
    return min(nets, key=lambda p: (p.quantity_min, p.price)).price


def _sample_set_product_mutation(
    *,
    supplier_sku: str,
    product_name: str,
    push_prefix: str,
) -> dict:
    """Build the GraphQL request body the new payload_builder would emit."""
    return {
        "query": (
            "mutation setProduct($input: ProductInput!){ "
            "setProduct(input:$input){ id title status products_id } "
            "}"
        ),
        "variables": {
            "input": {
                "category_id": 0,
                "visible": 1,
                "products_title": f"{push_prefix}{product_name}",
                "products_internal_title": supplier_sku,
            }
        },
    }


async def _run(sku: str, customer_filter: str | None) -> int:
    failures: list[str] = []

    _hr("1. Load SanMar supplier row")
    async with async_session() as db:
        sanmar = (
            await db.execute(select(Supplier).where(Supplier.slug == "sanmar"))
        ).scalar_one_or_none()
    if not sanmar:
        print("FAIL: no Supplier with slug='sanmar' in DB.")
        return 2
    auth = dict(sanmar.auth_config or {})
    has_creds = bool(auth.get("id") and auth.get("password"))
    print(f"  supplier_id={sanmar.id}  has_auth_config={has_creds}")
    if not has_creds:
        print("FAIL: SanMar supplier.auth_config missing id/password.")
        failures.append("sanmar_auth_missing")

    _hr("2. Hydrate PC61 via SanMarAdapter (modern path)")
    ingest: ProductIngest | None = None
    try:
        async with async_session() as db:
            adapter = SanMarAdapter(supplier=sanmar, db=db)
            ingest = await adapter.hydrate_product(ProductRef(supplier_sku=sku))
        print(f"  product_name={ingest.product_name!r}")
        print(f"  brand={ingest.brand!r}  category={ingest.category_name!r}")
        print(f"  variants={len(ingest.variants)}  images={len(ingest.images)}")
    except Exception as exc:
        print(f"FAIL: hydrate threw {type(exc).__name__}: {exc}")
        failures.append("hydrate_failed")
        return 1 if failures else 0

    _hr("3. base_price bug check on first 3 variants")
    sample = ingest.variants[:3]
    bug_count = 0
    for v in sample:
        backfill = _pick_min_net(v.prices)
        marker = "BUG" if v.base_price is None else "ok "
        if v.base_price is None:
            bug_count += 1
        print(
            f"  [{marker}] sku={v.sku!r:>15} color={v.color!r:>15} size={v.size!r:>6} "
            f"base_price={v.base_price!s:>6}  min_net_would_set={backfill!s}"
        )
    if bug_count:
        print(
            f"  CONFIRMED: {bug_count}/{len(sample)} variants have base_price=None. "
            "Spec fix in ps_normalizer_v2.merge_pricing is required."
        )
        failures.append("base_price_none_bug")
    else:
        print("  No bug observed — base_price already set. Spec fix may not be needed.")

    _hr("4. Inventory bug check (SOAP not called)")
    has_inv = any(v.inventory is not None for v in ingest.variants)
    if not has_inv:
        print("  CONFIRMED: variant.inventory is None for all variants.")
        print("  Spec fix: wire SanMar Inventory v200 SOAP into adapter.hydrate.")
        failures.append("inventory_soap_not_called")
    else:
        print("  Inventory present — adapter may already call Inventory v200.")

    _hr("5. Image presence")
    if ingest.images:
        print(f"  {len(ingest.images)} images. First URL: {ingest.images[0].url[:80]}")
    else:
        print("  WARN: no images. SanMar primaryImageUrl + MediaContent may have failed.")

    _hr("6. Load VG OPS customer row")
    async with async_session() as db:
        q = select(Customer)
        if customer_filter:
            q = q.where(Customer.name == customer_filter)
        customer = (await db.execute(q.limit(1))).scalar_one_or_none()
    if not customer:
        print("FAIL: no Customer row found (use --customer-name to filter).")
        return 2
    secret = (customer.ops_auth_config or {}).get("client_secret", "")
    print(f"  customer={customer.name!r}  id={customer.id}")
    print(f"  ops_base_url={customer.ops_base_url!r}")
    print(f"  ops_token_url={customer.ops_token_url!r}")
    print(f"  ops_client_id_set={bool(customer.ops_client_id)}  client_secret_set={bool(secret)}")
    missing_fields = [
        f
        for f, v in {
            "ops_base_url": customer.ops_base_url,
            "ops_token_url": customer.ops_token_url,
            "ops_client_id": customer.ops_client_id,
            "ops_auth_config.client_secret": secret,
        }.items()
        if not v
    ]
    if missing_fields:
        print(f"FAIL: missing fields: {missing_fields}")
        failures.append("customer_creds_incomplete")
        return 1

    _hr("7. OAuth2 client_credentials probe (no OPS write)")
    access_token: str | None = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.post(
                customer.ops_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": customer.ops_client_id,
                    "client_secret": secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code == 200:
            access_token = resp.json().get("access_token")
            tlen = len(access_token or "")
            print(f"  OK 200. access_token length={tlen}.")
        else:
            print(f"FAIL: token endpoint returned {resp.status_code}: {resp.text[:200]}")
            failures.append("oauth2_failed")
    except Exception as exc:
        print(f"FAIL: OAuth2 threw {type(exc).__name__}: {exc}")
        failures.append("oauth2_threw")

    _hr("8. Sample setProduct mutation body (NOT sent)")
    push_prefix = sanmar.push_name_prefix or "VG-"
    mutation_body = _sample_set_product_mutation(
        supplier_sku=ingest.supplier_sku,
        product_name=ingest.product_name,
        push_prefix=push_prefix,
    )
    print("  Endpoint that WOULD be hit:")
    print(f"    POST {customer.ops_base_url}/graphql")
    print("  Headers:")
    print('    Authorization: Bearer ***')
    print('    Content-Type: application/json')
    print("  Body:")
    print(json.dumps(mutation_body, indent=2))

    _hr("9. Sample setProductPrice for variants[0] (NOT sent)")
    if ingest.variants:
        v0 = ingest.variants[0]
        backfilled = _pick_min_net(v0.prices)
        markup_pct = Decimal("50.0")
        final = (backfilled or Decimal("0")) * (Decimal("1") + markup_pct / Decimal("100"))
        print(
            json.dumps(
                {
                    "query": (
                        "mutation setProductPrice($input: ProductPriceInput!){ "
                        "setProductPrice(input:$input){ status message } "
                        "}"
                    ),
                    "variables": {
                        "input": {
                            "product_price_id": 0,
                            "products_id": "<from setProduct response>",
                            "qty": 1,
                            "qty_to": 999999,
                            "vendor_price": str(backfilled) if backfilled else None,
                            "price": str(final.quantize(Decimal("0.01"))),
                            "size_id": 0,
                            "visible": "1",
                        }
                    },
                },
                indent=2,
            )
        )

    _hr("Summary")
    if failures:
        print(f"  ✗ {len(failures)} check(s) failed: {failures}")
        print("  These confirm the bugs documented in the design spec.")
    else:
        print("  ✓ all credential + reachability checks passed.")
        print("  Pipeline is unblocked from a credentials standpoint.")
    print(
        "\n  Note: this script never wrote to OPS. The mutations above are "
        "preview-only, matching what payload_builder will emit."
    )
    return 1 if failures else 0


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sku", default="PC61", help="SanMar style number (default: PC61)")
    ap.add_argument(
        "--customer-name",
        default=None,
        help="Customer name to match (default: first row in customers table).",
    )
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(sku=args.sku, customer_filter=args.customer_name))


if __name__ == "__main__":
    sys.exit(main())
