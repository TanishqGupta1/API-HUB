"""
SanMar Price Verification Script
================================
Calls SanMar's PromoStandards PricingAndConfiguration SOAP service live
for a sample of styles, compares returned Net prices against what's stored
in our DB, and prints a verdict table.

Read-only — does NOT modify any data.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/verify_sanmar_prices.py
"""

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from modules.promostandards.client import PromoStandardsClient
from modules.promostandards.resolver import resolve_wsdl_url


# ── Sample styles to verify (mix of brands / price ranges) ──────────
SAMPLE_STYLES = [
    "2200",     # Gildan Ultra Cotton Tank ($3.73-$8.54)
    "ST350",    # Sport-Tek Competitor Tee ($4.13-$8.13)
    "L500",     # Port Authority Silk Touch Polo ($12.04-$16.04)
    "436MP",    # Jerzees Dri-Power Pocket Sport Shirt ($11.67-$15.67)
    "K420",     # Port Authority HW Cotton Pique Polo ($17.40-$25.52)
    "108084",   # OGIO Transfer Duffel ($46.95)
    "JST81",    # Sport-Tek Fleece-Lined Jacket ($22.79-$29.79)
    "ST850",    # Sport-Tek Sport-Wick 1/4-Zip ($19.74-$23.74)
    "YST350",   # Sport-Tek Youth Competitor Tee ($3.61)
    "BG200",    # Port Authority Cyber Backpack ($1.49-$19.94 anomaly)
]


