from uuid import UUID
from pydantic import BaseModel
from typing import Optional


class CategoryMappingBase(BaseModel):
    supplier_id: UUID
    source_category: str
    ops_category_id: str


class CategoryMappingCreate(CategoryMappingBase):
    pass


class CategoryMappingRead(CategoryMappingBase):
    id: UUID

    class Config:
        from_attributes = True


class OptionMappingBase(BaseModel):
    supplier_id: UUID
    option_type: str
    source_value: str
    ops_attribute_id: str


class OptionMappingCreate(OptionMappingBase):
    pass


class OptionMappingRead(OptionMappingBase):
    id: UUID

    class Config:
        from_attributes = True


class ProductConfigBase(BaseModel):
    product_id: UUID
    customer_id: UUID
    target_category_id: Optional[str] = None
    is_active: bool = True


class ProductConfigCreate(ProductConfigBase):
    pass


class ProductConfigRead(ProductConfigBase):
    id: UUID
    ops_product_id: Optional[str] = None

    class Config:
        from_attributes = True
