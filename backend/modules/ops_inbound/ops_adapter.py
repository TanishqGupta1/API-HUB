"""OnPrintShop inbound adapter.

Reads products from OPS GraphQL, normalizes to ProductIngest with
product_type='print', and feeds Phase 1's persist_product. Outbound push
to OPS lives in modules/ops_push and stays untouched here.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from modules.catalog.schemas import (
    ImageIngest,
    OptionAttributeIngest,
    OptionIngest,
    PrintDetailsIngest,
    ProductIngest,
    ProductSizeIngest,
)
from modules.import_jobs.base import (
    AuthError,
    BaseAdapter,
    DiscoveryMode,
    ProductRef,
    SupplierError,
)
from modules.import_jobs.registry import register_adapter

from .ops_client import OPSClient


_LIST_PRODUCTS_QUERY = """
query ListProducts {
  listProducts {
    product_id
  }
}
""".strip()


_GET_PRODUCT_QUERY = """
query GetProduct($id: Int!) {
  getProduct(product_id: $id) {
    product_id
    product_name
    main_sku
    status
    default_category_id
    small_image
    large_image
    externalCatalogue
    description
    brand
    pricing_method
    product_size {
      size_id
      size_title
      size_width
      size_height
    }
    product_additional_options {
      master_option_id
      option_key
      title
      options_type
      required
      attributes {
        attribute_id
        master_attribute_id
        attribute_key
        title
        sort_order
        status
        setup_cost
        multiplier
      }
    }
  }
}
""".strip()


_LIST_MODIFIED_QUERY = """
query ListModifiedSince($since: String!) {
  listProductsModifiedSince(since: $since) {
    product_id
  }
}
""".strip()


class OPSAdapter(BaseAdapter):
    product_type = "print"

    def __init__(self, supplier, db) -> None:
        super().__init__(supplier=supplier, db=db)
        if not supplier.base_url:
            raise AuthError("OPS supplier missing base_url")
        token = (supplier.auth_config or {}).get("auth_token")
        if not token:
            raise AuthError("OPS supplier missing auth_token in auth_config")
        self.client = OPSClient(base_url=supplier.base_url, auth_token=token)

    async def discover(
        self,
        mode: DiscoveryMode,
        *,
        limit: Optional[int] = None,
        explicit_list: Optional[list[str]] = None,
    ) -> list[ProductRef]:
        if mode == DiscoveryMode.EXPLICIT_LIST:
            if not explicit_list:
                raise ValueError("EXPLICIT_LIST mode requires explicit_list")
            return [ProductRef(supplier_sku=str(s)) for s in explicit_list]

        if mode in (DiscoveryMode.FIRST_N, DiscoveryMode.FULL):
            data = await self.client.query(_LIST_PRODUCTS_QUERY)
            rows = data.get("listProducts", [])
            refs = [ProductRef(supplier_sku=str(r["product_id"])) for r in rows]
            if mode == DiscoveryMode.FIRST_N and limit is not None:
                refs = refs[:limit]
            return refs

        if mode == DiscoveryMode.DELTA:
            raise NotImplementedError("DELTA discovery comes in Task 6")

        raise ValueError(f"Unsupported discovery mode for OPS: {mode}")

    async def hydrate_product(self, ref: ProductRef) -> ProductIngest:
        product_id_int = int(ref.supplier_sku)
        data = await self.client.query(
            _GET_PRODUCT_QUERY, variables={"id": product_id_int}
        )
        raw = data.get("getProduct")
        if raw is None:
            raise SupplierError(f"OPS product {ref.supplier_sku} not found", code="404")
        return self._normalize_to_ingest(raw)

    def _normalize_to_ingest(self, raw: dict[str, Any]) -> ProductIngest:
        sizes = [
            ProductSizeIngest(
                ops_size_id=s.get("size_id"),
                size_title=s.get("size_title", "Custom Size"),
                width=Decimal(str(s.get("size_width", 0) or 0)),
                height=Decimal(str(s.get("size_height", 0) or 0)),
                unit="in",
                label=s.get("size_title", "Custom Size"),
            )
            for s in (raw.get("product_size") or [])
        ]

        options = [
            OptionIngest(
                master_option_id=opt.get("master_option_id"),
                option_key=opt.get("option_key", ""),
                title=opt.get("title", ""),
                options_type=opt.get("options_type"),
                required=bool(opt.get("required", False)),
                attributes=[
                    OptionAttributeIngest(
                        ops_attribute_id=a.get("attribute_id") or 0,
                        master_attribute_id=a.get("master_attribute_id"),
                        attribute_key=a.get("attribute_key"),
                        title=a.get("title", ""),
                        sort_order=int(a.get("sort_order", 0)),
                        price=Decimal("0"),
                        setup_cost=Decimal(str(a.get("setup_cost", 0) or 0)),
                        multiplier=Decimal(str(a.get("multiplier", 1) or 1)),
                    )
                    for a in (opt.get("attributes") or [])
                ],
            )
            for opt in (raw.get("product_additional_options") or [])
        ]

        images: list[ImageIngest] = []
        if raw.get("large_image"):
            images.append(ImageIngest(url=raw["large_image"], image_type="front", sort_order=0))
        if raw.get("small_image"):
            images.append(ImageIngest(url=raw["small_image"], image_type="thumbnail", sort_order=1))

        print_details = PrintDetailsIngest(
            ops_product_id_int=int(raw.get("product_id", 0)),
            default_category_id=raw.get("default_category_id"),
            external_catalogue=raw.get("externalCatalogue") or raw.get("external_catalogue"),
            pricing_method=raw.get("pricing_method"),
        )

        return ProductIngest(
            supplier_sku=str(raw["product_id"]),
            ops_product_id=str(raw["product_id"]),
            product_name=raw.get("product_name", ""),
            product_type="print",
            brand=raw.get("brand"),
            description=raw.get("description"),
            print_details=print_details,
            sizes=sizes,
            options=options,
            images=images,
            raw_payload=raw,
        )

    async def discover_changed(self, since: datetime) -> list[ProductRef]:
        data = await self.client.query(
            _LIST_MODIFIED_QUERY, variables={"since": since.isoformat()}
        )
        rows = data.get("listProductsModifiedSince") or []
        return [ProductRef(supplier_sku=str(r["product_id"])) for r in rows]


register_adapter("OPSAdapter", OPSAdapter)
