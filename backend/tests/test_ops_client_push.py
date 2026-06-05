"""Tests for push_apparel_product orchestrator.

Uses AsyncMock on client.execute — no FakeOpsClient or real OPS needed.
Covers:
- Happy path: ID threading across all 4 steps, correct mutation order
- step 1 failure (setProductCategory) → status=failed, no cleanup_targets
- step 2 failure (setProduct) → status=failed, ops_category_id in cleanup_targets
- step 3 failure mid-variants (setProductSize) → status=partial_failure, cleanup_targets populated
- step 4 failure mid-variants (setProductPrice) → status=partial_failure
- variant missing sku → recorded in step_results, push continues
- variant missing final_price → recorded in step_results, skipped
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from modules.catalog.schemas import ProductIngest, VariantIngest
from modules.ops_client.client import OpsAuth, OpsGraphQLClient, OpsResult
from modules.ops_client.push import push_apparel_product


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_client() -> OpsGraphQLClient:
    return OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))


def _product(*skus: str, category: str = "T-Shirts") -> ProductIngest:
    return ProductIngest(
        supplier_sku="PC61",
        product_name="Port & Company Essential Tee",
        category_name=category,
        variants=[
            VariantIngest(part_id=sku, sku=sku, color="Navy", size="M", base_price=Decimal("3.99"))
            for sku in skus
        ],
    )


def _final_prices(*skus: str, price: str = "9.99") -> dict[str, Decimal]:
    return {sku: Decimal(price) for sku in skus}


# Returns OpsResult shaped like each mutation's real OPS response
_CATEGORY_OK  = OpsResult(ok=True, data={"setProductCategory": {"category_id": 100}})
_PRODUCT_OK   = OpsResult(ok=True, data={"setProduct": {"products_id": 200}})
_SIZE_OK_1    = OpsResult(ok=True, data={"setProductSize": {"product_size_id": 301}})
_SIZE_OK_2    = OpsResult(ok=True, data={"setProductSize": {"product_size_id": 302}})
_PRICE_OK     = OpsResult(ok=True, data={"setProductPrice": {"product_price_id": 401}})
_ERR          = OpsResult(ok=False, ops_error_code="OPS_ERR", ops_error_message="boom")


# ── Happy path ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_happy_path_returns_pushed_status():
    client = _make_client()
    client.execute = AsyncMock(side_effect=[
        _CATEGORY_OK, _PRODUCT_OK, _SIZE_OK_1, _SIZE_OK_2, _PRICE_OK, _PRICE_OK,
    ])
    result = await push_apparel_product(
        client=client,
        product=_product("SKU-A", "SKU-B"),
        final_prices=_final_prices("SKU-A", "SKU-B"),
    )
    assert result["ok"] is True
    assert result["status"] == "pushed"
    assert result["ops_product_id"] == 200
    assert result["ops_category_id"] == 100
    assert result["cleanup_targets"] == []
    assert result["error"] is None


@pytest.mark.asyncio
async def test_happy_path_mutation_order():
    """Mutations must fire in exact order: category → product → size×N → price×N."""
    client = _make_client()
    calls: list[str] = []

    async def _capture(query, *, variables):
        if "SetProductCategory" in query:
            calls.append("category")
            return _CATEGORY_OK
        if "SetProductSize" in query:
            calls.append("size")
            return OpsResult(ok=True, data={"setProductSize": {"product_size_id": len(calls) * 10}})
        if "SetProductPrice" in query:
            calls.append("price")
            return _PRICE_OK
        if "SetProduct" in query:
            calls.append("product")
            return _PRODUCT_OK
        return _ERR

    client.execute = _capture
    await push_apparel_product(
        client=client,
        product=_product("A", "B"),
        final_prices=_final_prices("A", "B"),
    )
    assert calls == ["category", "product", "size", "size", "price", "price"]


@pytest.mark.asyncio
async def test_happy_path_ids_threaded_correctly():
    """category_id flows into setProduct; products_id + size_id flow into setProductPrice."""
    client = _make_client()
    captured: list[dict] = []

    async def _capture(query, *, variables):
        captured.append({"query": query, "vars": variables})
        # Array-input mutations send variables.inputs (list); responses
        # return canonical `id` wrapped in a list — mutations.py unwraps both.
        if "SetProductCategory" in query:
            return OpsResult(ok=True, data={"setProductCategory": [{"id": 555}]})
        if "SetProduct(" in query:
            assert variables["inputs"][0]["category_id"] == 555
            return OpsResult(ok=True, data={"setProduct": [{"id": 777}]})
        if "SetProductSize" in query:
            assert variables["inputs"][0]["products_id"] == 777
            return OpsResult(ok=True, data={"setProductSize": [{"id": 888}]})
        if "SetProductPrice" in query:
            assert variables["inputs"][0]["products_id"] == 777
            assert variables["inputs"][0]["size_id"] == 888
            return OpsResult(ok=True, data={"setProductPrice": [{"id": 999}]})
        return _ERR

    client.execute = _capture
    result = await push_apparel_product(
        client=client,
        product=_product("SKU-X"),
        final_prices=_final_prices("SKU-X"),
    )
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_happy_path_step_results_all_ok():
    client = _make_client()
    client.execute = AsyncMock(side_effect=[
        _CATEGORY_OK, _PRODUCT_OK, _SIZE_OK_1, _PRICE_OK,
    ])
    result = await push_apparel_product(
        client=client,
        product=_product("SKU-A"),
        final_prices=_final_prices("SKU-A"),
    )
    assert all(s["ok"] for s in result["step_results"])
    steps = [s["step"] for s in result["step_results"]]
    assert steps == ["set_product_category", "set_product", "set_product_size", "set_product_price"]


# ── Step 1 failure ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_step1_failure_returns_failed_no_cleanup():
    """setProductCategory fails → status=failed, nothing reached OPS, no cleanup needed."""
    client = _make_client()
    client.execute = AsyncMock(return_value=_ERR)
    result = await push_apparel_product(
        client=client,
        product=_product("SKU-A"),
        final_prices=_final_prices("SKU-A"),
    )
    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["ops_product_id"] is None
    assert result["ops_category_id"] is None
    assert result["cleanup_targets"] == []
    assert result["error"] == "boom"


# ── Step 2 failure ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_step2_failure_returns_failed_with_category_in_cleanup():
    """setProduct fails → status=failed, category was created so it appears in cleanup_targets."""
    client = _make_client()
    client.execute = AsyncMock(side_effect=[_CATEGORY_OK, _ERR])
    result = await push_apparel_product(
        client=client,
        product=_product("SKU-A"),
        final_prices=_final_prices("SKU-A"),
    )
    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["ops_product_id"] is None
    assert result["ops_category_id"] == 100
    assert any("ops_category_id" in t for t in result["cleanup_targets"])


# ── Step 3 failure ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_step3_failure_on_first_variant_returns_partial_failure():
    client = _make_client()
    client.execute = AsyncMock(side_effect=[_CATEGORY_OK, _PRODUCT_OK, _ERR])
    result = await push_apparel_product(
        client=client,
        product=_product("SKU-A", "SKU-B"),
        final_prices=_final_prices("SKU-A", "SKU-B"),
    )
    assert result["ok"] is False
    assert result["status"] == "partial_failure"
    assert result["ops_product_id"] == 200
    assert any("ops_product_id" in t for t in result["cleanup_targets"])


@pytest.mark.asyncio
async def test_step3_failure_on_second_variant_includes_first_size_in_cleanup():
    """First variant size succeeded; second fails → first size_id appears in cleanup_targets."""
    client = _make_client()
    client.execute = AsyncMock(side_effect=[
        _CATEGORY_OK, _PRODUCT_OK, _SIZE_OK_1, _ERR,
    ])
    result = await push_apparel_product(
        client=client,
        product=_product("SKU-A", "SKU-B"),
        final_prices=_final_prices("SKU-A", "SKU-B"),
    )
    assert result["status"] == "partial_failure"
    assert any("ops_size_id" in t for t in result["cleanup_targets"])
    assert result["size_id_by_sku"] == {"SKU-A": 301}


# ── Step 4 failure ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_step4_failure_returns_partial_failure():
    client = _make_client()
    client.execute = AsyncMock(side_effect=[
        _CATEGORY_OK, _PRODUCT_OK, _SIZE_OK_1, _ERR,
    ])
    result = await push_apparel_product(
        client=client,
        product=_product("SKU-A"),
        final_prices=_final_prices("SKU-A"),
    )
    assert result["ok"] is False
    assert result["status"] == "partial_failure"
    assert result["ops_product_id"] == 200


# ── Missing SKU ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_variant_missing_sku_is_recorded_and_push_continues():
    """Variant with no SKU is recorded as failed step but push continues to next variant."""
    client = _make_client()
    client.execute = AsyncMock(side_effect=[
        _CATEGORY_OK, _PRODUCT_OK, _SIZE_OK_1, _PRICE_OK,
    ])
    product = ProductIngest(
        supplier_sku="PC61",
        product_name="Port & Company Tee",
        category_name="T-Shirts",
        variants=[
            VariantIngest(part_id="NO-SKU", sku=None, color="Navy", size="S"),
            VariantIngest(part_id="HAS-SKU", sku="HAS-SKU", color="Navy", size="M", base_price=Decimal("3.99")),
        ],
    )
    result = await push_apparel_product(
        client=client,
        product=product,
        final_prices={"HAS-SKU": Decimal("9.99")},
    )
    assert result["ok"] is True
    assert result["status"] == "pushed"
    failed_steps = [s for s in result["step_results"] if not s["ok"]]
    assert any("missing sku" in s.get("error", "") for s in failed_steps)


# ── Missing final_price ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_variant_missing_final_price_is_recorded_and_skipped():
    """Variant present in size map but absent from final_prices → recorded, not halted."""
    client = _make_client()
    client.execute = AsyncMock(side_effect=[
        _CATEGORY_OK, _PRODUCT_OK, _SIZE_OK_1, _SIZE_OK_2, _PRICE_OK,
    ])
    result = await push_apparel_product(
        client=client,
        product=_product("SKU-A", "SKU-B"),
        final_prices={"SKU-A": Decimal("9.99")},  # SKU-B intentionally missing
    )
    assert result["ok"] is True
    assert result["status"] == "pushed"
    failed = [s for s in result["step_results"] if not s["ok"] and s["step"] == "set_product_price"]
    assert any(s.get("sku") == "SKU-B" for s in failed)


# ── No variants ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_product_with_no_variants_pushes_category_and_product_only():
    client = _make_client()
    client.execute = AsyncMock(side_effect=[_CATEGORY_OK, _PRODUCT_OK])
    result = await push_apparel_product(
        client=client,
        product=ProductIngest(supplier_sku="PC61", product_name="Tee", category_name="T-Shirts"),
        final_prices={},
    )
    assert result["ok"] is True
    assert result["status"] == "pushed"
    assert client.execute.call_count == 2
