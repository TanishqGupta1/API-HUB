"""OPS GraphQL operation strings + the wrappers still in use.

The M1 Integration Gateway (`modules/ops_push/gateway.py`) sends OPS mutations
by dispatching the raw query CONSTANTS below (`_SET_*` / `_UPDATE_*`) through its
own adapter — it does not call per-operation wrapper functions for the push.

What remains here and why:
  * `_SET_*` / `_UPDATE_*` / `_GET_*` query constants — single source of truth
    for OPS field shapes; referenced by the gateway's `_MUTATION_DISPATCH`.
  * `get_product_by_sku()` — live: used by the gateway dedup/verify paths.
  * `set_product` / `set_product_size` / `set_product_price` /
    `update_product_stock` — retained as the reference implementation +
    regression coverage for OPS application-level `result:false` rejection
    (the PC54/PC61 silent-failure scenario, tested in
    `test_ops_push_normalization.py`). This `_check_result` logic is what the
    gateway silent-failure guard (PENDING-WORK §1.2) needs to adopt.
  * `_unwrap_list()` / `_check_result()` — array-response unwrap + rejection
    detection used by the wrappers above.

Removed (no production callers, no remaining tests): the legacy
`set_product_category`, `set_products_image_gallery`, `set_assign_options`,
`set_additional_option`, `set_additional_option_attributes`,
`set_products_attribute_price`, `set_product_design` wrappers, and
`modules/ops_client/push.py`. Their query constants are kept (the gateway
dispatches them directly).
"""
from __future__ import annotations

