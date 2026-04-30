from typing import Optional
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator, ConfigDict


class VariantRead(BaseModel):
    id: UUID
    color: Optional[str]
    size: Optional[str]
    sku: Optional[str]
    base_price: Optional[float]
    inventory: Optional[int]
    warehouse: Optional[str]
    prices: list["VariantPriceRead"] = []

    model_config = ConfigDict(from_attributes=True)


class VariantPriceRead(BaseModel):
    price_type: str
    quantity_min: int
    quantity_max: Optional[int]
    price: Decimal

    model_config = ConfigDict(from_attributes=True)


class ProductImageRead(BaseModel):
    id: UUID
    url: str
    image_type: str
    color: Optional[str]
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class ProductOptionAttributeRead(BaseModel):
    id: UUID
    title: str
    sort_order: int
    ops_attribute_id: Optional[int] = None
    master_attribute_id: Optional[int] = None
    attribute_key: Optional[str] = None
    price: Optional[Decimal] = None
    setup_cost: Optional[Decimal] = None
    multiplier: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class ProductOptionRead(BaseModel):
    id: UUID
    option_key: str
    title: str
    options_type: Optional[str] = None
    sort_order: int
    master_option_id: Optional[int] = None
    ops_option_id: Optional[int] = None
    required: bool
    attributes: list[ProductOptionAttributeRead] = []

    model_config = ConfigDict(from_attributes=True)


class ApparelDetailsRead(BaseModel):
    pricing_method: str
    raw_payload: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class PrintDetailsRead(BaseModel):
    pricing_method: str
    min_width: Optional[Decimal] = None
    max_width: Optional[Decimal] = None
    min_height: Optional[Decimal] = None
    max_height: Optional[Decimal] = None
    size_unit: Optional[str] = None
    base_price_per_sq_unit: Optional[Decimal] = None
    raw_payload: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class ProductSizeRead(BaseModel):
    width: Decimal
    height: Decimal
    unit: str
    label: str

    model_config = ConfigDict(from_attributes=True)


