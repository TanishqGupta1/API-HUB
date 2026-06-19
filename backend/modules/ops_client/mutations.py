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
    # Hard safety ceiling only. The scan normally stops far earlier via the
    # `totalProducts` early-exit below; this bound just stops a pathological/huge
    # catalog from looping unboundedly. 1000 × 200 ≈ 200k products — comfortably
    # above real customer catalogs, so a SKU is no longer silently missed (and
    # re-created as a duplicate) at the old 50-page / 10k-product cutoff.
    max_pages: int = 1000,
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
        # Exhausted the hard max_pages ceiling WITHOUT the totalProducts early-exit
        # firing → the catalog is larger than we scanned, so a real match may have
        # been missed. Returning "not found" here makes the push CREATE the product,
        # risking a duplicate — so log at error level: a truncated scan must never
        # hide behind a silent "not found".
        log.error(
            "dedup scan hit hard ceiling max_pages=%d (page_size=%d, ~%d products) "
            "without finding sku=%s — catalog may be larger than scanned; treating "
            "as not-found may create a DUPLICATE. Raise max_pages or add a cached "
            "external_ref→id map.",
            max_pages, page_size, max_pages * page_size, products_sku,
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


# ── products_details (dedup + post-push verify) ─────────────────────────────
#
# The dedup replacement called out in the apparel-push plan: filters by
# products_id and returns full product details including main_sku / external_ref
# (for dedup matching) and the nested product_size / product_additional_options
# arrays (for post-push verify).
#
# Why not just use `products`?
#   `products` returns product_id + main_sku + external_ref only — fine for
#   "does this exist?" but no shape info for verify. `productsDetails` is the
#   richer call when the gateway wants to confirm OPS actually persisted the
#   sizes/options it just sent.

_PRODUCTS_DETAILS = """
query ProductsDetails(
  $products_id: Int
  $limit: Int
  $offset: Int
  $status: Int
  $all_store: Int
  $external_catalogue: Int
) {
  productsDetails(
    products_id: $products_id
    limit: $limit
    offset: $offset
    status: $status
    all_store: $all_store
    external_catalogue: $external_catalogue
  ) {
    products {
      product_id
      product_name
      main_sku
      external_ref
      status
      default_category_id
      product_type
      price_defining_method
      product_size {
        size_id
        size_title
        size_width
        size_height
        default_size
      }
      product_additional_options {
        prod_add_opt_id
        title
        options_type
        option_key
        master_option_id
      }
    }
    totalProducts
    currentCount
  }
}
""".strip()


async def get_products_details(
    *,
    client: OpsGraphQLClient,
    products_id: int | None = None,
    limit: int = 10,
    offset: int = 0,
    status: int | None = None,
    all_store: int | None = None,
    external_catalogue: int | None = None,
) -> OpsResult:
    """Fetch full product details from OPS.

    Returns OpsResult.data = {"products": [...], "totalProducts": N, "currentCount": M}.
    Only the filters explicitly passed are forwarded — passing products_id=0
    would filter for product 0, not "no filter."
    """
    variables: dict = {"limit": limit, "offset": offset}
    if products_id is not None:
        variables["products_id"] = products_id
    if status is not None:
        variables["status"] = status
    if all_store is not None:
        variables["all_store"] = all_store
    if external_catalogue is not None:
        variables["external_catalogue"] = external_catalogue
    result = await client.execute(_PRODUCTS_DETAILS, variables=variables)
    if not result.ok:
        return result
    payload = (result.data or {}).get("productsDetails") or {}
    return OpsResult(
        ok=True,
        data={
            "products": payload.get("products") or [],
            "totalProducts": payload.get("totalProducts") or 0,
            "currentCount": payload.get("currentCount") or 0,
        },
        raw=result.raw,
    )


# ── product_category (list / lookup OPS categories) ─────────────────────────
#
# Read-side companion to set_product_category. Operators may need to discover
# existing OPS category ids before mapping a customer/product to them — the
# category_resolvable preflight check currently fails closed when no mapping
# exists, and this query is how the operator finds the right id without
# clicking through the OPS admin UI.

_PRODUCT_CATEGORY = """
query ProductCategory($category_id: Int, $limit: Int, $offset: Int) {
  productCategory(category_id: $category_id, limit: $limit, offset: $offset) {
    productCategory {
      category_id
      sort_order
      status
      parent_id
      category_name
      category_url
      category_internal_name
      external_ref
    }
    totalProductCategorySize
    currentCount
  }
}
""".strip()


async def get_product_category(
    *,
    client: OpsGraphQLClient,
    category_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> OpsResult:
    """Fetch OPS product categories.

    Returns OpsResult.data = {"productCategory": [...], "totalProductCategorySize": N}.
    Pass category_id to look up one category; omit to list.
    """
    variables: dict = {"limit": limit, "offset": offset}
    if category_id is not None:
        variables["category_id"] = category_id
    result = await client.execute(_PRODUCT_CATEGORY, variables=variables)
    if not result.ok:
        return result
    payload = (result.data or {}).get("productCategory") or {}
    return OpsResult(
        ok=True,
        data={
            "productCategory": payload.get("productCategory") or [],
            "totalProductCategorySize": payload.get("totalProductCategorySize") or 0,
            "currentCount": payload.get("currentCount") or 0,
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
