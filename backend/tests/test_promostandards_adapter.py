"""PromoStandardsAdapter + SanMarAdapter tests.

All tests run against recorded XML fixtures — no live SOAP calls.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path


import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from modules.suppliers.models import Supplier
from modules.promostandards.adapter import PromoStandardsAdapter
from modules.import_jobs.base import ProductRef




FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_promostandards_adapter_requires_id_password(seed_supplier: Supplier):
    """PromoStandardsAdapter raises AuthError if id/password missing on supplier."""
    from modules.import_jobs.base import AuthError, DiscoveryMode
    from modules.promostandards.adapter import PromoStandardsAdapter

    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.auth_config = {}
        loaded.adapter_class = "PromoStandardsAdapter"
        await s.commit()
        await s.refresh(loaded)
        
        adapter = PromoStandardsAdapter(supplier=loaded, db=s)
        with pytest.raises(AuthError):
            await adapter.discover(DiscoveryMode.EXPLICIT_LIST, limit=1)



@pytest.mark.asyncio
async def test_supplier_has_protocol_config(db: AsyncSession, seed_supplier: Supplier):
    """Supplier carries a JSONB protocol_config column for adapter settings."""
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.protocol_config = {
            "discovery_mode": "explicit_list",
            "explicit_list": ["PC61", "MM1000"],
            "max_products": 20,
        }
        await s.commit()
        await s.refresh(loaded)
        assert loaded.protocol_config["discovery_mode"] == "explicit_list"
        assert loaded.protocol_config["max_products"] == 20


def test_base_adapter_contract():
    """BaseAdapter declares discover, hydrate_product, discover_changed,
    discover_closeouts — ABC enforces overriding."""
    from modules.import_jobs.base import (
        BaseAdapter,
        DiscoveryMode,
        ProductRef,
    )
    from sqlalchemy.ext.asyncio import AsyncSession

    # Cannot instantiate the abstract class.
    with pytest.raises(TypeError):
        BaseAdapter(supplier=None, db=None)

    # Discovery modes are stable strings.
    assert DiscoveryMode.EXPLICIT_LIST.value == "explicit_list"
    assert DiscoveryMode.FIRST_N.value == "first_n"
    assert DiscoveryMode.DELTA.value == "delta"
    assert DiscoveryMode.FULL_SELLABLE.value == "full_sellable"
    assert DiscoveryMode.CLOSEOUTS.value == "closeouts"

    # ProductRef carries supplier_sku + optional part_id.
    ref = ProductRef(supplier_sku="PC61", part_id=None)
    assert ref.supplier_sku == "PC61"
    assert ref.part_id is None


@pytest.mark.asyncio
async def test_ps_normalizer_v2_pc61():
    """Normalizer converts SanMar XML fixtures to ProductIngest."""
    from modules.promostandards.ps_normalizer_v2 import (
        normalize_get_product_xml,
        merge_pricing,
        merge_media,
    )
    
    product_xml = (FIXTURES_DIR / "sanmar_get_product_pc61.xml").read_bytes()
    media_xml = (FIXTURES_DIR / "sanmar_get_media_pc61.xml").read_bytes()
    pricing_xml = (FIXTURES_DIR / "sanmar_get_pricing_pc61.xml").read_bytes()

    ingest = normalize_get_product_xml(product_xml)
    ingest = merge_pricing(ingest, pricing_xml)
    ingest = merge_media(ingest, media_xml)


    assert ingest.supplier_sku == "PC61"
    assert ingest.product_name == "Port & Company Essential Tee"
    assert ingest.brand == "Port & Company"
    assert "classic" in ingest.description
    assert ingest.product_type == "apparel"
    
    # 2 variants defined in fixture
    assert len(ingest.variants) == 2
    v1 = next(v for v in ingest.variants if v.part_id == "PC61-WH-S")
    assert v1.color == "White"
    # Pricing: 1 @ 5.98, 12 @ 4.98
    assert len(v1.prices) == 2
    p1 = next(p for p in v1.prices if p.quantity_min == 1)
    assert p1.price == Decimal("5.98")

    
    # Media: pc61_white_front.jpg
    assert len(ingest.images) == 2
    img1 = next(img for img in ingest.images if "pc61_white_front.jpg" in img.url)
    assert img1.image_type == "front" # mapped from 'Primary'


def test_promostandards_adapter_skeleton():
    """PromoStandardsAdapter registers itself and has correct product_type."""
    from modules.import_jobs.registry import ADAPTERS
    from modules.promostandards.adapter import PromoStandardsAdapter
    
    assert "PromoStandardsAdapter" in ADAPTERS
    assert PromoStandardsAdapter.product_type == "apparel"


class FixtureBackedPSAdapter(PromoStandardsAdapter):
    """Overrides transport hooks to read XML from fixtures."""
    fixture_map: dict[str, str] = {}

    async def _call_get_product(self, ref):
        path = self.fixture_map[f"product:{ref.supplier_sku}"]
        return (FIXTURES_DIR / path).read_bytes()

    async def _call_get_pricing(self, ref):
        path = self.fixture_map[f"pricing:{ref.supplier_sku}"]
        return (FIXTURES_DIR / path).read_bytes()

    async def _call_get_media(self, ref):
        path = self.fixture_map[f"media:{ref.supplier_sku}"]
        return (FIXTURES_DIR / path).read_bytes()

    async def _call_get_product_sellable(self):
        from lxml import etree
        path = self.fixture_map["sellable"]
        root = etree.fromstring((FIXTURES_DIR / path).read_bytes())
        out = []
        for p in root.xpath("//*[local-name()='ProductSellable']"):
            pid = p.xpath("*[local-name()='productId']/text()")
            if pid:
                out.append(ProductRef(supplier_sku=str(pid[0])))
        return out


@pytest.mark.asyncio
async def test_promostandards_adapter_hydrate_pc61_fixture(seed_supplier: Supplier):
    """PromoStandardsAdapter.hydrate_product works end-to-end with fixtures."""
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.auth_config = {"id": "test", "password": "test"}
        
        adapter = FixtureBackedPSAdapter(supplier=loaded, db=s)
        adapter.fixture_map = {
            "product:PC61": "sanmar_get_product_pc61.xml",
            "pricing:PC61": "sanmar_get_pricing_pc61.xml",
            "media:PC61": "sanmar_get_media_pc61.xml",
        }
        
        ref = ProductRef(supplier_sku="PC61")
        ingest = await adapter.hydrate_product(ref)
        
        assert ingest.supplier_sku == "PC61"
        assert len(ingest.variants) == 2
        # Pricing from pricing fixture (SanMar uses 'P' for Net/Coded) merged
        v = next(var for var in ingest.variants if var.part_id == "PC61-WH-S")
        assert any(p.price_type == "P" and p.price == Decimal("5.98") for p in v.prices)


        # Media from media fixture merged
        assert any("pc61_white_front.jpg" in img.url for img in ingest.images)


def test_sanmar_adapter_skeleton():
    """SanMarAdapter registers itself and identifies as apparel."""
    from modules.import_jobs.registry import ADAPTERS
    from modules.promostandards.sanmar_adapter import SanMarAdapter
    
    assert "SanMarAdapter" in ADAPTERS
    assert SanMarAdapter.product_type == "apparel"
    assert issubclass(SanMarAdapter, PromoStandardsAdapter)


def test_ps_fault_xml_maps_to_auth_error_and_supplier_error():
    from modules.promostandards.adapter import _classify_fault_xml
    from modules.import_jobs.base import AuthError, SupplierError

    auth_xml = (FIXTURES_DIR / "sanmar_auth_failure.xml").read_bytes()
    with pytest.raises(AuthError):
        _classify_fault_xml(auth_xml)

    not_found_xml = (FIXTURES_DIR / "sanmar_product_not_found.xml").read_bytes()
    # Code 105 is in _AUTH_CODES, so it raises AuthError
    with pytest.raises(AuthError):
        _classify_fault_xml(not_found_xml)
    
    # Generic fault should map to SupplierError
    generic_xml = b"<Fault><errorMessage><code>999</code><description>Kaboom</description></errorMessage></Fault>"
    with pytest.raises(SupplierError) as exc:
        _classify_fault_xml(generic_xml)
    assert exc.value.code == "999"


@pytest.mark.asyncio
async def test_sanmar_import_orchestration(seed_supplier: Supplier):
    """Full run_import orchestration works with SanMarAdapter + Fixtures."""
    from modules.import_jobs.service import run_import
    from modules.import_jobs.base import DiscoveryMode
    from modules.sync_jobs.models import SyncJob
    
    async with async_session() as s:
        loaded = await s.get(Supplier, seed_supplier.id)
        loaded.adapter_class = "SanMarAdapter"
        loaded.auth_config = {"id": "test", "password": "test"}
        await s.commit()
        await s.refresh(loaded)

        # Cleanup existing products for this SKU to avoid MultipleResultsFound
        from modules.catalog.models import Product
        from sqlalchemy import delete
        await s.execute(delete(Product).where(Product.supplier_sku == "PC61"))
        await s.commit()

        # We monkeypatch the registry to return our fixture-backed adapter

        from modules.import_jobs.registry import ADAPTERS
        
        class TestSanMarAdapter(FixtureBackedPSAdapter):
            pass
            
        ADAPTERS["SanMarAdapter"] = TestSanMarAdapter
        
        adapter_instance = TestSanMarAdapter(loaded, s)
        adapter_instance.fixture_map = {
            "sellable": "sanmar_get_product_sellable.xml",
            "product:PC61": "sanmar_get_product_pc61.xml",
            "pricing:PC61": "sanmar_get_pricing_pc61.xml",
            "media:PC61": "sanmar_get_media_pc61.xml",
        }
        
        # Override the get_adapter in service.py to return our instance with the map
        import modules.import_jobs.service as service_mod
        original_get = service_mod.get_adapter
        service_mod.get_adapter = lambda sup, db: adapter_instance
        
        try:
            job_id = await run_import(
                supplier_id=loaded.id,
                mode=DiscoveryMode.EXPLICIT_LIST,
                explicit_list=["PC61"]
            )
            
            # Fetch job to verify
            job = await s.get(SyncJob, job_id)
            assert job.status in ("success", "completed") # Service uses 'success'
            assert job.records_processed == 1
            
            # Verify persistence (Phase 1/2 foundation)
            from modules.catalog.models import Product
            from sqlalchemy import select
            q = select(Product).where(Product.supplier_sku == "PC61")
            res = await s.execute(q)
            product = res.scalar_one_or_none()
            assert product is not None
            assert product.product_name == "Port & Company Essential Tee"

            
        finally:
            service_mod.get_adapter = original_get













