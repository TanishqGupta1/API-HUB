"""Standalone repro for the OPS staging setProduct INTERNAL_SERVER_ERROR.

No database. No FastAPI. Reads credentials from environment variables.

Usage:
    export OPS_BASE_URL=https://staging.visualgraphx.com
    export OPS_TOKEN_URL=https://staging.visualgraphx.com/api/oauth/token
    export OPS_CLIENT_ID=2190fd7c-596b-11ef-9e9f-06bd824fb541
    export OPS_CLIENT_SECRET=<your_secret>
    python backend/scripts/repro_setproduct_500.py

What it does:
    Step 1 — fetches an OAuth2 token (confirms auth works)
    Step 2 — calls setProductCategory (confirms token has write permissions)
    Step 3 — calls setProduct with the same minimal payload that 500s (the bug)

Expected outcome if the bug is NOT fixed:
    Step 1: OK
    Step 2: OK  (category created)
    Step 3: FAIL — INTERNAL_SERVER_ERROR

Expected outcome if the bug IS fixed:
    Step 1: OK
    Step 2: OK
    Step 3: OK  (product created, products_id returned)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import httpx


# ── Config from env ──────────────────────────────────────────────────────────

BASE_URL    = os.environ.get("OPS_BASE_URL",    "https://staging.visualgraphx.com")
TOKEN_URL   = os.environ.get("OPS_TOKEN_URL",   f"{BASE_URL}/api/oauth/token")
CLIENT_ID   = os.environ.get("OPS_CLIENT_ID",   "")
CLIENT_SECRET = os.environ.get("OPS_CLIENT_SECRET", "")

GRAPHQL_URL = f"{BASE_URL.rstrip('/')}/api/"


# ── GraphQL strings ──────────────────────────────────────────────────────────

_SET_PRODUCT_CATEGORY = """
mutation SetProductCategory($inputs: [ProductCategoryInput!]!) {
  setProductCategory(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()

# OPS uses array-input mutations: $inputs (plural), not $input.
_SET_PRODUCT = """
mutation SetProduct($inputs: [ProductInput!]!) {
  setProduct(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _print_step(n: int, label: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  Step {n}: {label}")
    print(f"{'─' * 60}")


def _print_response(resp: httpx.Response | None, body: dict | None) -> None:
    if resp is not None:
        print(f"  HTTP {resp.status_code}  ({resp.elapsed.total_seconds():.2f}s)")
    if body is not None:
        print(f"  Body: {json.dumps(body, indent=2)}")


def _check_env() -> bool:
    missing = [v for v in ("OPS_CLIENT_ID", "OPS_CLIENT_SECRET") if not os.environ.get(v)]
    if missing:
        print(f"ERROR: missing env vars: {', '.join(missing)}")
        print("Set them and re-run:")
        print("  export OPS_CLIENT_ID=<id>")
        print("  export OPS_CLIENT_SECRET=<secret>")
        return False
    return True


# ── Main flow ────────────────────────────────────────────────────────────────

async def main() -> int:
    if not _check_env():
        return 1

    print(f"\nOPS repro script — setProduct INTERNAL_SERVER_ERROR")
    print(f"  Base URL : {BASE_URL}")
    print(f"  Token URL: {TOKEN_URL}")
    print(f"  GraphQL  : {GRAPHQL_URL}")
    print(f"  Client ID: {CLIENT_ID}")

    async with httpx.AsyncClient(timeout=30.0) as http:

        # ── Step 1: OAuth2 token ─────────────────────────────────────────────
        _print_step(1, "Fetch OAuth2 token (client_credentials, JSON body)")
        token_resp = await http.post(
            TOKEN_URL,
            json={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
        try:
            token_body = token_resp.json()
        except Exception:
            token_body = {"raw": token_resp.text[:300]}

        _print_response(token_resp, token_body)

        token = token_body.get("access_token")
        if not token:
            print("\nFAIL — could not get token. Check CLIENT_ID / CLIENT_SECRET.")
            return 1
        print(f"\n  OK — token obtained ({token[:20]}…)")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # ── Step 2: setProductCategory (should succeed) ──────────────────────
        _print_step(2, "setProductCategory — confirms auth + write permissions")
        cat_payload = {
            "query": _SET_PRODUCT_CATEGORY,
            "variables": {
                "inputs": [{"category_name": "REPRO-TEST", "visible": 1}]
            },
        }
        cat_resp = await http.post(GRAPHQL_URL, headers=headers, json=cat_payload)
        cat_body = cat_resp.json()
        _print_response(cat_resp, cat_body)

        cat_errors = cat_body.get("errors")
        cat_data = (cat_body.get("data") or {}).get("setProductCategory") or {}
        if cat_errors:
            print(f"\n  UNEXPECTED FAIL — setProductCategory errored: {cat_errors}")
        elif isinstance(cat_data, list):
            item = cat_data[0] if cat_data else {}
            cat_id = item.get("id")
            print(f"\n  OK — category created, id={cat_id}")
        else:
            cat_id = cat_data.get("id") if isinstance(cat_data, dict) else None
            print(f"\n  OK (or unexpected shape) — id={cat_id}")

        # ── Step 3: setProduct minimal (reproduces the 500) ──────────────────
        _print_step(3, "setProduct — minimal payload (this is the bug)")
        prod_payload = {
            "query": _SET_PRODUCT,
            "variables": {
                "inputs": [{
                    "category_id": 0,
                    "visible": 1,
                    "products_title": "REPRO-TEST-PRODUCT",
                    "products_internal_title": "REPRO001",
                    "price_defining_method": "1",
                    "user_type_id": "1",
                }]
            },
        }
        print(f"\n  Request variables:")
        print(f"  {json.dumps(prod_payload['variables'], indent=4)}")

        prod_resp = await http.post(GRAPHQL_URL, headers=headers, json=prod_payload)
        prod_body = prod_resp.json()
        _print_response(prod_resp, prod_body)

        prod_errors = prod_body.get("errors")
        prod_data = (prod_body.get("data") or {}).get("setProduct")

        print()
        if prod_errors:
            first_err = prod_errors[0]
            code = first_err.get("extensions", {}).get("code", "unknown")
            msg  = first_err.get("message", "")
            print(f"  RESULT: FAIL — {code}: {msg}")
            if code == "INTERNAL_SERVER_ERROR":
                print()
                print("  *** Bug confirmed. OPS server-side error — check the Express")
                print("  *** app-server log for the real exception. Search for:")
                print(f"  ***   products_internal_title = REPRO001")
                print(f"  ***   OAuth client_id         = {CLIENT_ID}")
            return 1
        elif prod_data:
            if isinstance(prod_data, list):
                item = prod_data[0] if prod_data else {}
            else:
                item = prod_data
            if item.get("result") is False:
                print(f"  RESULT: OPS_REJECTED — {item.get('message')}")
                return 1
            pid = item.get("id") or item.get("products_id")
            print(f"  RESULT: OK — product created, id={pid}")
            print()
            print("  *** Bug is FIXED. Update the team and enable the push pipeline.")
            return 0
        else:
            print(f"  RESULT: unexpected response shape — {prod_body}")
            return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
