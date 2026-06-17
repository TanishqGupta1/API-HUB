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

import logging

from .client import OpsGraphQLClient, OpsResult

log = logging.getLogger(__name__)


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


async def create_product_category(
    *,
    client: OpsGraphQLClient,
    category_name: str,
    external_ref: str | None = None,
    parent_id: int = -1,
    status: str = "1",
    sort_order: int = 0,
) -> OpsResult:
    """Create an OPS storefront category and return its new id.

    Used by the gateway's auto-category resolver to create-on-first-use the
    category matching a product's category name. Returns
    OpsResult(ok=True, data={"category_id": <int>}) on success, or an error
    OpsResult (caller falls back to the customer default category).
    """
    inp: dict = {
        "category_id": 0,  # 0 = insert
        "category_name": category_name,
        "parent_id": parent_id,  # -1 = root level
        "status": status,        # "1" = active/visible in storefront
        "sort_order": sort_order,
        "delete": 0,
    }
    if external_ref:
        inp["external_ref"] = external_ref
    result = await client.execute(_SET_PRODUCT_CATEGORY, variables={"inputs": [inp]})
    if not result.ok:
        return result
    data = _unwrap_list(result.data, "setProductCategory")
    rejected = _check_result(data, "setProductCategory")
    if rejected is not None:
        return rejected
    return OpsResult(ok=True, data={"category_id": data.get("id")}, raw=result.raw)


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
# Also used post-push by _verify_post_push to confirm the write persisted, and
# by the setProduct-null-id fallback in execute_push.
#
# IMPORTANT (confirmed against the client's Postman collection, 2026-06-15):
# OPS has NO reverse "find product by SKU" query. The `products` query filters
# only by products_id (plus limit/offset) — there is no main_sku/external_ref
# filter. So we PAGINATE the catalog and match client-side on external_ref
# (our own back-reference, written on setProduct) first, then main_sku.
#
# Cost note: this scan runs whenever a push has no push_mapping yet (first push
# of a product, or crash recovery). For very large OPS catalogs a bulk onboarding
# does one scan per product — acceptable for now; a cached external_ref→id map or
# the reconciliation job (docs/backlog-ops-additional-options.md) is the follow-up
# optimization if it becomes a bottleneck.

_PRODUCTS_LIST = """
query products ($limit: Int, $offset: Int) {
  products (limit: $limit, offset: $offset) {
    products {
      product_id
      main_sku
      external_ref
    }
    totalProducts
    currentCount
  }
}
""".strip()


async def get_product_by_sku(
    *,
    client: OpsGraphQLClient,
    products_sku: str,
    page_size: int = 200,
    max_pages: int = 50,
) -> OpsResult:
    """Find an existing OPS product whose external_ref or main_sku == products_sku.

    Paginates the `products` query (OPS has no server-side SKU filter) and
    matches client-side. Returns:
      - OpsResult(ok=True, data={"products_id": <int>})  on a match
      - OpsResult(ok=True, data={})                       when not found
      - the upstream error OpsResult                      if a page query fails

    Callers must check result.ok AND result.data.get('products_id').
    A missing products_id is a successful 'not found', not a failure.
    """
    offset = 0
    for _page in range(max_pages):
        result = await client.execute(
            _PRODUCTS_LIST, variables={"limit": page_size, "offset": offset}
        )
        if not result.ok:
            return result
        block = (result.data or {}).get("products") or {}
        rows = block.get("products") or []
        if not rows:
            break
        for row in rows:
            ref = row.get("external_ref")
            msku = row.get("main_sku")
            if (ref and str(ref) == products_sku) or (msku and str(msku) == products_sku):
                return OpsResult(
                    ok=True,
                    data={"products_id": row.get("product_id")},
                    raw=result.raw,
                )
        total = block.get("totalProducts")
        offset += page_size
        if total is not None and offset >= int(total):
            break
    else:
        # Loop ran the full max_pages without a `break` → the catalog may be
        # larger than we scanned, so a real match could have been missed.
        # Surface it so a silent "not found" can't mask a truncated scan.
        log.warning(
            "dedup scan reached max_pages=%d (page_size=%d) without finding sku=%s",
            max_pages, page_size, products_sku,
        )
    return OpsResult(ok=True, data={})


# ── set_product_sku ──────────────────────────────────────────────────────────
#
# Registers per-size (size_wise) or per-size×option (size_option_wise) variant
# SKUs in OPS. Must be called AFTER setProductSize and BEFORE updateProductStock.
# Inputs come from getProductSkuMatrix — pass the size_id / attribute_ids from
# the matrix so OPS recognises each combo as stock-eligible.
#
# Contract: batch array inputs:[ProductSkuInput!]!
# sku_type MUST match enable_stock_management on the parent product:
#   enable_stock_management=1 ↔ sku_type="size_wise"
#   enable_stock_management=2 ↔ sku_type="size_option_wise"

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


async def set_product_sku(
    *,
    client: OpsGraphQLClient,
    inputs: list[dict],
) -> OpsResult:
    """Register variant SKUs in OPS (batch). Returns OpsResult with raw list.

    Each element in `inputs` must include at minimum:
      products_id, sku_type, size_id (and for size_option_wise: prod_add_opt_ids,
      attribute_ids). Obtain size_id + attribute_ids from get_product_sku_matrix.
    """
    result = await client.execute(_SET_PRODUCT_SKU, variables={"inputs": inputs})
    if not result.ok:
        return result
    rows = (result.data or {}).get("setProductSku") or []
    rejected = [r for r in rows if r.get("result") is False or str(r.get("result", "")).lower() == "false"]
    if rejected:
        msgs = "; ".join(r.get("message") or "rejected" for r in rejected)
        return OpsResult(
            ok=False,
            ops_error_code="OPS_REJECTED",
            ops_error_message=msgs[:400],
            raw=result.raw,
        )
    return OpsResult(ok=True, data={"setProductSku": rows}, raw=result.raw)


# ── get_product_sku_matrix ────────────────────────────────────────────────────
#
# Returns the valid size / size×option combinations for a product. Use this
# BEFORE setProductSku to get the size_id / attribute_ids pairs that OPS will
# accept. Without this step, setProductSku calls land on invalid combos and
# updateProductStock later fails with "Invalid Product SKU".
#
# prod_add_opt_ids: omit (or pass None) for size-wise matrix (one row per size);
#                  pass comma-separated option ids for size×option matrix.

_GET_PRODUCT_SKU_MATRIX = """
query GetProductSkuMatrix($products_id: Int!, $prod_add_opt_ids: String) {
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
    prod_add_opt_ids: str | None = None,
) -> OpsResult:
    """Fetch the valid size / size×option combos for a product.

    Returns OpsResult.data = {"matrix": [...], "totalRecords": N} on success.
    Pass prod_add_opt_ids (comma-separated) only when sku_type is size_option_wise.
    """
    variables: dict = {"products_id": products_id}
    if prod_add_opt_ids:
        variables["prod_add_opt_ids"] = prod_add_opt_ids
    result = await client.execute(_GET_PRODUCT_SKU_MATRIX, variables=variables)
    if not result.ok:
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
query GetProductStocks($product_id: Int, $limit: Int, $offset: Int) {
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
