"""Task 10 — FakeOpsClient unit tests. Hermetic; no DB, no HTTP."""
import pytest

pytestmark = pytest.mark.no_db

from modules.ops_client.fake import FakeOpsClient


@pytest.mark.asyncio
async def test_fake_client_returns_synthetic_ids_in_order():
    """Allocates monotonically-increasing IDs for each mutation."""
    c = FakeOpsClient()
    r1 = await c.execute(
        "mutation SetProductCategory($input: x!) { setProductCategory(input: $input) { category_id } }",
        variables={"input": {"category_name": "X"}},
    )
    r2 = await c.execute(
        "mutation SetProduct($input: x!) { setProduct(input: $input) { products_id } }",
        variables={"input": {"category_id": r1.data["setProductCategory"]["category_id"]}},
    )
    assert r1.ok and r1.data["setProductCategory"]["category_id"] > 0
    assert r2.ok and r2.data["setProduct"]["products_id"] > r1.data["setProductCategory"]["category_id"]


@pytest.mark.asyncio
async def test_fake_client_records_calls():
    """Every execute() call appends to self.calls — usable as a spy in tests."""
    c = FakeOpsClient()
    await c.execute(
        "mutation SetProduct($input: x!) { setProduct(input: $input) { products_id } }",
        variables={"input": {"products_title": "PC61"}},
    )
    assert len(c.calls) == 1
    assert c.calls[0]["mutation_name"] == "SetProduct"
    assert c.calls[0]["variables"]["input"]["products_title"] == "PC61"


@pytest.mark.asyncio
async def test_fake_client_handles_all_known_mutations():
    """Every supported mutation returns ok=True with the right shape key."""
    c = FakeOpsClient()
    expected = {
        "SetProductCategory":            ("setProductCategory", "category_id"),
        "SetProduct":                    ("setProduct", "products_id"),
        "SetProductSize":                ("setProductSize", "product_size_id"),
        "SetProductPrice":               ("setProductPrice", "product_price_id"),
        "SetAdditionalOption":           ("setAdditionalOption", "prod_add_opt_id"),
        "SetAdditionalOptionAttributes": ("setAdditionalOptionAttributes", "attribute_id"),
    }
    for name, (root_key, id_key) in expected.items():
        r = await c.execute(
            f"mutation {name}($input: x!) {{ {root_key}(input: $input) {{ {id_key} }} }}",
            variables={"input": {}},
        )
        assert r.ok, f"{name} should be ok=True"
        assert root_key in r.data and id_key in r.data[root_key]
        assert r.data[root_key][id_key] > 0


@pytest.mark.asyncio
async def test_fake_client_handles_attribute_price_no_id():
    """SetProductsAttributePrice doesn't return a new ID — just confirmation."""
    c = FakeOpsClient()
    r = await c.execute(
        "mutation SetProductsAttributePrice($input: x!) { setProductsAttributePrice(input: $input) { ok } }",
        variables={"input": {"attribute_id": 5, "price": 12.50}},
    )
    assert r.ok and r.data["setProductsAttributePrice"]["ok"] is True


@pytest.mark.asyncio
async def test_fake_client_unknown_mutation_returns_not_ok():
    """An unrecognized mutation returns ok=False with diagnostic info."""
    c = FakeOpsClient()
    r = await c.execute(
        "mutation SetBogusThing($input: x!) { setBogusThing { id } }",
        variables={"input": {}},
    )
    assert r.ok is False
    assert r.ops_error_code == "UNKNOWN_OPERATION"
    assert r.ops_error_message == "SetBogusThing"


@pytest.mark.asyncio
async def test_fake_client_ids_are_unique_across_calls():
    """ID allocation is global per client — no two calls return the same ID."""
    c = FakeOpsClient()
    seen = set()
    for _ in range(5):
        r = await c.execute(
            "mutation SetProduct($input: x!) { setProduct(input: $input) { products_id } }",
            variables={"input": {}},
        )
        new_id = r.data["setProduct"]["products_id"]
        assert new_id not in seen
        seen.add(new_id)


@pytest.mark.asyncio
async def test_fake_client_starts_id_at_1000():
    """Synthetic IDs start at 1000 so they're visually distinct from real OPS IDs in test output."""
    c = FakeOpsClient()
    r = await c.execute(
        "mutation SetProductCategory($input: x!) { setProductCategory(input: $input) { category_id } }",
        variables={"input": {}},
    )
    assert r.data["setProductCategory"]["category_id"] == 1000
