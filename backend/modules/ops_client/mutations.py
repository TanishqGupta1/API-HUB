"""OPS GraphQL mutation + query constants — single source of truth for all OPS query strings.

The gateway (modules/ops_push/gateway.py) dispatches plan steps via _MUTATION_DISPATCH,
which maps mutation names to (query_string, response_root_key) pairs defined here.

_check_result and _unwrap_list are utility helpers available to any caller that
receives a raw OPS response dict and needs to detect application-level rejection
(HTTP 200 + result:false) or unwrap array-input responses.

Queries:
  get_product_by_sku — dedup / post-push verify (called from gateway via _dedup_lookup_in_ops)
"""
from __future__ import annotations

from .client import OpsGraphQLClient, OpsResult


# ── set_product_category ─────────────────────────────────────────────────────

_SET_PRODUCT_CATEGORY = """
mutation SetProductCategory($inputs: [ProductCategoryInput!]!) {
  setProductCategory(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()


def _unwrap_list(data: dict | None, key: str) -> dict:
    """Unwrap a list response (array-input mutations return a list) → first item."""
    val = (data or {}).get(key)
    if isinstance(val, list):
        val = val[0] if val else {}
    return val or {}


def _check_result(data: dict, mutation_name: str) -> OpsResult | None:
    """Detect OPS application-level failures (HTTP 200 with `result: false`).

    Background — Phase 1.1 of the OPS audit:
      OPS returns 200 OK with `{result: false, message: "...", id: null}`
      when a mutation is rejected at the application layer (missing required
      field, invalid value, etc.). Without this check the caller treats the
      response as success, the gateway records the step as `ok`, and the
      downstream id-threading silently drops to None — producing phantom
      "successful" pushes like PC54 (id 10001) that don't actually exist
      in OPS.

    Returns:
      An error `OpsResult` when `result is False`, else `None` (success path).
    """
    # `result` may come back as bool or string from different OPS deployments.
    # Treat both False (bool) and "false" (string) as the rejection signal.
    result_val = data.get("result")
    is_rejected = (
        result_val is False
        or (isinstance(result_val, str) and result_val.lower() == "false")
    )
    if is_rejected:
        msg = data.get("message") or f"OPS rejected {mutation_name}"
        return OpsResult(
            ok=False,
            ops_error_code="OPS_REJECTED",
            ops_error_message=str(msg)[:400],
            raw={"mutation": mutation_name, "ops_response": data},
        )
    return None


# ── set_product ──────────────────────────────────────────────────────────────

_SET_PRODUCT = """
mutation SetProduct($inputs: [ProductInput!]!) {
  setProduct(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()


# ── set_products_image_gallery ───────────────────────────────────────────────

_SET_PRODUCTS_IMAGE_GALLERY = """
mutation SetProductsImageGallery($products_id: Int!, $optimizeimg: Int, $input: ProductsImageGalleryBulkInput!) {
  setProductsImageGallery(products_id: $products_id, optimizeimg: $optimizeimg, input: $input) {
    result
    message
  }
}
""".strip()


# ── set_product_size ─────────────────────────────────────────────────────────

_SET_PRODUCT_SIZE = """
mutation SetProductSize($inputs: [ProductSizeInput!]!) {
  setProductSize(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()


# ── set_product_price ────────────────────────────────────────────────────────

_SET_PRODUCT_PRICE = """
mutation SetProductPrice($inputs: [ProductPriceInput!]!) {
  setProductPrice(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()


# ── set_assign_options ───────────────────────────────────────────────────────

_SET_ASSIGN_OPTIONS = """
mutation SetAssignOptions($inputs: [AssignOptionsInput!]!) {
  setAssignOptions(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()


# ── set_additional_option ────────────────────────────────────────────────────

_SET_ADDITIONAL_OPTION = """
mutation SetAdditionalOption($inputs: [AdditionalOptionInput!]!) {
  setAdditionalOption(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()


# ── set_additional_option_attributes ─────────────────────────────────────────

_SET_ADDITIONAL_OPTION_ATTRIBUTES = """
mutation SetAdditionalOptionAttributes($inputs: [AdditionalOptionAttributesInput!]!) {
  setAdditionalOptionAttributes(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()


# ── set_products_attribute_price ─────────────────────────────────────────────

_SET_PRODUCTS_ATTRIBUTE_PRICE = """
mutation SetProductsAttributePrice($inputs: [ProductsAttributePriceInput!]!) {
  setProductsAttributePrice(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()


# ── update_product_stock ─────────────────────────────────────────────────────

_UPDATE_PRODUCT_STOCK = """
mutation UpdateProductStock($stock_id: Int, $product_sku: String, $action: UpdateProductStockActionEnum!, $input: UpdateProductStockInput!) {
  updateProductStock(stock_id: $stock_id, product_sku: $product_sku, action: $action, input: $input) {
    result
    message
    id
    stock_quantity
  }
}
""".strip()


# ── set_product_design ───────────────────────────────────────────────────────
# Dormant — real OPS schema differs from this stub; needs a rewrite before use.

_SET_PRODUCT_DESIGN = """
mutation SetProductDesign($input: setProductDesign_input!) {
  setProductDesign(input: $input) {
    products_id
  }
}
""".strip()


# ── get_product_by_sku (dedup / post-push verify) ────────────────────────────
#
# Used pre-push (_dedup_lookup_in_ops) to ask OPS whether it already has a
# product with this SKU, so a retry of a failed push doesn't create a duplicate.
# Also used post-push by _verify_post_push to confirm the write persisted.
#
# Schema is PROVISIONAL — confirm against the OPS Postman collection when
# Christian shares it. The function returns Optional[int] (products_id) so
# the dedup caller never sees raw schema details.

_GET_PRODUCT_BY_SKU = """
query GetProductBySku($products_sku: String!) {
  getProductBySku(products_sku: $products_sku) {
    products_id
    products_sku
  }
}
""".strip()


async def get_product_by_sku(
    *,
    client: OpsGraphQLClient,
    products_sku: str,
) -> OpsResult:
    """Look up an existing OPS product by SKU. Returns data dict containing
    products_id when found, or an empty dict when not found.

    Callers must check result.ok AND result.data.get('products_id').
    A missing products_id is a successful 'not found', not a failure.
    """
    result = await client.execute(
        _GET_PRODUCT_BY_SKU,
        variables={"products_sku": products_sku},
    )
    if not result.ok:
        return result
    payload = (result.data or {}).get("getProductBySku") or {}
    return OpsResult(ok=True, data=payload, raw=result.raw)


# ── get_product_stocks (Phase 6 — stock_id read-back) ───────────────────────
#
# OPS's updateProductStock requires either stock_id or product_sku to identify
# the variant. The catch:
#   * There is no per-size SKU field anywhere in OPS's product / size schema;
#     OPS appears to assume SKUs were assigned via the admin UI.
#   * stock entries (stock_id rows) only exist for variants where an admin
#     manually initialized stock through the OPS UI. They are NOT auto-created
#     by setProductSize or by enabling enable_stock_management.
#
# This query lets the gateway read the existing stock entries for a product
# after setProductSize completes, then thread the stock_id into each
# updateProductStock step (instead of the supplier SKU that OPS doesn't know
# about). Variants without a stock entry are skipped with an actionable
# warning so an operator can initialize them in OPS admin.

_GET_PRODUCT_STOCKS = """
query GetProductStocks($product_id: Int!, $limit: Int, $offset: Int) {
  productStocks(product_id: $product_id, limit: $limit, offset: $offset) {
    productStocks {
      stock_id
      size_id
      size_title
      stock_quantity
    }
  }
}
""".strip()


async def get_product_stocks(
    *,
    client: OpsGraphQLClient,
    product_id: int,
    limit: int = 500,
) -> OpsResult:
    """Return the list of existing OPS stock entries for a product.

    Returns ``OpsResult.data = {"productStocks": [...]}`` on success
    (possibly empty list when no entries exist). The "Data not found"
    error OPS returns for products with zero stock entries is mapped to
    an empty list so callers don't need to special-case the error path.
    """
    result = await client.execute(
        _GET_PRODUCT_STOCKS, variables={"product_id": product_id, "limit": limit, "offset": 0},
    )
    if not result.ok:
        # OPS returns DATA_NOT_FOUND when no stock entries exist — treat
        # as "empty list" so callers can iterate cleanly.
        if (result.ops_error_code or "") == "DATA_NOT_FOUND":
            return OpsResult(ok=True, data={"productStocks": []}, raw=result.raw)
        return result
    payload = (result.data or {}).get("productStocks") or {}
    return OpsResult(
        ok=True,
        data={"productStocks": payload.get("productStocks") or []},
        raw=result.raw,
    )
