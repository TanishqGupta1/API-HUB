"""OPS GraphQL mutation wrappers.

Each function wraps one OPS GraphQL mutation. They all:
1. Accept an OpsGraphQLClient instance
2. Build the GraphQL query string + variables
3. Call client.execute() and return an OpsResult
4. Unwrap the inner data so callers get e.g. result.data["category_id"]
   not result.data["setProductCategory"]["category_id"]

These wrappers are called by the push orchestrator (push.py) in sequence,
threading IDs from one step to the next:

    set_product_category → category_id
        ↓
    set_product(category_id) → products_id
        ↓
    set_product_size(products_id) → size_id
        ↓
    set_product_price(products_id, size_id) → done
"""
from __future__ import annotations

from .client import OpsGraphQLClient, OpsResult


# ── T6: set_product_category ────────────────────────────────────────────────

_SET_PRODUCT_CATEGORY = """
mutation SetProductCategory($input: setProductCategory_input!) {
  setProductCategory(input: $input) {
    category_id
  }
}
""".strip()


async def set_product_category(
    *,
    client: OpsGraphQLClient,
    category_name: str,
    parent_id: int = 0,
    visible: int = 1,
) -> OpsResult:
    """Create or update a product category in OPS.

    Returns OpsResult.data = {"category_id": int} on success.
    category_id is passed to set_product() as an input.
    """
    result = await client.execute(
        _SET_PRODUCT_CATEGORY,
        variables={
            "input": {
                "category_name": category_name,
                "parent_id": parent_id,
                "visible": visible,
            }
        },
    )
    if not result.ok:
        return result
    inner = (result.data or {}).get("setProductCategory") or {}
    return OpsResult(ok=True, data=inner, raw=result.raw)


# ── T7: set_product ─────────────────────────────────────────────────────────

_SET_PRODUCT = """
mutation SetProduct($input: setProduct_input!) {
  setProduct(input: $input) {
    products_id
  }
}
""".strip()


async def set_product(
    *,
    client: OpsGraphQLClient,
    category_id: int,
    products_title: str,
    products_internal_title: str,
    visible: int = 1,
) -> OpsResult:
    """Create a product in OPS under the given category.

    Returns OpsResult.data = {"products_id": int} on success.
    products_id is passed to set_product_size() and set_product_price().
    """
    result = await client.execute(
        _SET_PRODUCT,
        variables={
            "input": {
                "category_id": category_id,
                "products_title": products_title,
                "products_internal_title": products_internal_title,
                "visible": visible,
            }
        },
    )
    if not result.ok:
        return result
    inner = (result.data or {}).get("setProduct") or {}
    return OpsResult(ok=True, data=inner, raw=result.raw)


# ── T8: set_product_size ────────────────────────────────────────────────────

_SET_PRODUCT_SIZE = """
mutation SetProductSize($input: setProductSize_input!) {
  setProductSize(input: $input) {
    size_id
  }
}
""".strip()


async def set_product_size(
    *,
    client: OpsGraphQLClient,
    products_id: int,
    size_name: str,
    color_name: str,
    products_sku: str,
    visible: int = 1,
) -> OpsResult:
    """Create one size+color variant for a product in OPS.

    Called once per variant. Returns OpsResult.data = {"size_id": int}.
    size_id is paired 1:1 with set_product_price().
    """
    result = await client.execute(
        _SET_PRODUCT_SIZE,
        variables={
            "input": {
                "products_id": products_id,
                "size_name": size_name,
                "color_name": color_name,
                "products_sku": products_sku,
                "visible": visible,
            }
        },
    )
    if not result.ok:
        return result
    inner = (result.data or {}).get("setProductSize") or {}
    return OpsResult(ok=True, data=inner, raw=result.raw)


# ── T9: set_product_price ───────────────────────────────────────────────────

_SET_PRODUCT_PRICE = """
mutation SetProductPrice($input: setProductPrice_input!) {
  setProductPrice(input: $input) {
    product_price_id
  }
}
""".strip()


async def set_product_price(
    *,
    client: OpsGraphQLClient,
    products_id: int,
    size_id: int,
    price: str,
    vendor_price: str,
    qty: int = 1,
    qty_to: int | None = None,
    visible: int = 1,
) -> OpsResult:
    """Set the price for one variant (size+color) in OPS.

    price / vendor_price are strings to preserve Decimal precision.
    Returns OpsResult.data = {"product_price_id": int} on success.
    """
    input_dict: dict = {
        "products_id": products_id,
        "size_id": size_id,
        "qty": qty,
        "price": price,
        "vendor_price": vendor_price,
        "visible": visible,
    }
    if qty_to is not None:
        input_dict["qty_to"] = qty_to
    result = await client.execute(_SET_PRODUCT_PRICE, variables={"input": input_dict})
    if not result.ok:
        return result
    inner = (result.data or {}).get("setProductPrice") or {}
    return OpsResult(ok=True, data=inner, raw=result.raw)
