from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CustomerCreate(BaseModel):
    name: str
    ops_base_url: str
    ops_token_url: str
    ops_client_id: str
    ops_client_secret: str  # stored encrypted in ops_auth_config
    logo_url: str | None = None


class CustomerRead(BaseModel):
    id: UUID
    name: str
    ops_base_url: str
    ops_token_url: str
    ops_client_id: str
    is_active: bool
    logo_url: str | None = None
    created_at: datetime
    products_pushed: int = 0
    markup_rules_count: int = 0
    # Per-customer fallback OPS category for product pushes (Phase 2 of
    # the OPS push audit). When set, products without a per-product
    # storefront category land in OPS under this category instead of
    # being uncategorized (which OPS admin hides from default views).
    default_ops_category_id: int | None = None
    ops_associated_category_ids: str | None = None
    ops_predefined_product_type: int | None = None

    model_config = ConfigDict(from_attributes=True)
