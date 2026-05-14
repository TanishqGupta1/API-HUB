"""push_apparel_product — 4-step ID-threaded push orchestrator.

Sequence:
  1. setProductCategory  → category_id
  2. setProduct          → products_id
  3. setProductSize      → size_id   (once per variant)
  4. setProductPrice     → done      (once per variant)

Halt-no-rollback: on any failure after step 2 succeeds, we stop and
return cleanup_targets so an operator can delete the stranded OPS rows.
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
    """Execute the 4-step apparel push.

    Returns:
        {
            "ok": bool,
            "status": "pushed" | "partial_failure" | "failed",
            "ops_product_id": int | None,
            "ops_category_id": int | None,
            "size_id_by_sku": dict[str, int],
            "step_results": list[dict],
            "cleanup_targets": list[dict],
            "error": str | None,
        }

    final_prices keys are variant.sku; values are marked-up final prices.
    """
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
        visible=1,
    )
    if not r.ok:
        _record("set_product_category", False, error=r.ops_error_message)
        return {
            "ok": False, "status": "failed",
            "ops_product_id": None, "ops_category_id": None,
            "size_id_by_sku": {}, "step_results": step_results,
            "cleanup_targets": [], "error": r.ops_error_message,
        }
    ops_category_id = r.data["category_id"]
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
    ops_product_id = r.data["products_id"]
    _record("set_product", True, products_id=ops_product_id)

    # Step 3: setProductSize per variant
    for variant in product.variants:
        if not variant.sku:
            _record("set_product_size", False, error=f"variant {variant.part_id} missing sku")
            continue
        r = await m.set_product_size(
            client=client,
            products_id=ops_product_id,
            size_name=variant.size or "",
            color_name=variant.color or "",
            products_sku=variant.sku,
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
        size_id_by_sku[variant.sku] = r.data["size_id"]
        _record("set_product_size", True, sku=variant.sku, size_id=r.data["size_id"])

    # Step 4: setProductPrice per variant
    for variant in product.variants:
        if not variant.sku or variant.sku not in size_id_by_sku:
            continue
        final = final_prices.get(variant.sku)
        if final is None or variant.base_price is None:
            _record("set_product_price", False, sku=variant.sku,
                    error="missing final_price or base_price")
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
