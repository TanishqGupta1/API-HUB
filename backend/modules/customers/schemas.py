from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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

    model_config = {"from_attributes": True}
