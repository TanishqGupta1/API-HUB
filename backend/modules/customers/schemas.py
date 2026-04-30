from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CustomerCreate(BaseModel):
    name: str
    ops_base_url: str
    ops_token_url: str
    ops_client_id: str
    ops_client_secret: str  # stored encrypted in ops_auth_config


class CustomerRead(BaseModel):
    id: UUID
    name: str
    ops_base_url: str
    ops_token_url: str
    ops_client_id: str
    is_active: bool
    created_at: datetime
    products_pushed: int = 0
    markup_rules_count: int = 0

    model_config = ConfigDict(from_attributes=True)