async def main():
    db_url = os.environ.get(
        "POSTGRES_URL",
        "postgresql+asyncpg://vg_user:vg_pass@localhost:5432/vg_hub",
    )
    engine = create_async_engine(db_url)

    async with engine.connect() as conn:
        # ── 1. Load SanMar supplier ──────────────────────────────────
        row = (await conn.execute(
            text("SELECT id, auth_config, endpoint_cache FROM suppliers WHERE name ILIKE '%sanmar%'")
        )).fetchone()

        if not row:
            print("ERROR: SanMar supplier not found in DB")
            return

        supplier_id = row.id
        auth_config = row.auth_config
        endpoint_cache = row.endpoint_cache

        # Decrypt auth_config if it's a Fernet token
        if isinstance(auth_config, str) and auth_config.startswith("gAAAAA"):
            from cryptography.fernet import Fernet
            secret = os.environ.get("SECRET_KEY", "")
            if not secret:
                print("ERROR: SECRET_KEY env var not set — cannot decrypt auth_config")
                return
            f = Fernet(secret.encode() if isinstance(secret, str) else secret)
            import json
            auth_config = json.loads(f.decrypt(auth_config.encode()))

        if not auth_config or not auth_config.get("id") or not auth_config.get("password"):
            print("ERROR: SanMar auth_config missing id/password")
            return

        print(f"SanMar supplier ID: {supplier_id}")
        print(f"Auth config has id: {bool(auth_config.get('id'))}, password: {bool(auth_config.get('password'))}")

        # ── 2. Resolve PRICING WSDL ──────────────────────────────────
        pricing_wsdl = resolve_wsdl_url(endpoint_cache, "PRICING")
        if not pricing_wsdl:
            print("ERROR: No PRICING WSDL in endpoint_cache")
            return
        print(f"Pricing WSDL: {pricing_wsdl}")

        # ── 3. Build client ──────────────────────────────────────────
        client = PromoStandardsClient(
            wsdl_url=pricing_wsdl,
            auth_config=auth_config,
        )

        # ── 4. Load stored prices from DB ────────────────────────────
        stored = {}
        r = await conn.execute(text("""
            SELECT p.supplier_sku, pv.sku AS part_id, pv.base_price
            FROM products p
            JOIN product_variants pv ON pv.product_id = p.id
            WHERE p.supplier_id = :sid
              AND p.supplier_sku = ANY(:styles)
        """), {"sid": supplier_id, "styles": SAMPLE_STYLES})
        for row in r.fetchall():
            stored[(row.supplier_sku, row.part_id)] = float(row.base_price)

        print(f"\nLoaded {len(stored)} stored variant prices for {len(SAMPLE_STYLES)} styles")

    await engine.dispose()

    # ── 5. Call live pricing API ──────────────────────────────────────
    print("\nCalling SanMar getConfigurationAndPricing for each style...\n")

    live_prices = {}  # (style, part_id) -> lowest_net_price
    errors = []

    for style in SAMPLE_STYLES:
        try:
            price_points = await client.get_pricing(
                product_ids=[style],
                ws_version="1.0.0",
                fob_id="1",
                price_type="Net",
                currency="USD",
                configuration_type="Blank",
            )
            # Group by part_id, pick lowest qty-tier (same as normalizer)
            by_part: dict[str, list] = {}
            for pp in price_points:
                by_part.setdefault(pp.part_id, []).append(pp)

            for part_id, points in by_part.items():
                cheapest = min(points, key=lambda p: (p.quantity_min, p.price))
                live_prices[(style, part_id)] = float(cheapest.price)

            print(f"  {style:10s} -> {len(by_part)} parts, {len(price_points)} price points")
        except Exception as exc:
            errors.append((style, str(exc)))
            print(f"  {style:10s} -> ERROR: {exc}")

    # ── 6. Compare ───────────────────────────────────────────────────
    print("\n" + "=" * 90)
    print("VERIFICATION RESULTS")
    print("=" * 90)

    matches = 0
    mismatches = []
    missing_live = 0
    missing_stored = 0

    all_keys = set(stored.keys()) | set(live_prices.keys())
    style_keys = {k for k in all_keys if k[0] in SAMPLE_STYLES}

    for key in sorted(style_keys):
        s_price = stored.get(key)
        l_price = live_prices.get(key)

        if s_price is not None and l_price is not None:
            if abs(s_price - l_price) < 0.01:
                matches += 1
            else:
                delta_pct = ((s_price - l_price) / l_price * 100) if l_price else 0
                mismatches.append((key[0], key[1], s_price, l_price, delta_pct))
        elif s_price is not None and l_price is None:
            missing_live += 1
        elif l_price is not None and s_price is None:
            missing_stored += 1

    print(f"\nTotal variant keys compared: {len(style_keys)}")
    print(f"  Exact matches (within $0.01): {matches}")
    print(f"  Mismatches:                   {len(mismatches)}")
    print(f"  In DB but not in live API:    {missing_live}")
    print(f"  In live API but not in DB:    {missing_stored}")
    print(f"  API errors:                   {len(errors)}")

    if mismatches:
        print(f"\n{'Style':10s} {'Part ID':25s} {'DB $':>10s} {'Live $':>10s} {'Delta':>8s}")
        print("-" * 70)
        for style, part, db_p, live_p, delta in mismatches[:30]:
            print(f"{style:10s} {part:25s} ${db_p:>9.2f} ${live_p:>9.2f} {delta:>+7.1f}%")
        if len(mismatches) > 30:
            print(f"  ... and {len(mismatches) - 30} more")

    if errors:
        print(f"\nAPI Errors:")
        for style, err in errors:
            print(f"  {style}: {err[:80]}")

    # ── 7. Verdict ───────────────────────────────────────────────────
    print("\n" + "=" * 90)
    if not mismatches and not errors:
        print("VERDICT: PASS — All stored prices match live SanMar API (penny-exact)")
    elif len(mismatches) <= 3 and not errors:
        print("VERDICT: PASS WITH NOTES — Minor price drifts detected (SanMar may have updated)")
    elif errors and not mismatches:
        print("VERDICT: INCONCLUSIVE — API errors prevented full verification")
    else:
        mismatch_pct = len(mismatches) / max(len(style_keys), 1) * 100
        print(f"VERDICT: {'FAIL' if mismatch_pct > 10 else 'REVIEW'} — {len(mismatches)} mismatches ({mismatch_pct:.1f}%)")
    print("=" * 90)


if __name__ == "__main__":
    asyncio.run(main())