from .client import OpsGraphQLClient, OpsResult


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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OPS mutation query constants — dispatched by gateway._MUTATION_DISPATCH.
# Single source of truth for OPS input field shapes. Keep all of these even
# where the wrapper function was removed; the gateway sends them directly.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_SET_PRODUCT_CATEGORY = """
mutation SetProductCategory($inputs: [ProductCategoryInput!]!) {
  setProductCategory(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()

_SET_PRODUCT = """
mutation SetProduct($inputs: [ProductInput!]!) {
  setProduct(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()

_SET_PRODUCTS_IMAGE_GALLERY = """
mutation SetProductsImageGallery($products_id: Int!, $optimizeimg: Int, $input: ProductsImageGalleryBulkInput!) {
  setProductsImageGallery(products_id: $products_id, optimizeimg: $optimizeimg, input: $input) {
    result
    message
  }
}
""".strip()

_SET_PRODUCT_SIZE = """
mutation SetProductSize($inputs: [ProductSizeInput!]!) {
  setProductSize(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()

_SET_PRODUCT_PRICE = """
mutation SetProductPrice($inputs: [ProductPriceInput!]!) {
  setProductPrice(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()

_SET_ASSIGN_OPTIONS = """
mutation SetAssignOptions($inputs: [AssignOptionsInput!]!) {
  setAssignOptions(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()

_SET_ADDITIONAL_OPTION = """
mutation SetAdditionalOption($inputs: [AdditionalOptionInput!]!) {
  setAdditionalOption(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()

_SET_ADDITIONAL_OPTION_ATTRIBUTES = """
mutation SetAdditionalOptionAttributes($inputs: [AdditionalOptionAttributesInput!]!) {
  setAdditionalOptionAttributes(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()

_SET_PRODUCTS_ATTRIBUTE_PRICE = """
mutation SetProductsAttributePrice($inputs: [ProductsAttributePriceInput!]!) {
  setProductsAttributePrice(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()

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

_SET_PRODUCT_DESIGN = """
mutation SetProductDesign($input: setProductDesign_input!) {
  setProductDesign(input: $input) {
    products_id
  }
}
""".strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Retained wrappers — reference impl + silent-failure (`result:false`)
# regression coverage (PENDING-WORK §1.2). Not on the production push path.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def set_product(
    *,
    client: OpsGraphQLClient,
    category_id: int,
    products_title: str,
    products_internal_title: str,
    visible: int = 1,
) -> OpsResult:
    result = await client.execute(
        _SET_PRODUCT,
        variables={"inputs": [{
            "category_id": category_id,
            "products_title": products_title,
            "products_internal_title": products_internal_title,
            "visible": visible,
        }]},
    )
    if not result.ok:
        return result
    data = _unwrap_list(result.data, "setProduct")
    err = _check_result(data, "setProduct")
    if err is not None:
        return err
    return OpsResult(ok=True, data=data, raw=result.raw)


async def set_product_size(
    *,
    client: OpsGraphQLClient,
    products_id: int,
    size_title: str,
    visible: int = 1,
) -> OpsResult:
    result = await client.execute(
        _SET_PRODUCT_SIZE,
        variables={"inputs": [{
            "products_id": products_id,
            "size_title": size_title,
            "visible": visible,
        }]},
    )
    if not result.ok:
        return result
    data = _unwrap_list(result.data, "setProductSize")
    err = _check_result(data, "setProductSize")
    if err is not None:
        return err
    return OpsResult(ok=True, data=data, raw=result.raw)


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
    price_defining_method: str = "1",
) -> OpsResult:
    # OPS requires:
    # - price/vendor_price as Float (not string) — string causes INVALID_USER_INPUT
    # - price_defining_method — missing causes "Price Defining method is required"
    if price is None or vendor_price is None:
        return OpsResult(ok=False, ops_error_code="MISSING_PRICE",
                         ops_error_message="price and vendor_price must not be None")
    input_dict: dict = {
        "products_id": products_id,
        "size_id": size_id,
        "qty": qty,
        "price": float(price),
        "vendor_price": float(vendor_price),
        "visible": str(visible),
        "price_defining_method": price_defining_method,
    }
    if qty_to is not None:
        input_dict["qty_to"] = qty_to
    result = await client.execute(_SET_PRODUCT_PRICE, variables={"inputs": [input_dict]})
    if not result.ok:
        return result
    data = _unwrap_list(result.data, "setProductPrice")
    err = _check_result(data, "setProductPrice")
    if err is not None:
        return err
    return OpsResult(ok=True, data=data, raw=result.raw)


async def update_product_stock(
    *,
    client: OpsGraphQLClient,
    action: str,
    stock_quantity: int,
    stock_id: int | None = None,
    product_sku: str | None = None,
    comment: str | None = None,
) -> OpsResult:
    variables: dict = {
        "action": action,
        "input": {"stock_quantity": stock_quantity},
    }
    if stock_id is not None:
        variables["stock_id"] = stock_id
    if product_sku is not None:
        variables["product_sku"] = product_sku
    if comment is not None:
        variables["input"]["comment"] = comment
    result = await client.execute(_UPDATE_PRODUCT_STOCK, variables=variables)
    if not result.ok:
        return result
    # updateProductStock is the one mutation that doesn't use array inputs;
    # its response is a single dict, not a list. Still subject to the same
    # application-level result-checking.
    data = (result.data or {}).get("updateProductStock") or {}
    err = _check_result(data, "updateProductStock")
    if err is not None:
        return err
    return OpsResult(ok=True, data=data, raw=result.raw)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# get_product_by_sku (P2.2 dedup) — live wrapper.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Used pre-push to ask OPS "do you already have a product with this SKU?" so
# a retry of a previously-failed push doesn't create a duplicate row in OPS.
#
# Schema is PROVISIONAL — confirm against the OPS Postman collection when
# Christian shares it. The function returns the wrapper's data dict so the
# dedup caller never sees raw schema details; only the wrapper has to change
# if OPS uses a different operation name (e.g. getProductsList with a SKU
# filter) or different field names.

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
    """Look up an existing OPS product by SKU. Returns the wrapper's data
    dict containing products_id when found, or an empty dict when not.

    Callers should check result.ok AND result.data.get('products_id').
    A missing products_id is a successful 'not found', not a failure.
    """
    result = await client.execute(
        _GET_PRODUCT_BY_SKU,
        variables={"products_sku": products_sku},
    )
    if not result.ok:
        return result
    # OPS convention nests the operation result under the operation name;
    # mirror the unwrap pattern from the mutation helpers.
    payload = (result.data or {}).get("getProductBySku") or {}
    return OpsResult(ok=True, data=payload, raw=result.raw)
