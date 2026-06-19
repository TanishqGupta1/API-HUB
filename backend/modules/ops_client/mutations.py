"""OPS GraphQL mutation + query constants — single source of truth for all OPS query strings.

The gateway (modules/ops_push/gateway.py) dispatches plan steps via _MUTATION_DISPATCH,
which maps mutation names to (query_string, response_root_key) pairs defined here.

_check_result and _unwrap_list are utility helpers available to any caller that
receives a raw OPS response dict and needs to detect application-level rejection
(HTTP 200 + result:false) or unwrap array-input responses.

Queries:
  find_product_id_by_main_sku — dedup / post-push verify (gateway _dedup_lookup_in_ops)
  get_product_sku_matrix — valid size/option combos before setProductSku
  get_product_stocks — existing stock entries (stock_id read-back)
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


# ── set_product_sku ──────────────────────────────────────────────────────────
# Assigns a per-variant SKU to an OPS product. sku_type drives which dimension
# the SKU keys on: "size_wise" (size_id only) for products with no options, or
# "size_option_wise" (size_id + prod_add_opt_ids + attribute_ids) when the
# variant maps to option-attributes. prod_add_opt_ids / attribute_ids are
# comma-joined strings; delete=0 to upsert, 1 to remove.

_SET_PRODUCT_SKU = """
mutation SetProductSku($inputs: [ProductSkuInput!]!) {
  setProductSku(inputs: $inputs) {
    index
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


# ── find_product_id_by_main_sku (dedup / post-push verify) ───────────────────
# AI-1: the prior getProductBySku(products_sku) query does NOT exist in OPS —
# it was invented in api-hub and returns empty against the live API, so dedup
# never actually fired in production. The supported way to find an existing
# product by SKU is the `products` query (which exposes main_sku), scanned
# client-side: OPS provides no server-side SKU filter on any query.
#
# Used pre-push (_dedup_lookup_in_ops) so a retry of a crashed push doesn't
# create a duplicate, and post-push by _verify_post_push. Returns the same
# OpsResult shape the old helper did — data={"products_id": <int>} on a match,
# data={} on a clean not-found — so callers are unchanged.

_PRODUCTS_LIST = """
query products($products_id: Int, $limit: Int, $offset: Int) {
  products(products_id: $products_id, limit: $limit, offset: $offset) {
    products {
      product_id
      main_sku
    }
    totalProducts
    currentCount
  }
}
""".strip()


async def find_product_id_by_main_sku(
    *,
    client: OpsGraphQLClient,
    main_sku: str,
    page_size: int = 100,
    max_pages: int = 50,
) -> OpsResult:
    """Find an OPS product whose ``main_sku`` equals ``main_sku``.

    OPS has no server-side SKU filter, so this pages the ``products`` query and
    matches client-side. Bounded by ``max_pages`` (page_size × max_pages =
    5,000 products by default) so a large catalog can't make a push hang; if the
    SKU isn't found within the cap it's reported as a clean not-found and the
    caller proceeds with create.

    Returns:
      * ``OpsResult(ok=True, data={"products_id": int})`` on a match,
      * ``OpsResult(ok=True, data={})`` when not found (caller treats as create),
      * the underlying error ``OpsResult`` if a page query fails.
    """
    if not main_sku:
        return OpsResult(ok=True, data={})
    target = str(main_sku)
    offset = 0
    for _ in range(max_pages):
        result = await client.execute(
            _PRODUCTS_LIST, variables={"limit": page_size, "offset": offset},
        )
        if not result.ok:
            return result
        payload = (result.data or {}).get("products") or {}
        rows = payload.get("products") or []
        if not rows:
            break
        for row in rows:
            if str(row.get("main_sku") or "") == target:
                return OpsResult(
                    ok=True,
                    data={"products_id": row.get("product_id")},
                    raw=result.raw,
                )
        offset += len(rows)
        total = payload.get("totalProducts")
        if total is not None and offset >= int(total):
            break
    return OpsResult(ok=True, data={})


# ── get_product_sku_matrix (AI-2 — valid size/option combos before setProductSku) ─
#
# OPS docs: "Use it to get valid size and option combinations before calling
# setProductSku." Returns the authoritative list of assignable variant slots
# for a product:
#   * No prod_add_opt_ids ("")  → size-wise matrix (one row per size).
#   * With prod_add_opt_ids     → size × option-attribute matrix.
#
# This is the supported replacement for the invented getProductBySku (AI-1):
# it tells us which (size_id, prod_add_opt_ids, attribute_ids) combinations
# OPS will actually accept, so the setProductSku batch only assigns SKUs to
# real slots and stock (updateProductStock) can find them later.
#
# `prod_add_opt_ids` is declared String! (required) in the live schema, so the
# size-wise call passes an empty string rather than omitting the variable.

_GET_PRODUCT_SKU_MATRIX = """
query getProductSkuMatrix($products_id: Int!, $prod_add_opt_ids: String!) {
  getProductSkuMatrix(products_id: $products_id, prod_add_opt_ids: $prod_add_opt_ids) {
    matrix {
      size_id
      prod_add_opt_ids
      attribute_ids
    }
    totalRecords
  }
}
""".strip()


async def get_product_sku_matrix(
    *,
    client: OpsGraphQLClient,
    products_id: int,
    prod_add_opt_ids: str = "",
) -> OpsResult:
    """Return the valid size/option combinations OPS will accept for a product.

    On success ``OpsResult.data = {"matrix": [...], "totalRecords": int}``
    (``matrix`` possibly empty). The "Data not found" error OPS returns for a
    product with no configured combinations yet is mapped to an empty matrix so
    callers don't need to special-case the error path (mirrors
    ``get_product_stocks``).
    """
    result = await client.execute(
        _GET_PRODUCT_SKU_MATRIX,
        variables={"products_id": products_id, "prod_add_opt_ids": prod_add_opt_ids},
    )
    if not result.ok:
        if (result.ops_error_code or "") == "DATA_NOT_FOUND":
            return OpsResult(ok=True, data={"matrix": [], "totalRecords": 0}, raw=result.raw)
        return result
    payload = (result.data or {}).get("getProductSkuMatrix") or {}
    return OpsResult(
        ok=True,
        data={
            "matrix": payload.get("matrix") or [],
            "totalRecords": payload.get("totalRecords") or 0,
        },
        raw=result.raw,
    )


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
