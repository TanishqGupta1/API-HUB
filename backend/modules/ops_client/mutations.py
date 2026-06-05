"""OPS GraphQL mutation + query wrappers — one function per operation.

ID threading order for apparel push:
  set_product_category → category_id
  set_product(category_id) → products_id
  set_product_size(products_id) → size_id  (once per variant)
  set_product_price(products_id, size_id)  (once per variant)
  set_assign_options(products_id)
  set_additional_option / set_additional_option_attributes / set_products_attribute_price
  update_product_stock(products_id)
  set_product_design(products_id)

Queries (P2.2 — read-back / dedup):
  get_product_by_sku(products_sku) → products_id | None
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


async def set_product_category(
    *,
    client: OpsGraphQLClient,
    category_name: str,
    parent_id: int = 0,
    visible: int = 1,
) -> OpsResult:
    result = await client.execute(
        _SET_PRODUCT_CATEGORY,
        variables={"inputs": [{"category_name": category_name, "parent_id": parent_id, "visible": visible}]},
    )
    if not result.ok:
        return result
    return OpsResult(ok=True, data=_unwrap_list(result.data, "setProductCategory"), raw=result.raw)


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
    data = result.data or {}
    # setProduct returns a list when inputs is an array — unwrap first item
    sp = data.get("setProduct")
    if isinstance(sp, list):
        sp = sp[0] if sp else {}
    return OpsResult(ok=True, data=sp or {}, raw=result.raw)


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
    return OpsResult(ok=True, data=_unwrap_list(result.data, "setProductSize"), raw=result.raw)


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
    result = await client.execute(_SET_PRODUCT_PRICE, variables={"inputs": [input_dict]})
    if not result.ok:
        return result
    return OpsResult(ok=True, data=_unwrap_list(result.data, "setProductPrice"), raw=result.raw)


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


async def set_assign_options(
    *,
    client: OpsGraphQLClient,
    products_id: int,
    master_option_id: int,
) -> OpsResult:
    result = await client.execute(
        _SET_ASSIGN_OPTIONS,
        variables={"inputs": [{"products_id": products_id, "master_option_id": master_option_id}]},
    )
    if not result.ok:
        return result
    return OpsResult(ok=True, data=_unwrap_list(result.data, "setAssignOptions"), raw=result.raw)


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


async def set_additional_option(
    *,
    client: OpsGraphQLClient,
    products_id: int,
    option_key: str,
    title: str,
    options_type: str,
    sort_order: int = 0,
) -> OpsResult:
    result = await client.execute(
        _SET_ADDITIONAL_OPTION,
        variables={"inputs": [{
            "products_id": products_id,
            "option_key": option_key,
            "title": title,
            "options_type": options_type,
            "sort_order": sort_order,
        }]},
    )
    if not result.ok:
        return result
    return OpsResult(ok=True, data=_unwrap_list(result.data, "setAdditionalOption"), raw=result.raw)


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


async def set_additional_option_attributes(
    *,
    client: OpsGraphQLClient,
    prod_add_opt_id: int,
    attribute_key: str,
    label: str,
    setup_cost: float = 0.0,
    multiplier: float = 1.0,
) -> OpsResult:
    result = await client.execute(
        _SET_ADDITIONAL_OPTION_ATTRIBUTES,
        variables={"inputs": [{
            "prod_add_opt_id": prod_add_opt_id,
            "attribute_key": attribute_key,
            "label": label,
            "setup_cost": setup_cost,
            "multiplier": multiplier,
        }]},
    )
    if not result.ok:
        return result
    return OpsResult(
        ok=True,
        data=_unwrap_list(result.data, "setAdditionalOptionAttributes"),
        raw=result.raw,
    )


# ── set_products_attribute_price ──────────────────────────────────────────────

_SET_PRODUCTS_ATTRIBUTE_PRICE = """
mutation SetProductsAttributePrice($inputs: [ProductsAttributePriceInput!]!) {
  setProductsAttributePrice(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()


async def set_products_attribute_price(
    *,
    client: OpsGraphQLClient,
    product_id: int,
    attribute_id: int,
    size_id: int,
    attributes_price: str,
    vendor_price: str | None = None,
) -> OpsResult:
    inp: dict = {
        "product_id": product_id,
        "attribute_id": attribute_id,
        "size_id": size_id,
        "attributes_price": attributes_price,
    }
    if vendor_price is not None:
        inp["vendor_price"] = vendor_price
    result = await client.execute(
        _SET_PRODUCTS_ATTRIBUTE_PRICE,
        variables={"inputs": [inp]},
    )
    if not result.ok:
        return result
    return OpsResult(
        ok=True,
        data=_unwrap_list(result.data, "setProductsAttributePrice"),
        raw=result.raw,
    )


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
    return OpsResult(ok=True, data=(result.data or {}).get("updateProductStock") or {}, raw=result.raw)


# ── set_product_design ───────────────────────────────────────────────────────

_SET_PRODUCT_DESIGN = """
mutation SetProductDesign($input: setProductDesign_input!) {
  setProductDesign(input: $input) {
    products_id
  }
}
""".strip()


async def set_product_design(
    *,
    client: OpsGraphQLClient,
    products_id: int,
    design_url: str,
    design_type: str | None = None,
) -> OpsResult:
    input_dict: dict = {"products_id": products_id, "design_url": design_url}
    if design_type is not None:
        input_dict["design_type"] = design_type
    result = await client.execute(_SET_PRODUCT_DESIGN, variables={"input": input_dict})
    if not result.ok:
        return result
    return OpsResult(ok=True, data=(result.data or {}).get("setProductDesign") or {}, raw=result.raw)


# ── get_product_by_sku (P2.2 dedup) ─────────────────────────────────────────
#
# Used pre-push to ask OPS "do you already have a product with this SKU?" so
# a retry of a previously-failed push doesn't create a duplicate row in OPS.
#
# Schema is PROVISIONAL — confirm against the OPS Postman collection when
# Christian shares it. The function returns Optional[int] (products_id) so
# the dedup caller never sees raw schema details; only the wrapper has to
# change if OPS uses a different operation name (e.g. getProductsList with
# a SKU filter) or different field names.

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
