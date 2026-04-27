# SanMar PromoStandards Smoke Test — Runbook

One-time manual steps to validate the `PromoStandardsClient` against SanMar
production SOAP endpoints using real credentials supplied by SanMar Integration
Support.

## Prerequisites

- PostgreSQL running: `docker compose up -d postgres`
- Backend deps installed: `cd backend && source .venv/bin/activate && pip install -r requirements.txt`
- Client patches landed (commits from Tasks 1–5 of the smoke-test plan)
- SanMar credentials in hand: SanMar Customer Number, SanMar.com username, SanMar.com password

## Step 1 — Create the SanMar Supplier row via UI

1. Start the stack:

   ```bash
   cd api-hub
   docker compose up -d postgres n8n
   cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000 &
   cd ../frontend && npm run dev &
   ```

2. Open `http://localhost:3000/suppliers` in a browser.
3. Click **Add supplier** and fill in:
   - **Name:** `SanMar`
   - **Slug:** `sanmar`
   - **Protocol:** `promostandards`
   - **PromoStandards code:** `SANM`
   - **Auth config (JSON):**

     ```json
     {"id": "<SanMar.com username>", "password": "<SanMar.com password>"}
     ```

   - **Is active:** yes
4. Save. The backend encrypts `auth_config` via the `EncryptedJSON` column type.

**Alternative:** instead of the UI, set `SANMAR_ID` + `SANMAR_PASSWORD` in
`api-hub/.env`. The script prefers env values over the DB when both are
present.

## Step 2 — Seed the endpoint cache (optional)

The smoke script hardcodes the four SanMar WSDL URLs, so this step is only
needed if you later wire SanMar into the generic `POST /api/sync/:id/*` route
path. Seed via SQL:

```bash
psql -h localhost -U vg_user -d vg_hub <<'SQL'
UPDATE suppliers
SET endpoint_cache = '[
  {"ServiceType": "Product Data", "ProductionURL": "https://ws.sanmar.com:8080/promostandards/ProductDataServiceV2.xml?wsdl"},
  {"ServiceType": "Inventory Levels", "ProductionURL": "https://ws.sanmar.com:8080/promostandards/InventoryServiceBindingV2final?WSDL"},
  {"ServiceType": "Media Content", "ProductionURL": "https://ws.sanmar.com:8080/promostandards/MediaContentServiceBinding?wsdl"},
  {"ServiceType": "Product Pricing and Configuration", "ProductionURL": "https://ws.sanmar.com:8080/promostandards/PricingAndConfigurationServiceBinding?WSDL"}
]'::jsonb
WHERE slug='sanmar';
SQL
```

## Step 3 — Run the smoke script

```bash
cd api-hub/backend && source .venv/bin/activate
python scripts/sanmar_smoke.py
```

Expected output (real values will differ):

```
=== PC61 ===
  [PRODUCT] name='Essential Tee' brand='Port & Company' parts=300+ cats=['T-Shirts']
  [INVENTORY] 300+ part-level records
    part=PC61-NVY-M qty=12345 primary_wh='Dallas'
    ...
  [MEDIA] 15+ urls
    Front: https://cdnl.sanmar.com/imglib/mresjpg/...
    ...
  [PRICING] 300+ price points
    part=PC61-NVY-M price=3.99 min_qty=1
    ...

=== K420 ===
  ...

=== Summary: 16/16 calls passed ===
```

Exit code `0` means all calls landed. Anything non-zero means at least one
service returned a SOAP fault, empty response, or parse error — check the
corresponding `FAIL:` line in the output.

## Step 4 — Test environment variant

To hit `test-ws.sanmar.com` instead of production (optional; test env may be
offline during SanMar internal maintenance):

```bash
python scripts/sanmar_smoke.py --test
```

## Step 5 — Override SKU list

Either positional or repeated `--sku`:

```bash
python scripts/sanmar_smoke.py PC61 K420
python scripts/sanmar_smoke.py --sku PC61 --sku K420
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `[ERROR] auth_config missing id/password` | Supplier row exists but creds blank, and no env override | Re-save creds via `/suppliers` UI or set `SANMAR_ID` + `SANMAR_PASSWORD` in `.env` |
| `[PRODUCT] FAIL: ... authenticating failed` | Wrong username/password | Verify credentials with SanMar; confirm SanMar.com account (not FTP) |
| `[INVENTORY] FAIL: Connection refused` | WSDL unreachable | Check network; confirm port 8080 isn't firewalled |
| `[PRICING] FAIL: ... fobId required` | Client patches missing | Verify Tasks 1–5 landed: `git log --oneline backend/modules/promostandards/client.py` |
| `[MEDIA] 0 urls` but product exists | Wrong `mediaType` or account flag | Try `media_type="Document"`; contact SanMar integrations |
| `RuntimeError: Supplier slug='sanmar' not found` | Supplier row never created | Follow Step 1 |

## Next Steps

Once all four SKUs report `16/16 calls passed`, the client is SanMar-ready.
Next plan: wire the SanMar supplier into the existing `POST /api/sync/{id}/products`
route path for a real catalog pull, then run a bounded sync against ~50 SKUs
before opening the gate to the full catalog.
