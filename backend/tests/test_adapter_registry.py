"""BaseAdapter contract + adapter registry tests."""
from __future__ import annotations

import pytest
from pydantic import BaseModel

# We import from modules.import_jobs.base which doesn't exist yet
from modules.import_jobs.base import (
    AuthError,
    BaseAdapter,
    DiscoveryMode,
    ProductRef,
    SupplierError,
)


def test_product_ref_carries_supplier_sku_and_optional_part_id():
    ref = ProductRef(supplier_sku="DECAL-131", part_id=None)
    assert ref.supplier_sku == "DECAL-131"
    assert ref.part_id is None
    ref2 = ProductRef(supplier_sku="PC61", part_id="1878771")
    assert ref2.part_id == "1878771"


def test_discovery_mode_enum_values():
    assert DiscoveryMode.EXPLICIT_LIST.value == "explicit_list"
    assert DiscoveryMode.FIRST_N.value == "first_n"
    assert DiscoveryMode.FULL.value == "full"
    assert DiscoveryMode.DELTA.value == "delta"


def test_base_adapter_is_abstract():
    with pytest.raises(TypeError):
        # BaseAdapter is an ABC, so it should raise TypeError on instantiation
        BaseAdapter(supplier=None, db=None)   


from modules.import_jobs.registry import ADAPTERS, get_adapter

def test_registry_contains_adapters_dict():
    assert isinstance(ADAPTERS, dict)

def test_get_adapter_returns_correct_class():
    # We'll need a mock supplier with adapter_class attribute
    class MockSupplier:
        def __init__(self, adapter_class):
            self.adapter_class = adapter_class
    
    # Register a dummy adapter
    class DummyAdapter(BaseAdapter):
        async def discover(self, **kwargs): return []
        async def hydrate_product(self, ref): pass
        async def discover_changed(self, since): return []
    
    ADAPTERS["dummy"] = DummyAdapter
    
    sup = MockSupplier(adapter_class="dummy")
    adapter = get_adapter(sup, db=None)
    assert isinstance(adapter, DummyAdapter)

def test_get_adapter_raises_on_unknown():
    from modules.import_jobs.registry import AdapterNotRegisteredError

    class MockSupplier:
        def __init__(self, adapter_class):
            self.adapter_class = adapter_class
            self.name = "Unknown Supplier"

    sup = MockSupplier(adapter_class="nonexistent")
    with pytest.raises(AdapterNotRegisteredError) as exc:
        get_adapter(sup, db=None)
    assert "nonexistent" in str(exc.value)
