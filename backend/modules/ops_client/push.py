"""push_apparel_product — 4-step ID-threaded push orchestrator.

Sequence: setProductCategory → setProduct → setProductSize × N → setProductPrice × N
Halt-no-rollback: on any failure after step 2, stop and return cleanup_targets.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from modules.catalog.schemas import ProductIngest
from .client import OpsGraphQLClient
from . import mutations as m


async def push_apparel_product(
    *,
    client: OpsGraphQLClient,
    product: ProductIngest,
    final_prices: dict[str, Decimal],
) -> dict[str, Any]:
    """Execute the 4-step apparel push. final_prices keys are variant.sku."""
    step_results: list[dict[str, Any]] = []
    cleanup_targets: list[dict[str, Any]] = []
    size_id_by_sku: dict[str, int] = {}
    ops_category_id: int | None = None
    ops_product_id: int | None = None

    def _record(step: str, ok: bool, **extra: Any) -> None:
        step_results.append({"step": step, "ok": ok, **extra})

    # Step 1: setProductCategory
    r = await m.set_product_category(
        client=client,
        category_name=product.category_name or "Uncategorized",
        parent_id=0,
        status="1",  # ProductCategoryInput uses `status` (String), not `visible` (Int)
    )
    if not r.ok:
        _record("set_product_category", False, error=r.ops_error_message)
        return {
            "ok": False, "status": "failed",
            "ops_product_id": None, "ops_category_id": None,
            "size_id_by_sku": {}, "step_results": step_results,
            "cleanup_targets": [], "error": r.ops_error_message,
        }
    # OPS returns canonical `id`; older wrappers may still return category_id.
    ops_category_id = (r.data or {}).get("id") or (r.data or {}).get("category_id")
    if ops_category_id is None:
        _record("set_product_category", False, error="OPS returned null category_id")
        return {
            "ok": False, "status": "failed",
            "ops_product_id": None, "ops_category_id": None,
            "size_id_by_sku": {}, "step_results": step_results,
            "cleanup_targets": [], "error": "OPS returned null category_id",
        }
    _record("set_product_category", True, category_id=ops_category_id)

    # Step 2: setProduct
    r = await m.set_product(
        client=client,
        category_id=ops_category_id,
        products_title=product.product_name,
        products_internal_title=product.supplier_sku,
        visible=1,
    )
    if not r.ok:
        _record("set_product", False, error=r.ops_error_message)
        cleanup_targets.append({"ops_category_id": ops_category_id})
        return {
            "ok": False, "status": "failed",
            "ops_product_id": None, "ops_category_id": ops_category_id,
            "size_id_by_sku": {}, "step_results": step_results,
            "cleanup_targets": cleanup_targets, "error": r.ops_error_message,
        }
    # OPS returns canonical `id`; older wrappers may still return products_id.
    ops_product_id = (r.data or {}).get("id") or (r.data or {}).get("products_id")
    if ops_product_id is None:
        _record("set_product", False, error="OPS returned null products_id")
        cleanup_targets.append({"ops_category_id": ops_category_id})
        return {
            "ok": False, "status": "failed",
            "ops_product_id": None, "ops_category_id": ops_category_id,
            "size_id_by_sku": {}, "step_results": step_results,
            "cleanup_targets": cleanup_targets, "error": "OPS returned null products_id",
        }
    _record("set_product", True, products_id=ops_product_id)

    # Step 3: setProductSize per variant
    for variant in product.variants:
        if not variant.sku:
            _record("set_product_size", False, sku="", error=f"variant {variant.part_id} missing sku")
            continue
        # ProductSizeInput has size_title (no separate size_name/color_name)
        # and no products_sku field. Fold color into the title.
        color = (variant.color or "").strip()
        size = (variant.size or "").strip()
        if color and size:
            size_title = f"{color} / {size}"
        else:
            size_title = color or size or variant.sku
        r = await m.set_product_size(
            client=client,
            products_id=ops_product_id,
            size_title=size_title,
            visible=1,
        )
        if not r.ok:
            _record("set_product_size", False, sku=variant.sku, error=r.ops_error_message)
            cleanup_targets.append({"ops_product_id": ops_product_id})
            for sku, sid in size_id_by_sku.items():
                cleanup_targets.append({"ops_size_id": sid, "sku": sku})
            return {
                "ok": False, "status": "partial_failure",
                "ops_product_id": ops_product_id, "ops_category_id": ops_category_id,
                "size_id_by_sku": size_id_by_sku, "step_results": step_results,
                "cleanup_targets": cleanup_targets, "error": r.ops_error_message,
            }
        # OPS returns canonical `id`; older wrappers may still return product_size_id.
        size_id = (r.data or {}).get("id") or (r.data or {}).get("product_size_id")
        if size_id is None:
            _record("set_product_size", False, sku=variant.sku, error="OPS returned null product_size_id")
            cleanup_targets.append({"ops_product_id": ops_product_id})
            for sku, sid in size_id_by_sku.items():
                cleanup_targets.append({"ops_size_id": sid, "sku": sku})
            return {
                "ok": False, "status": "partial_failure",
                "ops_product_id": ops_product_id, "ops_category_id": ops_category_id,
                "size_id_by_sku": size_id_by_sku, "step_results": step_results,
                "cleanup_targets": cleanup_targets, "error": "OPS returned null size_id",
            }
        size_id_by_sku[variant.sku] = size_id
        _record("set_product_size", True, sku=variant.sku, size_id=size_id)

    # Step 4: setProductPrice per variant
    for variant in product.variants:
        if not variant.sku or variant.sku not in size_id_by_sku:
            _record("set_product_price", False, sku=variant.sku or "", error="variant missing sku or not in size map")
            continue
        final = final_prices.get(variant.sku)
        if final is None or variant.base_price is None:
            _record("set_product_price", False, sku=variant.sku, error="missing final_price or base_price")
            continue
        r = await m.set_product_price(
            client=client,
            products_id=ops_product_id,
            size_id=size_id_by_sku[variant.sku],
            price=str(final),
            vendor_price=str(variant.base_price),
            qty=1,
            visible=1,
        )
        if not r.ok:
            _record("set_product_price", False, sku=variant.sku, error=r.ops_error_message)
            cleanup_targets.append({"ops_product_id": ops_product_id})
            return {
                "ok": False, "status": "partial_failure",
                "ops_product_id": ops_product_id, "ops_category_id": ops_category_id,
                "size_id_by_sku": size_id_by_sku, "step_results": step_results,
                "cleanup_targets": cleanup_targets, "error": r.ops_error_message,
            }
        _record("set_product_price", True, sku=variant.sku)

    return {
        "ok": True, "status": "pushed",
        "ops_product_id": ops_product_id, "ops_category_id": ops_category_id,
        "size_id_by_sku": size_id_by_sku, "step_results": step_results,
        "cleanup_targets": [], "error": None,
    }