class ProductRead(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: Optional[str] = None
    supplier_sku: str
    product_name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    category_id: Optional[UUID] = None
    description: Optional[str] = None
    product_type: str
    image_url: Optional[str] = None
    ops_product_id: Optional[str] = None
    external_catalogue: Optional[int] = None
    last_synced: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    variants: list[VariantRead] = []
    images: list[ProductImageRead] = []
    options: list[ProductOptionRead] = []
    apparel_details: Optional[ApparelDetailsRead] = None
    print_details: Optional[PrintDetailsRead] = None
    sizes: list[ProductSizeRead] = []

    model_config = ConfigDict(from_attributes=True)


class ProductListRead(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: Optional[str] = None
    supplier_sku: str
    product_name: str
    brand: Optional[str]
    category: Optional[str]
    category_id: Optional[UUID] = None
    product_type: str
    image_url: Optional[str]
    ops_product_id: Optional[str] = None
    external_catalogue: Optional[int] = None
    variant_count: int = 0
    price_min: Optional[Decimal] = None
    price_max: Optional[Decimal] = None
    total_inventory: int = 0
    archived_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------- Ingest schemas (used by POST /api/ingest/{supplier_id}/...) ----------
#
# Shape mirrors PSProductData / PSInventoryLevel / PSPricePoint so every supplier
# (SanMar SOAP, S&S REST, 4Over HMAC, VG OPS GraphQL) feeds the same contract.


class VariantIngest(BaseModel):
    part_id: str
    color: Optional[str] = None
    size: Optional[str] = None
    sku: Optional[str] = None
    base_price: Optional[Decimal] = None
    inventory: Optional[int] = None
    warehouse: Optional[str] = None
    prices: list["VariantPriceIngest"] = Field(default_factory=list)


class VariantPriceIngest(BaseModel):
    price_type: str  # MSRP | Net | Sale | Case
    quantity_min: int = 1
    quantity_max: Optional[int] = None
    price: Decimal


class ProductSizeIngest(BaseModel):
    width: Decimal
    height: Decimal
    unit: str = "in"
    label: Optional[str] = None
    # OPS-specific fields
    ops_size_id: Optional[int] = None
    size_title: Optional[str] = None


class ApparelDetailsIngest(BaseModel):
    pricing_method: str = "tiered_variant"
    raw_payload: Optional[dict] = None


class PrintDetailsIngest(BaseModel):
    pricing_method: str = "formula"
    min_width: Optional[Decimal] = None
    max_width: Optional[Decimal] = None
    min_height: Optional[Decimal] = None
    max_height: Optional[Decimal] = None
    size_unit: str = "in"
    base_price_per_sq_unit: Optional[Decimal] = None
    raw_payload: Optional[dict] = None
    # OPS-specific fields
    ops_product_id_int: Optional[int] = None
    default_category_id: Optional[int] = None
    external_catalogue: Optional[int] = None


class ImageIngest(BaseModel):
    url: str
    image_type: str = "front"
    color: Optional[str] = None
    sort_order: int = 0


class OptionAttributeIngest(BaseModel):
    title: str
    sort_order: int = 0
    ops_attribute_id: Optional[int] = None
    master_attribute_id: Optional[int] = None
    attribute_key: Optional[str] = None
    price: Optional[Decimal] = None
    setup_cost: Optional[Decimal] = None
    multiplier: Optional[Decimal] = None


class OptionIngest(BaseModel):
    option_key: str
    title: str
    options_type: Optional[str] = None
    sort_order: int = 0
    master_option_id: Optional[int] = None
    ops_option_id: Optional[int] = None
    required: bool = False
    # OPS sometimes returns this as a JSON string; ingest normalizes in ingest.py.
    attributes: list[OptionAttributeIngest] | str | None = None


class ProductIngest(BaseModel):
    supplier_sku: str
    product_name: str
    brand: Optional[str] = None
    description: Optional[str] = None
    product_type: str = "apparel"
    image_url: Optional[str] = None
    ops_product_id: Optional[str] = None
    external_catalogue: Optional[int] = None
    category_external_id: Optional[str] = None
    category_name: Optional[str] = None
    variants: list[VariantIngest] = Field(default_factory=list)
    images: list[ImageIngest] = Field(default_factory=list)
    options: list[OptionIngest] = Field(default_factory=list)
    apparel_details: Optional[ApparelDetailsIngest] = None
    print_details: Optional[PrintDetailsIngest] = None
    sizes: list[ProductSizeIngest] = Field(default_factory=list)
    raw_payload: Optional[dict] = None

    @model_validator(mode="after")
    def validate_type_details(self) -> "ProductIngest":
        if self.product_type == "apparel" and not self.apparel_details:
            self.apparel_details = ApparelDetailsIngest()
        if self.product_type == "print" and not self.print_details and not self.sizes:
            raise ValueError("print_details or sizes must be provided for product_type='print'")
        return self


class InventoryIngest(BaseModel):
    supplier_sku: str
    part_id: str
    quantity_available: int = 0
    warehouse: Optional[str] = None


class PriceIngest(BaseModel):
    supplier_sku: str
    part_id: str
    base_price: Decimal


class CategoryIngest(BaseModel):
    external_id: str
    name: str
    parent_external_id: Optional[str] = None
    sort_order: int = 0


class IngestResult(BaseModel):
    sync_job_id: UUID
    records_processed: int
    status: str


class OPSCategoryInput(BaseModel):
    category_name: str
    parent_id: int = -1
    status: int = 1
    category_internal_name: str


class AttributeUpdate(BaseModel):
    title: Optional[str] = None
    price: Optional[Decimal] = None
    sort_order: Optional[int] = None
    enabled: Optional[bool] = None


class OptionUpdate(BaseModel):
    title: Optional[str] = None
    enabled: Optional[bool] = None
    sort_order: Optional[int] = None


class OptionBulkSave(BaseModel):
    options: list[OptionIngest]
